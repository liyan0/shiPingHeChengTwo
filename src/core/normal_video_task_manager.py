import asyncio
import os
import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from ..models.config import SubtitleStyleConfig, TitleStyleConfig, BlurredBorderConfig, OverlayMaterialConfig, PipConfig
from ..utils.ffmpeg_manager import FFmpegManager
from .ffmpeg_pipeline import (
    BATCH_SIZE_NORMAL,
    run_ffmpeg_async,
    check_disk_space,
    create_temp_dir,
    cleanup_stale_temp_dirs,
    build_batch_concat_cmd,
    build_concat_demuxer_cmd,
)


@dataclass
class NormalVideoTaskInfo:
    """Information about a single normal video task"""
    audio_path: str
    srt_path: Optional[str]
    index: int


@dataclass
class NormalVideoTaskProgress:
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    current_task: str = ""


class NormalVideoTaskManager:
    SUPPORTED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
    SUPPORTED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.aac', '.m4a', '.flac'}

    def __init__(
        self,
        video_source_dir: str,
        audio_source_dir: str,
        bgm_dir: str,
        output_dir: str,
        recycle_dir: str,
        recycle_subdir: str = "流量语音",
        clip_duration_min: float = 5.0,
        clip_duration_max: float = 10.0,
        bgm_volume: float = 0.2,
        voice_volume: float = 1.0,
        resolution: Tuple[int, int] = (1080, 1920),
        max_concurrent: int = 2,
        subtitle_config: Optional[SubtitleStyleConfig] = None,
        title_config: Optional[TitleStyleConfig] = None,
        blurred_border_config: Optional[BlurredBorderConfig] = None,
        border_video_dir: str = "",
        overlay_material_config: Optional[OverlayMaterialConfig] = None,
        overlay_material_dir: str = "",
        pip_config: Optional[PipConfig] = None,
        chuchuang_mode: bool = False,
        chuchuang_material_dir: str = "",
        chuchuang_duration: int = 60,
        chuchuang_material_type: str = "图片",
        chuchuang_keyword: str = "橱窗",
    ):
        self.video_source_dir = video_source_dir
        self.audio_source_dir = audio_source_dir
        self.bgm_dir = bgm_dir
        self.output_dir = output_dir
        self.recycle_dir = recycle_dir
        self.recycle_subdir = recycle_subdir
        self.clip_duration_min = clip_duration_min
        self.clip_duration_max = clip_duration_max
        self.bgm_volume = bgm_volume
        self.voice_volume = voice_volume
        self.resolution = resolution
        self.max_concurrent = max_concurrent
        self.subtitle_config = subtitle_config or SubtitleStyleConfig()
        self.title_config = title_config
        self.blurred_border_config = blurred_border_config
        self.border_video_dir = border_video_dir
        self.overlay_material_config = overlay_material_config
        self.overlay_material_dir = overlay_material_dir
        self.pip_config = pip_config
        self.chuchuang_mode = chuchuang_mode
        self.chuchuang_material_dir = chuchuang_material_dir
        self.chuchuang_duration = chuchuang_duration
        self.chuchuang_material_type = chuchuang_material_type
        self.chuchuang_keyword = chuchuang_keyword

        self._log_callback: Optional[Callable[[str], None]] = None
        self._progress_callback: Optional[Callable[[NormalVideoTaskProgress], None]] = None

        self._paused = False
        self._stopped = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._progress = NormalVideoTaskProgress()
        self._lock = asyncio.Lock()

        self._video_duration_cache: Dict[str, float] = {}

    def _random_clip_duration(self) -> float:
        return random.uniform(self.clip_duration_min, self.clip_duration_max)

    def set_log_callback(self, callback: Callable[[str], None]):
        self._log_callback = callback

    def set_progress_callback(self, callback: Callable[[NormalVideoTaskProgress], None]):
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

    def _get_files_by_extension(self, directory: str, extensions: set) -> List[str]:
        if not os.path.exists(directory):
            return []
        files = []
        for f in sorted(os.listdir(directory)):
            ext = os.path.splitext(f)[1].lower()
            if ext in extensions:
                files.append(os.path.join(directory, f))
        return files

    def _get_source_videos(self) -> List[str]:
        return self._get_files_by_extension(self.video_source_dir, self.SUPPORTED_VIDEO_EXTENSIONS)

    def _get_bgm_files(self) -> List[str]:
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

    def _prepare_pip_clips(self, target_duration: float, exclude_videos: List[str]) -> List[Tuple[str, float, float]]:
        """Select PiP videos to cover target_duration using balanced selection + random start.
        Returns list of (video_path, start_time, actual_duration).
        """
        all_videos = self._get_source_videos()
        exclude_set = set(os.path.normpath(v) for v in exclude_videos)
        pip_videos = [v for v in all_videos if os.path.normpath(v) not in exclude_set]
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

    def _get_audio_duration(self, audio_path: str) -> float:
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
            self._video_duration_cache[video_path] = dur
            return dur
        except Exception as e:
            self._log(f"Failed to get video duration: {str(e)}")
            return 0.0

    def _build_subtitle_filter(self, subtitle_path: str, width: int, height: int) -> str:
        """Build FFmpeg subtitle filter string using ASS conversion."""
        from .subtitle_effects import convert_srt_to_ass
        ass_path = convert_srt_to_ass(
            srt_path=subtitle_path,
            config=self.subtitle_config,
            video_height=height,
            video_width=width,
        )
        return self._build_ass_filter(ass_path)

    def _build_subtitle_filter_with_delay(self, subtitle_path: str, width: int, height: int, delay_seconds: float) -> str:
        """Build FFmpeg subtitle filter with time delay for cover mode."""
        from .subtitle_effects import convert_srt_to_ass_with_delay
        ass_path = convert_srt_to_ass_with_delay(
            srt_path=subtitle_path,
            config=self.subtitle_config,
            video_height=height,
            video_width=width,
            delay_seconds=delay_seconds,
        )
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

    def _get_base_name(self, filename: str) -> str:
        """Remove all extensions from filename (e.g., 'test.mp3.mp3' -> 'test')"""
        name = filename
        while True:
            base, ext = os.path.splitext(name)
            if not ext or base == name:
                break
            name = base
        return name

    def _collect_tasks(self, max_count: int) -> List[NormalVideoTaskInfo]:
        if not os.path.exists(self.audio_source_dir):
            return []
        tasks: List[NormalVideoTaskInfo] = []
        audio_files = self._get_files_by_extension(self.audio_source_dir, self.SUPPORTED_AUDIO_EXTENSIONS)
        random.shuffle(audio_files)
        for i, audio_path in enumerate(audio_files):
            if len(tasks) >= max_count:
                break
            # Get base name without any extensions
            audio_basename = self._get_base_name(os.path.basename(audio_path))
            srt_path = None
            for f in os.listdir(self.audio_source_dir):
                if f.lower().endswith('.srt'):
                    srt_basename = self._get_base_name(f)
                    if srt_basename == audio_basename:
                        srt_path = os.path.join(self.audio_source_dir, f)
                        break
            tasks.append(NormalVideoTaskInfo(
                audio_path=audio_path,
                srt_path=srt_path,
                index=i,
            ))
        return tasks

    def _plan_clips(
        self, source_videos: List[str], target_duration: float
    ) -> List[Tuple[str, float, float]]:
        """Plan clips from source videos using balanced selection + random start.
        Returns list of (video_path, start_time, duration).
        """
        if not source_videos:
            return []
        clips: List[Tuple[str, float, float]] = []
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

    def _move_to_recycle(self, audio_path: str, srt_path: Optional[str]):
        recycle_audio_dir = os.path.join(self.recycle_dir, self.recycle_subdir)
        os.makedirs(recycle_audio_dir, exist_ok=True)
        try:
            shutil.move(audio_path, os.path.join(recycle_audio_dir, os.path.basename(audio_path)))
        except Exception as e:
            self._log(f"Failed to move audio to recycle: {str(e)}")
        if srt_path and os.path.exists(srt_path):
            try:
                shutil.move(srt_path, os.path.join(recycle_audio_dir, os.path.basename(srt_path)))
            except Exception as e:
                self._log(f"Failed to move srt to recycle: {str(e)}")

            # 移动ASS文件（可能有多个变体）
            base_name = os.path.splitext(srt_path)[0]
            srt_dir = os.path.dirname(srt_path)

            # 查找所有相关的ASS文件（包括 _delayed 后缀的）
            for ass_file in [
                base_name + ".ass",
                base_name + "_delayed.ass",
            ]:
                if os.path.exists(ass_file):
                    try:
                        shutil.move(ass_file, os.path.join(recycle_audio_dir, os.path.basename(ass_file)))
                    except Exception as e:
                        self._log(f"Failed to move {os.path.basename(ass_file)} to recycle: {str(e)}")

    async def _generate_single(
        self,
        task_info: NormalVideoTaskInfo,
        source_videos: List[str],
        bgm_file: Optional[str],
    ) -> bool:
        """Generate a single normal video using three-stage FFmpeg pipeline."""
        audio_path = task_info.audio_path
        srt_path = task_info.srt_path
        audio_name = os.path.basename(audio_path)
        self._log(f"Task #{task_info.index + 1}: Processing {audio_name}")

        audio_duration = self._get_audio_duration(audio_path)
        if audio_duration <= 0:
            self._log(f"Task #{task_info.index + 1}: Failed to get audio duration")
            return False

        clips = self._plan_clips(source_videos, audio_duration)
        if not clips:
            self._log(f"Task #{task_info.index + 1}: Failed to plan video clips")
            return False

        width, height = self.resolution
        audio_basename = self._get_base_name(os.path.basename(audio_path))
        output_filename = f"{audio_basename}.mp4"
        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(self.output_dir, output_filename)
        counter = 1
        while os.path.exists(output_path):
            output_filename = f"{audio_basename}_{counter}.mp4"
            output_path = os.path.join(self.output_dir, output_filename)
            counter += 1

        # Check disk space
        if not check_disk_space(self.output_dir, audio_duration, self._log):
            return False

        temp_dir = create_temp_dir(self.output_dir, "nvtm_")
        try:
            return await self._generate_single_pipeline(
                task_info, clips, audio_path, srt_path, bgm_file,
                audio_duration, width, height, output_path, output_filename, temp_dir,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _generate_single_pipeline(
        self,
        task_info: NormalVideoTaskInfo,
        clips: List[Tuple[str, float, float]],
        audio_path: str,
        srt_path: Optional[str],
        bgm_file: Optional[str],
        audio_duration: float,
        width: int, height: int,
        output_path: str,
        output_filename: str,
        temp_dir: str,
    ) -> bool:
        """Three-stage pipeline implementation for NormalVideo."""
        task_label = f"Task #{task_info.index + 1}"

        # === Stage 1: Batch scale/pad/concat ===
        self._log(f"{task_label}: Stage 1 - batch concat ({len(clips)} clips)")
        batches = [
            clips[i:i + BATCH_SIZE_NORMAL]
            for i in range(0, len(clips), BATCH_SIZE_NORMAL)
        ]
        batch_files = []
        # 1:1模式需要裁剪，16:9模式用黑边填充
        crop_to_square = (width == height)

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
            # Single batch: just trim with -c copy
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
        ok = await self._stage3_normal(
            task_info, stage2_path, audio_path, srt_path, bgm_file,
            audio_duration, width, height, output_path, temp_dir,
        )
        if not ok:
            return False

        self._log(f"{task_label}: Output -> {output_filename}")
        self._move_to_recycle(audio_path, srt_path)
        return True

    async def _stage3_normal(
        self,
        task_info: NormalVideoTaskInfo,
        stage2_path: str,
        audio_path: str,
        srt_path: Optional[str],
        bgm_file: Optional[str],
        audio_duration: float,
        width: int, height: int,
        output_path: str,
        temp_dir: str,
    ) -> bool:
        """Stage 3: border/pip/overlay/subtitle/title + audio mix -> final output."""
        task_label = f"Task #{task_info.index + 1}"

        cmd = [FFmpegManager.get_ffmpeg_path(), '-y', '-threads', '2']
        # Input 0: stage2 base video
        cmd.extend(['-i', stage2_path])
        next_idx = 1

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
            pip_clips = self._prepare_pip_clips(audio_duration, [])
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
            cmd.extend(['-i', bgm_file])
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
                output_label="vbordered",
                width=width,
                height=height,
            )
            filter_parts.extend(border_filter_parts)
            current_video = "[vbordered]"

        # PiP effect
        if self.pip_config and self.pip_config.enabled and pip_clips:
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
            current_label = current_video.strip("[]")
            pip_filter_parts = build_pip_filter(
                config=self.pip_config,
                main_label=current_label,
                pip_label="piptrimmed",
                output_label="vpip",
                width=width,
                height=height,
            )
            filter_parts.extend(pip_filter_parts)
            current_video = "[vpip]"

        # Overlay materials
        if overlay_inputs:
            from .video_effects import build_overlay_material_filters
            current_label = current_video.strip("[]")
            ol_parts = build_overlay_material_filters(
                input_label=current_label,
                output_label="voverlay",
                overlay_input_indices=overlay_inputs,
                width=width,
                height=height,
                duration=audio_duration,
            )
            filter_parts.extend(ol_parts)
            current_video = "[voverlay]"

        # 橱窗素材叠加（在字幕和标题之前）
        if self.chuchuang_mode:
            # 如果有字幕文件，根据字幕检测关键词；否则在最后一分钟叠加
            chuchuang_overlay_result = self._add_chuchuang_overlay(
                cmd, filter_parts, current_video, srt_path if (srt_path and os.path.exists(srt_path)) else None,
                audio_duration, width, height, task_label
            )
            if chuchuang_overlay_result:
                current_video = chuchuang_overlay_result

        # 先确定封面时长（需要在添加字幕前知道）
        cover_duration = 0.0
        if self.title_config and self.title_config.enabled:
            cover_mode = getattr(self.title_config, 'cover_mode', False)
            cover_duration = 0.04 if cover_mode else 0.0  # 固定为1帧（0.04秒）

        # Subtitle (需要考虑封面时长偏移)
        if self.subtitle_config.enabled and srt_path and os.path.exists(srt_path):
            if cover_duration > 0:
                # 封面模式：字幕需要延迟
                sub_filter = self._build_subtitle_filter_with_delay(srt_path, width, height, cover_duration)
            else:
                sub_filter = self._build_subtitle_filter(srt_path, width, height)
            filter_parts.append(f"{current_video}{sub_filter}[vsub]")
            current_video = "[vsub]"

        # Title overlay (with optional cover mode)
        if self.title_config and self.title_config.enabled:
            title_text = self._get_base_name(os.path.basename(audio_path))

            # 处理随机特效：如果是 random，随机选择一个实际特效
            actual_effect_type = self.title_config.effect_type
            if actual_effect_type == "random":
                actual_effect_type = random.choice(["none", "fade"])
                self._log(f"{task_label}: 随机选择标题特效 -> {actual_effect_type}")

            # 创建临时配置副本，使用实际特效
            from dataclasses import replace
            title_config_copy = replace(self.title_config, effect_type=actual_effect_type)

            # 检查是否启用封面模式
            cover_mode = getattr(title_config_copy, 'cover_mode', False)
            cover_duration = 0.04 if cover_mode else 0.0  # 固定为1帧（0.04秒）

            # 统一使用ASS字幕方式（简化，移除花字效果）
            from .subtitle_effects import generate_title_ass
            title_ass_path = os.path.join(
                tempfile.gettempdir(), f"title_{task_info.index}_{os.getpid()}.ass"
            )

            if cover_mode and cover_duration > 0:
                # 封面模式：在视频开头插入冻结的第一帧（裁剪成1:1）
                cover_crop_to_square = (width == height)  # 只有1:1模式才裁剪，16:9不裁剪

                generate_title_ass(
                    title_text=title_text,
                    config=title_config_copy,
                    video_height=height,
                    video_width=width,
                    duration_ms=int(cover_duration * 1000),
                    output_path=title_ass_path,
                )
                title_ass_filter = self._build_ass_filter(title_ass_path)
                filter_parts.append(f"{current_video}split=2[vcopy][vmain]")

                # 裁剪成1:1正方形（垂直居中）
                if cover_crop_to_square:
                    crop_size = min(width, height)
                    crop_x = (width - crop_size) // 2
                    crop_y = (height - crop_size) // 2
                    # 裁剪成正方形
                    crop_filter = f"crop={crop_size}:{crop_size}:{crop_x}:{crop_y}"
                    filter_parts.append(
                        f"[vcopy]trim=start=0:end=0.04,{crop_filter},"
                        f"loop=loop={int(cover_duration * 25)}:size=1:start=0,"
                        f"setpts=PTS-STARTPTS,{title_ass_filter}[vcover]"
                    )
                    # 后面的视频也要裁剪成正方形
                    filter_parts.append(f"[vmain]{crop_filter}[vmain_cropped]")
                    filter_parts.append(f"[vcover][vmain_cropped]concat=n=2:v=1:a=0[vfinal]")
                    current_video = "[vfinal]"
                    # 更新实际输出尺寸
                    width = height = crop_size
                else:
                    filter_parts.append(
                        f"[vcopy]trim=start=0:end=0.04,loop=loop={int(cover_duration * 25)}:size=1:start=0,"
                        f"setpts=PTS-STARTPTS,{title_ass_filter}[vcover]"
                    )
                    filter_parts.append(f"[vcover][vmain]concat=n=2:v=1:a=0[vfinal]")
                    current_video = "[vfinal]"
            else:
                # 普通标题模式
                generate_title_ass(
                    title_text=title_text,
                    config=title_config_copy,
                    video_height=height,
                    video_width=width,
                    duration_ms=int(audio_duration * 1000),
                    output_path=title_ass_path,
                )
                title_ass_filter = self._build_ass_filter(title_ass_path)
                filter_parts.append(f"{current_video}{title_ass_filter}[vtitle]")
                current_video = "[vtitle]"

        # Audio mixing: voice + BGM (aloop preserved)
        # 如果有封面，需要在音频开头添加静音
        total_duration = audio_duration + cover_duration
        audio_needs_filter = False
        if bgm_file and bgm_input_idx is not None:
            if cover_duration > 0:
                # 封面模式：在音频开头添加静音
                filter_parts.append(
                    f"aevalsrc=0:d={cover_duration:.3f}[silence]"
                )
                filter_parts.append(
                    f"[{audio_input_idx}:a]volume={self.voice_volume:.2f}[voice]"
                )
                filter_parts.append(
                    f"[silence][voice]concat=n=2:v=0:a=1[voicedelay]"
                )
                filter_parts.append(
                    f"[{bgm_input_idx}:a]volume={self.bgm_volume:.2f},"
                    f"aloop=loop=-1:size=2e+09,atrim=duration={total_duration:.3f}[bgm]"
                )
                filter_parts.append(
                    f"[voicedelay][bgm]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
                )
            else:
                filter_parts.append(
                    f"[{audio_input_idx}:a]volume={self.voice_volume:.2f}[voice]"
                )
                filter_parts.append(
                    f"[{bgm_input_idx}:a]volume={self.bgm_volume:.2f},"
                    f"aloop=loop=-1:size=2e+09,atrim=duration={audio_duration:.3f}[bgm]"
                )
                filter_parts.append(
                    f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
                )
            audio_out = "[aout]"
            audio_needs_filter = True
        else:
            if cover_duration > 0:
                # 封面模式：在音频开头添加静音
                filter_parts.append(
                    f"aevalsrc=0:d={cover_duration:.3f}[silence]"
                )
                if self.voice_volume != 1.0:
                    filter_parts.append(
                        f"[{audio_input_idx}:a]volume={self.voice_volume:.2f}[voice]"
                    )
                    filter_parts.append(
                        f"[silence][voice]concat=n=2:v=0:a=1[voicedelay]"
                    )
                else:
                    filter_parts.append(
                        f"[silence][{audio_input_idx}:a]concat=n=2:v=0:a=1[voicedelay]"
                    )
                audio_out = "[voicedelay]"
                audio_needs_filter = True
            elif self.voice_volume != 1.0:
                filter_parts.append(
                    f"[{audio_input_idx}:a]volume={self.voice_volume:.2f}[voice]"
                )
                audio_out = "[voice]"
                audio_needs_filter = True
            else:
                audio_out = f"{audio_input_idx}:a"
                audio_needs_filter = False

        # If no video filters were added, use input directly
        if not filter_parts:
            current_video = "[0:v]"
            filter_parts.append(f"[0:v]null[vpass]")
            current_video = "[vpass]"

        filter_complex = ";".join(filter_parts)

        # 计算输出时长（封面模式下需要加上封面时长）
        output_duration = audio_duration + cover_duration

        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', current_video,
            '-map', audio_out if audio_needs_filter else f'{audio_input_idx}:a',
            '-c:v', 'h264_nvenc', '-preset', 'p4', '-cq', '23',
            '-pix_fmt', 'yuv420p',
            '-threads:v', '1', '-x264-params', 'rc-lookahead=10:refs=2',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            '-t', f'{output_duration:.3f}',
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

    def _add_chuchuang_overlay(
        self,
        cmd: list,
        filter_parts: list,
        current_video: str,
        srt_path: str,
        audio_duration: float,
        width: int,
        height: int,
        task_label: str,
    ) -> Optional[str]:
        """添加橱窗素材叠加

        Returns:
            新的视频标签，如果没有检测到关键词则返回None
        """
        from .subtitle_keyword_detector import detect_keyword_in_srt
        from .chuchuang_material_helper import select_random_material, is_image_file, is_video_file

        # 检测关键词（如果有字幕文件）
        keyword_time = None
        if srt_path:
            keyword_time = detect_keyword_in_srt(srt_path, self.chuchuang_keyword, return_first=True)

        if keyword_time:
            # 检测到关键词，在该时间点叠加
            start_time, _ = keyword_time
            self._log(f"{task_label}: 检测到'{self.chuchuang_keyword}'关键词，时间点: {start_time:.2f}秒")
        else:
            # 未检测到关键词或无字幕文件，在视频最后一分钟叠加
            start_time = max(0, audio_duration - 60)
            if srt_path:
                self._log(f"{task_label}: 未检测到'{self.chuchuang_keyword}'关键词，将在视频最后一分钟叠加 (从 {start_time:.2f}秒 开始)")
            else:
                self._log(f"{task_label}: 无字幕文件，将在视频最后一分钟叠加 (从 {start_time:.2f}秒 开始)")

        # 选择随机素材（根据关键词和类型）
        # 素材路径：input/橱窗素材/{关键词}/{图片或视频}/
        keyword_material_dir = os.path.join(self.chuchuang_material_dir, self.chuchuang_keyword)
        material_path = select_random_material(keyword_material_dir, self.chuchuang_material_type)
        if not material_path:
            self._log(f"{task_label}: 橱窗素材文件夹为空 ({self.chuchuang_keyword}/{self.chuchuang_material_type})，跳过叠加")
            return None

        material_name = os.path.basename(material_path)
        material_type_name = "图片" if is_image_file(material_path) else "视频"
        self._log(f"{task_label}: 选择橱窗素材: {material_name} (类型: {material_type_name})")

        # 添加素材输入（如果是视频，只使用视频流，忽略音频流）
        material_input_idx = len([arg for arg in cmd if arg == '-i'])
        if is_image_file(material_path):
            cmd.extend(['-i', material_path])
        else:
            # 视频素材：使用 -an 忽略音频流，避免干扰BGM
            cmd.extend(['-i', material_path, '-an'])

        # 计算叠加时长（不超过视频剩余时长）
        overlay_duration = min(self.chuchuang_duration, audio_duration - start_time)
        if overlay_duration <= 0:
            self._log(f"{task_label}: 橱窗关键词出现时间过晚，跳过叠加")
            return None

        current_label = current_video.strip("[]")

        if is_image_file(material_path):
            # 图片素材：缩放居中，不超出边界
            filter_parts.append(
                f"[{material_input_idx}:v]scale='min({width},iw)':'min({height},ih)':force_original_aspect_ratio=decrease,"
                f"format=rgba[chuchuang_scaled];"
                f"[chuchuang_scaled]loop=loop=-1:size=32767:start=0,"
                f"trim=duration={overlay_duration},setpts=PTS+{start_time}/TB[chuchuang]"
            )
        else:
            # 视频素材：去除背景色，循环播放，缩放居中
            # 橱窗关键词用黄色背景，其他用黑色背景
            bg_color = "0xFFFF00" if self.chuchuang_keyword == "橱窗" else "0x000000"
            filter_parts.append(
                f"[{material_input_idx}:v]colorkey={bg_color}:0.3:0.1,"
                f"scale='min({width},iw)':'min({height},ih)':force_original_aspect_ratio=decrease,"
                f"format=rgba,loop=loop=-1:size=32767,"
                f"trim=duration={overlay_duration},setpts=PTS+{start_time}/TB[chuchuang]"
            )

        # 叠加到视频上半部分（距离顶部1/8高度位置）
        filter_parts.append(
            f"[{current_label}][chuchuang]overlay=x=(W-w)/2:y=(H-h)/8:eof_action=pass:format=auto[vchuchuang]"
        )

        self._log(f"{task_label}: 橱窗素材将在 {start_time:.2f}秒 叠加，时长 {overlay_duration:.2f}秒")
        return "[vchuchuang]"

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

    async def run(self, max_count: int) -> NormalVideoTaskProgress:
        cleanup_stale_temp_dirs(self.output_dir, "nvtm_")
        source_videos = self._get_source_videos()
        if not source_videos:
            self._log("Error: No video files found in source directory")
            return self._progress

        bgm_files = self._get_bgm_files()

        tasks = self._collect_tasks(max_count)
        if not tasks:
            self._log("No audio files found in source directory")
            return self._progress

        self._progress = NormalVideoTaskProgress(total_tasks=len(tasks))
        self._paused = False
        self._stopped = False
        self._pause_event.set()

        self._log(f"Found {len(tasks)} audio file(s) to process")
        self._log(f"Source videos: {len(source_videos)}, Clip duration: {self.clip_duration_min}s~{self.clip_duration_max}s")
        if bgm_files:
            self._log(f"BGM: {len(bgm_files)} 首可用 (每次随机选择)")
        else:
            self._log("No BGM (folder empty)")
        if self.subtitle_config.enabled:
            self._log("Subtitle enabled")
        if self.title_config and self.title_config.enabled:
            self._log("Title overlay enabled")
        if self.blurred_border_config and self.blurred_border_config.enabled:
            self._log("Blurred border enabled")
        if self.overlay_material_config and self.overlay_material_config.enabled:
            names = list(self.overlay_material_config.selections.keys())
            self._log(f"Overlay material enabled: {', '.join(names)}")
        if self.pip_config and self.pip_config.enabled:
            self._log(f"PiP enabled (size={self.pip_config.size_percent}%)")
        self._update_progress()

        # Pre-cache video durations
        self._log("Caching source video durations...")
        for v in source_videos:
            self._get_video_duration(v)

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def bounded_task(task_info: NormalVideoTaskInfo):
            async with semaphore:
                if self._stopped:
                    return
                await self._wait_if_paused()
                if self._stopped:
                    return

                async with self._lock:
                    self._progress.current_task = os.path.basename(task_info.audio_path)
                    self._update_progress()

                # 每次生成视频时随机选择 BGM
                bgm_file = random.choice(bgm_files) if bgm_files else None
                if bgm_file:
                    self._log(f"Task #{task_info.index + 1}: BGM -> {os.path.basename(bgm_file)}")

                try:
                    success = await self._generate_single(task_info, source_videos, bgm_file)
                except Exception as e:
                    self._log(f"Task #{task_info.index + 1}: Unhandled exception: {str(e)}")
                    success = False

                async with self._lock:
                    self._progress.completed_tasks += 1
                    if not success:
                        self._progress.failed_tasks += 1
                    self._update_progress()

        task_list = [bounded_task(task) for task in tasks]
        await asyncio.gather(*task_list, return_exceptions=True)

        return self._progress
