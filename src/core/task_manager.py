import asyncio
import aiohttp
from dataclasses import dataclass
from typing import Callable, Optional
from enum import Enum

from .api_client import JimengAPIClient, GenerationResult
from .downloader import ImageDownloader
from ..utils.helpers import get_timestamp


class TaskState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"


@dataclass
class TaskProgress:
    total_requests: int = 0
    completed_requests: int = 0
    success_requests: int = 0
    failed_requests: int = 0
    total_images: int = 0
    downloaded_images: int = 0


class TaskManager:
    def __init__(
        self,
        api_client: JimengAPIClient,
        downloader: ImageDownloader,
        max_concurrent: int = 100,
        max_retries: int = 3,
    ):
        self.api_client = api_client
        self.downloader = downloader
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries

        self.state = TaskState.IDLE
        self.progress = TaskProgress()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._pause_event: Optional[asyncio.Event] = None
        self._stop_flag = False
        self._image_index = 0
        self._timestamp = ""

        self._log_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[TaskProgress], None]] = None

    def set_log_callback(self, callback: Callable[[str], None]) -> None:
        self._log_callback = callback

    def set_progress_callback(self, callback: Callable[[TaskProgress], None]) -> None:
        self._progress_callback = callback

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def _update_progress(self) -> None:
        if self._progress_callback:
            self._progress_callback(self.progress)

    async def _process_single_request(
        self,
        request_id: int,
        prompt: str,
        session: aiohttp.ClientSession,
    ) -> bool:
        """Process a single generation request with retry"""
        async with self._semaphore:
            if self._stop_flag:
                return False

            while self.state == TaskState.PAUSED:
                await self._pause_event.wait()
                if self._stop_flag:
                    return False

            self._log(f"请求 #{request_id} 已发送...")

            for attempt in range(self.max_retries + 1):
                if self._stop_flag:
                    return False

                result = await self.api_client.generate_image(prompt, session)

                if result.success:
                    if len(result.urls) == 0:
                        self._log(
                            f"请求 #{request_id} 成功但未获取到图片URL，请检查控制台的API响应日志"
                        )
                    else:
                        self._log(
                            f"请求 #{request_id} 成功，获取 {len(result.urls)} 张图片"
                        )

                    start_index = self._image_index
                    self._image_index += len(result.urls)
                    self.progress.total_images += len(result.urls)
                    self._update_progress()

                    downloaded = await self.downloader.download_batch(
                        result.urls,
                        self._timestamp,
                        start_index,
                        session,
                        self._on_download_complete,
                    )

                    self.progress.downloaded_images += downloaded
                    self.progress.completed_requests += 1
                    self.progress.success_requests += 1
                    self._update_progress()
                    return True

                else:
                    if (
                        JimengAPIClient.is_retryable_error(result.status_code)
                        and attempt < self.max_retries
                    ):
                        wait_time = 2 ** attempt
                        self._log(
                            f"请求 #{request_id} 失败: {result.error}，"
                            f"等待重试 ({attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        self._log(f"请求 #{request_id} 失败: {result.error}")
                        self.progress.completed_requests += 1
                        self.progress.failed_requests += 1
                        self._update_progress()
                        return False

            return False

    def _on_download_complete(self, filename: str, success: bool, error: str) -> None:
        if success:
            self._log(f"下载完成: {filename}")
        else:
            self._log(f"下载失败: {filename} - {error}")

    async def run(self, prompt: str, request_count: int) -> TaskProgress:
        """Run the generation task"""
        self.state = TaskState.RUNNING
        self._stop_flag = False
        self._image_index = 0
        self._timestamp = get_timestamp()

        self.progress = TaskProgress(total_requests=request_count)
        self._update_progress()

        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._log(f"开始生图任务: {request_count} 次请求，最大并行 {self.max_concurrent}")

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._process_single_request(i + 1, prompt, session)
                for i in range(request_count)
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

        if self._stop_flag:
            self.state = TaskState.IDLE
            self._log("任务已停止")
        else:
            self.state = TaskState.COMPLETED
            self._log(
                f"任务完成: 成功 {self.progress.success_requests}/"
                f"{self.progress.total_requests}，"
                f"下载 {self.progress.downloaded_images} 张图片"
            )

        return self.progress

    def pause(self) -> None:
        """Pause the task"""
        if self.state == TaskState.RUNNING:
            self.state = TaskState.PAUSED
            self._pause_event.clear()
            self._log("任务已暂停")

    def resume(self) -> None:
        """Resume the task"""
        if self.state == TaskState.PAUSED:
            self.state = TaskState.RUNNING
            self._pause_event.set()
            self._log("任务已继续")

    def stop(self) -> None:
        """Stop the task"""
        self._stop_flag = True
        self.state = TaskState.STOPPING
        if self._pause_event:
            self._pause_event.set()
        self._log("正在停止任务...")

    def get_state(self) -> TaskState:
        return self.state
