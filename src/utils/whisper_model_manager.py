import os
import shutil
from typing import Optional, Callable


class WhisperModelManager:
    MODELS_DIR: Optional[str] = None
    HF_BASE = "https://huggingface.co"
    HF_MIRROR = "https://hf-mirror.com"

    MODEL_INFO = {
        "small":    {"repo": "Systran/faster-whisper-small",    "size_hint": "~500 MB"},
        "medium":   {"repo": "Systran/faster-whisper-medium",   "size_hint": "~1.5 GB"},
        "large-v2": {"repo": "Systran/faster-whisper-large-v2", "size_hint": "~3 GB"},
        "large-v3": {"repo": "Systran/faster-whisper-large-v3", "size_hint": "~3 GB"},
    }

    @classmethod
    def init(cls, project_dir: str):
        cls.MODELS_DIR = os.path.join(project_dir, "models")

    @classmethod
    def get_models_dir(cls) -> str:
        return cls.MODELS_DIR or "models"

    @classmethod
    def get_model_dir(cls, model_name: str) -> str:
        return os.path.join(cls.get_models_dir(), f"faster-whisper-{model_name}")

    @classmethod
    def is_model_downloaded(cls, model_name: str) -> bool:
        d = cls.get_model_dir(model_name)
        return os.path.isdir(d) and os.path.isfile(os.path.join(d, "model.bin"))

    @classmethod
    def delete_model(cls, model_name: str) -> bool:
        d = cls.get_model_dir(model_name)
        if os.path.isdir(d):
            shutil.rmtree(d)
            return True
        return False

    @classmethod
    def _pick_base_url(cls, repo: str) -> Optional[str]:
        import requests
        for base in (cls.HF_BASE, cls.HF_MIRROR):
            try:
                url = f"{base}/{repo}"
                resp = requests.head(url, timeout=5, allow_redirects=True)
                if resp.status_code < 500:
                    return base
            except Exception:
                continue
        return None

    @classmethod
    def _list_repo_files(cls, base_url: str, repo: str) -> list:
        import requests
        api_url = f"{base_url}/api/models/{repo}"
        resp = requests.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        siblings = data.get("siblings", [])
        return [
            {"name": s["rfilename"], "size": s.get("size", 0)}
            for s in siblings
        ]

    @classmethod
    def download_model(
        cls,
        model_name: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> bool:
        import requests

        def _report(percent: int, message: str):
            if progress_callback:
                progress_callback(percent, message)

        info = cls.MODEL_INFO.get(model_name)
        if not info:
            _report(0, f"未知模型: {model_name}")
            return False

        repo = info["repo"]
        _report(0, f"正在检测下载源...")

        base_url = cls._pick_base_url(repo)
        if base_url is None:
            _report(0, "无法连接 HuggingFace 或镜像站，请检查网络")
            return False

        _report(2, f"使用下载源: {base_url}")

        try:
            files = cls._list_repo_files(base_url, repo)
        except Exception as e:
            _report(0, f"获取文件列表失败: {e}")
            return False

        if not files:
            _report(0, "文件列表为空")
            return False

        dest_dir = cls.get_model_dir(model_name)
        os.makedirs(dest_dir, exist_ok=True)

        total_size = sum(f["size"] for f in files if f["size"])
        downloaded_total = 0

        for file_info in files:
            fname = file_info["name"]
            fsize = file_info["size"]
            dest_path = os.path.join(dest_dir, fname)

            # Skip if already complete
            if fsize and os.path.isfile(dest_path) and os.path.getsize(dest_path) == fsize:
                downloaded_total += fsize
                if total_size > 0:
                    _report(int(downloaded_total / total_size * 100), f"跳过已存在: {fname}")
                continue

            file_url = f"{base_url}/{repo}/resolve/main/{fname}"
            success = cls._download_file(
                file_url, dest_path, fname, fsize,
                downloaded_total, total_size, base_url, repo, _report,
            )
            if not success:
                return False

            if fsize:
                downloaded_total += fsize
            elif os.path.isfile(dest_path):
                downloaded_total += os.path.getsize(dest_path)

        _report(100, "下载完成")
        return True

    @classmethod
    def _download_file(
        cls, url, dest_path, fname, fsize,
        downloaded_total, total_size, base_url, repo, _report,
    ) -> bool:
        import requests

        # Determine alternate base for retry
        alt_base = cls.HF_MIRROR if base_url == cls.HF_BASE else cls.HF_BASE

        for attempt, current_url in enumerate([url, f"{alt_base}/{repo}/resolve/main/{fname}"]):
            try:
                resp = requests.get(current_url, stream=True, timeout=60)
                resp.raise_for_status()

                file_total = int(resp.headers.get("content-length", fsize or 0))
                file_downloaded = 0

                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        file_downloaded += len(chunk)

                        if total_size > 0:
                            done = downloaded_total + file_downloaded
                            percent = min(99, int(done / total_size * 100))
                            mb = done / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            _report(percent, f"下载 {fname} ... {mb:.1f}/{total_mb:.1f} MB")

                return True

            except Exception as e:
                if attempt == 0:
                    _report(0, f"主源失败，切换镜像重试: {e}")
                    continue
                _report(0, f"下载失败 {fname}: {e}")
                return False

        return False
