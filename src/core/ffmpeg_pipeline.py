"""Shared FFmpeg three-stage pipeline utilities.

Stage 1: Batch scale/pad/concat -> intermediate files (CRF 16 medium)
Stage 2: concat demuxer + -c copy -> single base video
Stage 3: effects + audio mix -> final output (CRF 23 medium)
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
import time
from typing import Callable, List, Optional, Tuple

BATCH_SIZE_NORMAL = 8
BATCH_SIZE_REVERSE = 4
INTERMEDIATE_CRF = 16
INTERMEDIATE_PRESET = 'medium'


async def run_ffmpeg_async(
    cmd: list,
    log_fn: Optional[Callable] = None,
    task_label: str = "",
) -> bool:
    """Execute an FFmpeg command asynchronously. Returns True on success."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='replace')[-2000:]
            if log_fn:
                log_fn(f"{task_label} FFmpeg error: {error_msg}")
            return False
        return True
    except Exception as e:
        if log_fn:
            log_fn(f"{task_label} exception: {str(e)}")
        return False


def check_disk_space(
    temp_dir: str,
    audio_duration: float,
    log_fn: Optional[Callable] = None,
) -> bool:
    """Check disk space. CRF 16 ~8-15 MB/s, conservative 15 MB/s * 2.5x margin."""
    estimated_bytes = int(audio_duration * 15 * 1024 * 1024 * 2.5)
    free = shutil.disk_usage(temp_dir).free
    if free < estimated_bytes:
        if log_fn:
            log_fn(
                f"磁盘空间不足: 需要约 {estimated_bytes // (1024*1024)} MB, "
                f"可用 {free // (1024*1024)} MB"
            )
        return False
    return True


def create_temp_dir(base_dir: str, prefix: str) -> str:
    """Create a temporary directory under base_dir."""
    os.makedirs(base_dir, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=base_dir)


def cleanup_stale_temp_dirs(
    base_dir: str,
    prefix: str,
    max_age_hours: float = 24.0,
):
    """Clean up temp directories older than max_age_hours."""
    if not os.path.exists(base_dir):
        return
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    for name in os.listdir(base_dir):
        if not name.startswith(prefix):
            continue
        path = os.path.join(base_dir, name)
        if not os.path.isdir(path):
            continue
        try:
            mtime = os.path.getmtime(path)
            if now - mtime > max_age_seconds:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


def build_batch_concat_cmd(
    clips: List[Tuple[str, float, float]],
    width: int,
    height: int,
    output_path: str,
    fps: int = 25,
) -> list:
    """Build Stage 1 single-batch command: scale/pad/setsar/fps + concat. No audio.

    Args:
        clips: [(path, start_time, duration), ...]
        width: Target width.
        height: Target height.
        output_path: Output file path.
        fps: Target frame rate.

    Returns:
        FFmpeg command as list of strings.
    """
    cmd = ['ffmpeg', '-y', '-threads', '2']
    for path, start, dur in clips:
        cmd.extend(['-ss', f'{start:.3f}', '-t', f'{dur:.3f}', '-i', path])

    filter_parts = []
    concat_inputs = []
    for i in range(len(clips)):
        filter_parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps={fps}[v{i}]"
        )
        concat_inputs.append(f"[v{i}]")

    filter_parts.append(
        f"{''.join(concat_inputs)}concat=n={len(concat_inputs)}:v=1:a=0[out]"
    )

    cmd.extend([
        '-filter_complex', ';'.join(filter_parts),
        '-map', '[out]', '-an',
        '-c:v', 'libx264', '-preset', INTERMEDIATE_PRESET,
        '-crf', str(INTERMEDIATE_CRF),
        '-pix_fmt', 'yuv420p', '-r', str(fps),
        '-video_track_timescale', '12800',
        '-movflags', '+faststart',
        output_path,
    ])
    return cmd


def build_concat_demuxer_cmd(
    batch_files: List[str],
    audio_duration: float,
    output_path: str,
    temp_dir: str,
) -> list:
    """Build Stage 2 concat demuxer command. -c copy lossless join + trim.

    Automatically creates concat_list.txt in temp_dir.
    """
    concat_list_path = os.path.join(temp_dir, "concat_list.txt")
    with open(concat_list_path, 'w', encoding='utf-8') as f:
        for p in batch_files:
            escaped = p.replace('\\', '/').replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    return [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', concat_list_path,
        '-c', 'copy',
        '-t', f'{audio_duration:.3f}',
        '-movflags', '+faststart',
        output_path,
    ]
