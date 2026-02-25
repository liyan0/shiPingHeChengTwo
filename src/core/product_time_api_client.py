import json
import re
import ssl
from dataclasses import dataclass
from typing import List, Tuple

import aiohttp


@dataclass
class ProductTimeResult:
    success: bool
    start_time: str = ""  # HH:MM:SS,mmm
    end_time: str = ""    # HH:MM:SS,mmm
    error: str = ""


class ProductTimeAPIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        prompt: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.prompt = prompt

    def _get_ssl_context(self) -> ssl.SSLContext:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    def _validate_time_format(self, time_str: str) -> bool:
        """Validate time format is HH:MM:SS,mmm"""
        if not time_str:
            return False
        pattern = r"^\d{2}:\d{2}:\d{2},\d{3}$"
        return bool(re.match(pattern, time_str))

    def _parse_time_response(self, content: str) -> Tuple[str, str]:
        """
        Parse API response JSON to extract start and end time.
        Returns: (start_time, end_time)
        """
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{[^}]+\}', content)
            if not json_match:
                return "", ""

            data = json.loads(json_match.group())
            start_time = data.get("start", "")
            end_time = data.get("end", "")

            # Validate time format
            if not self._validate_time_format(start_time):
                start_time = ""
            if not self._validate_time_format(end_time):
                end_time = ""

            return start_time, end_time
        except (json.JSONDecodeError, AttributeError):
            return "", ""

    async def recognize(
        self,
        srt_content: str,
        session: aiohttp.ClientSession,
    ) -> ProductTimeResult:
        """
        Send SRT content to LLM API to recognize product time segment.

        Args:
            srt_content: SRT subtitle content
            session: aiohttp session

        Returns:
            ProductTimeResult with start and end time or error
        """
        url = f"{self.base_url}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        full_prompt = self.prompt + srt_content

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": full_prompt}],
        }

        try:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                ssl=self._get_ssl_context(),
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return ProductTimeResult(
                        success=False,
                        error=f"API error: {response.status} - {error_text}",
                    )

                data = await response.json()

                if "choices" not in data or len(data["choices"]) == 0:
                    return ProductTimeResult(
                        success=False,
                        error="No choices in response",
                    )

                content = data["choices"][0].get("message", {}).get("content", "")
                if not content:
                    return ProductTimeResult(
                        success=False,
                        error="Empty content in response",
                    )

                start_time, end_time = self._parse_time_response(content)

                return ProductTimeResult(
                    success=True,
                    start_time=start_time,
                    end_time=end_time,
                )

        except aiohttp.ClientError as e:
            return ProductTimeResult(
                success=False,
                error=f"Network error: {str(e)}",
            )
        except Exception as e:
            return ProductTimeResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
            )

    async def list_models(
        self, session: aiohttp.ClientSession
    ) -> Tuple[bool, List[str], str]:
        """
        GET /v1/models
        Query available models list
        Returns: (success, model_list, error_message)
        """
        url = f"{self.base_url}/v1/models"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with session.get(
                url,
                headers=headers,
                ssl=self._get_ssl_context(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return False, [], f"API error: {response.status} - {error_text}"

                data = await response.json()

                if "data" not in data:
                    return False, [], "Invalid response format"

                models = [item.get("id", "") for item in data["data"] if item.get("id")]
                models.sort()

                return True, models, ""

        except aiohttp.ClientError as e:
            return False, [], f"Network error: {str(e)}"
        except Exception as e:
            return False, [], f"Unexpected error: {str(e)}"
