"""SRT to ASS conversion with style and effects support.

Converts SRT subtitle files to ASS format using pysubs2,
applying full ASS V4+ styles and dynamic effects (fade, karaoke).
"""

import os
import re
import unicodedata
from typing import Optional

import pysubs2
from pysubs2 import SSAStyle, Color

from ..models.config import SubtitleStyleConfig, TitleStyleConfig


def hex_to_ass_color(hex_color: str, alpha: int = 0) -> Color:
    """Convert #RRGGBB hex color to pysubs2.Color.

    Args:
        hex_color: Color string like '#RRGGBB'.
        alpha: Transparency 0=opaque, 255=fully transparent.

    Returns:
        pysubs2.Color instance.
    """
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return Color(r, g, b, alpha)


def build_ass_style(config: SubtitleStyleConfig, video_height: int) -> SSAStyle:
    """Build an SSAStyle from SubtitleStyleConfig.

    Args:
        config: Subtitle style configuration.
        video_height: Video height in pixels for margin calculation.

    Returns:
        Configured SSAStyle object.
    """
    margin_v = int(video_height * config.margin_v_percent / 100)

    style = SSAStyle()
    style.fontname = config.font_name
    style.fontsize = config.font_size
    style.primarycolor = hex_to_ass_color(config.primary_color)
    style.outlinecolor = hex_to_ass_color(config.outline_color)
    style.outline = config.outline_width
    style.marginv = margin_v

    style.bold = config.bold
    style.italic = config.italic
    style.shadow = config.shadow_depth
    style.borderstyle = config.border_style
    style.backcolor = hex_to_ass_color(config.back_color, config.back_color_alpha)
    style.spacing = config.letter_spacing
    style.alignment = config.alignment
    style.marginl = config.margin_l
    style.marginr = config.margin_r
    style.scalex = config.scale_x
    style.scaley = config.scale_y

    return style


def _apply_fade_effect(
    subs: pysubs2.SSAFile,
    fade_in_ms: int,
    fade_out_ms: int,
) -> None:
    """Add \\fad() tags to every dialogue line.

    Args:
        subs: Loaded subtitle file (modified in-place).
        fade_in_ms: Fade-in duration in milliseconds.
        fade_out_ms: Fade-out duration in milliseconds.
    """
    for event in subs.events:
        if event.is_comment:
            continue
        event.text = rf"{{\fad({fade_in_ms},{fade_out_ms})}}" + event.text


def _is_cjk(char: str) -> bool:
    """Check if a character is CJK (Chinese/Japanese/Korean)."""
    try:
        name = unicodedata.name(char, "")
    except ValueError:
        return False
    return "CJK" in name or "HANGUL" in name or "HIRAGANA" in name or "KATAKANA" in name


def _is_punctuation(char: str) -> bool:
    """Check if a character is punctuation."""
    cat = unicodedata.category(char)
    return cat.startswith("P") or cat.startswith("S")


# Characters that must not appear at the start of a line (CJK punctuation prohibition).
_NO_LINE_START = set("，。！？、；：）》」』】〉…—～·")


def _estimate_text_width(text: str, font_size: float, letter_spacing: float) -> float:
    """Estimate rendered text width in ASS coordinate units.

    Skips ASS override tags ``{...}`` and ``\\N`` line breaks.
    """
    width = 0.0
    i = 0
    length = len(text)
    char_count = 0
    while i < length:
        ch = text[i]
        # Skip ASS override tags
        if ch == '{':
            end = text.find('}', i)
            if end != -1:
                i = end + 1
                continue
            # No closing brace – treat as literal
        # Skip \N line break marker
        if ch == '\\' and i + 1 < length and text[i + 1] == 'N':
            i += 2
            continue
        if _is_cjk(ch):
            width += font_size
        elif ch.isalpha() or ch.isdigit():
            width += font_size * 0.55
        elif ord(ch) > 0x2000:
            # CJK punctuation / fullwidth symbols – narrower than a full CJK char
            width += font_size * 0.55
        else:
            # ASCII punctuation, spaces, etc.
            width += font_size * 0.3
        char_count += 1
        i += 1
    if char_count > 1:
        width += letter_spacing * (char_count - 1)
    return width


def _wrap_subtitle_lines(
    text: str,
    available_width: float,
    font_size: float,
    letter_spacing: float,
) -> str:
    """Insert ``\\N`` hard line breaks so that no line exceeds *available_width*.

    Preserves existing ``\\N`` breaks and ASS override tags ``{...}``.
    Applies CJK punctuation prohibition: characters in ``_NO_LINE_START``
    are pulled back to the previous line rather than starting a new one.
    """
    if available_width <= 0:
        return text

    result: list[str] = []
    line_width = 0.0
    char_on_line = 0
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        # --- Preserve existing \N ---
        if ch == '\\' and i + 1 < length and text[i + 1] == 'N':
            result.append('\\N')
            line_width = 0.0
            char_on_line = 0
            i += 2
            continue

        # --- Preserve ASS override tags (don't count width) ---
        if ch == '{':
            end = text.find('}', i)
            if end != -1:
                result.append(text[i:end + 1])
                i = end + 1
                continue

        # --- Calculate character width ---
        if _is_cjk(ch):
            ch_width = font_size
        elif ch.isalpha() or ch.isdigit():
            ch_width = font_size * 0.55
        elif ord(ch) > 0x2000:
            ch_width = font_size * 0.55
        else:
            ch_width = font_size * 0.3

        spacing = letter_spacing if char_on_line > 0 else 0.0
        new_width = line_width + spacing + ch_width

        # --- Need to wrap? ---
        if new_width > available_width and char_on_line > 0:
            # CJK punctuation prohibition: don't let these start a new line
            if ch in _NO_LINE_START:
                result.append(ch)
                line_width = new_width
                char_on_line += 1
                i += 1
                # If the *next* char also needs wrapping, break after this one
                continue
            result.append('\\N')
            line_width = ch_width
            char_on_line = 1
        else:
            line_width = new_width
            char_on_line += 1

        result.append(ch)
        i += 1

    return ''.join(result)


def _tokenize_for_karaoke(text: str):
    """Split text into tokens for karaoke timing.

    Chinese characters are individual tokens; English words are grouped;
    punctuation attaches to the preceding token.

    Returns:
        List of (token_text, weight) tuples.
    """
    tokens = []
    i = 0
    while i < len(text):
        # Detect \N line break – emit as zero-weight token
        if text[i] == '\\' and i + 1 < len(text) and text[i + 1] == 'N':
            tokens.append(("\\N", 0.0))
            i += 2
            continue
        ch = text[i]
        if _is_cjk(ch):
            tokens.append((ch, 1.0))
            i += 1
        elif ch.isalpha():
            word = []
            while i < len(text) and text[i].isalpha():
                word.append(text[i])
                i += 1
            tokens.append(("".join(word), max(0.5, len(word) * 0.5)))
        elif _is_punctuation(ch):
            tokens.append((ch, 0.2))
            i += 1
        elif ch.isspace():
            tokens.append((ch, 0.1))
            i += 1
        else:
            tokens.append((ch, 0.5))
            i += 1
    return tokens


def _apply_karaoke_effect(
    subs: pysubs2.SSAFile,
    highlight_color: str,
) -> None:
    """Add karaoke \\k tags to every dialogue line.

    The primary colour is swapped to the highlight colour and the
    secondary colour is set to the original text colour so that the
    karaoke sweep reveals the highlight.

    Args:
        subs: Loaded subtitle file (modified in-place).
        highlight_color: Hex colour for the karaoke highlight.
    """
    original_primary = subs.styles["Default"].primarycolor
    subs.styles["Default"].secondarycolor = original_primary
    subs.styles["Default"].primarycolor = hex_to_ass_color(highlight_color)

    for event in subs.events:
        if event.is_comment:
            continue

        # Strip existing override tags for clean tokenisation
        plain = re.sub(r"\{[^}]*\}", "", event.text)
        tokens = _tokenize_for_karaoke(plain)

        total_weight = sum(w for _, w in tokens)
        if total_weight <= 0:
            continue

        duration_cs = (event.end - event.start) // 10  # centiseconds
        parts = []
        for token_text, weight in tokens:
            if token_text == "\\N":
                parts.append("\\N")
                continue
            k_cs = max(1, int(duration_cs * weight / total_weight))
            parts.append(rf"{{\k{k_cs}}}{token_text}")

        event.text = "".join(parts)


def convert_srt_to_ass(
    srt_path: str,
    config: SubtitleStyleConfig,
    video_height: int,
    video_width: int = 0,
    output_path: Optional[str] = None,
) -> str:
    """Convert an SRT file to ASS with styles and effects.

    Args:
        srt_path: Path to the source SRT file.
        config: Subtitle style configuration.
        video_height: Video height in pixels.
        output_path: Optional output path; defaults to same dir with .ass extension.

    Returns:
        Absolute path to the generated ASS file.
    """
    subs = pysubs2.load(srt_path, encoding="utf-8")

    style = build_ass_style(config, video_height)
    subs.styles["Default"] = style

    # --- Auto-wrap long lines ---
    if config.wrap_width_percent > 0 and video_width > 0:
        play_res_x = int(subs.info.get("PlayResX", 384))
        play_res_y = int(subs.info.get("PlayResY", 288))
        margin_l_px = config.margin_l * video_width / play_res_x
        margin_r_px = config.margin_r * video_width / play_res_x
        available_width_px = video_width * config.wrap_width_percent / 100 - margin_l_px - margin_r_px
        rendered_font_size = config.font_size * video_height / play_res_y
        rendered_spacing = config.letter_spacing * video_height / play_res_y
        for event in subs.events:
            if event.is_comment:
                continue
            event.text = _wrap_subtitle_lines(
                event.text, available_width_px, rendered_font_size, rendered_spacing
            )

    if config.effect_type == "fade":
        _apply_fade_effect(subs, config.fade_in_ms, config.fade_out_ms)
    elif config.effect_type == "karaoke":
        _apply_karaoke_effect(subs, config.karaoke_highlight_color)

    if output_path is None:
        base, _ = os.path.splitext(srt_path)
        output_path = base + ".ass"

    subs.save(output_path, encoding="utf-8")
    return output_path


def wrap_title_text(
    text: str,
    font_size: int,
    scale_x: int,
    video_width: int,
    margin_l: int,
    margin_r: int,
    max_width_percent: float,
    letter_spacing: float = 0.0,
) -> str:
    """Insert \\N hard line breaks so the title fits within max_width_percent of video width.

    Prefers breaking after punctuation; falls back to breaking before the
    character that would overflow.
    """
    PUNCTUATION = set("。，！？、；：…—,.!?;:")

    effective_font_size = font_size * scale_x / 100.0
    max_width = (video_width - margin_l - margin_r) * max_width_percent / 100.0

    if max_width <= 0 or not text:
        return text

    def char_width(ch: str) -> float:
        eaw = unicodedata.east_asian_width(ch)
        if eaw in ("W", "F"):
            return effective_font_size
        return effective_font_size * 0.55

    lines = []
    current_line: list[str] = []
    current_width = 0.0
    last_punct_pos = -1  # index in current_line of last punctuation char

    for ch in text:
        cw = char_width(ch)
        spacing = letter_spacing if current_line else 0.0
        if current_width + spacing + cw > max_width and current_line:
            if last_punct_pos >= 0:
                break_at = last_punct_pos + 1
                lines.append("".join(current_line[:break_at]))
                remaining = current_line[break_at:]
            else:
                lines.append("".join(current_line))
                remaining = []
            current_line = remaining
            current_width = sum(
                char_width(c) + (letter_spacing if i > 0 else 0.0)
                for i, c in enumerate(current_line)
            )
            last_punct_pos = -1
            spacing = letter_spacing if current_line else 0.0

        current_line.append(ch)
        current_width += spacing + cw
        if ch in PUNCTUATION:
            last_punct_pos = len(current_line) - 1

    if current_line:
        lines.append("".join(current_line))

    return r"\N".join(lines)


def generate_title_ass(
    title_text: str,
    config: TitleStyleConfig,
    video_height: int,
    video_width: int,
    duration_ms: int,
    output_path: str,
) -> str:
    """Generate an ASS file with a single full-duration title event.

    Args:
        title_text: The title text to display.
        config: Title style configuration.
        video_height: Video height in pixels.
        video_width: Video width in pixels.
        duration_ms: Total duration in milliseconds.
        output_path: Path to write the ASS file.

    Returns:
        Absolute path to the generated ASS file.
    """
    subs = pysubs2.SSAFile()
    subs.info["PlayResX"] = str(video_width)
    subs.info["PlayResY"] = str(video_height)

    margin_v = int(video_height * config.margin_v_percent / 100)

    style = SSAStyle()
    style.fontname = config.font_name
    style.fontsize = config.font_size
    style.primarycolor = hex_to_ass_color(config.primary_color)
    style.outlinecolor = hex_to_ass_color(config.outline_color)
    style.outline = config.outline_width
    style.marginv = margin_v
    style.bold = config.bold
    style.italic = config.italic
    style.shadow = config.shadow_depth
    style.borderstyle = config.border_style
    style.backcolor = hex_to_ass_color(config.back_color, config.back_color_alpha)
    style.spacing = config.letter_spacing
    style.alignment = config.alignment
    style.marginl = config.margin_l
    style.marginr = config.margin_r
    style.scalex = config.scale_x
    style.scaley = config.scale_y

    subs.styles["Title"] = style

    wrapped = wrap_title_text(
        text=title_text,
        font_size=config.font_size,
        scale_x=config.scale_x,
        video_width=video_width,
        margin_l=config.margin_l,
        margin_r=config.margin_r,
        max_width_percent=config.max_width_percent,
        letter_spacing=config.letter_spacing,
    )

    if config.line_spacing != 0 and r"\N" in wrapped:
        # Split into individual lines and position each with \pos
        lines = wrapped.split(r"\N")
        # Use 1.2x font size as approximate rendered line height (ASS convention)
        rendered_line_h = int(config.font_size * config.scale_y / 100 * 1.2)
        line_height = rendered_line_h + config.line_spacing
        margin_v = int(video_height * config.margin_v_percent / 100)

        align = config.alignment
        # Determine x anchor based on alignment
        if align in (1, 4, 7):
            x = config.margin_l
        elif align in (3, 6, 9):
            x = video_width - config.margin_r
        else:
            x = video_width // 2

        # Determine y start based on alignment
        total_block_height = rendered_line_h * len(lines) + config.line_spacing * (len(lines) - 1)
        if align in (7, 8, 9):
            y_start = margin_v
        elif align in (4, 5, 6):
            y_start = (video_height - total_block_height) // 2
        else:
            y_start = video_height - margin_v - total_block_height

        fade_tag = rf"{{\fad({config.fade_in_ms},{config.fade_out_ms})}}" if config.effect_type == "fade" else ""

        for i, line in enumerate(lines):
            y = y_start + i * line_height
            line_text = rf"{{\an{align}\pos({x},{y})}}{fade_tag}{line}"
            event = pysubs2.SSAEvent(
                start=0,
                end=duration_ms,
                text=line_text,
                style="Title",
            )
            subs.events.append(event)
    else:
        text = wrapped
        if config.effect_type == "fade":
            text = rf"{{\fad({config.fade_in_ms},{config.fade_out_ms})}}" + text

        event = pysubs2.SSAEvent(
            start=0,
            end=duration_ms,
            text=text,
            style="Title",
        )
        subs.events.append(event)

    subs.save(output_path, encoding="utf-8")
    return output_path
