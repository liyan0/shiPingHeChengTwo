import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

import aiohttp

from .image_recognition_api_client import ImageRecognitionAPIClient, ImageRecognitionResult


@dataclass
class ImageRecognitionTaskProgress:
    total_folders: int = 0
    completed_folders: int = 0
    current_folder: str = ""
    current_file_index: int = 0
    total_files: int = 0
    saved_files: int = 0
    failed_tasks: int = 0


class ImageRecognitionTaskManager:
    def __init__(
        self,
        api_client: ImageRecognitionAPIClient,
        input_base_dir: str,
        output_base_dir: str,
        max_concurrent: int = 3,
        max_retries: int = 3,
    ):
        self.api_client = api_client
        self.input_base_dir = input_base_dir
        self.output_base_dir = output_base_dir
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries

        self._log_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[ImageRecognitionTaskProgress], None]] = None

        self._paused = False
        self._stopped = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._progress = ImageRecognitionTaskProgress()
        self._lock = asyncio.Lock()

    def set_log_callback(self, callback: Callable[[str], None]):
        self._log_callback = callback

    def set_progress_callback(self, callback: Callable[[ImageRecognitionTaskProgress], None]):
        self._progress_callback = callback

    def _log(self, message: str):
        if self._log_callback:
            self._log_callback(message)

    def _update_progress(self):
        if self._progress_callback:
            self._progress_callback(self._progress)

    def pause(self):
        self._paused = True
        self._pause_event.clear()

    def resume(self):
        self._paused = False
        self._pause_event.set()

    def stop(self):
        self._stopped = True
        self._pause_event.set()

    async def _wait_if_paused(self):
        await self._pause_event.wait()

    def _get_images_in_folder(self, folder_path: str) -> List[str]:
        """Get all image files in a folder"""
        if not os.path.exists(folder_path):
            return []

        image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
        images = []
        for f in sorted(os.listdir(folder_path)):
            if f.lower().endswith(image_extensions):
                images.append(os.path.join(folder_path, f))
        return images

    async def _generate_single(
        self,
        folder_name: str,
        image_paths: List[str],
        prompt: str,
        file_index: int,
        output_folder: str,
        session: aiohttp.ClientSession,
    ) -> bool:
        """Generate a single recognition result with retries"""
        for attempt in range(self.max_retries):
            if self._stopped:
                return False

            await self._wait_if_paused()

            self._log(f"[{folder_name}] 生成第 {file_index + 1} 个文件 (尝试 {attempt + 1}/{self.max_retries})")

            result = await self.api_client.recognize(image_paths, prompt, session)

            if result.success:
                saved = await self._save_content(result.content, file_index, output_folder)
                if saved:
                    async with self._lock:
                        self._progress.saved_files += 1
                        self._update_progress()
                    self._log(f"[{folder_name}] 第 {file_index + 1} 个文件已保存")
                    return True
                else:
                    self._log(f"[{folder_name}] 第 {file_index + 1} 个文件保存失败")
            else:
                self._log(f"[{folder_name}] 识别失败: {result.error}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(1)

        async with self._lock:
            self._progress.failed_tasks += 1
            self._update_progress()

        self._log(f"[{folder_name}] 第 {file_index + 1} 个文件最终失败")
        return False

    async def _save_content(self, content: str, file_index: int, output_folder: str) -> bool:
        """Save content to txt file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{file_index + 1:04d}.txt"
            filepath = os.path.join(output_folder, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            return True
        except Exception as e:
            self._log(f"保存文件失败: {str(e)}")
            return False

    async def run(
        self,
        folder_names: List[str],
        prompt: str,
        file_count: int = 1,
    ) -> ImageRecognitionTaskProgress:
        """
        全并行处理所有TXT生成任务。
        使用 Semaphore 控制总并发数，所有任务（跨文件夹）同时竞争执行。
        """
        # 1. 收集所有任务
        all_tasks_info = []  # [(folder_name, file_index, image_paths, output_folder), ...]

        for folder_name in folder_names:
            folder_path = os.path.join(self.input_base_dir, folder_name)
            image_paths = self._get_images_in_folder(folder_path)

            if not image_paths:
                self._log(f"文件夹 '{folder_name}' 中没有图片，跳过")
                continue

            output_folder = os.path.join(self.output_base_dir, folder_name)
            os.makedirs(output_folder, exist_ok=True)

            self._log(f"文件夹 '{folder_name}': 发现 {len(image_paths)} 张图片，将生成 {file_count} 个文件")

            for file_index in range(file_count):
                all_tasks_info.append((folder_name, file_index, image_paths, output_folder))

        # 2. 初始化进度
        total_files = len(all_tasks_info)
        self._progress = ImageRecognitionTaskProgress(
            total_folders=len(folder_names),
            total_files=total_files,
        )
        self._paused = False
        self._stopped = False
        self._pause_event.set()
        self._update_progress()

        if total_files == 0:
            return self._progress

        # 3. 并行执行所有任务
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_single_task(task_info, session):
            folder_name, file_index, image_paths, output_folder = task_info
            async with semaphore:
                if self._stopped:
                    return

                async with self._lock:
                    self._progress.current_folder = folder_name
                    self._progress.current_file_index = file_index + 1
                    self._update_progress()

                await self._generate_single(
                    folder_name, image_paths, prompt, file_index, output_folder, session
                )

        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [process_single_task(info, session) for info in all_tasks_info]
            await asyncio.gather(*tasks, return_exceptions=True)

        # 4. 计算完成的文件夹数
        self._progress.completed_folders = len(folder_names)
        self._update_progress()

        return self._progress
