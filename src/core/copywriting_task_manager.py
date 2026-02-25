import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import aiohttp

from .copywriting_api_client import CopywritingAPIClient, CopywritingResult


@dataclass
class CopywritingTaskProgress:
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    saved_files: int = 0


class CopywritingTaskManager:
    def __init__(
        self,
        api_client: CopywritingAPIClient,
        output_dir: str,
        max_concurrent: int = 3,
        max_retries: int = 3,
    ):
        self.api_client = api_client
        self.output_dir = output_dir
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries

        self._log_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[CopywritingTaskProgress], None]] = None

        self._paused = False
        self._stopped = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._progress = CopywritingTaskProgress()
        self._lock = asyncio.Lock()

    def set_log_callback(self, callback: Callable[[str], None]):
        self._log_callback = callback

    def set_progress_callback(self, callback: Callable[[CopywritingTaskProgress], None]):
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

    @staticmethod
    def _is_valid_chinese_content(content: str) -> bool:
        """检查内容是否为有效的中文文案（非英文拒绝回复）"""
        if not content or not content.strip():
            return False
        chinese_count = sum(1 for ch in content if '\u4e00' <= ch <= '\u9fff')
        non_space = sum(1 for ch in content if not ch.isspace())
        if non_space == 0:
            return False
        return chinese_count / non_space >= 0.5

    async def _generate_single(
        self,
        prompt: str,
        task_index: int,
        session: aiohttp.ClientSession,
    ) -> bool:
        """Generate a single copywriting task with retries"""
        for attempt in range(self.max_retries):
            if self._stopped:
                return False

            await self._wait_if_paused()

            self._log(f"任务 #{task_index + 1} 开始生成 (尝试 {attempt + 1}/{self.max_retries})")

            result = await self.api_client.generate(prompt, session)

            if result.success:
                if not self._is_valid_chinese_content(result.content):
                    self._log(f"任务 #{task_index + 1} AI 返回非中文内容，视为失败")
                else:
                    saved = await self._save_content(result.content, task_index)
                    if saved:
                        async with self._lock:
                            self._progress.completed_tasks += 1
                            self._progress.saved_files += 1
                            self._update_progress()
                        self._log(f"任务 #{task_index + 1} 完成，已保存")
                        return True
                    else:
                        self._log(f"任务 #{task_index + 1} 保存失败")
            else:
                self._log(f"任务 #{task_index + 1} 生成失败: {result.error}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(1)

        async with self._lock:
            self._progress.completed_tasks += 1
            self._progress.failed_tasks += 1
            self._update_progress()

        self._log(f"任务 #{task_index + 1} 最终失败")
        return False

    async def _save_content(self, content: str, task_index: int) -> bool:
        """Save content to txt file"""
        try:
            os.makedirs(self.output_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{task_index + 1:04d}.txt"
            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            return True
        except Exception as e:
            self._log(f"保存文件失败: {str(e)}")
            return False

    async def run(self, prompt: str, request_count: int) -> CopywritingTaskProgress:
        """
        Batch generate copywriting
        - Concurrency control
        - Progress callback
        - Save as txt files
        """
        self._progress = CopywritingTaskProgress(total_tasks=request_count)
        self._paused = False
        self._stopped = False
        self._pause_event.set()

        self._update_progress()

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def bounded_task(index: int, session: aiohttp.ClientSession):
            async with semaphore:
                if self._stopped:
                    return
                await self._generate_single(prompt, index, session)

        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [bounded_task(i, session) for i in range(request_count)]
            await asyncio.gather(*tasks, return_exceptions=True)

        return self._progress
