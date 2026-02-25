import base64
import mimetypes
import ssl
from dataclasses import dataclass
from typing import List

import aiohttp


@dataclass
class ImageRecognitionResult:
    success: bool
    content: str = ""
    error: str = ""
    status_code: int = 0


class ImageRecognitionAPIClient:
    def __init__(self, base_url: str, api_key: str, model: str = "gemini-2.0-flash"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _get_ssl_context(self) -> ssl.SSLContext:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    def _get_mime_type(self, file_path: str) -> str:
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            if file_path.lower().endswith(".jpg") or file_path.lower().endswith(".jpeg"):
                return "image/jpeg"
            elif file_path.lower().endswith(".png"):
                return "image/png"
            elif file_path.lower().endswith(".webp"):
                return "image/webp"
            elif file_path.lower().endswith(".gif"):
                return "image/gif"
            return "image/jpeg"
        return mime_type

    def _encode_image(self, file_path: str) -> tuple[str, str]:
        """Read and encode image to base64, return (base64_data, mime_type)"""
        with open(file_path, "rb") as f:
            image_data = f.read()
        base64_data = base64.b64encode(image_data).decode("utf-8")
        mime_type = self._get_mime_type(file_path)
        return base64_data, mime_type

    async def recognize(
        self,
        image_paths: List[str],
        prompt: str,
        session: aiohttp.ClientSession,
    ) -> ImageRecognitionResult:
        """
        Send multiple images in a single request using Gemini generateContent API format.

        POST /v1beta/models/{model}:generateContent
        """
        url = f"{self.base_url}/v1beta/models/{self.model}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        parts = []
        for image_path in image_paths:
            try:
                base64_data, mime_type = self._encode_image(image_path)
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64_data,
                    }
                })
            except Exception as e:
                return ImageRecognitionResult(
                    success=False,
                    error=f"Failed to read image {image_path}: {str(e)}",
                )

        parts.append({"text": prompt})

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ]
        }

        try:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                ssl=self._get_ssl_context(),
                timeout=aiohttp.ClientTimeout(total=180),
            ) as response:
                status_code = response.status

                if status_code != 200:
                    error_text = await response.text()
                    return ImageRecognitionResult(
                        success=False,
                        error=f"API error: {status_code} - {error_text}",
                        status_code=status_code,
                    )

                data = await response.json()

                if "candidates" not in data or len(data["candidates"]) == 0:
                    return ImageRecognitionResult(
                        success=False,
                        error="No candidates in response",
                        status_code=status_code,
                    )

                candidate = data["candidates"][0]
                if "content" not in candidate or "parts" not in candidate["content"]:
                    return ImageRecognitionResult(
                        success=False,
                        error="Invalid response structure",
                        status_code=status_code,
                    )

                text_parts = [
                    part.get("text", "")
                    for part in candidate["content"]["parts"]
                    if "text" in part
                ]
                content = "\n".join(text_parts)

                if not content:
                    return ImageRecognitionResult(
                        success=False,
                        error="Empty content in response",
                        status_code=status_code,
                    )

                return ImageRecognitionResult(
                    success=True,
                    content=content,
                    status_code=status_code,
                )

        except aiohttp.ClientError as e:
            return ImageRecognitionResult(
                success=False,
                error=f"Network error: {str(e)}",
            )
        except Exception as e:
            return ImageRecognitionResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
            )
