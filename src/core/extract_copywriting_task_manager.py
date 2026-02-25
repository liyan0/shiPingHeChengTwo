import asyncio
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

import aiohttp

from .video_scraper_client import VideoScraperClient, VideoInfo
from .whisper_transcriber import WhisperTranscriber


@dataclass
class ExtractCopywritingTaskInfo:
    url: str
    index: int


@dataclass
class ExtractCopywritingTaskProgress:
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    saved_files: int = 0
    current_task: str = ""


class ExtractCopywritingTaskManager:
    """Task manager for extracting copywriting from video URLs"""

    def __init__(
        self,
        output_dir: str,
        temp_dir: str,
        whisper_model: str = "small",
        whisper_device: str = "cpu",
        max_concurrent: int = 2,
        max_retries: int = 3,
    ):
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        self.whisper_model = whisper_model
        self.whisper_device = whisper_device
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries

        self._log_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[ExtractCopywritingTaskProgress], None]] = None

        self._paused = False
        self._stopped = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._progress = ExtractCopywritingTaskProgress()
        self._lock = asyncio.Lock()

        self._scraper: Optional[VideoScraperClient] = None
        self._transcriber: Optional[WhisperTranscriber] = None

    def set_log_callback(self, callback: Callable[[str], None]):
        self._log_callback = callback

    def set_progress_callback(self, callback: Callable[[ExtractCopywritingTaskProgress], None]):
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

    async def _initialize_components(self):
        """Initialize scraper and transcriber"""
        self._log("Initializing browser...")
        self._scraper = VideoScraperClient(headless=True)
        await self._scraper.initialize()

        self._log(f"Loading Whisper model ({self.whisper_model})...")
        self._transcriber = WhisperTranscriber(
            model_name=self.whisper_model,
            device=self.whisper_device,
        )
        self._transcriber.initialize()
        self._log("Components initialized")

    async def _cleanup_components(self):
        """Cleanup scraper and transcriber"""
        if self._scraper:
            await self._scraper.close()
            self._scraper = None
        if self._transcriber:
            self._transcriber.close()
            self._transcriber = None

    def _parse_urls(self, text: str) -> List[str]:
        """Parse URLs from text input"""
        lines = text.strip().split("\n")
        urls = []
        for line in lines:
            line = line.strip()
            if line and (line.startswith("http://") or line.startswith("https://")):
                urls.append(line)
        return urls

    async def _download_video(self, video_url: str, save_path: str) -> bool:
        """Download video from URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status != 200:
                        self._log(f"Download failed: HTTP {response.status}")
                        return False

                    with open(save_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if self._stopped:
                                return False
                            f.write(chunk)
            return True
        except Exception as e:
            self._log(f"Download error: {str(e)}")
            return False

    def _extract_audio(self, video_path: str, audio_path: str) -> bool:
        """Extract audio from video using FFmpeg (sync, run in executor)"""
        try:
            import subprocess
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                audio_path
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode == 0
        except Exception as e:
            self._log(f"Audio extraction error: {str(e)}")
            return False

    async def _extract_audio_async(self, video_path: str, audio_path: str) -> bool:
        """Extract audio from video using FFmpeg (async)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_audio, video_path, audio_path)

    def _transcribe_sync(self, audio_path: str):
        """Synchronous transcription wrapper"""
        return self._transcriber.transcribe(audio_path)

    async def _transcribe_async(self, audio_path: str):
        """Run transcription in thread pool to avoid blocking"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_path)

    def _save_copywriting(self, title: str, text: str) -> str:
        """Save copywriting to file"""
        os.makedirs(self.output_dir, exist_ok=True)

        # Clean filename
        safe_title = re.sub(r'[\\/:*?"<>|]', "", title)
        safe_title = safe_title.replace("..", "")  # Prevent path traversal
        safe_title = safe_title.strip(". ")  # Remove leading/trailing dots and spaces
        safe_title = safe_title[:80] if len(safe_title) > 80 else safe_title
        if not safe_title:
            safe_title = "untitled"

        file_path = os.path.join(self.output_dir, f"{safe_title}.txt")

        # Handle duplicate filenames
        counter = 1
        while os.path.exists(file_path):
            file_path = os.path.join(self.output_dir, f"{safe_title}_{counter}.txt")
            counter += 1

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

        return file_path

    def _cleanup_temp_files(self, *paths):
        """Remove temporary files"""
        for path in paths:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    async def _process_single_url(self, task: ExtractCopywritingTaskInfo) -> bool:
        """Process a single video URL"""
        url = task.url
        index = task.index

        video_path = None
        audio_path = None

        try:
            # Step 1: Extract video info
            self._progress.current_task = f"[{index + 1}] Extracting video info..."
            self._update_progress()
            self._log(f"[{index + 1}] Extracting video info from: {url[:50]}...")

            video_info = await self._scraper.extract_video_info(url)
            if not video_info.success:
                self._log(f"[{index + 1}] Failed to extract video info: {video_info.error}")
                return False

            title = video_info.title or f"video_{index + 1}"
            self._log(f"[{index + 1}] Title: {title}")

            # Step 2: Download video
            await self._wait_if_paused()
            if self._stopped:
                return False

            self._progress.current_task = f"[{index + 1}] Downloading video..."
            self._update_progress()
            self._log(f"[{index + 1}] Downloading video...")

            os.makedirs(self.temp_dir, exist_ok=True)
            video_path = os.path.join(self.temp_dir, f"video_{index}_{datetime.now().strftime('%H%M%S')}.mp4")

            if not await self._download_video(video_info.video_url, video_path):
                self._log(f"[{index + 1}] Failed to download video")
                return False

            # Step 3: Extract audio
            await self._wait_if_paused()
            if self._stopped:
                return False

            self._progress.current_task = f"[{index + 1}] Extracting audio..."
            self._update_progress()
            self._log(f"[{index + 1}] Extracting audio...")

            audio_path = os.path.join(self.temp_dir, f"audio_{index}_{datetime.now().strftime('%H%M%S')}.wav")

            if not await self._extract_audio_async(video_path, audio_path):
                self._log(f"[{index + 1}] Failed to extract audio")
                return False

            # Step 4: Transcribe
            await self._wait_if_paused()
            if self._stopped:
                return False

            self._progress.current_task = f"[{index + 1}] Transcribing..."
            self._update_progress()
            self._log(f"[{index + 1}] Transcribing audio...")

            result = await self._transcribe_async(audio_path)
            if not result.success:
                self._log(f"[{index + 1}] Transcription failed: {result.error}")
                return False

            # Step 5: Save result
            self._progress.current_task = f"[{index + 1}] Saving..."
            self._update_progress()

            saved_path = self._save_copywriting(title, result.text)
            self._log(f"[{index + 1}] Saved: {os.path.basename(saved_path)}")

            async with self._lock:
                self._progress.saved_files += 1

            return True

        except Exception as e:
            self._log(f"[{index + 1}] Error: {str(e)}")
            return False

        finally:
            # Cleanup temp files
            self._cleanup_temp_files(video_path, audio_path)

    async def _process_with_retry(self, task: ExtractCopywritingTaskInfo) -> bool:
        """Process URL with retry logic"""
        for attempt in range(self.max_retries):
            if self._stopped:
                return False

            if attempt > 0:
                self._log(f"[{task.index + 1}] Retry attempt {attempt + 1}/{self.max_retries}")
                await asyncio.sleep(2)

            success = await self._process_single_url(task)
            if success:
                return True

        return False

    async def _worker(self, semaphore: asyncio.Semaphore, task: ExtractCopywritingTaskInfo):
        """Worker coroutine for processing tasks"""
        async with semaphore:
            await self._wait_if_paused()
            if self._stopped:
                return

            success = await self._process_with_retry(task)

            async with self._lock:
                if success:
                    self._progress.completed_tasks += 1
                else:
                    self._progress.failed_tasks += 1
                self._update_progress()

    async def run(self, url_text: str) -> ExtractCopywritingTaskProgress:
        """Run the extraction task"""
        # Reset state
        self._paused = False
        self._stopped = False
        self._pause_event.set()
        self._progress = ExtractCopywritingTaskProgress()

        # Parse URLs
        urls = self._parse_urls(url_text)
        if not urls:
            self._log("No valid URLs found")
            return self._progress

        self._progress.total_tasks = len(urls)
        self._update_progress()
        self._log(f"Found {len(urls)} URLs to process")

        try:
            # Initialize components
            await self._initialize_components()

            # Create tasks
            tasks = [
                ExtractCopywritingTaskInfo(url=url, index=i)
                for i, url in enumerate(urls)
            ]

            # Process with semaphore
            semaphore = asyncio.Semaphore(self.max_concurrent)
            workers = [self._worker(semaphore, task) for task in tasks]
            await asyncio.gather(*workers)

            self._log(f"Completed: {self._progress.completed_tasks}/{self._progress.total_tasks}, "
                     f"Failed: {self._progress.failed_tasks}, Saved: {self._progress.saved_files}")

        except Exception as e:
            self._log(f"Task error: {str(e)}")

        finally:
            await self._cleanup_components()

        return self._progress
