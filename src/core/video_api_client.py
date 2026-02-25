import aiohttp
import asyncio
import os
from dataclasses import dataclass
from typing import Optional


def get_content_type(filename: str) -> str:
    """Get content type based on file extension"""
    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return content_types.get(ext, "image/jpeg")


@dataclass
class VideoSubmitResult:
    success: bool
    task_id: str = ""
    error: str = ""
    status_code: int = 0


@dataclass
class VideoQueryResult:
    success: bool
    status: str = ""
    progress: int = 0
    video_url: str = ""
    error: str = ""


class VideoAPIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "veo_3_1",
        seconds: str = "8",
        size: str = "16x9",
        watermark: str = "false",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.seconds = seconds
        self.size = size
        self.watermark = watermark

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

    def _get_query_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def submit_video(
        self,
        prompt: str,
        image_path: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> VideoSubmitResult:
        """Submit video generation task with image (multipart/form-data)"""
        close_session = False
        if session is None:
            session = aiohttp.ClientSession()
            close_session = True

        try:
            url = f"{self.base_url}/v1/videos"

            data = aiohttp.FormData()
            data.add_field("model", self.model)
            data.add_field("prompt", prompt)
            data.add_field("seconds", self.seconds)
            data.add_field("size", self.size)
            data.add_field("watermark", self.watermark)

            with open(image_path, "rb") as f:
                file_content = f.read()
                filename = os.path.basename(image_path)
                content_type = get_content_type(filename)
                data.add_field(
                    "input_reference",
                    file_content,
                    filename=filename,
                    content_type=content_type,
                )

            async with session.post(
                url,
                data=data,
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                status_code = response.status
                resp_data = await response.json()

                # Debug log
                import json
                print(f"[DEBUG] Video API Submit Response: {json.dumps(resp_data, ensure_ascii=False, indent=2)}")

                if status_code == 200 or status_code == 201:
                    task_id = resp_data.get("id", "")
                    return VideoSubmitResult(
                        success=True,
                        task_id=task_id,
                        status_code=status_code,
                    )
                else:
                    error_msg = resp_data.get("error", {}).get(
                        "message", f"HTTP {status_code}"
                    )
                    if isinstance(resp_data.get("error"), str):
                        error_msg = resp_data.get("error")

                    return VideoSubmitResult(
                        success=False,
                        error=error_msg,
                        status_code=status_code,
                    )

        except asyncio.TimeoutError:
            return VideoSubmitResult(
                success=False,
                error="请求超时",
                status_code=0,
            )
        except aiohttp.ClientError as e:
            return VideoSubmitResult(
                success=False,
                error=f"网络错误: {str(e)}",
                status_code=0,
            )
        except Exception as e:
            return VideoSubmitResult(
                success=False,
                error=f"未知错误: {str(e)}",
                status_code=0,
            )
        finally:
            if close_session:
                await session.close()

    async def query_status(
        self,
        task_id: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> VideoQueryResult:
        """Query video generation task status"""
        close_session = False
        if session is None:
            session = aiohttp.ClientSession()
            close_session = True

        try:
            url = f"{self.base_url}/v1/videos/{task_id}"

            async with session.get(
                url,
                headers=self._get_query_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                data = await response.json()

                # Debug log
                import json
                print(f"[DEBUG] Video API Query Response: {json.dumps(data, ensure_ascii=False, indent=2)}")

                if response.status == 200:
                    status = data.get("status", "pending")
                    progress = data.get("progress", 0)
                    video_url = data.get("video_url", "") or data.get("url", "")

                    return VideoQueryResult(
                        success=True,
                        status=status,
                        progress=progress,
                        video_url=video_url,
                    )
                else:
                    error_msg = data.get("error", {}).get(
                        "message", f"HTTP {response.status}"
                    )
                    if isinstance(data.get("error"), str):
                        error_msg = data.get("error")

                    return VideoQueryResult(
                        success=False,
                        error=error_msg,
                    )

        except asyncio.TimeoutError:
            return VideoQueryResult(
                success=False,
                error="查询超时",
            )
        except aiohttp.ClientError as e:
            return VideoQueryResult(
                success=False,
                error=f"网络错误: {str(e)}",
            )
        except Exception as e:
            return VideoQueryResult(
                success=False,
                error=f"未知错误: {str(e)}",
            )
        finally:
            if close_session:
                await session.close()

    @staticmethod
    def is_retryable_error(status_code: int) -> bool:
        """Check if error is retryable"""
        return status_code in (0, 429, 500, 502, 503, 504)
