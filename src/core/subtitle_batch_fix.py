"""Batch fix existing SRT subtitle files using the improved splitter.

Provides two public functions:
  - fix_srt_file(path, max_chars) — fix a single file in-place
  - batch_fix_srt_files(dirs, max_chars, callback) — scan directories and fix all SRT files
"""

import os
from pathlib import Path
from typing import Callable, List, Optional

from .subtitle_splitter import split_long_segments


def fix_srt_file(path: str, max_chars: int = 8) -> bool:  # 从12改成8，适配1:1视频
    """Read an SRT file, re-split with improved algorithm, and overwrite.

    Returns True if the file was modified, False if unchanged or on error.
    """
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    if not content.strip():
        return False

    fixed = split_long_segments(content, max_chars)

    if fixed == content:
        return False

    Path(path).write_text(fixed, encoding="utf-8")
    return True


def batch_fix_srt_files(
    dirs: List[str],
    max_chars: int = 8,  # 从12改成8，适配1:1视频
    callback: Optional[Callable[[str, bool], None]] = None,
) -> dict:
    """Scan *dirs* for .srt files and fix them in-place.

    Args:
        dirs: list of directory paths to scan (recursively).
        max_chars: maximum characters per subtitle segment.
        callback: optional function called after each file with (path, modified).

    Returns a dict with keys: total, modified, failed.
    """
    stats = {"total": 0, "modified": 0, "failed": 0}

    for dir_path in dirs:
        if not os.path.isdir(dir_path):
            continue
        for root, _dirs, files in os.walk(dir_path):
            for fname in files:
                if not fname.lower().endswith(".srt"):
                    continue
                fpath = os.path.join(root, fname)
                stats["total"] += 1
                try:
                    modified = fix_srt_file(fpath, max_chars)
                    if modified:
                        stats["modified"] += 1
                except Exception:
                    stats["failed"] += 1
                    modified = False

                if callback is not None:
                    callback(fpath, modified)

    return stats
