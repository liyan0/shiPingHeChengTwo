import aiohttp
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class GenerationResult:
    success: bool
    urls: List[str] = None
    error: str = None
    status_code: int = 0

    def __post_init__(self):
        if self.urls is None:
            self.urls = []


class JimengAPIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "jimeng-4.5",
        ratio: str = "1:1",
        resolution: str = "2k",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.ratio = ratio
        self.resolution = resolution

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def generate_image(
        self,
        prompt: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> GenerationResult:
        """Generate images from prompt"""
        close_session = False
        if session is None:
            session = aiohttp.ClientSession()
            close_session = True

        try:
            url = f"{self.base_url}/v1/images/generations"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "ratio": self.ratio,
                "resolution": self.resolution,
            }

            async with session.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                status_code = response.status

                if status_code == 200:
                    data = await response.json()
                    # 调试日志：打印完整API响应以便排查URL提取问题
                    import json
                    print(f"[DEBUG] API响应: {json.dumps(data, ensure_ascii=False, indent=2)}")

                    data_list = data.get("data") or []
                    # 尝试多种可能的URL字段名
                    urls = []
                    for item in data_list:
                        if not item:
                            continue
                        # 按优先级尝试不同的字段名
                        url = item.get("url") or item.get("image_url") or item.get("imageUrl") or ""
                        if url:
                            urls.append(url)

                    if not urls and data_list:
                        print(f"[DEBUG] 警告: data列表有 {len(data_list)} 项但未提取到URL，请检查字段名")
                        print(f"[DEBUG] data[0] 的键: {list(data_list[0].keys()) if data_list[0] else 'None'}")
                    return GenerationResult(
                        success=True,
                        urls=urls,
                        status_code=status_code,
                    )
                else:
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get("error", {}).get(
                            "message", f"HTTP {status_code}"
                        )
                    except Exception:
                        error_msg = f"HTTP {status_code}"

                    return GenerationResult(
                        success=False,
                        error=error_msg,
                        status_code=status_code,
                    )

        except asyncio.TimeoutError:
            return GenerationResult(
                success=False,
                error="请求超时",
                status_code=0,
            )
        except aiohttp.ClientError as e:
            return GenerationResult(
                success=False,
                error=f"网络错误: {str(e)}",
                status_code=0,
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                error=f"未知错误: {str(e)}",
                status_code=0,
            )
        finally:
            if close_session:
                await session.close()

    @staticmethod
    def is_retryable_error(status_code: int) -> bool:
        """Check if error is retryable"""
        return status_code in (0, 429, 500, 502, 503, 504)
