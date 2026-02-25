import ssl
from dataclasses import dataclass
from typing import List

import aiohttp


@dataclass
class MergeCopywritingResult:
    success: bool
    content: str = ""
    error: str = ""
    status_code: int = 0


class MergeCopywritingAPIClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _get_ssl_context(self) -> ssl.SSLContext:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    async def merge(
        self,
        product_content: str,
        video_content: str,
        user_prompt: str,
        session: aiohttp.ClientSession,
    ) -> MergeCopywritingResult:
        """
        POST /v1/chat/completions
        Merge product copywriting with video copywriting using LLM
        """
        url = f"{self.base_url}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        prompt = f"""商品文案:
{product_content}

视频文案:
{video_content}

{user_prompt}"""

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                ssl=self._get_ssl_context(),
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                status_code = response.status

                if status_code != 200:
                    error_text = await response.text()
                    return MergeCopywritingResult(
                        success=False,
                        error=f"API error: {status_code} - {error_text}",
                        status_code=status_code,
                    )

                data = await response.json()

                if "choices" not in data or len(data["choices"]) == 0:
                    return MergeCopywritingResult(
                        success=False,
                        error="No choices in response",
                        status_code=status_code,
                    )

                content = data["choices"][0].get("message", {}).get("content", "")
                if not content:
                    return MergeCopywritingResult(
                        success=False,
                        error="Empty content in response",
                        status_code=status_code,
                    )

                return MergeCopywritingResult(
                    success=True,
                    content=content,
                    status_code=status_code,
                )

        except aiohttp.ClientError as e:
            return MergeCopywritingResult(
                success=False,
                error=f"Network error: {str(e)}",
            )
        except Exception as e:
            return MergeCopywritingResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
            )

    async def list_models(
        self, session: aiohttp.ClientSession
    ) -> tuple[bool, List[str], str]:
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
