import asyncio
import os
import random
import shutil
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import aiohttp

from .merge_copywriting_api_client import MergeCopywritingAPIClient, MergeCopywritingResult


@dataclass
class MergeTaskInfo:
    """Information about a single merge task"""
    product_txt_path: str
    product_folder_name: str
    video_txt_path: str
    index: int


@dataclass
class MergeCopywritingTaskProgress:
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    saved_files: int = 0
    current_task: str = ""


class MergeCopywritingTaskManager:
    def __init__(
        self,
        api_client: MergeCopywritingAPIClient,
        product_copywriting_dir: str,
        video_copywriting_dir: str,
        output_dir: str,
        recycle_dir: str,
        max_concurrent: int = 3,
        max_retries: int = 3,
    ):
        self.api_client = api_client
        self.product_copywriting_dir = product_copywriting_dir
        self.video_copywriting_dir = video_copywriting_dir
        self.output_dir = output_dir
        self.recycle_dir = recycle_dir
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries

        self._log_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[MergeCopywritingTaskProgress], None]] = None

        self._paused = False
        self._stopped = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._progress = MergeCopywritingTaskProgress()
        self._lock = asyncio.Lock()

    def set_log_callback(self, callback: Callable[[str], None]):
        self._log_callback = callback

    def set_progress_callback(self, callback: Callable[[MergeCopywritingTaskProgress], None]):
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

    def _get_txt_files_in_folder(self, folder_path: str) -> List[str]:
        """Get all txt files in a folder, sorted by filename"""
        if not os.path.exists(folder_path):
            return []

        txt_files = []
        for f in sorted(os.listdir(folder_path)):
            if f.lower().endswith('.txt'):
                txt_files.append(os.path.join(folder_path, f))
        return txt_files

    def _collect_and_pair_files(
        self,
        selected_folders: List[str],
        max_pairs: int,
    ) -> List[MergeTaskInfo]:
        """
        Collect product txt files from selected folders and pair with video txt files.

        Pairing rule:
        1. Build per-folder file lists (skip empty folders)
        2. Get video txt files, sorted by filename
        3. For each video file, pick a folder round-robin and randomly select
           a product file from that folder (with replacement)
        4. Limit to max_pairs
        """
        # Build list of (folder_name, [file_paths]) for folders that have files
        folder_files: List[Tuple[str, List[str]]] = []
        for folder_name in selected_folders:
            folder_path = os.path.join(self.product_copywriting_dir, folder_name)
            txt_files = self._get_txt_files_in_folder(folder_path)
            if txt_files:
                folder_files.append((folder_name, txt_files))

        if not folder_files:
            return []

        # Get video txt files
        video_files = self._get_txt_files_in_folder(self.video_copywriting_dir)

        if not video_files:
            return []

        # Pair: round-robin folders, random within each folder (with replacement)
        pairs: List[MergeTaskInfo] = []
        pair_count = min(len(video_files), max_pairs)

        for i in range(pair_count):
            folder_name, files = folder_files[i % len(folder_files)]
            product_path = random.choice(files)
            pairs.append(MergeTaskInfo(
                product_txt_path=product_path,
                product_folder_name=folder_name,
                video_txt_path=video_files[i],
                index=i,
            ))

        return pairs

    def _read_file_content(self, file_path: str) -> str:
        """Read content from a text file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self._log(f"读取文件失败 {file_path}: {str(e)}")
            return ""

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

    async def _merge_single(
        self,
        task_info: MergeTaskInfo,
        prompt: str,
        session: aiohttp.ClientSession,
    ) -> bool:
        """Merge a single pair of copywriting files with retries"""
        product_content = self._read_file_content(task_info.product_txt_path)
        video_content = self._read_file_content(task_info.video_txt_path)

        if not product_content or not video_content:
            self._log(f"任务 #{task_info.index + 1} 文件内容为空，跳过")
            return False

        for attempt in range(self.max_retries):
            if self._stopped:
                return False

            await self._wait_if_paused()

            self._log(
                f"任务 #{task_info.index + 1} [{task_info.product_folder_name}] "
                f"开始合并 (尝试 {attempt + 1}/{self.max_retries})"
            )

            result = await self.api_client.merge(
                product_content, video_content, prompt, session
            )

            if result.success:
                if not self._is_valid_chinese_content(result.content):
                    self._log(f"任务 #{task_info.index + 1} AI 返回非中文内容，视为失败")
                else:
                    video_filename = os.path.basename(task_info.video_txt_path)
                    saved = await self._save_content(
                        result.content, task_info.product_folder_name, video_filename
                    )
                    if saved:
                        self._move_to_recycle(task_info)

                        async with self._lock:
                            self._progress.completed_tasks += 1
                            self._progress.saved_files += 1
                            self._update_progress()
                        self._log(f"任务 #{task_info.index + 1} 完成，已保存并回收视频文案")
                        return True
                    else:
                        self._log(f"任务 #{task_info.index + 1} 保存失败")
            else:
                self._log(f"任务 #{task_info.index + 1} 合并失败: {result.error}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(1)

        async with self._lock:
            self._progress.completed_tasks += 1
            self._progress.failed_tasks += 1
            self._update_progress()

        self._log(f"任务 #{task_info.index + 1} 最终失败")
        return False

    async def _save_content(
        self, content: str, folder_name: str, video_filename: str
    ) -> bool:
        """Save merged content to txt file"""
        try:
            output_folder = os.path.join(self.output_dir, folder_name)
            os.makedirs(output_folder, exist_ok=True)

            filepath = os.path.join(output_folder, video_filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            return True
        except Exception as e:
            self._log(f"保存文件失败: {str(e)}")
            return False

    def _move_to_recycle(self, task_info: MergeTaskInfo):
        """Move used video txt file to recycle bin"""
        try:
            video_recycle_folder = os.path.join(self.recycle_dir, "视频文案")
            os.makedirs(video_recycle_folder, exist_ok=True)
            video_dest = os.path.join(
                video_recycle_folder, os.path.basename(task_info.video_txt_path)
            )
            shutil.move(task_info.video_txt_path, video_dest)
        except Exception as e:
            self._log(f"移动文件到回收站失败: {str(e)}")

    async def run(
        self,
        selected_folders: List[str],
        prompt: str,
        max_pairs: int,
    ) -> MergeCopywritingTaskProgress:
        """
        Batch merge copywriting files
        - Collect and pair files
        - Concurrency control
        - Progress callback
        - Move used files to recycle bin
        """
        # Collect and pair files
        pairs = self._collect_and_pair_files(selected_folders, max_pairs)

        if not pairs:
            self._log("没有可配对的文件")
            return self._progress

        self._progress = MergeCopywritingTaskProgress(total_tasks=len(pairs))
        self._paused = False
        self._stopped = False
        self._pause_event.set()

        self._log(f"共配对 {len(pairs)} 组文件")
        self._update_progress()

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def bounded_task(task_info: MergeTaskInfo, session: aiohttp.ClientSession):
            async with semaphore:
                if self._stopped:
                    return
                async with self._lock:
                    self._progress.current_task = (
                        f"{task_info.product_folder_name}/{os.path.basename(task_info.product_txt_path)}"
                    )
                    self._update_progress()
                await self._merge_single(task_info, prompt, session)

        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [bounded_task(pair, session) for pair in pairs]
            await asyncio.gather(*tasks, return_exceptions=True)

        return self._progress
