import asyncio
import io
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

import aiohttp

from .tts_api_client import TTSAPIClient
from .subtitle_api_client import SubtitleAPIClient
from .product_time_api_client import ProductTimeAPIClient


@dataclass
class TTSTaskInfo:
    """Information about a single TTS task"""
    txt_path: str
    folder_name: str
    index: int


@dataclass
class TTSTaskProgress:
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    saved_files: int = 0
    current_task: str = ""
    subtitle_completed: int = 0
    subtitle_failed: int = 0
    current_subtitle_task: str = ""
    product_time_completed: int = 0
    product_time_failed: int = 0
    current_product_time_task: str = ""


class TTSTaskManager:
    MAX_TEXT_LENGTH = 4096

    def __init__(
        self,
        api_client: TTSAPIClient,
        input_dir: str,
        output_dir: str,
        recycle_dir: str,
        max_concurrent: int = 3,
        max_retries: int = 3,
        subtitle_enabled: bool = False,
        subtitle_api_client: Optional[SubtitleAPIClient] = None,
        subtitle_method: str = "api",
        local_model: str = "small",
        local_device: str = "cpu",
        product_time_enabled: bool = False,
        product_time_api_client: Optional[ProductTimeAPIClient] = None,
        force_simplified: bool = False,
        max_chars_per_segment: int = 0,
        subtitle_correction_enabled: bool = False,
    ):
        self.api_client = api_client
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.recycle_dir = recycle_dir
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.subtitle_enabled = subtitle_enabled
        self.subtitle_api_client = subtitle_api_client
        self.subtitle_method = subtitle_method
        self.local_model = local_model
        self.local_device = local_device
        self.whisper_transcriber = None
        self.product_time_enabled = product_time_enabled
        self.product_time_api_client = product_time_api_client
        self.force_simplified = force_simplified
        self.max_chars_per_segment = max_chars_per_segment
        self.subtitle_correction_enabled = subtitle_correction_enabled

        self._log_callback: Optional[Callable[[str, str], None]] = None
        self._progress_callback: Optional[Callable[[TTSTaskProgress], None]] = None

        self._paused = False
        self._stopped = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._progress = TTSTaskProgress()
        self._lock = asyncio.Lock()
        self._file_counter = 0

    def set_log_callback(self, callback: Callable[[str, str], None]):
        self._log_callback = callback

    def set_progress_callback(self, callback: Callable[[TTSTaskProgress], None]):
        self._progress_callback = callback

    def _log(self, message: str, level: str = "info"):
        if self._log_callback:
            self._log_callback(message, level)

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

    def _collect_tasks(
        self,
        selected_folders: List[str],
        max_count: int,
    ) -> List[TTSTaskInfo]:
        """Collect txt files from selected folders"""
        tasks: List[TTSTaskInfo] = []
        task_index = 0

        for folder_name in selected_folders:
            folder_path = os.path.join(self.input_dir, folder_name)
            txt_files = self._get_txt_files_in_folder(folder_path)

            for txt_path in txt_files:
                if task_index >= max_count:
                    return tasks
                tasks.append(TTSTaskInfo(
                    txt_path=txt_path,
                    folder_name=folder_name,
                    index=task_index,
                ))
                task_index += 1

        return tasks

    def _read_file_content(self, file_path: str) -> str:
        """Read content from a text file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self._log(f"Read file failed {file_path}: {str(e)}")
            return ""

    def _split_text(self, text: str) -> List[str]:
        """
        Split text into segments, each not exceeding MAX_TEXT_LENGTH.
        Split by sentence boundaries (。！？.!?)
        """
        if len(text) <= self.MAX_TEXT_LENGTH:
            return [text]

        segments = []
        sentence_pattern = re.compile(r'([^。！？.!?]*[。！？.!?])')
        sentences = sentence_pattern.findall(text)

        remaining = sentence_pattern.sub('', text)
        if remaining.strip():
            sentences.append(remaining)

        current_segment = ""
        for sentence in sentences:
            if len(current_segment) + len(sentence) <= self.MAX_TEXT_LENGTH:
                current_segment += sentence
            else:
                if current_segment:
                    segments.append(current_segment)
                if len(sentence) > self.MAX_TEXT_LENGTH:
                    for i in range(0, len(sentence), self.MAX_TEXT_LENGTH):
                        segments.append(sentence[i:i + self.MAX_TEXT_LENGTH])
                    current_segment = ""
                else:
                    current_segment = sentence

        if current_segment:
            segments.append(current_segment)

        return segments if segments else [text]

    def _merge_audio_segments(self, audio_segments: List[bytes]) -> Optional[bytes]:
        """Merge multiple audio segments into one using pydub"""
        try:
            from pydub import AudioSegment

            if len(audio_segments) == 1:
                return audio_segments[0]

            combined = AudioSegment.empty()
            for audio_data in audio_segments:
                segment = AudioSegment.from_mp3(io.BytesIO(audio_data))
                combined += segment

            output_buffer = io.BytesIO()
            combined.export(output_buffer, format="mp3")
            return output_buffer.getvalue()
        except ImportError:
            self._log("pydub not installed, cannot merge audio segments")
            return None
        except Exception as e:
            self._log(f"Merge audio failed: {str(e)}")
            return None

    async def _generate_single(
        self,
        task_info: TTSTaskInfo,
        session: aiohttp.ClientSession,
    ) -> bool:
        """Generate speech for a single txt file with retries"""
        content = self._read_file_content(task_info.txt_path)

        if not content.strip():
            self._log(f"Task #{task_info.index + 1} file content is empty, skipping")
            return False

        if len(content) > self.MAX_TEXT_LENGTH:
            self._log(
                f"Task #{task_info.index + 1} [{task_info.folder_name}] "
                f"text too long ({len(content)} > {self.MAX_TEXT_LENGTH} chars), skipping"
            )
            return False

        self._log(
            f"Task #{task_info.index + 1} [{task_info.folder_name}] "
            f"generating speech ({len(content)} chars)"
        )

        final_audio = None
        for attempt in range(self.max_retries):
            if self._stopped:
                return False

            await self._wait_if_paused()

            self._log(
                f"Task #{task_info.index + 1} "
                f"(attempt {attempt + 1}/{self.max_retries})"
            )

            result = await self.api_client.generate_speech(content, session)

            if result.success and result.audio_data:
                final_audio = result.audio_data
                break
            else:
                self._log(f"Task #{task_info.index + 1} failed: {result.error}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)

        if not final_audio:
            self._log(f"Task #{task_info.index + 1} all attempts failed")
            async with self._lock:
                self._progress.completed_tasks += 1
                self._progress.failed_tasks += 1
                self._update_progress()
            return False

        if final_audio:
            saved_path = await self._save_audio(final_audio, task_info)
            if saved_path:
                self._move_to_recycle(task_info)
                async with self._lock:
                    self._progress.completed_tasks += 1
                    self._progress.saved_files += 1
                    self._update_progress()
                self._log(f"Task #{task_info.index + 1} completed, saved and recycled source file")

                # Generate subtitle if enabled
                if self.subtitle_enabled:
                    subtitle_success, srt_path, srt_content = await self._generate_subtitle(
                        saved_path, task_info, session
                    )

                    # Apply subtitle text correction if enabled
                    if subtitle_success and self.subtitle_correction_enabled and srt_content:
                        srt_content, srt_path = self._apply_subtitle_correction(
                            srt_content, srt_path, content, task_info
                        )

                    # Split long subtitle segments if configured
                    if subtitle_success and srt_content and self.max_chars_per_segment > 0:
                        srt_content, srt_path = self._apply_subtitle_split(
                            srt_content, srt_path, task_info
                        )

                    # Recognize product time if enabled and subtitle was generated
                    if (
                        subtitle_success
                        and self.product_time_enabled
                        and self.product_time_api_client
                    ):
                        await self._recognize_product_time(
                            srt_path, srt_content, task_info, session
                        )

                return True
            else:
                self._log(f"Task #{task_info.index + 1} save failed")

        async with self._lock:
            self._progress.completed_tasks += 1
            self._progress.failed_tasks += 1
            self._update_progress()

        self._log(f"Task #{task_info.index + 1} final failure")
        return False

    async def _save_audio(self, audio_data: bytes, task_info: TTSTaskInfo) -> Optional[str]:
        """Save audio data to mp3 file, returns filepath on success"""
        try:
            output_folder = os.path.join(self.output_dir, task_info.folder_name)
            os.makedirs(output_folder, exist_ok=True)

            # 使用源TXT文件名（不含扩展名）作为音频文件名
            txt_filename = os.path.basename(task_info.txt_path)
            base_name = os.path.splitext(txt_filename)[0]
            filename = f"{base_name}.mp3"
            filepath = os.path.join(output_folder, filename)

            with open(filepath, "wb") as f:
                f.write(audio_data)

            return filepath
        except Exception as e:
            self._log(f"Save audio failed: {str(e)}")
            return None

    async def _generate_subtitle(
        self,
        audio_path: str,
        task_info: TTSTaskInfo,
        session: aiohttp.ClientSession,
    ) -> tuple[bool, str, str]:
        """
        Generate SRT subtitle for audio file.

        Returns:
            tuple: (success, srt_path, srt_content)
        """
        if self.subtitle_method == "local":
            return await self._generate_subtitle_local(audio_path, task_info)
        else:
            return await self._generate_subtitle_api(audio_path, task_info, session)

    async def _generate_subtitle_api(
        self,
        audio_path: str,
        task_info: TTSTaskInfo,
        session: aiohttp.ClientSession,
    ) -> tuple[bool, str, str]:
        """
        Generate SRT subtitle using API.

        Returns:
            tuple: (success, srt_path, srt_content)
        """
        if not self.subtitle_api_client:
            return False, "", ""

        async with self._lock:
            self._progress.current_subtitle_task = os.path.basename(audio_path)
            self._update_progress()

        self._log(f"Task #{task_info.index + 1} generating subtitle...")

        result = await self.subtitle_api_client.generate_subtitle(audio_path, session)

        if result.success and result.srt_content:
            # 转换为简体中文（如果启用）
            converted_content = self._convert_to_simplified(result.srt_content)

            srt_path = audio_path.rsplit(".", 1)[0] + ".srt"
            try:
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(converted_content)
                async with self._lock:
                    self._progress.subtitle_completed += 1
                    self._update_progress()
                self._log(f"Task #{task_info.index + 1} subtitle saved: {os.path.basename(srt_path)}")
                return True, srt_path, converted_content
            except Exception as e:
                self._log(f"Task #{task_info.index + 1} save subtitle failed: {str(e)}", "error")
                async with self._lock:
                    self._progress.subtitle_failed += 1
                    self._update_progress()
                return False, "", ""
        else:
            self._log(f"Task #{task_info.index + 1} subtitle generation failed: {result.error}", "error")
            async with self._lock:
                self._progress.subtitle_failed += 1
                self._update_progress()
            return False, "", ""

    async def _generate_subtitle_local(
        self,
        audio_path: str,
        task_info: TTSTaskInfo,
    ) -> tuple[bool, str, str]:
        """
        Generate SRT subtitle using local Whisper model.

        Returns:
            tuple: (success, srt_path, srt_content)
        """
        try:
            # Lazy initialize Whisper transcriber
            if self.whisper_transcriber is None:
                from .whisper_transcriber import WhisperTranscriber
                self.whisper_transcriber = WhisperTranscriber(
                    model_name=self.local_model,
                    device=self.local_device,
                )
                self._log(f"Initializing local Whisper model: {self.local_model} ({self.local_device})...")
                self.whisper_transcriber.initialize()

            async with self._lock:
                self._progress.current_subtitle_task = os.path.basename(audio_path)
                self._update_progress()

            self._log(f"Task #{task_info.index + 1} generating subtitle using local model {self.local_model} ({self.local_device})...")

            # Run transcription in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.whisper_transcriber.transcribe,
                audio_path,
                "zh",
                5
            )

            if not result.success:
                self._log(f"Task #{task_info.index + 1} local model transcription failed: {result.error}", "error")
                async with self._lock:
                    self._progress.subtitle_failed += 1
                    self._update_progress()
                return False, "", ""

            # Convert segments to SRT format
            srt_content = self._segments_to_srt(result.segments)

            if not srt_content:
                self._log(f"Task #{task_info.index + 1} local model generated empty subtitle", "error")
                async with self._lock:
                    self._progress.subtitle_failed += 1
                    self._update_progress()
                return False, "", ""

            # 转换为简体中文（如果启用）
            converted_content = self._convert_to_simplified(srt_content)

            # Save SRT file
            srt_path = audio_path.rsplit(".", 1)[0] + ".srt"
            try:
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(converted_content)
                async with self._lock:
                    self._progress.subtitle_completed += 1
                    self._update_progress()
                self._log(f"Task #{task_info.index + 1} local model subtitle saved: {os.path.basename(srt_path)}")
                return True, srt_path, converted_content
            except Exception as e:
                self._log(f"Task #{task_info.index + 1} save subtitle failed: {str(e)}", "error")
                async with self._lock:
                    self._progress.subtitle_failed += 1
                    self._update_progress()
                return False, "", ""

        except Exception as e:
            self._log(f"Task #{task_info.index + 1} local model subtitle generation failed: {str(e)}", "error")
            async with self._lock:
                self._progress.subtitle_failed += 1
                self._update_progress()
            return False, "", ""

    def _segments_to_srt(self, segments: List[dict]) -> str:
        """Convert transcription segments to SRT format"""
        if not segments:
            return ""

        srt_lines = []
        for i, segment in enumerate(segments, 1):
            start_time = self._format_srt_time(segment["start"])
            end_time = self._format_srt_time(segment["end"])
            text = segment["text"]

            srt_lines.append(f"{i}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(text)
            srt_lines.append("")

        return "\n".join(srt_lines)

    def _format_srt_time(self, seconds: float) -> str:
        """Format seconds to SRT time format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _convert_to_simplified(self, text: str) -> str:
        """
        Convert text to Simplified Chinese.

        Args:
            text: Input text (may contain Traditional Chinese)

        Returns:
            Text converted to Simplified Chinese
        """
        if not self.subtitle_enabled or not self.force_simplified:
            return text

        try:
            from opencc import OpenCC

            # Lazy initialize OpenCC converter
            if not hasattr(self, '_opencc_converter'):
                self._opencc_converter = OpenCC('t2s')  # Traditional to Simplified

            return self._opencc_converter.convert(text)
        except ImportError:
            self._log("Warning: opencc not installed, skipping Traditional to Simplified conversion")
            return text
        except Exception as e:
            self._log(f"Warning: Failed to convert to Simplified Chinese: {e}")
            return text

    def _apply_subtitle_correction(
        self,
        srt_content: str,
        srt_path: str,
        original_text: str,
        task_info: TTSTaskInfo,
    ) -> tuple[str, str]:
        """Apply subtitle text correction using original source text.

        Returns:
            tuple: (corrected_srt_content, srt_path)
        """
        try:
            from .subtitle_corrector import correct_subtitles

            corrected = correct_subtitles(srt_content, original_text)
            if corrected:
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(corrected)
                self._log(f"Task #{task_info.index + 1} subtitle text corrected using original text")
                return corrected, srt_path
            else:
                self._log(f"Task #{task_info.index + 1} subtitle correction returned empty, keeping original")
                return srt_content, srt_path
        except Exception as e:
            self._log(f"Task #{task_info.index + 1} subtitle correction failed: {str(e)}", "error")
            return srt_content, srt_path

    def _apply_subtitle_split(
        self,
        srt_content: str,
        srt_path: str,
        task_info: TTSTaskInfo,
    ) -> tuple[str, str]:
        """Split long subtitle segments based on max_chars_per_segment.

        Returns:
            tuple: (split_srt_content, srt_path)
        """
        try:
            from .subtitle_splitter import split_long_segments, _HAS_JIEBA

            if not _HAS_JIEBA:
                self._log(
                    f"Task #{task_info.index + 1} 警告: jieba 未安装，字幕将按字符硬切。"
                    f"建议运行 pip install jieba"
                )

            split_content = split_long_segments(srt_content, self.max_chars_per_segment)
            if split_content and split_content != srt_content:
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(split_content)
                self._log(
                    f"Task #{task_info.index + 1} long subtitles split "
                    f"(max {self.max_chars_per_segment} chars)"
                )
                return split_content, srt_path
            return srt_content, srt_path
        except Exception as e:
            self._log(f"Task #{task_info.index + 1} subtitle split failed: {str(e)}", "error")
            return srt_content, srt_path

    async def _recognize_product_time(
        self,
        srt_path: str,
        srt_content: str,
        task_info: TTSTaskInfo,
        session: aiohttp.ClientSession,
    ) -> bool:
        """
        Recognize product time segment from SRT content and rename the SRT file.

        Returns:
            bool: True if recognition succeeded and file was renamed
        """
        if not self.product_time_api_client:
            return False

        async with self._lock:
            self._progress.current_product_time_task = os.path.basename(srt_path)
            self._update_progress()

        self._log(f"Task #{task_info.index + 1} recognizing product time...")

        result = await self.product_time_api_client.recognize(srt_content, session)

        if result.success and result.start_time and result.end_time:
            new_path = self._rename_srt_with_time(srt_path, result.start_time, result.end_time)
            if new_path:
                async with self._lock:
                    self._progress.product_time_completed += 1
                    self._progress.current_product_time_task = ""
                    self._update_progress()
                self._log(
                    f"Task #{task_info.index + 1} product time recognized: "
                    f"{result.start_time} - {result.end_time}, renamed to {os.path.basename(new_path)}"
                )
                return True
            else:
                self._log(f"Task #{task_info.index + 1} failed to rename SRT file")
                async with self._lock:
                    self._progress.product_time_failed += 1
                    self._progress.current_product_time_task = ""
                    self._update_progress()
                return False
        elif result.success:
            # API call succeeded but no valid time segment found
            self._log(f"Task #{task_info.index + 1} no product time segment found")
            async with self._lock:
                self._progress.product_time_failed += 1
                self._progress.current_product_time_task = ""
                self._update_progress()
            return False
        else:
            self._log(f"Task #{task_info.index + 1} product time recognition failed: {result.error}")
            async with self._lock:
                self._progress.product_time_failed += 1
                self._progress.current_product_time_task = ""
                self._update_progress()
            return False

    def _rename_srt_with_time(
        self,
        srt_path: str,
        start_time: str,
        end_time: str,
    ) -> Optional[str]:
        """
        Rename SRT file to include time segment.

        Original: xxx.srt
        New: xxx-00-01-10,279-00-01-49,199.srt

        Note: Replace ':' with '-' for Windows filename compatibility.
        """
        try:
            # Convert time format: HH:MM:SS,mmm -> HH-MM-SS,mmm
            start_time_safe = start_time.replace(":", "-")
            end_time_safe = end_time.replace(":", "-")

            # Build new filename
            base_path = srt_path.rsplit(".", 1)[0]
            new_path = f"{base_path}-{start_time_safe}-{end_time_safe}.srt"

            # Rename file
            os.rename(srt_path, new_path)
            return new_path
        except Exception as e:
            self._log(f"Rename SRT file failed: {str(e)}")
            return None

    def _move_to_recycle(self, task_info: TTSTaskInfo):
        """Move used source file to recycle bin"""
        try:
            recycle_folder = os.path.join(
                self.recycle_dir, "合并文案", task_info.folder_name
            )
            os.makedirs(recycle_folder, exist_ok=True)
            dest = os.path.join(recycle_folder, os.path.basename(task_info.txt_path))
            shutil.move(task_info.txt_path, dest)
        except Exception as e:
            self._log(f"Move to recycle bin failed: {str(e)}")

    async def run(
        self,
        selected_folders: List[str],
        max_count: int,
    ) -> TTSTaskProgress:
        """
        Batch generate speech from txt files
        - Collect tasks from selected folders
        - Concurrency control
        - Progress callback
        - Move used files to recycle bin
        """
        tasks = self._collect_tasks(selected_folders, max_count)

        if not tasks:
            self._log("No txt files found")
            return self._progress

        self._progress = TTSTaskProgress(total_tasks=len(tasks))
        self._paused = False
        self._stopped = False
        self._pause_event.set()
        self._file_counter = 0

        self._log(f"Found {len(tasks)} txt file(s) to process")
        self._update_progress()

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def bounded_task(task_info: TTSTaskInfo, session: aiohttp.ClientSession):
            async with semaphore:
                if self._stopped:
                    return
                async with self._lock:
                    self._progress.current_task = (
                        f"{task_info.folder_name}/{os.path.basename(task_info.txt_path)}"
                    )
                    self._update_progress()
                try:
                    await self._generate_single(task_info, session)
                except Exception as e:
                    self._log(f"Task #{task_info.index + 1} unexpected error: {str(e)}", "error")
                    async with self._lock:
                        self._progress.completed_tasks += 1
                        self._progress.failed_tasks += 1
                        self._update_progress()

        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            task_list = [bounded_task(task, session) for task in tasks]
            await asyncio.gather(*task_list, return_exceptions=True)

        return self._progress

    async def run_with_files(
        self,
        file_paths: List[str],
        liuliang_recycle_dir: str,
    ) -> TTSTaskProgress:
        """
        Generate speech from a list of txt file paths (for liuliang mode)
        - Process files directly without folder structure
        - Move used files to liuliang recycle folder
        """
        if not file_paths:
            self._log("No txt files provided")
            return self._progress

        # Filter out non-existent files
        valid_files = [f for f in file_paths if os.path.exists(f)]
        if len(valid_files) < len(file_paths):
            self._log(f"Warning: {len(file_paths) - len(valid_files)} file(s) no longer exist")

        if not valid_files:
            self._log("No valid txt files to process")
            return self._progress

        # Create tasks from valid file paths
        tasks: List[TTSTaskInfo] = []
        for idx, file_path in enumerate(valid_files):
            tasks.append(TTSTaskInfo(
                txt_path=file_path,
                folder_name="流量语音",  # Use fixed folder name for liuliang mode
                index=idx,
            ))

        self._progress = TTSTaskProgress(total_tasks=len(tasks))
        self._paused = False
        self._stopped = False
        self._pause_event.set()
        self._file_counter = 0

        self._log(f"Found {len(tasks)} txt file(s) to process")
        self._update_progress()

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def bounded_task(task_info: TTSTaskInfo, session: aiohttp.ClientSession):
            async with semaphore:
                if self._stopped:
                    return
                async with self._lock:
                    self._progress.current_task = os.path.basename(task_info.txt_path)
                    self._update_progress()
                try:
                    await self._generate_single_liuliang(task_info, session, liuliang_recycle_dir)
                except Exception as e:
                    self._log(f"Task #{task_info.index + 1} unexpected error: {str(e)}", "error")
                    async with self._lock:
                        self._progress.completed_tasks += 1
                        self._progress.failed_tasks += 1
                        self._update_progress()

        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            task_list = [bounded_task(task, session) for task in tasks]
            await asyncio.gather(*task_list, return_exceptions=True)

        return self._progress

    async def _generate_single_liuliang(
        self,
        task_info: TTSTaskInfo,
        session: aiohttp.ClientSession,
        liuliang_recycle_dir: str,
    ) -> bool:
        """Generate speech for a single txt file in liuliang mode"""
        content = self._read_file_content(task_info.txt_path)

        if not content.strip():
            self._log(f"Task #{task_info.index + 1} file content is empty, skipping")
            async with self._lock:
                self._progress.completed_tasks += 1
                self._progress.failed_tasks += 1
                self._update_progress()
            return False

        if len(content) > self.MAX_TEXT_LENGTH:
            self._log(
                f"Task #{task_info.index + 1} [{os.path.basename(task_info.txt_path)}] "
                f"text too long ({len(content)} > {self.MAX_TEXT_LENGTH} chars), skipping"
            )
            async with self._lock:
                self._progress.completed_tasks += 1
                self._progress.failed_tasks += 1
                self._update_progress()
            return False

        self._log(
            f"Task #{task_info.index + 1} [{os.path.basename(task_info.txt_path)}] "
            f"generating speech ({len(content)} chars)"
        )

        final_audio = None
        for attempt in range(self.max_retries):
            if self._stopped:
                return False

            await self._wait_if_paused()

            self._log(
                f"Task #{task_info.index + 1} "
                f"(attempt {attempt + 1}/{self.max_retries})"
            )

            result = await self.api_client.generate_speech(content, session)

            if result.success and result.audio_data:
                final_audio = result.audio_data
                break
            else:
                self._log(f"Task #{task_info.index + 1} failed: {result.error}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)

        if not final_audio:
            self._log(f"Task #{task_info.index + 1} all attempts failed")
            async with self._lock:
                self._progress.completed_tasks += 1
                self._progress.failed_tasks += 1
                self._update_progress()
            return False

        if final_audio:
            saved_path = await self._save_audio_liuliang(final_audio, task_info)
            if saved_path:
                self._move_to_recycle_liuliang(task_info, liuliang_recycle_dir)
                async with self._lock:
                    self._progress.completed_tasks += 1
                    self._progress.saved_files += 1
                    self._update_progress()
                self._log(f"Task #{task_info.index + 1} completed, saved and recycled source file")

                # 生成字幕（如果启用）
                if self.subtitle_enabled:
                    subtitle_success, srt_path, srt_content = await self._generate_subtitle(
                        saved_path, task_info, session
                    )

                    # Apply subtitle text correction if enabled
                    if subtitle_success and self.subtitle_correction_enabled and srt_content:
                        srt_content, srt_path = self._apply_subtitle_correction(
                            srt_content, srt_path, content, task_info
                        )

                    # Split long subtitle segments if configured
                    if subtitle_success and srt_content and self.max_chars_per_segment > 0:
                        srt_content, srt_path = self._apply_subtitle_split(
                            srt_content, srt_path, task_info
                        )

                    # 注意：流量模式不需要产品时间识别功能
                    # product_time_enabled 在流量模式下总是 False

                return True
            else:
                self._log(f"Task #{task_info.index + 1} save failed")

        async with self._lock:
            self._progress.completed_tasks += 1
            self._progress.failed_tasks += 1
            self._update_progress()
        return False

    async def _save_audio_liuliang(self, audio_data: bytes, task_info: TTSTaskInfo) -> Optional[str]:
        """Save audio data to mp3 file for liuliang mode (no subfolder)"""
        try:
            os.makedirs(self.output_dir, exist_ok=True)

            # 使用源TXT文件名（不含扩展名）作为音频文件名
            txt_filename = os.path.basename(task_info.txt_path)
            base_name = os.path.splitext(txt_filename)[0]
            filename = f"{base_name}.mp3"
            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, "wb") as f:
                f.write(audio_data)

            return filepath
        except Exception as e:
            self._log(f"Save audio failed: {str(e)}")
            return None

    def _move_to_recycle_liuliang(self, task_info: TTSTaskInfo, liuliang_recycle_dir: str):
        """Move used source file to liuliang recycle folder"""
        try:
            recycle_folder = os.path.join(liuliang_recycle_dir, "流量文案")
            os.makedirs(recycle_folder, exist_ok=True)
            dest = os.path.join(recycle_folder, os.path.basename(task_info.txt_path))
            shutil.move(task_info.txt_path, dest)
        except Exception as e:
            self._log(f"Move to recycle bin failed: {str(e)}")
