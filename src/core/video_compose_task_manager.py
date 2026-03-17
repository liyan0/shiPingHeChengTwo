import asyncio
import os
import random
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from ..models.config import SubtitleStyleConfig, BlurredBorderConfig, OverlayMaterialConfig, PipConfig, TitleStyleConfig
from ..utils.ffmpeg_manager import FFmpegManager
from .ffmpeg_pipeline import (
    BATCH_SIZE_NORMAL,
    INTERMEDIATE_CRF,
    INTERMEDIATE_PRESET,
    run_ffmpeg_async,
    check_disk_space,
    create_temp_dir,
    cleanup_stale_temp_dirs,
    build_concat_demuxer_cmd,
    build_batch_concat_cmd,
)


@dataclass
class VideoComposeTaskInfo:
    """Information about a single video compose task"""
    audio_path: str
    folder_name: str
    index: int


@dataclass
class VideoComposeTaskProgress:
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    current_task: str = ""
    current_folder: str = ""


class VideoComposeTaskManager:
    SUPPORTED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
    SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    SUPPORTED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.aac', '.m4a', '.flac'}

    def __init__(
        self,
        audio_dir: str,
        bgm_dir: str,
        output_dir: str,
        clip_duration_min: float = 5.0,
        clip_duration_max: float = 10.0,
        bgm_volume: float = 0.2,
        voice_volume: float = 1.0,
        resolution: Tuple[int, int] = (1080, 1920),
        max_concurrent: int = 2,
        subtitle_config: Optional[SubtitleStyleConfig] = None,
        product_image_dir: str = "",
        product_video_count: int = 2,
        product_image_count: int = 2,
        product_image_duration_min: float = 2.0,
        product_image_duration_max: float = 5.0,
        priority_video: bool = True,
        overlay_mode: bool = True,
        overlay_effect_type: str = "none",  # "none", "blur", "mask"
        overlay_blur_strength: int = 20,
        overlay_mask_opacity: int = 30,
        blurred_border_config: Optional[BlurredBorderConfig] = None,
        border_video_dir: str = "",
        overlay_material_config: Optional[OverlayMaterialConfig] = None,
        overlay_material_dir: str = "",
        pip_config: Optional[PipConfig] = None,
        title_config: Optional[TitleStyleConfig] = None,
    ):
        self.audio_dir = audio_dir
        self.bgm_dir = bgm_dir
        self.output_dir = output_dir
        self.clip_duration_min = clip_duration_min
        self.clip_duration_max = clip_duration_max
        self.bgm_volume = bgm_volume
        self.voice_volume = voice_volume
        self.resolution = resolution
        self.max_concurrent = max_concurrent
        self.subtitle_config = subtitle_config or SubtitleStyleConfig()
        self.product_image_dir = product_image_dir
        self.product_video_count = product_video_count
        self.product_image_count = product_image_count
        self.product_image_duration_min = product_image_duration_min
        self.product_image_duration_max = product_image_duration_max
        self.priority_video = priority_video
        self.overlay_mode = overlay_mode
        self.overlay_effect_type = overlay_effect_type
        self.overlay_blur_strength = overlay_blur_strength
        self.overlay_mask_opacity = overlay_mask_opacity
        self.blurred_border_config = blurred_border_config
        self.border_video_dir = border_video_dir
        self.overlay_material_config = overlay_material_config
        self.overlay_material_dir = overlay_material_dir
        self.pip_config = pip_config
        self.title_config = title_config
        self._video_duration_cache: dict = {}

        self._log_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[VideoComposeTaskProgress], None]] = None
        self._missing_subtitle_callback: Optional[Callable[[str], str]] = None

        self._paused = False
        self._stopped = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._progress = VideoComposeTaskProgress()
        self._lock = asyncio.Lock()

    def _random_clip_duration(self) -> float:
        return random.uniform(self.clip_duration_min, self.clip_duration_max)

    def _random_product_image_duration(self) -> float:
        return random.uniform(self.product_image_duration_min, self.product_image_duration_max)

    def set_log_callback(self, callback: Callable[[str], None]):
        self._log_callback = callback

    def set_progress_callback(self, callback: Callable[[VideoComposeTaskProgress], None]):
        self._progress_callback = callback

    def set_missing_subtitle_callback(self, callback: Callable[[str], str]):
        """Set callback for handling missing subtitle files.
        Callback receives audio_path and should return: 'continue', 'skip', or 'cancel'
        """
        self._missing_subtitle_callback = callback

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

    def _get_base_name(self, filename: str) -> str:
        """Remove all extensions from filename (e.g., 'test.mp3.mp3' -> 'test')"""
        name = filename
        while True:
            base, ext = os.path.splitext(name)
            if not ext or base == name:
                break
            name = base
        return name

    def _get_files_by_extension(self, directory: str, extensions: set) -> List[str]:
        """Get all files with specified extensions in a directory"""
        if not os.path.exists(directory):
            return []

        files = []
        for f in sorted(os.listdir(directory)):
            ext = os.path.splitext(f)[1].lower()
            if ext in extensions:
                files.append(os.path.join(directory, f))
        return files

    def _get_source_videos(self) -> List[str]:
        """主体内容来源：border_video_dir（真实视频素材）"""
        if not self.border_video_dir:
            return []
        return self._get_files_by_extension(self.border_video_dir, self.SUPPORTED_VIDEO_EXTENSIONS)

    def _plan_clips(self, source_videos: List[str], target_duration: float) -> List[Tuple[str, float, float]]:
        """均衡选取 + 随机起始时间，返回 [(path, start, duration), ...]"""
        if not source_videos:
            return []
        clips = []
        accumulated = 0.0
        usage_count = {v: 0 for v in source_videos}
        max_attempts = len(source_videos) * 5 + 20
        attempts = 0
        while accumulated < target_duration and attempts < max_attempts:
            attempts += 1
            min_usage = min(usage_count.values())
            candidates = [v for v, c in usage_count.items() if c == min_usage]
            video = random.choice(candidates)
            usage_count[video] += 1
            video_dur = self._get_video_duration(video)
            if video_dur <= 0:
                continue
            clip_dur = min(self._random_clip_duration(), video_dur)
            max_start = max(0.0, video_dur - clip_dur)
            start = random.uniform(0, max_start) if max_start > 0 else 0.0
            actual_dur = min(clip_dur, video_dur - start)
            if actual_dur <= 0:
                continue
            clips.append((video, start, actual_dur))
            accumulated += actual_dur
        return clips

    def _get_bgm_files(self) -> List[str]:
        """Get all background music files"""
        return self._get_files_by_extension(self.bgm_dir, self.SUPPORTED_AUDIO_EXTENSIONS)

    def _get_border_videos(self) -> List[str]:
        if not self.border_video_dir:
            return []
        return self._get_files_by_extension(self.border_video_dir, self.SUPPORTED_VIDEO_EXTENSIONS)

    def _prepare_border_clips(self, target_duration: float) -> List[Tuple[str, float, float]]:
        """Select border videos to cover target_duration using balanced selection + random start.
        Returns list of (video_path, start_time, actual_duration).
        """
        border_videos = self._get_border_videos()
        if not border_videos:
            return []
        clips = []
        accumulated = 0.0
        usage_count = {v: 0 for v in border_videos}
        max_attempts = len(border_videos) * 5 + 20
        attempts = 0
        while accumulated < target_duration and attempts < max_attempts:
            attempts += 1
            min_usage = min(usage_count.values())
            candidates = [v for v, c in usage_count.items() if c == min_usage]
            video = random.choice(candidates)
            usage_count[video] += 1
            dur = self._get_video_duration(video)
            if dur <= 0:
                continue
            clip_dur = min(self._random_clip_duration(), dur)
            max_start = max(0.0, dur - clip_dur)
            start = random.uniform(0, max_start) if max_start > 0 else 0.0
            actual_dur = min(clip_dur, dur - start)
            clips.append((video, start, actual_dur))
            accumulated += actual_dur
        return clips

    def _prepare_pip_clips(self, target_duration: float, exclude_videos: List[str] = None) -> List[Tuple[str, float, float]]:
        """Select PiP videos to cover target_duration using balanced selection + random start.
        Returns list of (video_path, start_time, actual_duration).
        """
        all_videos = self._get_border_videos()  # same source: border_video_dir = 真实视频素材
        if exclude_videos:
            exclude_set = set(os.path.normpath(v) for v in exclude_videos)
            pip_videos = [v for v in all_videos if os.path.normpath(v) not in exclude_set]
        else:
            pip_videos = all_videos
        if not pip_videos:
            pip_videos = all_videos  # fallback if all excluded
        if not pip_videos:
            return []
        clips = []
        accumulated = 0.0
        usage_count = {v: 0 for v in pip_videos}
        max_attempts = len(pip_videos) * 5 + 20
        attempts = 0
        while accumulated < target_duration and attempts < max_attempts:
            attempts += 1
            min_usage = min(usage_count.values())
            candidates = [v for v, c in usage_count.items() if c == min_usage]
            video = random.choice(candidates)
            usage_count[video] += 1
            dur = self._get_video_duration(video)
            if dur <= 0:
                continue
            clip_dur = min(self._random_clip_duration(), dur)
            max_start = max(0.0, dur - clip_dur)
            start = random.uniform(0, max_start) if max_start > 0 else 0.0
            actual_dur = min(clip_dur, dur - start)
            clips.append((video, start, actual_dur))
            accumulated += actual_dur
        return clips

    def _count_inputs(self, cmd: list) -> int:
        return sum(1 for arg in cmd if arg == '-i')

    def _prepare_overlay_inputs(self, cmd: list) -> List[Tuple[int, float]]:
        """Add overlay material inputs to cmd. Returns [(input_idx, opacity_float)]."""
        if not self.overlay_material_config or not self.overlay_material_config.enabled:
            return []
        if not self.overlay_material_dir:
            return []

        result = []
        selections = self.overlay_material_config.selections

        # 检查是否是随机模式
        if "__random__" in selections:
            opacity_int = selections["__random__"]
            # 扫描所有子文件夹
            all_folders = []
            if os.path.isdir(self.overlay_material_dir):
                for name in os.listdir(self.overlay_material_dir):
                    folder_path = os.path.join(self.overlay_material_dir, name)
                    if os.path.isdir(folder_path):
                        videos = self._get_files_by_extension(folder_path, self.SUPPORTED_VIDEO_EXTENSIONS)
                        if videos:
                            all_folders.append((name, folder_path, videos))
            if all_folders:
                # 随机选择一个文件夹
                folder_name, folder_path, videos = random.choice(all_folders)
                chosen = random.choice(videos)
                input_idx = self._count_inputs(cmd)
                cmd.extend(['-stream_loop', '-1', '-i', chosen])
                result.append((input_idx, opacity_int / 100.0))
                self._log(f"Overlay (随机): {folder_name} -> {os.path.basename(chosen)} (opacity={opacity_int}%)")
        else:
            # 手动模式：使用选中的文件夹
            for folder_name, opacity_int in selections.items():
                folder_path = os.path.join(self.overlay_material_dir, folder_name)
                if not os.path.isdir(folder_path):
                    continue
                videos = self._get_files_by_extension(folder_path, self.SUPPORTED_VIDEO_EXTENSIONS)
                if not videos:
                    continue
                chosen = random.choice(videos)
                input_idx = self._count_inputs(cmd)
                cmd.extend(['-stream_loop', '-1', '-i', chosen])
                result.append((input_idx, opacity_int / 100.0))
                self._log(f"Overlay: {folder_name} -> {os.path.basename(chosen)} (opacity={opacity_int}%)")
        return result

    def _get_audio_files_in_folder(self, folder_path: str) -> List[str]:
        """Get all audio files in a folder"""
        return self._get_files_by_extension(folder_path, self.SUPPORTED_AUDIO_EXTENSIONS)

    def _find_subtitle_file(self, audio_path: str) -> Optional[str]:
        """Find subtitle file matching the audio file.
        Matches: audio_basename*.srt (e.g., 20260204_001.mp3 -> 20260204_001*.srt)
        """
        audio_dir = os.path.dirname(audio_path)
        audio_basename = self._get_base_name(os.path.basename(audio_path))

        if not os.path.exists(audio_dir):
            return None

        for f in os.listdir(audio_dir):
            if f.lower().endswith('.srt') and f.startswith(audio_basename):
                return os.path.join(audio_dir, f)
        return None

    def _parse_product_time_from_subtitle(self, subtitle_path: str) -> Optional[Tuple[float, float]]:
        """Parse product introduction start and end time from subtitle filename.

        Filename format: 20260205_001-00-01-16,099-00-01-58,099.srt
        Returns: (start_seconds, end_seconds) or None
        """
        filename = os.path.basename(subtitle_path)
        name_without_ext = os.path.splitext(filename)[0]

        # Match time pattern: -HH-MM-SS,mmm-HH-MM-SS,mmm
        pattern = r'-(\d{2})-(\d{2})-(\d{2}),(\d{3})-(\d{2})-(\d{2})-(\d{2}),(\d{3})$'
        match = re.search(pattern, name_without_ext)

        if not match:
            return None

        # Parse start time
        start_h = int(match.group(1))
        start_m = int(match.group(2))
        start_s = int(match.group(3))
        start_ms = int(match.group(4))
        start_seconds = start_h * 3600 + start_m * 60 + start_s + start_ms / 1000

        # Parse end time
        end_h = int(match.group(5))
        end_m = int(match.group(6))
        end_s = int(match.group(7))
        end_ms = int(match.group(8))
        end_seconds = end_h * 3600 + end_m * 60 + end_s + end_ms / 1000

        return (start_seconds, end_seconds)

    def _get_product_materials(self, folder_name: str) -> Tuple[List[str], List[str]]:
        """Get video and image materials from product folder.

        Args:
            folder_name: Product folder name (e.g., "金如意")

        Returns:
            (videos, images): List of video paths and image paths
        """
        product_folder = os.path.join(self.product_image_dir, folder_name)

        if not os.path.exists(product_folder):
            return [], []

        videos = []
        images = []

        for f in os.listdir(product_folder):
            ext = os.path.splitext(f)[1].lower()
            full_path = os.path.join(product_folder, f)

            if ext in self.SUPPORTED_VIDEO_EXTENSIONS:
                videos.append(full_path)
            elif ext in self.SUPPORTED_IMAGE_EXTENSIONS:
                images.append(full_path)

        return videos, images

    def _select_product_materials(
        self,
        videos: List[str],
        images: List[str],
        target_duration: float
    ) -> Tuple[List[str], List[str]]:
        """Select product materials based on settings.

        Args:
            videos: Available video list
            images: Available image list
            target_duration: Target duration in seconds

        Returns:
            (selected_videos, selected_images): Selected videos and images
        """
        selected_videos = []
        selected_images = []
        current_duration = 0.0

        if self.priority_video and videos:
            # Sort by duration, prefer longest videos
            video_durations = [(v, self._get_video_duration(v)) for v in videos]
            video_durations.sort(key=lambda x: x[1], reverse=True)

            # Add videos until filled or count limit reached
            for video_path, duration in video_durations:
                if len(selected_videos) >= self.product_video_count:
                    break
                if current_duration >= target_duration:
                    break
                selected_videos.append(video_path)
                current_duration += duration

            # If videos not enough, supplement with images
            if current_duration < target_duration and images:
                remaining_duration = target_duration - current_duration
                avg_product_image_duration = (self.product_image_duration_min + self.product_image_duration_max) / 2
                if avg_product_image_duration > 0:
                    images_needed = min(
                        int(remaining_duration / avg_product_image_duration) + 1,
                        self.product_image_count,
                        len(images)
                    )
                else:
                    images_needed = min(self.product_image_count, len(images))
                if images_needed > 0:
                    selected_images = random.sample(images, images_needed)
        else:
            # Not prioritizing video: select by count settings
            if videos:
                count = min(self.product_video_count, len(videos))
                selected_videos = random.sample(videos, count)
            if images:
                count = min(self.product_image_count, len(images))
                selected_images = random.sample(images, count)

        return selected_videos, selected_images

    def _rgb_to_ass_color(self, hex_color: str) -> str:
        """Convert RGB hex color to ASS format.
        #RRGGBB -> &H00BBGGRR
        """
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"&H00{b:02X}{g:02X}{r:02X}"

    def _build_subtitle_filter(self, subtitle_path: str, height: int, width: int) -> str:
        """Build FFmpeg subtitle filter string using ASS for accurate line wrapping."""
        from .subtitle_effects import convert_srt_to_ass
        ass_path = convert_srt_to_ass(subtitle_path, self.subtitle_config, height, width)
        return self._build_ass_filter(ass_path)

    @staticmethod
    def _escape_filter_path(path: str) -> str:
        return path.replace('\\', '/').replace(':', '\\:').replace("'", "\\'")

    def _build_ass_filter(self, ass_path: str) -> str:
        escaped_path = self._escape_filter_path(ass_path)
        if os.name == "nt":
            windir = os.environ.get("WINDIR", "C:/Windows")
            fonts_dir = os.path.join(windir, "Fonts")
            escaped_fonts = self._escape_filter_path(fonts_dir)
            return f"ass='{escaped_path}':fontsdir='{escaped_fonts}'"
        return f"ass='{escaped_path}'"

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds using ffprobe"""
        try:
            result = subprocess.run(
                [
                    FFmpegManager.get_ffprobe_path(), '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    audio_path
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return float(result.stdout.strip())
        except Exception as e:
            self._log(f"Failed to get audio duration: {str(e)}")
            return 0.0

    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds using ffprobe"""
        if video_path in self._video_duration_cache:
            return self._video_duration_cache[video_path]
        try:
            result = subprocess.run(
                [
                    FFmpegManager.get_ffprobe_path(), '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    video_path
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            dur = float(result.stdout.strip())
        except Exception as e:
            self._log(f"Failed to get video duration: {str(e)}")
            dur = 0.0
        self._video_duration_cache[video_path] = dur
        return dur

    def _collect_tasks(
        self,
        selected_folders: List[str],
        max_count: int,
    ) -> List[VideoComposeTaskInfo]:
        """Collect audio files from selected folders"""
        tasks: List[VideoComposeTaskInfo] = []
        task_index = 0

        for folder_name in selected_folders:
            folder_path = os.path.join(self.audio_dir, folder_name)
            audio_files = self._get_audio_files_in_folder(folder_path)

            for audio_path in audio_files:
                if task_index >= max_count:
                    return tasks
                tasks.append(VideoComposeTaskInfo(
                    audio_path=audio_path,
                    folder_name=folder_name,
                    index=task_index,
                ))
                task_index += 1

        return tasks

    async def _compose_single(
        self,
        task_info: VideoComposeTaskInfo,
        source_videos: List[str],
        bgm_file: Optional[str],
        subtitle_path: Optional[str] = None,
    ) -> bool:
        """Compose a single video using three-stage FFmpeg pipeline."""
        if self._stopped:
            return False

        await self._wait_if_paused()

        audio_path = task_info.audio_path
        audio_duration = self._get_audio_duration(audio_path)

        if audio_duration <= 0:
            self._log(f"Task #{task_info.index + 1} invalid audio duration, skipping")
            return False

        clips = self._plan_clips(source_videos, audio_duration)
        if not clips:
            self._log(f"Task #{task_info.index + 1}: Failed to plan video clips")
            return False

        self._log(f"Task #{task_info.index + 1} Planned {len(clips)} clips for {audio_duration:.2f}s")

        # Check for product introduction time from subtitle filename
        product_time = None
        product_videos = []
        product_images = []
        if subtitle_path and self.product_image_dir:
            product_time = self._parse_product_time_from_subtitle(subtitle_path)
            if product_time:
                start_time, end_time = product_time
                product_duration = end_time - start_time
                self._log(f"Task #{task_info.index + 1} detected product time: "
                          f"{start_time:.2f}s - {end_time:.2f}s ({product_duration:.2f}s)")

                all_product_videos, all_product_images = self._get_product_materials(task_info.folder_name)
                if all_product_videos or all_product_images:
                    product_videos, product_images = self._select_product_materials(
                        all_product_videos, all_product_images, product_duration
                    )
                    self._log(f"Task #{task_info.index + 1} selected product videos: "
                              f"{[os.path.basename(v) for v in product_videos]}")
                    self._log(f"Task #{task_info.index + 1} selected product images: "
                              f"{[os.path.basename(i) for i in product_images]}")
                else:
                    self._log(f"Task #{task_info.index + 1} no product materials found for {task_info.folder_name}")
                    product_time = None

        # Build output path
        output_folder = os.path.join(self.output_dir, task_info.folder_name)
        os.makedirs(output_folder, exist_ok=True)

        audio_basename = self._get_base_name(os.path.basename(audio_path))
        output_filename = f"{audio_basename}.mp4"
        output_path = os.path.join(output_folder, output_filename)
        counter = 1
        while os.path.exists(output_path):
            output_filename = f"{audio_basename}_{counter}.mp4"
            output_path = os.path.join(output_folder, output_filename)
            counter += 1

        width, height = self.resolution

        # Check disk space
        if not check_disk_space(output_folder, audio_duration, self._log):
            return False

        temp_dir = create_temp_dir(output_folder, "vctm_")
        try:
            return await self._compose_single_pipeline(
                task_info, clips, bgm_file, subtitle_path,
                audio_path, audio_duration, width, height,
                output_path, output_filename, temp_dir,
                product_time, product_videos, product_images,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _compose_single_pipeline(
        self,
        task_info: VideoComposeTaskInfo,
        clips: List[Tuple[str, float, float]],
        bgm_file: Optional[str],
        subtitle_path: Optional[str],
        audio_path: str,
        audio_duration: float,
        width: int, height: int,
        output_path: str,
        output_filename: str,
        temp_dir: str,
        product_time: Optional[Tuple[float, float]],
        product_videos: List[str],
        product_images: List[str],
    ) -> bool:
        """Three-stage pipeline implementation for VideoCompose."""
        task_label = f"Task #{task_info.index + 1}"

        # === Stage 1: Build clip batches using build_batch_concat_cmd ===
        self._log(f"{task_label}: Stage 1 - batch concat")

        batches = [clips[i:i + BATCH_SIZE_NORMAL] for i in range(0, len(clips), BATCH_SIZE_NORMAL)]

        # 1:1模式需要裁剪，16:9模式用黑边填充
        crop_to_square = (width == height)

        batch_files = []
        for bi, batch in enumerate(batches):
            await self._wait_if_paused()
            if self._stopped:
                return False
            batch_path = os.path.join(temp_dir, f"batch_{bi:03d}.mp4")
            cmd = build_batch_concat_cmd(batch, width, height, batch_path, crop_to_square=crop_to_square)
            ok = await run_ffmpeg_async(cmd, self._log, f"{task_label} batch {bi}")
            if not ok:
                self._log(f"{task_label}: Stage 1 batch {bi} failed")
                return False
            batch_files.append(batch_path)

        # === Stage 2: Concat demuxer lossless join ===
        await self._wait_if_paused()
        if self._stopped:
            return False
        self._log(f"{task_label}: Stage 2 - concat demuxer ({len(batch_files)} parts)")
        stage2_path = os.path.join(temp_dir, "stage2.mp4")
        if len(batch_files) == 1:
            cmd = [
                FFmpegManager.get_ffmpeg_path(), '-y', '-i', batch_files[0],
                '-c', 'copy', '-t', f'{audio_duration:.3f}',
                '-movflags', '+faststart', stage2_path,
            ]
        else:
            cmd = build_concat_demuxer_cmd(
                batch_files, audio_duration, stage2_path, temp_dir,
            )
        ok = await run_ffmpeg_async(cmd, self._log, f"{task_label} stage2")
        if not ok:
            self._log(f"{task_label}: Stage 2 failed")
            return False

        # === Stage 3: Effects + audio mix ===
        await self._wait_if_paused()
        if self._stopped:
            return False
        self._log(f"{task_label}: Stage 3 - effects + audio")
        ok = await self._stage3_compose(
            task_info, stage2_path, audio_path, bgm_file, subtitle_path,
            audio_duration, width, height, output_path, temp_dir,
            product_time, product_videos, product_images,
        )
        if not ok:
            return False

        self._log(f"{task_label} completed: {output_filename}")
        return True

    async def _stage3_compose(
        self,
        task_info: VideoComposeTaskInfo,
        stage2_path: str,
        audio_path: str,
        bgm_file: Optional[str],
        subtitle_path: Optional[str],
        audio_duration: float,
        width: int, height: int,
        output_path: str,
        temp_dir: str,
        product_time: Optional[Tuple[float, float]],
        product_videos: List[str],
        product_images: List[str],
    ) -> bool:
        """Stage 3: product/border/pip/overlay/subtitle/title + audio -> final."""
        task_label = f"Task #{task_info.index + 1}"

        cmd = [FFmpegManager.get_ffmpeg_path(), '-y', '-threads', '2']
        # Input 0: stage2 base video
        cmd.extend(['-i', stage2_path])
        next_idx = 1

        # Product video inputs
        product_input_start_idx = next_idx
        if product_time and (product_videos or product_images):
            for pv in product_videos:
                cmd.extend(['-i', pv])
                next_idx += 1
            for pi in product_images:
                cmd.extend(['-i', pi])
                next_idx += 1

        # Border clips
        border_clips = []
        border_input_start = next_idx
        if self.blurred_border_config and self.blurred_border_config.enabled:
            border_clips = self._prepare_border_clips(audio_duration)
            for bv_path, bv_start, bv_dur in border_clips:
                cmd.extend(['-ss', f'{bv_start:.3f}', '-t', f'{bv_dur:.3f}', '-i', bv_path])
                next_idx += 1

        # PiP clips
        pip_clips = []
        pip_input_start = next_idx
        if self.pip_config and self.pip_config.enabled:
            pip_clips = self._prepare_pip_clips(audio_duration)
            for pv_path, pv_start, pv_dur in pip_clips:
                cmd.extend(['-ss', f'{pv_start:.3f}', '-t', f'{pv_dur:.3f}', '-i', pv_path])
                next_idx += 1

        # Audio input
        audio_input_idx = next_idx
        cmd.extend(['-i', audio_path])
        next_idx += 1

        # BGM input
        bgm_input_idx = None
        if bgm_file:
            bgm_input_idx = next_idx
            cmd.extend(['-stream_loop', '-1', '-i', bgm_file])
            next_idx += 1

        # Overlay material inputs
        overlay_inputs = self._prepare_overlay_inputs(cmd)

        # Build filter_complex
        filter_parts = []
        current_video = "[0:v]"

        # Border effect
        if self.blurred_border_config and self.blurred_border_config.enabled and border_clips:
            border_concat_inputs = []
            for bi in range(len(border_clips)):
                idx = border_input_start + bi
                filter_parts.append(
                    f"[{idx}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=25[bv{bi}]"
                )
                border_concat_inputs.append(f"[bv{bi}]")
            filter_parts.append(
                f"{''.join(border_concat_inputs)}concat=n={len(border_clips)}:v=1:a=0[bconcat]"
            )
            filter_parts.append(
                f"[bconcat]trim=duration={audio_duration:.3f},setpts=PTS-STARTPTS[btrimmed]"
            )
            from .video_effects import build_blurred_border_filter
            border_filter_parts = build_blurred_border_filter(
                config=self.blurred_border_config,
                main_label="0:v",
                border_label="btrimmed",
                output_label="mainv",
                width=width,
                height=height,
            )
            filter_parts.extend(border_filter_parts)
            current_video = "[mainv]"
        else:
            filter_parts.append(f"[0:v]null[mainv]")
            current_video = "[mainv]"

        # PiP effect
        if self.pip_config and self.pip_config.enabled and pip_clips:
            filter_parts.append(f"[mainv]null[mainv_pre_pip]")
            pip_concat_inputs = []
            for pi in range(len(pip_clips)):
                idx = pip_input_start + pi
                filter_parts.append(
                    f"[{idx}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=25[pipv{pi}]"
                )
                pip_concat_inputs.append(f"[pipv{pi}]")
            filter_parts.append(
                f"{''.join(pip_concat_inputs)}concat=n={len(pip_clips)}:v=1:a=0[pipconcat]"
            )
            filter_parts.append(
                f"[pipconcat]trim=duration={audio_duration:.3f},setpts=PTS-STARTPTS[piptrimmed]"
            )
            from .video_effects import build_pip_filter
            pip_filter_parts = build_pip_filter(
                config=self.pip_config,
                main_label="mainv_pre_pip",
                pip_label="piptrimmed",
                output_label="mainv_pip",
                width=width,
                height=height,
            )
            filter_parts.extend(pip_filter_parts)
            current_video = "[mainv_pip]"

        # Overlay materials (before product, so product renders on top)
        if overlay_inputs:
            from .video_effects import build_overlay_material_filters
            ol_parts = build_overlay_material_filters(
                input_label=current_video.strip("[]"),
                output_label="voverlay",
                overlay_input_indices=overlay_inputs,
                width=width,
                height=height,
                duration=audio_duration,
            )
            filter_parts.extend(ol_parts)
            current_video = "[voverlay]"

        # Title overlay (rendered before product insertion so product overlays cover it)
        if self.title_config and self.title_config.enabled:
            title_text = self._get_base_name(os.path.basename(task_info.audio_path))

            # 处理随机特效：如果是 random，随机选择一个实际特效
            actual_effect_type = self.title_config.effect_type
            if actual_effect_type == "random":
                actual_effect_type = random.choice(["none", "fade"])
                self._log(f"{task_label}: 随机选择标题特效 -> {actual_effect_type}")

            # 创建临时配置副本，使用实际特效
            from dataclasses import replace
            title_config_copy = replace(self.title_config, effect_type=actual_effect_type)

            # 统一使用ASS字幕方式（简化，移除花字效果）
            from .subtitle_effects import generate_title_ass
            title_ass_path = os.path.join(
                tempfile.gettempdir(), f"title_{task_info.index}_{os.getpid()}.ass"
            )
            generate_title_ass(
                title_text=title_text,
                config=title_config_copy,
                video_height=height,
                video_width=width,
                duration_ms=int(audio_duration * 1000),
                output_path=title_ass_path,
            )
            title_ass_filter = self._build_ass_filter(title_ass_path)
            filter_parts.append(f"[{current_video.strip('[]')}]{title_ass_filter}[vtitle]")
            current_video = "[vtitle]"

        # Determine the label for product insertion
        main_label_for_product = current_video.strip("[]")

        # Product material insertion
        final_video_label = main_label_for_product
        if product_time and (product_videos or product_images):
            start_time, end_time = product_time
            product_duration = end_time - start_time

            product_concat_inputs = []
            product_filter_idx = 0

            product_video_durations = [self._get_video_duration(v) for v in product_videos]
            product_image_durations_list = [self._random_product_image_duration() for _ in product_images]
            product_segment_duration = sum(product_video_durations) + sum(product_image_durations_list)

            if product_segment_duration <= 0:
                self._log(f"{task_label} no product materials with valid duration, skipping insertion")
            else:
                loops_needed = int(product_duration / product_segment_duration) + 1

                # Split filters for looping
                for i, pv in enumerate(product_videos):
                    pv_input_idx = product_input_start_idx + i
                    if loops_needed > 1:
                        split_labels = "".join([f"[pvs{i}_{l}]" for l in range(loops_needed)])
                        filter_parts.append(
                            f"[{pv_input_idx}:v]split={loops_needed}{split_labels}"
                        )

                for i, pi in enumerate(product_images):
                    pi_input_idx = product_input_start_idx + len(product_videos) + i
                    if loops_needed > 1:
                        split_labels = "".join([f"[pis{i}_{l}]" for l in range(loops_needed)])
                        filter_parts.append(
                            f"[{pi_input_idx}:v]split={loops_needed}{split_labels}"
                        )

                for loop in range(loops_needed):
                    for i, pv in enumerate(product_videos):
                        if loops_needed > 1:
                            source_label = f"[pvs{i}_{loop}]"
                        else:
                            pv_input_idx = product_input_start_idx + i
                            source_label = f"[{pv_input_idx}:v]"
                        if self.overlay_mode:
                            filter_parts.append(
                                f"{source_label}scale={width}:{height}:force_original_aspect_ratio=decrease,"
                                f"format=rgba,"
                                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,setsar=1[pv{product_filter_idx}]"
                            )
                        else:
                            filter_parts.append(
                                f"{source_label}scale={width}:{height}:force_original_aspect_ratio=decrease,"
                                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1[pv{product_filter_idx}]"
                            )
                        product_concat_inputs.append(f"[pv{product_filter_idx}]")
                        product_filter_idx += 1

                    for i, pi in enumerate(product_images):
                        if loops_needed > 1:
                            source_label = f"[pis{i}_{loop}]"
                        else:
                            pi_input_idx = product_input_start_idx + len(product_videos) + i
                            source_label = f"[{pi_input_idx}:v]"
                        filter_parts.append(
                            f"{source_label}scale={width}:{height}:force_original_aspect_ratio=decrease,"
                            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
                            f"format=rgba,"
                            f"zoompan=z='min(zoom+0.001,1.2)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                            f"d={int(product_image_durations_list[i] * 25)}:s={width}x{height}:fps=25,"
                            f"setsar=1[pv{product_filter_idx}]"
                        )
                        product_concat_inputs.append(f"[pv{product_filter_idx}]")
                        product_filter_idx += 1

                if product_concat_inputs:
                    product_concat_count = len(product_concat_inputs)
                    if self.overlay_mode:
                        filter_parts.append(
                            f"{''.join(product_concat_inputs)}concat=n={product_concat_count}:v=1:a=0,"
                            f"format=rgba,"
                            f"trim=0:{product_duration},setpts=PTS-STARTPTS[productv]"
                        )
                    else:
                        filter_parts.append(
                            f"{''.join(product_concat_inputs)}concat=n={product_concat_count}:v=1:a=0,"
                            f"trim=0:{product_duration},setpts=PTS-STARTPTS[productv]"
                        )

                    final_video_label = self._build_product_merge_filters(
                        filter_parts, main_label_for_product,
                        start_time, product_duration, audio_duration,
                        width, height,
                    )

        # Subtitle
        if self.subtitle_config.enabled and subtitle_path:
            subtitle_filter = self._build_subtitle_filter(subtitle_path, height, width)
            filter_parts.append(
                f"[{final_video_label}]{subtitle_filter}[outv]"
            )
            self._log(f"{task_label} adding subtitles: {os.path.basename(subtitle_path)}")
            final_video_label = "outv"
        else:
            filter_parts.append(f"[{final_video_label}]null[outv]")
            final_video_label = "outv"

        # Audio mixing
        if bgm_file and bgm_input_idx is not None:
            filter_parts.append(
                f"[{audio_input_idx}:a]volume={self.voice_volume:.2f}[voice]"
            )
            filter_parts.append(
                f"[{bgm_input_idx}:a]volume={self.bgm_volume:.2f}[bgm]"
            )
            filter_parts.append(
                f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[outa]"
            )
            audio_map = "[outa]"
        else:
            if self.voice_volume != 1.0:
                filter_parts.append(
                    f"[{audio_input_idx}:a]volume={self.voice_volume:.2f}[voice]"
                )
                audio_map = "[voice]"
            else:
                audio_map = f"[{audio_input_idx}:a]"

        filter_complex = ";".join(filter_parts)
        self._log(f"{task_label} filter_complex length={len(filter_complex)} chars")

        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', f'[{final_video_label}]',
            '-map', audio_map,
            '-t', str(audio_duration),
            '-c:v', 'h264_nvenc', '-preset', 'p4', '-cq', '23',
            '-pix_fmt', 'yuv420p',
            '-threads:v', '1', '-x264-params', 'rc-lookahead=10:refs=2',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            output_path,
        ])

        success = await run_ffmpeg_async(cmd, self._log, task_label)

        # 验证输出文件是否有效
        if success and os.path.exists(output_path):
            if not self._verify_output_file(output_path):
                self._log(f"{task_label}: 输出文件验证失败，删除损坏的文件")
                try:
                    os.remove(output_path)
                except Exception:
                    pass
                return False

        return success

    def _verify_output_file(self, file_path: str) -> bool:
        """验证输出的MP4文件是否有效（检查moov atom）"""
        try:
            result = subprocess.run(
                [
                    FFmpegManager.get_ffprobe_path(), '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    file_path
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode != 0:
                return False
            duration = float(result.stdout.strip())
            return duration > 0
        except Exception:
            return False

    def _build_product_merge_filters(
        self,
        filter_parts: list,
        main_label: str,
        start_time: float,
        product_duration: float,
        audio_duration: float,
        width: int, height: int,
    ) -> str:
        """Build product merge filters (overlay or replace mode). Returns final label."""
        end_time = start_time + product_duration

        if self.overlay_mode:
            fade_duration = 0.5
            fade_in_end = start_time + fade_duration
            fade_out_start = end_time - fade_duration

            fade_expr = (
                f"if(lt(T,{start_time}),0,"
                f"if(lt(T,{fade_in_end}),(T-{start_time})/{fade_duration},"
                f"if(lt(T,{fade_out_start}),1,"
                f"if(lt(T,{end_time}),1-(T-{fade_out_start})/{fade_duration},"
                f"0))))"
            )

            if self.overlay_effect_type == "blur" and self.overlay_blur_strength > 0:
                blur_sigma = self.overlay_blur_strength * 0.3
                filter_parts.append(f"[{main_label}]split=2[mainv_clear][mainv_for_blur]")
                filter_parts.append(f"[mainv_for_blur]gblur=sigma={blur_sigma}[mainv_blur]")
                filter_parts.append(
                    f"[mainv_clear][mainv_blur]blend=all_expr='"
                    f"A*(1-({fade_expr}))+B*({fade_expr})'"
                    f"[mainv_processed]"
                )
                bg_label = "mainv_processed"
            elif self.overlay_effect_type == "mask" and self.overlay_mask_opacity > 0:
                opacity = self.overlay_mask_opacity / 100.0
                filter_parts.append(
                    f"color=black:s={width}x{height}:d={audio_duration}[black_layer]"
                )
                filter_parts.append(
                    f"[{main_label}][black_layer]blend=all_expr='"
                    f"A*(1-{opacity}*({fade_expr}))+B*{opacity}*({fade_expr})'"
                    f"[mainv_processed]"
                )
                bg_label = "mainv_processed"
            else:
                bg_label = main_label

            filter_parts.append(
                f"[productv]"
                f"fade=t=in:st=0:d={fade_duration}:alpha=1,"
                f"fade=t=out:st={product_duration - fade_duration}:d={fade_duration}:alpha=1,"
                f"setpts=PTS+{start_time}/TB[productv_faded]"
            )
            filter_parts.append(
                f"[{bg_label}][productv_faded]overlay="
                f"x=(W-w)/2:y=(H-h)/2:"
                f"eof_action=pass:format=auto[mergedv]"
            )
            return "mergedv"
        else:
            # Replace mode
            filter_parts.append(f"[{main_label}]split=2[mainv1][mainv2]")
            filter_parts.append(
                f"[mainv1]trim=0:{start_time},setpts=PTS-STARTPTS[part1]"
            )
            filter_parts.append(
                f"[mainv2]trim={end_time},setpts=PTS-STARTPTS[part3]"
            )
            filter_parts.append(
                f"[part1][productv][part3]concat=n=3:v=1:a=0[mergedv]"
            )
            return "mergedv"

    async def run(
        self,
        selected_folders: List[str],
        max_count: int,
    ) -> VideoComposeTaskProgress:
        """
        Batch compose videos from audio files
        """
        cleanup_stale_temp_dirs(self.output_dir, "vctm_")

        source_videos = self._get_source_videos()
        if not source_videos:
            self._log("Error: 真实视频素材 目录中没有找到视频文件")
            return self._progress

        bgm_files = self._get_bgm_files()

        # Pre-cache video durations
        for v in source_videos:
            self._get_video_duration(v)

        if bgm_files:
            self._log(f"BGM: {len(bgm_files)} 首可用 (每次随机选择)")
        else:
            self._log("No BGM selected (folder empty)")

        # Collect tasks
        tasks = self._collect_tasks(selected_folders, max_count)

        if not tasks:
            self._log("No audio files found")
            return self._progress

        self._progress = VideoComposeTaskProgress(total_tasks=len(tasks))
        self._paused = False
        self._stopped = False
        self._pause_event.set()

        self._log(f"Found {len(tasks)} audio file(s) to process")
        if self.subtitle_config.enabled:
            self._log("Subtitle enabled, will search for matching .srt files")
        self._update_progress()

        semaphore = asyncio.Semaphore(self.max_concurrent)
        cancel_all = False

        async def bounded_task(task_info: VideoComposeTaskInfo):
            nonlocal cancel_all
            async with semaphore:
                if self._stopped or cancel_all:
                    return

                async with self._lock:
                    self._progress.current_task = os.path.basename(task_info.audio_path)
                    self._progress.current_folder = task_info.folder_name
                    self._update_progress()

                # 每次生成视频时随机选择 BGM
                bgm_file = random.choice(bgm_files) if bgm_files else None
                if bgm_file:
                    self._log(f"Task #{task_info.index + 1}: BGM -> {os.path.basename(bgm_file)}")

                # Find subtitle file if subtitle is enabled
                subtitle_path = None
                if self.subtitle_config.enabled:
                    subtitle_path = self._find_subtitle_file(task_info.audio_path)
                    if not subtitle_path and self._missing_subtitle_callback:
                        action = self._missing_subtitle_callback(task_info.audio_path)
                        if action == "skip":
                            self._log(f"Task #{task_info.index + 1} skipped (no subtitle)")
                            async with self._lock:
                                self._progress.completed_tasks += 1
                                self._progress.failed_tasks += 1
                                self._update_progress()
                            return
                        elif action == "cancel":
                            self._log("All tasks cancelled by user")
                            cancel_all = True
                            return
                        # action == "continue": proceed without subtitle

                try:
                    success = await self._compose_single(
                        task_info, source_videos, bgm_file, subtitle_path
                    )
                except Exception as e:
                    self._log(f"Task #{task_info.index + 1} Unhandled exception: {str(e)}")
                    success = False

                async with self._lock:
                    self._progress.completed_tasks += 1
                    if not success:
                        self._progress.failed_tasks += 1
                    self._update_progress()

        task_list = [bounded_task(task) for task in tasks]
        await asyncio.gather(*task_list, return_exceptions=True)

        return self._progress
