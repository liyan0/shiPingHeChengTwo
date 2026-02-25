from dataclasses import dataclass
from typing import Optional

import aiohttp


@dataclass
class SubtitleResult:
    success: bool
    srt_content: Optional[str] = None
    error: str = ""


class SubtitleAPIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        language: str = "zh",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.language = language

    async def generate_subtitle(
        self,
        audio_path: str,
        session: aiohttp.ClientSession = None,
    ) -> SubtitleResult:
        """
        Generate SRT subtitle from audio file using Whisper API.

        Args:
            audio_path: Path to the audio file (MP3)
            session: Deprecated, not used (kept for backward compatibility)

        Returns:
            SubtitleResult with SRT content or error message
        """
        url = f"{self.base_url}/v1/audio/transcriptions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            # 创建独立的 session，避免与 TTS 请求的 session 复用导致 multipart EOF 问题
            async with aiohttp.ClientSession() as local_session:
                data = aiohttp.FormData()
                data.add_field(
                    "file",
                    audio_data,  # 直接使用 bytes，不用 BytesIO
                    filename="audio.mp3",
                    content_type="audio/mpeg",
                )
                data.add_field("model", self.model)
                data.add_field("response_format", "srt")
                if self.language:
                    data.add_field("language", self.language)

                async with local_session.post(
                    url,
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    if response.status == 200:
                        srt_content = await response.text()
                        return SubtitleResult(success=True, srt_content=srt_content)
                    else:
                        error_text = await response.text()
                        return SubtitleResult(
                            success=False,
                            error=f"API error {response.status}: {error_text}",
                        )
        except FileNotFoundError:
            return SubtitleResult(success=False, error=f"Audio file not found: {audio_path}")
        except aiohttp.ClientError as e:
            return SubtitleResult(success=False, error=f"Network error: {str(e)}")
        except Exception as e:
            return SubtitleResult(success=False, error=f"Unexpected error: {str(e)}")
