import asyncio
import os
from dataclasses import dataclass
from typing import Callable, List, Optional

import aiohttp

from .copywriting_api_client import CopywritingAPIClient, CopywritingResult


@dataclass
class RewriteTaskInfo:
    """Information about a single rewrite task"""
    source_path: str
    filename: str
    index: int
    title: str = ""


@dataclass
class RewriteCopywritingTaskProgress:
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    saved_files: int = 0
    current_task: str = ""


class RewriteCopywritingTaskManager:
    def __init__(
        self,
        api_client: CopywritingAPIClient,
        input_dir: str,
        output_dir: str,
        max_concurrent: int = 3,
        max_retries: int = 3,
        versions_per_file: int = 1,
    ):
        self.api_client = api_client
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.versions_per_file = max(1, versions_per_file)

        self._log_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[RewriteCopywritingTaskProgress], None]] = None

        self._paused = False
        self._stopped = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._progress = RewriteCopywritingTaskProgress()
        self._lock = asyncio.Lock()
        self._used_titles: dict = {}  # key: 原文件名, value: List[str]

    def set_log_callback(self, callback: Callable[[str], None]):
        self._log_callback = callback

    def set_progress_callback(self, callback: Callable[[RewriteCopywritingTaskProgress], None]):
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

    def _collect_txt_files(self) -> List[RewriteTaskInfo]:
        """Collect all txt files from input directory"""
        if not os.path.exists(self.input_dir):
            return []

        tasks = []
        index = 0
        for f in sorted(os.listdir(self.input_dir)):
            if f.lower().endswith('.txt'):
                tasks.append(RewriteTaskInfo(
                    source_path=os.path.join(self.input_dir, f),
                    filename=f,
                    index=index,
                    title=os.path.splitext(f)[0],
                ))
                index += 1
        return tasks

    @staticmethod
    def _parse_response(content: str) -> tuple:
        """Parse AI response: first non-empty line (<=40 chars) as title, rest as body."""
        lines = content.split('\n')
        first_non_empty = None
        first_idx = 0
        for i, line in enumerate(lines):
            if line.strip():
                first_non_empty = line.strip()
                first_idx = i
                break

        if first_non_empty and len(first_non_empty) <= 40:
            body_lines = lines[first_idx + 1:]
            # strip leading blank lines from body
            while body_lines and not body_lines[0].strip():
                body_lines.pop(0)
            return (first_non_empty, '\n'.join(body_lines))

        return ("", content)

    def _resolve_output_filename(self, new_title: str, fallback_title: str, version_index: int) -> str:
        """Determine output filename, handling fallback and conflicts."""
        os.makedirs(self.output_dir, exist_ok=True)

        base = new_title if new_title else f"{fallback_title}_{version_index + 1}"
        # sanitize: remove characters invalid in filenames
        for ch in r'\/:*?"<>|':
            base = base.replace(ch, '')
        base = base.strip()
        if not base:
            base = f"{fallback_title}_{version_index + 1}"

        candidate = f"{base}.txt"
        if not os.path.exists(os.path.join(self.output_dir, candidate)):
            return candidate

        suffix = 2
        while True:
            candidate = f"{base}_{suffix}.txt"
            if not os.path.exists(os.path.join(self.output_dir, candidate)):
                return candidate
            suffix += 1

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

    async def _rewrite_single(
        self,
        task_info: RewriteTaskInfo,
        prompt_template: str,
        session: aiohttp.ClientSession,
        version_index: int = 0,
    ) -> bool:
        """Rewrite a single file with retries"""
        content = self._read_file_content(task_info.source_path)

        if not content:
            self._log(f"任务 #{task_info.index + 1} 文件内容为空，跳过")
            return False

        for attempt in range(self.max_retries):
            if self._stopped:
                return False

            await self._wait_if_paused()

            prompt = prompt_template.replace("{content}", content)
            prompt = prompt.replace("{title}", task_info.title)

            if version_index == 0:
                pass
            else:
                prompt += (
                    f"\n\n【额外要求】在输出文案之前，先单独输出一行标题（不加任何标点或说明），然后换行输出文案正文。"
                    f"标题要求：在原标题「{task_info.title}」基础上，只替换或调整1-2个字词，"
                    f"保持整体句式和含义不变，不要大幅改动。"
                )
                async with self._lock:
                    used = list(self._used_titles.get(task_info.filename, []))
                if used:
                    prompt += f"\n\n注意：以下标题已被使用，请生成一个不同的标题：{'、'.join(used)}"

            self._log(
                f"任务 #{task_info.index + 1} [{task_info.filename}] "
                f"版本 {version_index + 1} 开始改写 (尝试 {attempt + 1}/{self.max_retries})"
            )

            result = await self.api_client.generate(prompt, session)

            if result.success:
                if not self._is_valid_chinese_content(result.content):
                    self._log(f"任务 #{task_info.index + 1} AI 返回非中文内容，视为失败")
                else:
                    if version_index == 0:
                        new_title = task_info.title
                        body = result.content
                    else:
                        new_title, body = self._parse_response(result.content)
                    save_content = body if new_title else result.content
                    async with self._lock:
                        out_filename = self._resolve_output_filename(new_title, task_info.title, version_index)
                    saved = await self._save_content(save_content, out_filename)
                    if saved:
                        async with self._lock:
                            self._progress.completed_tasks += 1
                            self._progress.saved_files += 1
                            self._used_titles.setdefault(task_info.filename, []).append(new_title if new_title else out_filename)
                            self._update_progress()
                        self._log(f"任务 #{task_info.index + 1} 版本 {version_index + 1} 完成，已保存为 [{out_filename}]")
                        return True
                    else:
                        self._log(f"任务 #{task_info.index + 1} 版本 {version_index + 1} 保存失败")
            else:
                self._log(f"任务 #{task_info.index + 1} 版本 {version_index + 1} 改写失败: {result.error}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(1)

        async with self._lock:
            self._progress.completed_tasks += 1
            self._progress.failed_tasks += 1
            self._update_progress()

        self._log(f"任务 #{task_info.index + 1} 版本 {version_index + 1} 最终失败")
        return False

    async def _save_content(self, content: str, filename: str) -> bool:
        """Save rewritten content to output directory"""
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            return True
        except Exception as e:
            self._log(f"保存文件失败: {str(e)}")
            return False

    async def run(self, prompt_template: str) -> RewriteCopywritingTaskProgress:
        """
        Batch rewrite copywriting files
        - Collect txt files from input directory
        - Rewrite each file N versions using AI API
        - Save to output directory with AI-generated titles
        """
        tasks = self._collect_txt_files()

        if not tasks:
            self._log("没有找到待改写的文件")
            return self._progress

        total_tasks = len(tasks) * self.versions_per_file
        self._progress = RewriteCopywritingTaskProgress(total_tasks=total_tasks)
        self._paused = False
        self._stopped = False
        self._pause_event.set()
        self._used_titles = {}

        self._log(f"共找到 {len(tasks)} 个文件，每文件 {self.versions_per_file} 个版本，共 {total_tasks} 个任务")
        self._update_progress()

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def rewrite_file_versions(task_info: RewriteTaskInfo, session: aiohttp.ClientSession):
            async with semaphore:
                for v in range(self.versions_per_file):
                    if self._stopped:
                        return
                    async with self._lock:
                        self._progress.current_task = f"{task_info.filename} v{v + 1}"
                        self._update_progress()
                    await self._rewrite_single(task_info, prompt_template, session, v)

        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            task_list = [rewrite_file_versions(task, session) for task in tasks]
            await asyncio.gather(*task_list, return_exceptions=True)

        return self._progress
