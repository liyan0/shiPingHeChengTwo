"""字幕关键词检测模块

用于检测SRT字幕文件中特定关键词出现的时间点
"""
import re
from typing import List, Tuple, Optional


def parse_srt_time(time_str: str) -> float:
    """将SRT时间格式转换为秒数

    Args:
        time_str: SRT时间格式，如 "00:01:23,456"

    Returns:
        float: 秒数
    """
    # 格式: HH:MM:SS,mmm
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
    if not match:
        return 0.0

    hours, minutes, seconds, milliseconds = match.groups()
    total_seconds = (
        int(hours) * 3600 +
        int(minutes) * 60 +
        int(seconds) +
        int(milliseconds) / 1000.0
    )
    return total_seconds


def detect_keyword_in_srt(
    srt_path: str,
    keyword: str,
    return_first: bool = True
) -> Optional[Tuple[float, float]]:
    """检测SRT字幕文件中关键词出现的时间点

    Args:
        srt_path: SRT字幕文件路径
        keyword: 要检测的关键词（如"橱窗"）
        return_first: 是否只返回第一次出现的时间，默认True

    Returns:
        Optional[Tuple[float, float]]: (开始时间, 结束时间)，单位秒
        如果未找到关键词，返回None
    """
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析SRT格式
        # 格式示例:
        # 1
        # 00:00:00,000 --> 00:00:02,500
        # 这是字幕文本

        pattern = r'(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})\s+(.+?)(?=\n\n|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)

        for index, start_time_str, end_time_str, text in matches:
            # 检查文本中是否包含关键词
            if keyword in text:
                start_time = parse_srt_time(start_time_str)
                end_time = parse_srt_time(end_time_str)

                if return_first:
                    return (start_time, end_time)

        return None

    except Exception as e:
        print(f"检测关键词时出错: {e}")
        return None


def detect_keywords_all_occurrences(
    srt_path: str,
    keyword: str
) -> List[Tuple[float, float]]:
    """检测SRT字幕文件中关键词所有出现的时间点

    Args:
        srt_path: SRT字幕文件路径
        keyword: 要检测的关键词

    Returns:
        List[Tuple[float, float]]: 所有出现的时间段列表 [(开始时间, 结束时间), ...]
    """
    results = []

    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        pattern = r'(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})\s+(.+?)(?=\n\n|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)

        for index, start_time_str, end_time_str, text in matches:
            if keyword in text:
                start_time = parse_srt_time(start_time_str)
                end_time = parse_srt_time(end_time_str)
                results.append((start_time, end_time))

    except Exception as e:
        print(f"检测关键词时出错: {e}")

    return results
