import aiohttp
from dataclasses import dataclass
from typing import Optional


@dataclass
class TTSResult:
    success: bool
    audio_data: Optional[bytes] = None
    error: str = ""


class TTSAPIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "gpt-4o-mini-tts",
        voice: str = "alloy",
        speed: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.speed = speed

    async def generate_speech(
        self,
        text: str,
        session: aiohttp.ClientSession,
    ) -> TTSResult:
        """
        Generate speech from text using OpenAI-compatible TTS API.
        POST /v1/audio/speech
        """
        if self.base_url.endswith("/v1/audio/speech"):
            url = self.base_url
        else:
            url = f"{self.base_url}/v1/audio/speech"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "speed": self.speed,
            "response_format": "mp3",
        }

        try:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                if response.status == 200:
                    audio_data = await response.read()
                    return TTSResult(success=True, audio_data=audio_data)
                else:
                    error_text = await response.text()
                    return TTSResult(
                        success=False,
                        error=f"HTTP {response.status}: {error_text}",
                    )
        except aiohttp.ClientError as e:
            return TTSResult(success=False, error=f"Network error: {str(e)}")
        except Exception as e:
            return TTSResult(success=False, error=f"Error: {str(e)}")
