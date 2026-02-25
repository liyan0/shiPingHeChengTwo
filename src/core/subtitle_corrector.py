"""Correct ASR-generated SRT subtitles using original source text.

Uses difflib.SequenceMatcher to align ASR output with the original text,
then maps corrected characters back to each SRT segment while preserving
the original timestamps. All punctuation is stripped from the final output.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional


@dataclass
class SrtSegment:
    index: int
    start_time: str
    end_time: str
    text: str


def _strip_whitespace_and_punctuation(text: str) -> str:
    """Remove all Unicode punctuation, symbols, and whitespace."""
    return "".join(
        ch for ch in text
        if not (
            unicodedata.category(ch).startswith("P")
            or unicodedata.category(ch).startswith("S")
            or unicodedata.category(ch).startswith("Z")
            or ch in "\r\n\t"
        )
    )


def parse_srt(srt_content: str) -> List[SrtSegment]:
    """Parse SRT content into a list of SrtSegment objects."""
    segments = []
    blocks = re.split(r"\n\s*\n", srt_content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        try:
            index = int(lines[0].strip())
        except ValueError:
            continue
        time_match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
            lines[1].strip(),
        )
        if not time_match:
            continue
        text = "\n".join(lines[2:]).strip()
        segments.append(SrtSegment(
            index=index,
            start_time=time_match.group(1),
            end_time=time_match.group(2),
            text=text,
        ))
    return segments


def build_srt(segments: List[SrtSegment]) -> str:
    """Rebuild SRT content from a list of SrtSegment objects."""
    parts = []
    for i, seg in enumerate(segments, 1):
        parts.append(f"{i}")
        parts.append(f"{seg.start_time} --> {seg.end_time}")
        parts.append(seg.text)
        parts.append("")
    return "\n".join(parts)


def correct_subtitles(
    srt_content: str,
    original_text: str,
) -> Optional[str]:
    """Correct SRT subtitle text using the original source text.

    Aligns ASR-recognized text with the original text using
    SequenceMatcher, then replaces each SRT segment's text with
    the corresponding portion of the original. All punctuation
    is stripped from the final output.

    Args:
        srt_content: The ASR-generated SRT content.
        original_text: The original TXT source text.

    Returns:
        Corrected SRT content string, or None if correction fails.
    """
    segments = parse_srt(srt_content)
    if not segments:
        return None

    # Build asr_full by concatenating cleaned segment texts,
    # tracking each segment's character range.
    seg_clean_texts = []
    seg_ranges = []
    pos = 0
    for seg in segments:
        clean = _strip_whitespace_and_punctuation(seg.text)
        seg_clean_texts.append(clean)
        seg_ranges.append((pos, pos + len(clean)))
        pos += len(clean)
    asr_full = "".join(seg_clean_texts)

    orig_clean = _strip_whitespace_and_punctuation(original_text)

    if not asr_full or not orig_clean:
        return None

    # Align using SequenceMatcher
    matcher = SequenceMatcher(None, asr_full, orig_clean, autojunk=False)
    matching_blocks = matcher.get_matching_blocks()

    # Build position mapping: asr_pos -> orig_pos
    asr_to_orig = [None] * len(asr_full)
    for a_start, b_start, size in matching_blocks:
        for i in range(size):
            asr_to_orig[a_start + i] = b_start + i

    # Forward fill unmapped positions
    last_known = None
    for i in range(len(asr_to_orig)):
        if asr_to_orig[i] is not None:
            last_known = asr_to_orig[i]
        elif last_known is not None:
            asr_to_orig[i] = min(last_known + 1, len(orig_clean) - 1)
            last_known = asr_to_orig[i]

    # Backward fill leading Nones
    last_known = None
    for i in range(len(asr_to_orig) - 1, -1, -1):
        if asr_to_orig[i] is not None:
            last_known = asr_to_orig[i]
        elif last_known is not None:
            asr_to_orig[i] = max(last_known - 1, 0)
            last_known = asr_to_orig[i]

    # Map each segment's range to orig_clean range
    for idx, seg in enumerate(segments):
        seg_start, seg_end = seg_ranges[idx]
        if seg_start >= seg_end:
            seg.text = _strip_whitespace_and_punctuation(seg.text)
            continue

        orig_start = asr_to_orig[seg_start]
        orig_end = (
            asr_to_orig[seg_end - 1] + 1
            if seg_end - 1 < len(asr_to_orig)
            else len(orig_clean)
        )
        orig_end = min(orig_end, len(orig_clean))

        if orig_start is not None and orig_end is not None and orig_start < orig_end:
            seg.text = orig_clean[orig_start:orig_end]
        else:
            seg.text = _strip_whitespace_and_punctuation(seg.text)

    return build_srt(segments)
