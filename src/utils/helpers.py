import os
from datetime import datetime
from urllib.parse import urlparse


def get_timestamp() -> str:
    """Generate timestamp string in format YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_file_extension(url: str) -> str:
    """Extract file extension from URL"""
    parsed = urlparse(url)
    path = parsed.path
    _, ext = os.path.splitext(path)
    if ext:
        return ext.lower()
    return ".webp"


def generate_filename(timestamp: str, index: int, url: str) -> str:
    """Generate filename with timestamp and index"""
    ext = get_file_extension(url)
    return f"{timestamp}_{index:04d}{ext}"


def ensure_dir(path: str) -> None:
    """Ensure directory exists"""
    if not os.path.exists(path):
        os.makedirs(path)
