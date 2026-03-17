"""橱窗素材叠加处理模块

用于在视频中叠加橱窗图片或视频素材
"""
import os
import random
from typing import Optional, Tuple, List


def get_chuchuang_materials(material_dir: str) -> List[str]:
    """获取橱窗素材列表（图片和视频）

    Args:
        material_dir: 橱窗素材根目录

    Returns:
        素材文件路径列表
    """
    materials = []

    # 图片素材
    image_dir = os.path.join(material_dir, "图片")
    if os.path.exists(image_dir):
        for f in os.listdir(image_dir):
            if os.path.splitext(f)[1].lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
                materials.append(os.path.join(image_dir, f))

    # 视频素材
    video_dir = os.path.join(material_dir, "视频")
    if os.path.exists(video_dir):
        for f in os.listdir(video_dir):
            if os.path.splitext(f)[1].lower() in {'.mp4', '.avi', '.mov', '.mkv'}:
                materials.append(os.path.join(video_dir, f))

    return materials


def select_random_material(material_dir: str, material_type: str = "图片") -> Optional[str]:
    """随机选择一个橱窗素材

    Args:
        material_dir: 橱窗素材根目录
        material_type: 素材类型，"图片" 或 "视频"

    Returns:
        选中的素材路径，如果没有素材则返回None
    """
    materials = get_chuchuang_materials(material_dir)
    if not materials:
        return None

    # 根据类型过滤素材
    if material_type == "图片":
        filtered = [m for m in materials if is_image_file(m)]
    elif material_type == "视频":
        filtered = [m for m in materials if is_video_file(m)]
    else:
        filtered = materials

    if not filtered:
        return None

    return random.choice(filtered)


def is_image_file(file_path: str) -> bool:
    """判断文件是否为图片"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def is_video_file(file_path: str) -> bool:
    """判断文件是否为视频"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in {'.mp4', '.avi', '.mov', '.mkv'}
