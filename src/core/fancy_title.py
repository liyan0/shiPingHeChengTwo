"""花字标题图片生成模块

使用PIL生成带渐变、描边、发光效果的花字标题图片，
可叠加到视频上实现类似剪映的花字效果。
"""

import os
import tempfile
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from ..models.config import TitleStyleConfig


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """将十六进制颜色转换为RGB元组"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """将十六进制颜色转换为RGBA元组"""
    r, g, b = hex_to_rgb(hex_color)
    return (r, g, b, alpha)


def get_font(font_name: str, font_size: int) -> ImageFont.FreeTypeFont:
    """获取字体，支持中文字体名称映射"""
    # 常用中文字体路径映射
    font_paths = {
        "Source Han Sans CN": "C:/Windows/Fonts/SourceHanSansCN-Regular.otf",
        "Microsoft YaHei": "C:/Windows/Fonts/msyh.ttc",
        "SimHei": "C:/Windows/Fonts/simhei.ttf",
        "SimSun": "C:/Windows/Fonts/simsun.ttc",
        "KaiTi": "C:/Windows/Fonts/simkai.ttf",
        "FangSong": "C:/Windows/Fonts/simfang.ttf",
        "STXihei": "C:/Windows/Fonts/STXIHEI.TTF",
        "STKaiti": "C:/Windows/Fonts/STKAITI.TTF",
        "STSong": "C:/Windows/Fonts/STSONG.TTF",
        "STFangsong": "C:/Windows/Fonts/STFANGSO.TTF",
        "LiSu": "C:/Windows/Fonts/SIMLI.TTF",
        "YouYuan": "C:/Windows/Fonts/SIMYOU.TTF",
    }

    # 尝试直接使用字体名
    try:
        return ImageFont.truetype(font_name, font_size)
    except (OSError, IOError):
        pass

    # 尝试映射路径
    if font_name in font_paths:
        try:
            return ImageFont.truetype(font_paths[font_name], font_size)
        except (OSError, IOError):
            pass

    # 尝试Windows字体目录
    for ext in ['.ttf', '.ttc', '.otf']:
        try:
            path = f"C:/Windows/Fonts/{font_name}{ext}"
            return ImageFont.truetype(path, font_size)
        except (OSError, IOError):
            pass

    # 回退到微软雅黑
    try:
        return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", font_size)
    except (OSError, IOError):
        return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """将文本按最大宽度换行，标点符号处优先换行"""
    PUNCTUATION = set("。，！？、；：…—,.!?;:")

    # 先按标点分割
    segments = []
    current = []
    for ch in text:
        if ch in PUNCTUATION:
            if current:
                segments.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        segments.append("".join(current))

    # 如果标点分割后有多段，检查每段是否需要再换行
    lines = []
    for segment in segments:
        # 检查这一段是否超宽
        try:
            bbox = font.getbbox(segment)
            seg_width = bbox[2] - bbox[0]
        except AttributeError:
            seg_width = font.getsize(segment)[0]

        if seg_width <= max_width:
            lines.append(segment)
        else:
            # 需要按字符换行
            current_line = ""
            for ch in segment:
                test_line = current_line + ch
                try:
                    bbox = font.getbbox(test_line)
                    test_width = bbox[2] - bbox[0]
                except AttributeError:
                    test_width = font.getsize(test_line)[0]

                if test_width <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = ch
            if current_line:
                lines.append(current_line)

    return lines if lines else [text]


def create_gradient_text_image(
    text: str,
    font: ImageFont.FreeTypeFont,
    color1: str,
    color2: str,
    direction: str = "vertical",
) -> Image.Image:
    """创建渐变色文字图片"""
    # 获取文字尺寸
    try:
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        offset_x = -bbox[0]
        offset_y = -bbox[1]
    except AttributeError:
        text_width, text_height = font.getsize(text)
        offset_x, offset_y = 0, 0

    # 创建文字蒙版
    mask = Image.new('L', (text_width + 20, text_height + 20), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.text((10 + offset_x, 10 + offset_y), text, font=font, fill=255)

    # 创建渐变背景
    gradient = Image.new('RGBA', mask.size, (0, 0, 0, 0))
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)

    for y in range(gradient.height):
        if direction == "vertical":
            ratio = y / gradient.height
        else:
            ratio = 0.5  # 水平渐变暂时用中间色

        r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * ratio)
        g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * ratio)
        b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * ratio)

        for x in range(gradient.width):
            if direction == "horizontal":
                ratio = x / gradient.width
                r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * ratio)
                g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * ratio)
                b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * ratio)
            gradient.putpixel((x, y), (r, g, b, 255))

    # 应用蒙版
    result = Image.new('RGBA', mask.size, (0, 0, 0, 0))
    result.paste(gradient, mask=mask)

    return result


def draw_text_with_outline(
    img: Image.Image,
    text: str,
    position: Tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill_color: str,
    outline_color: str,
    outline_width: int,
) -> None:
    """绘制带描边的文字"""
    draw = ImageDraw.Draw(img)
    x, y = position

    # 绘制描边（8个方向）
    if outline_width > 0:
        outline_rgb = hex_to_rgba(outline_color)
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=outline_rgb)

    # 绘制主文字
    fill_rgb = hex_to_rgba(fill_color)
    draw.text((x, y), text, font=font, fill=fill_rgb)


def generate_fancy_title_image(
    title_text: str,
    config: TitleStyleConfig,
    video_width: int,
    video_height: int,
    output_path: Optional[str] = None,
) -> str:
    """生成花字标题PNG图片

    Args:
        title_text: 标题文字
        config: 标题样式配置
        video_width: 视频宽度
        video_height: 视频高度
        output_path: 输出路径，默认生成临时文件

    Returns:
        生成的PNG图片路径
    """
    # 创建透明画布
    canvas = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))

    # 获取字体
    font = get_font(config.font_name, config.font_size)

    # 计算最大宽度并换行
    max_width = int(video_width * config.max_width_percent / 100 - config.margin_l - config.margin_r)
    lines = wrap_text(title_text, font, max_width)

    # 计算每行尺寸
    line_heights = []
    line_widths = []
    for line in lines:
        try:
            bbox = font.getbbox(line)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except AttributeError:
            w, h = font.getsize(line)
        line_widths.append(w)
        line_heights.append(h)

    # 计算总高度（含行间距）
    line_spacing = config.line_spacing if config.line_spacing > 0 else int(config.font_size * 0.3)
    total_height = sum(line_heights) + line_spacing * (len(lines) - 1)
    max_line_width = max(line_widths) if line_widths else 0

    # 根据对齐方式计算起始位置
    align = config.alignment
    margin_v = int(video_height * config.margin_v_percent / 100)

    # 垂直位置
    if align in (7, 8, 9):  # 顶部
        start_y = margin_v
    elif align in (4, 5, 6):  # 中部
        start_y = (video_height - total_height) // 2
    else:  # 底部
        start_y = video_height - margin_v - total_height

    # 获取花字效果参数
    use_gradient = getattr(config, 'use_gradient', False)
    gradient_color1 = getattr(config, 'gradient_color1', '#FFD700')
    gradient_color2 = getattr(config, 'gradient_color2', '#FFA500')
    use_outer_outline = getattr(config, 'use_outer_outline', False)
    outer_outline_color = getattr(config, 'outer_outline_color', '#000000')
    outer_outline_width = getattr(config, 'outer_outline_width', 4)
    use_glow = getattr(config, 'use_glow', False)
    glow_color = getattr(config, 'glow_color', '#FFFFFF')
    glow_strength = getattr(config, 'glow_strength', 10)

    # 逐行绘制
    current_y = start_y
    for i, line in enumerate(lines):
        line_width = line_widths[i]
        line_height = line_heights[i]

        # 水平位置
        if align in (1, 4, 7):  # 左对齐
            x = config.margin_l
        elif align in (3, 6, 9):  # 右对齐
            x = video_width - config.margin_r - line_width
        else:  # 居中
            x = (video_width - line_width) // 2

        # 1. 绘制发光层（使用高斯模糊，避免重影）
        if use_glow:
            glow_layer = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_layer)
            # 只绘制一次文字，然后用高斯模糊扩散
            glow_rgba = hex_to_rgba(glow_color, 200)
            glow_draw.text((x, current_y), line, font=font, fill=glow_rgba)
            # 多次模糊来创建柔和的发光效果
            blur_radius = max(3, glow_strength // 3)
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            canvas = Image.alpha_composite(canvas, glow_layer)

        # 2. 绘制外层描边
        if use_outer_outline:
            outer_layer = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
            outer_draw = ImageDraw.Draw(outer_layer)
            outer_rgba = hex_to_rgba(outer_outline_color)
            total_outline = config.outline_width + outer_outline_width
            for dx in range(-total_outline, total_outline + 1):
                for dy in range(-total_outline, total_outline + 1):
                    if dx * dx + dy * dy <= total_outline * total_outline:
                        outer_draw.text((x + dx, current_y + dy), line, font=font, fill=outer_rgba)
            canvas = Image.alpha_composite(canvas, outer_layer)

        # 3. 绘制内层描边
        if config.outline_width > 0:
            outline_layer = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
            outline_draw = ImageDraw.Draw(outline_layer)
            outline_rgba = hex_to_rgba(config.outline_color)
            for dx in range(-config.outline_width, config.outline_width + 1):
                for dy in range(-config.outline_width, config.outline_width + 1):
                    if dx != 0 or dy != 0:
                        outline_draw.text((x + dx, current_y + dy), line, font=font, fill=outline_rgba)
            canvas = Image.alpha_composite(canvas, outline_layer)

        # 4. 绘制主文字（支持渐变）
        if use_gradient:
            gradient_text = create_gradient_text_image(
                line, font, gradient_color1, gradient_color2, "vertical"
            )
            # 计算粘贴位置
            canvas.paste(gradient_text, (x - 10, current_y - 10), gradient_text)
        else:
            text_layer = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_layer)
            text_rgba = hex_to_rgba(config.primary_color)
            text_draw.text((x, current_y), line, font=font, fill=text_rgba)
            canvas = Image.alpha_composite(canvas, text_layer)

        current_y += line_height + line_spacing

    # 保存图片
    if output_path is None:
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"fancy_title_{os.getpid()}.png"
        )

    canvas.save(output_path, 'PNG')
    return output_path


def generate_fancy_title_for_ffmpeg(
    title_text: str,
    config: TitleStyleConfig,
    video_width: int,
    video_height: int,
    duration: float,
    output_dir: str,
) -> Tuple[str, str]:
    """生成花字标题图片并返回FFmpeg overlay滤镜参数

    Args:
        title_text: 标题文字
        config: 标题样式配置
        video_width: 视频宽度
        video_height: 视频高度
        duration: 显示时长（秒），0表示全程显示
        output_dir: 输出目录

    Returns:
        (图片路径, FFmpeg滤镜字符串)
    """
    # 生成图片
    img_path = os.path.join(output_dir, f"title_{os.getpid()}.png")
    generate_fancy_title_image(title_text, config, video_width, video_height, img_path)

    # 构建FFmpeg滤镜
    # 淡入淡出效果
    fade_in = config.fade_in_ms / 1000.0 if config.effect_type == "fade" else 0
    fade_out = config.fade_out_ms / 1000.0 if config.effect_type == "fade" else 0

    display_duration = getattr(config, 'display_duration', 0.0)
    if display_duration > 0:
        end_time = display_duration
    else:
        end_time = duration

    if fade_in > 0 or fade_out > 0:
        filter_str = (
            f"[title_in]format=rgba,"
            f"fade=t=in:st=0:d={fade_in}:alpha=1,"
            f"fade=t=out:st={end_time - fade_out}:d={fade_out}:alpha=1[title_faded]"
        )
    else:
        filter_str = "[title_in]format=rgba[title_faded]"

    return img_path, filter_str
