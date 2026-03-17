import os
import shutil
import subprocess
import zipfile
import tempfile


FFMPEG_DOWNLOAD_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)


class FFmpegManager:
    BIN_DIR = None

    @classmethod
    def init(cls, project_dir: str):
        cls.BIN_DIR = os.path.join(project_dir, "bin")

    @classmethod
    def get_ffmpeg_path(cls) -> str:
        if cls.BIN_DIR:
            local = os.path.join(cls.BIN_DIR, "ffmpeg.exe")
            if os.path.isfile(local):
                return local
        found = shutil.which("ffmpeg")
        return found if found else "ffmpeg"

    @classmethod
    def get_ffprobe_path(cls) -> str:
        if cls.BIN_DIR:
            local = os.path.join(cls.BIN_DIR, "ffprobe.exe")
            if os.path.isfile(local):
                return local
        found = shutil.which("ffprobe")
        return found if found else "ffprobe"

    @classmethod
    def is_available(cls) -> bool:
        try:
            subprocess.run(
                [cls.get_ffmpeg_path(), "-version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except Exception:
            return False

    @classmethod
    def download(cls, progress_callback=None) -> bool:
        """Download ffmpeg-master-latest-win64-gpl.zip and extract ffmpeg.exe/ffprobe.exe to BIN_DIR.

        progress_callback(percent: int, message: str)
        """
        import requests

        if cls.BIN_DIR is None:
            return False

        os.makedirs(cls.BIN_DIR, exist_ok=True)

        def _report(percent: int, message: str):
            if progress_callback:
                progress_callback(percent, message)

        _report(0, "开始下载 FFmpeg...")

        try:
            response = requests.get(
                FFMPEG_DOWNLOAD_URL,
                stream=True,
                timeout=60,
            )
            response.raise_for_status()

            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp_path = tmp.name
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    tmp.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        percent = int(downloaded / total * 80)
                        mb = downloaded / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        _report(percent, f"下载中... {mb:.1f} / {total_mb:.1f} MB")

        except Exception as e:
            _report(0, f"下载失败: {str(e)}")
            return False

        _report(80, "解压中...")

        try:
            with zipfile.ZipFile(tmp_path, "r") as zf:
                # Find ffmpeg.exe and ffprobe.exe inside the zip (they're in a bin/ subfolder)
                for member in zf.namelist():
                    basename = os.path.basename(member)
                    if basename in ("ffmpeg.exe", "ffprobe.exe"):
                        dest = os.path.join(cls.BIN_DIR, basename)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
        except Exception as e:
            _report(0, f"解压失败: {str(e)}")
            return False
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        ffmpeg_ok = os.path.isfile(os.path.join(cls.BIN_DIR, "ffmpeg.exe"))
        ffprobe_ok = os.path.isfile(os.path.join(cls.BIN_DIR, "ffprobe.exe"))

        if ffmpeg_ok and ffprobe_ok:
            _report(100, "安装完成")
            return True

        _report(0, "安装失败：未找到 ffmpeg.exe 或 ffprobe.exe")
        return False
