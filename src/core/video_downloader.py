import aiohttp
import aiofiles
import asyncio
import ssl
import os
from typing import Optional, Callable

from ..utils.helpers import ensure_dir


class VideoDownloader:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "video/mp4,video/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    def __init__(self, save_dir: str):
        self.save_dir = save_dir
        ensure_dir(save_dir)

    async def download_video(
        self,
        url: str,
        filename: str,
        session: Optional[aiohttp.ClientSession] = None,
        progress_callback: Optional[Callable[[str, bool, str], None]] = None,
    ) -> bool:
        """Download a single video from URL"""
        close_session = False
        if session is None:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            session = aiohttp.ClientSession(connector=connector)
            close_session = True

        filepath = os.path.join(self.save_dir, filename)

        try:
            async with session.get(
                url,
                headers=self.HEADERS,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                if response.status == 200:
                    content = await response.read()
                    async with aiofiles.open(filepath, "wb") as f:
                        await f.write(content)

                    if progress_callback:
                        progress_callback(filename, True, "")
                    return True
                else:
                    error_msg = f"HTTP {response.status}"
                    if progress_callback:
                        progress_callback(filename, False, error_msg)
                    return False

        except asyncio.TimeoutError:
            if progress_callback:
                progress_callback(filename, False, "下载超时")
            return False
        except Exception as e:
            if progress_callback:
                progress_callback(filename, False, str(e))
            return False
        finally:
            if close_session:
                await session.close()

    def _create_session(self) -> aiohttp.ClientSession:
        """Create a session with proper SSL context for video downloads"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        return aiohttp.ClientSession(connector=connector)
