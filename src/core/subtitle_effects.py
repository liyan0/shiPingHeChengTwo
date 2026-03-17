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


# 中文字体名到英文字体名的映射
FONT_NAME_MAP = {
    "微软雅黑": "Microsoft YaHei",
    "黑体": "SimHei",
    "宋体": "SimSun",
    "新宋体": "NSimSun",
    "楷体": "KaiTi",
    "仿宋": "FangSong",
    "华文细黑": "STXihei",
    "华文黑体": "STHeiti",
    "华文楷体": "STKaiti",
    "华文宋体": "STSong",
    "华文仿宋": "STFangsong",
    "华文中宋": "STZhongsong",
    "华文彩云": "STCaiyun",
    "华文琥珀": "STHupo",
    "华文隶书": "STLiti",
    "华文行楷": "STXingkai",
    "华文新魏": "STXinwei",
    "幼圆": "YouYuan",
    "隶书": "LiSu",
    "思源黑体": "Source Han Sans CN",
    "思源宋体": "Source Han Serif CN",
    "苹方": "PingFang SC",
    "方正黑体": "FZHei-B01",
    "方正书宋": "FZShuSong-Z01",
    "方正仿宋": "FZFangSong-Z02",
    "方正楷体": "FZKai-Z03",
    "方正舒体": "FZShuTi",
    "方正姚体": "FZYaoti",
}

WINDOWS_FONT_FILE_MAP = {
    "Microsoft YaHei": "msyh.ttc",
    "SimHei": "simhei.ttf",
    "SimSun": "simsun.ttc",
    "NSimSun": "simsun.ttc",
    "KaiTi": "simkai.ttf",
    "FangSong": "simfang.ttf",
    "STXihei": "STXIHEI.TTF",
    "STKaiti": "STKAITI.TTF",
    "STSong": "STSONG.TTF",
    "STFangsong": "STFANGSO.TTF",
    "STXingkai": "STXINGKA.TTF",
    "Source Han Sans CN": "SourceHanSansCN-Regular.otf",
    "Source Han Serif CN": "SourceHanSerifCN-Regular.otf",
    "PingFang SC": "PingFang.ttc",
}

FONT_FALLBACK_MAP = {
    "STXingkai": "KaiTi",
    "STKaiti": "KaiTi",
    "STSong": "SimSun",
    "STFangsong": "FangSong",
    "STXihei": "SimHei",
    "Source Han Sans CN": "Microsoft YaHei",
    "Source Han Serif CN": "SimSun",
    "PingFang SC": "Microsoft YaHei",
}


def _font_exists_on_windows(font_name: str) -> bool:
    if os.name != "nt":
        return True
    file_name = WINDOWS_FONT_FILE_MAP.get(font_name)
    if not file_name:
        return True
    windir = os.environ.get("WINDIR", "C:/Windows")
    return os.path.exists(os.path.join(windir, "Fonts", file_name))


def normalize_font_name(font_name: str) -> str:
    """将中文字体名转换为英文字体名，以确保ASS字幕正确渲染。"""
    normalized = FONT_NAME_MAP.get(font_name, font_name)
    fallback = FONT_FALLBACK_MAP.get(normalized)
    if fallback and not _font_exists_on_windows(normalized):
        return fallback
    return normalized


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
    style.fontname = normalize_font_name(config.font_name)
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
    # Prefer per-event \fsp tags for better compatibility with some ffmpeg/libass builds.
    style.spacing = 0
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
    max_chars_per_line: int = 8,
) -> str:
    """Insert ``\\N`` hard line breaks so that no line exceeds *available_width* or *max_chars_per_line*.

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

        # --- Need to wrap? (check both width and character count) ---
        needs_wrap = (new_width > available_width or char_on_line >= max_chars_per_line) and char_on_line > 0

        if needs_wrap:
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
                event.text, available_width_px, rendered_font_size, rendered_spacing, max_chars_per_line=8
            )

    if config.effect_type == "fade":
        _apply_fade_effect(subs, config.fade_in_ms, config.fade_out_ms)
    elif config.effect_type == "karaoke":
        _apply_karaoke_effect(subs, config.karaoke_highlight_color)

    if output_path is None:
        base, _ = os.path.splitext(srt_path)
        output_path = base + ".ass"

    # Enforce letter spacing via per-event ASS override tag for better
    # compatibility across ffmpeg/libass builds.
    if abs(config.letter_spacing) > 1e-6:
        spacing_tag = rf"{{\fsp{config.letter_spacing:g}}}"
        for event in subs.events:
            if not event.text:
                continue
            # Keep existing leading override tags; inject \fsp after all of them.
            if event.text.startswith("{"):
                idx = 0
                while idx < len(event.text) and event.text[idx] == "{":
                    end = event.text.find("}", idx)
                    if end == -1:
                        break
                    idx = end + 1
                head = event.text[:idx]
                tail = event.text[idx:]
                if r"\fsp" in head:
                    event.text = head + tail
                else:
                    event.text = head + spacing_tag + tail
            else:
                event.text = spacing_tag + event.text

    subs.save(output_path, encoding="utf-8")
    return output_path


def convert_srt_to_ass_with_delay(
    srt_path: str,
    config: SubtitleStyleConfig,
    video_height: int,
    video_width: int = 0,
    delay_seconds: float = 0.0,
    output_path: Optional[str] = None,
) -> str:
    """Convert an SRT file to ASS with styles, effects, and time delay.

    Args:
        srt_path: Path to the source SRT file.
        config: Subtitle style configuration.
        video_height: Video height in pixels.
        video_width: Video width in pixels.
        delay_seconds: Time delay in seconds to add to all subtitle timestamps.
        output_path: Optional output path; defaults to same dir with .ass extension.

    Returns:
        Absolute path to the generated ASS file.
    """
    subs = pysubs2.load(srt_path, encoding="utf-8")

    style = build_ass_style(config, video_height)
    subs.styles["Default"] = style

    # --- Apply time delay to all events ---
    delay_ms = int(delay_seconds * 1000)
    for event in subs.events:
        event.start += delay_ms
        event.end += delay_ms

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
                event.text, available_width_px, rendered_font_size, rendered_spacing, max_chars_per_line=8
            )

    if config.effect_type == "fade":
        _apply_fade_effect(subs, config.fade_in_ms, config.fade_out_ms)
    elif config.effect_type == "karaoke":
        _apply_karaoke_effect(subs, config.karaoke_highlight_color)

    if output_path is None:
        base, _ = os.path.splitext(srt_path)
        output_path = base + "_delayed.ass"

    # Enforce letter spacing via per-event ASS override tag for better
    # compatibility across ffmpeg/libass builds.
    if abs(config.letter_spacing) > 1e-6:
        spacing_tag = rf"{{\fsp{config.letter_spacing:g}}}"
        for event in subs.events:
            if not event.text:
                continue
            # Keep existing leading override tags; inject \fsp after all of them.
            if event.text.startswith("{"):
                idx = 0
                while idx < len(event.text) and event.text[idx] == "{":
                    end = event.text.find("}", idx)
                    if end == -1:
                        break
                    idx = end + 1
                head = event.text[:idx]
                tail = event.text[idx:]
                if r"\fsp" in head:
                    event.text = head + tail
                else:
                    event.text = head + spacing_tag + tail
            else:
                event.text = spacing_tag + event.text

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
    visual_padding: float = 0.0,
) -> str:
    """Insert \\N hard line breaks so the title fits within max_width_percent of video width.

    Punctuation marks are replaced with line breaks and removed from display.
    Falls back to breaking before the character that would overflow.
    """
    PUNCTUATION = set("。，！？、；：…—,.!?;:")
    MAX_CHARS_PER_LINE = 6  # 改成6个字

    # 先按标点切段，并去掉标点本身
    segments = []
    current_segment = []
    for ch in text:
        if ch in PUNCTUATION:
            if current_segment:
                segments.append("".join(current_segment))
                current_segment = []
        else:
            current_segment.append(ch)
    if current_segment:
        segments.append("".join(current_segment))
    if not segments:
        return ""

    # 新策略：找到第一个超过限制的段，从它的前一段开始把所有剩余文字连起来按固定长度切分
    wrapped_lines = []
    found_long_index = -1

    # 先找到第一个超过限制的段的位置
    for i, seg in enumerate(segments):
        if len(seg) > MAX_CHARS_PER_LINE:
            found_long_index = i
            break

    if found_long_index >= 0:
        # 找到了长段，保留长段之前的所有段，从长段开始连起来切分
        if found_long_index > 0:
            # 有前面的段，保留它们，从长段开始连起来切
            wrapped_lines = segments[:found_long_index]
            remaining_text = segments[found_long_index:]
        else:
            # 第一段就超过了，全部连起来切
            remaining_text = segments

        # 把剩余文字连起来按固定长度切分
        all_remaining = "".join(remaining_text)
        for i in range(0, len(all_remaining), MAX_CHARS_PER_LINE):
            wrapped_lines.append(all_remaining[i:i + MAX_CHARS_PER_LINE])
    else:
        # 没有找到长段，直接按标点换行
        wrapped_lines = segments

    return r"\N".join(wrapped_lines)


def generate_title_ass(
    title_text: str,
    config: TitleStyleConfig,
    video_height: int,
    video_width: int,
    duration_ms: int,
    output_path: str,
) -> str:
    """Generate an ASS file with a single full-duration title event.

    Supports fancy text effects: double outline, glow.
    Note: True gradient colors require video filter; ASS uses solid colors.

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

    # 主标题样式
    style = SSAStyle()
    style.fontname = normalize_font_name(config.font_name)
    style.fontsize = config.font_size
    # 如果启用渐变，使用渐变的第一个颜色作为主色（ASS不支持真正渐变）
    if getattr(config, 'use_gradient', False):
        style.primarycolor = hex_to_ass_color(getattr(config, 'gradient_color1', '#FFD700'))
    else:
        style.primarycolor = hex_to_ass_color(config.primary_color)
    style.outlinecolor = hex_to_ass_color(config.outline_color)
    style.outline = config.outline_width
    style.marginv = margin_v
    style.bold = config.bold
    style.italic = config.italic
    style.shadow = config.shadow_depth
    style.borderstyle = config.border_style
    style.backcolor = hex_to_ass_color(config.back_color, config.back_color_alpha)
    style.spacing = 0
    style.alignment = config.alignment
    style.marginl = config.margin_l
    style.marginr = config.margin_r
    style.scalex = config.scale_x
    style.scaley = config.scale_y

    subs.styles["Title"] = style

    # 外层描边样式（双层描边效果）
    use_outer_outline = getattr(config, 'use_outer_outline', False)
    if use_outer_outline:
        outer_style = SSAStyle()
        outer_style.fontname = normalize_font_name(config.font_name)
        outer_style.fontsize = config.font_size
        outer_style.primarycolor = hex_to_ass_color(getattr(config, 'outer_outline_color', '#000000'))
        outer_style.outlinecolor = hex_to_ass_color(getattr(config, 'outer_outline_color', '#000000'))
        outer_style.outline = config.outline_width + getattr(config, 'outer_outline_width', 4)
        outer_style.marginv = margin_v
        outer_style.bold = config.bold
        outer_style.italic = config.italic
        outer_style.shadow = 0
        outer_style.borderstyle = 1
        outer_style.backcolor = hex_to_ass_color('#000000', 255)
        outer_style.spacing = 0
        outer_style.alignment = config.alignment
        outer_style.marginl = config.margin_l
        outer_style.marginr = config.margin_r
        outer_style.scalex = config.scale_x
        outer_style.scaley = config.scale_y
        subs.styles["TitleOuter"] = outer_style

    # 发光样式
    use_glow = getattr(config, 'use_glow', False)
    if use_glow:
        glow_style = SSAStyle()
        glow_style.fontname = normalize_font_name(config.font_name)
        glow_style.fontsize = config.font_size
        glow_color = getattr(config, 'glow_color', '#FFFFFF')
        glow_style.primarycolor = hex_to_ass_color(glow_color, 128)  # 半透明
        glow_style.outlinecolor = hex_to_ass_color(glow_color, 64)
        glow_strength = getattr(config, 'glow_strength', 10)
        glow_style.outline = glow_strength
        glow_style.marginv = margin_v
        glow_style.bold = config.bold
        glow_style.italic = config.italic
        glow_style.shadow = 0
        glow_style.borderstyle = 1
        glow_style.backcolor = hex_to_ass_color('#000000', 255)
        glow_style.spacing = 0
        glow_style.alignment = config.alignment
        glow_style.marginl = config.margin_l
        glow_style.marginr = config.margin_r
        glow_style.scalex = config.scale_x
        glow_style.scaley = config.scale_y
        subs.styles["TitleGlow"] = glow_style

    wrapped = wrap_title_text(
        text=title_text,
        font_size=config.font_size,
        scale_x=config.scale_x,
        video_width=video_width,
        margin_l=config.margin_l,
        margin_r=config.margin_r,
        max_width_percent=config.max_width_percent,
        letter_spacing=config.letter_spacing,
        visual_padding=(
            config.outline_width
            + (getattr(config, 'outer_outline_width', 0) if use_outer_outline else 0)
            + (getattr(config, 'glow_strength', 0) if use_glow else 0)
            + max(config.shadow_depth, 0)
            + 6
        ),
    )

    # 计算标题结束时间
    display_duration = getattr(config, 'display_duration', 0.0)
    if display_duration > 0:
        title_end_ms = int(display_duration * 1000)
        title_end_ms = min(title_end_ms, duration_ms)
    else:
        title_end_ms = duration_ms

    fade_tag = rf"{{\fad({config.fade_in_ms},{config.fade_out_ms})}}" if config.effect_type == "fade" else ""
    spacing_tag = rf"{{\fsp{config.letter_spacing:g}}}" if abs(config.letter_spacing) > 1e-6 else ""

    if config.line_spacing != 0 and r"\N" in wrapped:
        # Split into individual lines and position each with \pos
        lines = wrapped.split(r"\N")
        rendered_line_h = int(config.font_size * config.scale_y / 100 * 1.2)
        line_height = rendered_line_h + config.line_spacing
        margin_v = int(video_height * config.margin_v_percent / 100)

        align = config.alignment
        if align in (1, 4, 7):
            x = config.margin_l
        elif align in (3, 6, 9):
            x = video_width - config.margin_r
        else:
            x = video_width // 2

        total_block_height = rendered_line_h * len(lines) + config.line_spacing * (len(lines) - 1)
        if align in (7, 8, 9):
            y_start = margin_v
        elif align in (4, 5, 6):
            y_start = (video_height - total_block_height) // 2
        else:
            y_start = video_height - margin_v - total_block_height

        for i, line in enumerate(lines):
            y = y_start + i * line_height
            pos_tag = rf"{{\an{align}\pos({x},{y})}}"

            # 发光层（最底层）
            if use_glow:
                glow_text = f"{pos_tag}{fade_tag}{spacing_tag}{line}"
                event = pysubs2.SSAEvent(start=0, end=title_end_ms, text=glow_text, style="TitleGlow")
                subs.events.append(event)

            # 外层描边（中间层）
            if use_outer_outline:
                outer_text = f"{pos_tag}{fade_tag}{spacing_tag}{line}"
                event = pysubs2.SSAEvent(start=0, end=title_end_ms, text=outer_text, style="TitleOuter")
                subs.events.append(event)

            # 主标题（最上层）
            line_text = f"{pos_tag}{fade_tag}{spacing_tag}{line}"
            event = pysubs2.SSAEvent(start=0, end=title_end_ms, text=line_text, style="Title")
            subs.events.append(event)
    else:
        text = f"{spacing_tag}{wrapped}" if spacing_tag else wrapped

        # 发光层（最底层）
        if use_glow:
            glow_text = fade_tag + text if fade_tag else text
            event = pysubs2.SSAEvent(start=0, end=title_end_ms, text=glow_text, style="TitleGlow")
            subs.events.append(event)

        # 外层描边（中间层）
        if use_outer_outline:
            outer_text = fade_tag + text if fade_tag else text
            event = pysubs2.SSAEvent(start=0, end=title_end_ms, text=outer_text, style="TitleOuter")
            subs.events.append(event)

        # 主标题（最上层）
        if fade_tag:
            text = fade_tag + text
        event = pysubs2.SSAEvent(start=0, end=title_end_ms, text=text, style="Title")
        subs.events.append(event)

    subs.save(output_path, encoding="utf-8")
    return output_path
