import asyncio
import aiohttp
import ssl
import os
import shutil
from dataclasses import dataclass
from typing import Callable, Optional, List
from enum import Enum

from .video_api_client import VideoAPIClient
from .video_downloader import VideoDownloader
from ..utils.helpers import get_timestamp


class VideoTaskState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"


@dataclass
class VideoTaskProgress:
    total_tasks: int = 0
    submitted_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    downloaded_videos: int = 0
    current_task_progress: int = 0  # 当前任务的进度 (0-100)


class VideoTaskManager:
    def __init__(
        self,
        api_client: VideoAPIClient,
        downloader: VideoDownloader,
        max_concurrent: int = 5,
        poll_interval: int = 5,
        recycle_dir: str = "",
    ):
        self.api_client = api_client
        self.downloader = downloader
        self.max_concurrent = max_concurrent
        self.poll_interval = poll_interval
        self.recycle_dir = recycle_dir

        self.state = VideoTaskState.IDLE
        self.progress = VideoTaskProgress()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._pause_event: Optional[asyncio.Event] = None
        self._stop_flag = False
        self._timestamp = ""

        self._log_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[VideoTaskProgress], None]] = None

    def set_log_callback(self, callback: Callable[[str], None]) -> None:
        self._log_callback = callback

    def set_progress_callback(self, callback: Callable[[VideoTaskProgress], None]) -> None:
        self._progress_callback = callback

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def _update_progress(self) -> None:
        if self._progress_callback:
            self._progress_callback(self.progress)

    async def _process_single_video(
        self,
        task_id: int,
        image_path: str,
        prompt: str,
        session: aiohttp.ClientSession,
    ) -> bool:
        """Process a single video generation task"""
        async with self._semaphore:
            if self._stop_flag:
                return False

            while self.state == VideoTaskState.PAUSED:
                await self._pause_event.wait()
                if self._stop_flag:
                    return False

            image_name = os.path.basename(image_path)
            self._log(f"任务 #{task_id} 提交中: {image_name}")

            # 1. Submit video generation task
            submit_result = await self.api_client.submit_video(prompt, image_path, session)

            if not submit_result.success:
                self._log(f"任务 #{task_id} 提交失败: {submit_result.error}")
                self.progress.failed_tasks += 1
                self.progress.completed_tasks += 1
                self._update_progress()
                return False

            self.progress.submitted_tasks += 1
            self._update_progress()

            video_task_id = submit_result.task_id
            self._log(f"任务 #{task_id} 已提交，任务ID: {video_task_id}")

            # 2. Poll for completion
            poll_count = 0
            max_polls = 360  # Max 30 minutes (360 * 5s)
            max_consecutive_failures = 10
            consecutive_failures = 0

            while poll_count < max_polls:
                if self._stop_flag:
                    self._log(f"任务 #{task_id} 已取消")
                    return False

                while self.state == VideoTaskState.PAUSED:
                    await self._pause_event.wait()
                    if self._stop_flag:
                        return False

                await asyncio.sleep(self.poll_interval)
                poll_count += 1

                query_result = await self.api_client.query_status(video_task_id, session)

                if not query_result.success:
                    consecutive_failures += 1
                    self._log(f"任务 #{task_id} 查询失败 ({consecutive_failures}/{max_consecutive_failures}): {query_result.error}")
                    if consecutive_failures >= max_consecutive_failures:
                        self._log(f"任务 #{task_id} 连续查询失败次数过多，标记为失败")
                        self.progress.failed_tasks += 1
                        self.progress.completed_tasks += 1
                        self._update_progress()
                        return False
                    continue

                consecutive_failures = 0  # 重置失败计数

                # 完成状态
                if query_result.status in ("completed", "success"):
                    self._log(f"任务 #{task_id} 生成完成，开始下载...")

                    # 3. Download video
                    video_filename = f"{self._timestamp}_{task_id:04d}.mp4"
                    download_success = await self.downloader.download_video(
                        query_result.video_url,
                        video_filename,
                        progress_callback=self._on_download_complete,
                    )

                    # Debug log to diagnose recycle bin issue
                    self._log(f"[DEBUG] download_success={download_success}, recycle_dir='{self.recycle_dir}'")

                    if download_success:
                        self.progress.downloaded_videos += 1
                        # Move image to recycle bin
                        if self.recycle_dir:
                            try:
                                os.makedirs(self.recycle_dir, exist_ok=True)
                                dest_path = os.path.join(self.recycle_dir, image_name)
                                shutil.move(image_path, dest_path)
                                self._log(f"图片已移至回收站: {image_name}")
                            except Exception as e:
                                self._log(f"移动图片失败: {e}")

                    self.progress.completed_tasks += 1
                    self.progress.current_task_progress = 0  # 重置当前任务进度
                    self._update_progress()
                    return download_success

                # 失败状态
                elif query_result.status in ("failed", "error", "cancelled"):
                    self._log(f"任务 #{task_id} 生成失败")
                    self.progress.failed_tasks += 1
                    self.progress.completed_tasks += 1
                    self.progress.current_task_progress = 0  # 重置当前任务进度
                    self._update_progress()
                    return False

                # 处理中状态 (queued, pending, processing, etc.)
                else:
                    progress_pct = query_result.progress or 0
                    self.progress.current_task_progress = progress_pct
                    self._update_progress()  # 每次都更新进度
                    if poll_count % 6 == 0:  # Log every 30 seconds
                        self._log(f"任务 #{task_id} 生成中... {progress_pct}%")

            # Timeout
            self._log(f"任务 #{task_id} 超时")
            self.progress.failed_tasks += 1
            self.progress.completed_tasks += 1
            self._update_progress()
            return False

    def _on_download_complete(self, filename: str, success: bool, error: str) -> None:
        if success:
            self._log(f"下载完成: {filename}")
        else:
            self._log(f"下载失败: {filename} - {error}")

    async def run(self, image_paths: List[str], prompt: str) -> VideoTaskProgress:
        """Run batch video generation"""
        self.state = VideoTaskState.RUNNING
        self._stop_flag = False
        self._timestamp = get_timestamp()

        self.progress = VideoTaskProgress(total_tasks=len(image_paths))
        self._update_progress()

        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._log(f"开始视频生成任务: {len(image_paths)} 个任务，最大并行 {self.max_concurrent}")

        # Create session with SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [
                self._process_single_video(i + 1, image_path, prompt, session)
                for i, image_path in enumerate(image_paths)
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

        if self._stop_flag:
            self.state = VideoTaskState.IDLE
            self._log("任务已停止")
        else:
            self.state = VideoTaskState.COMPLETED
            self._log(
                f"任务完成: 成功 {self.progress.downloaded_videos}/"
                f"{self.progress.total_tasks}，"
                f"失败 {self.progress.failed_tasks}"
            )

        return self.progress

    def pause(self) -> None:
        """Pause the task"""
        if self.state == VideoTaskState.RUNNING:
            self.state = VideoTaskState.PAUSED
            self._pause_event.clear()
            self._log("任务已暂停")

    def resume(self) -> None:
        """Resume the task"""
        if self.state == VideoTaskState.PAUSED:
            self.state = VideoTaskState.RUNNING
            self._pause_event.set()
            self._log("任务已继续")

    def stop(self) -> None:
        """Stop the task"""
        self._stop_flag = True
        self.state = VideoTaskState.STOPPING
        if self._pause_event:
            self._pause_event.set()
        self._log("正在停止任务...")

    def get_state(self) -> VideoTaskState:
        return self.state
