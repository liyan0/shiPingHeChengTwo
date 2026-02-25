import asyncio
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass
class VideoInfo:
    success: bool
    title: str = ""
    video_url: str = ""
    error: str = ""
    platform: str = ""


class VideoScraperClient:
    """Playwright-based video page scraper for extracting video info"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser = None
        self._playwright = None

    async def initialize(self):
        """Start Playwright browser"""
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)

    async def close(self):
        """Close browser and cleanup"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def _detect_platform(self, url: str) -> str:
        """Detect video platform from URL"""
        parsed = urlparse(url)
        host = parsed.netloc.lower()

        if "baijiahao" in host or "baidu" in host:
            return "baijiahao"
        elif "douyin" in host:
            return "douyin"
        elif "kuaishou" in host:
            return "kuaishou"
        elif "bilibili" in host:
            return "bilibili"
        else:
            return "unknown"

    async def extract_video_info(self, url: str) -> VideoInfo:
        """Extract video title and MP4 URL from page"""
        if not self._browser:
            return VideoInfo(success=False, error="Browser not initialized")

        platform = self._detect_platform(url)

        try:
            if platform == "baijiahao":
                return await self._extract_baijiahao(url)
            else:
                return VideoInfo(
                    success=False,
                    error=f"Unsupported platform: {platform}",
                    platform=platform
                )
        except Exception as e:
            return VideoInfo(success=False, error=str(e), platform=platform)

    async def _extract_baijiahao(self, url: str) -> VideoInfo:
        """Extract video info from Baijiahao page"""
        context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Extract title
            title = ""
            title_selectors = [
                "h1.article-title",
                "h1",
                ".video-title",
                "title",
            ]
            for selector in title_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        title = await element.inner_text()
                        title = title.strip()
                        if title:
                            break
                except Exception:
                    continue

            if not title:
                title = await page.title()
                title = re.sub(r"[-_|].*$", "", title).strip()

            # Clean title for filename
            title = re.sub(r'[\\/:*?"<>|]', "", title)
            title = title[:100] if len(title) > 100 else title

            # Extract video URL from page content
            video_url = ""

            # Method 1: Find video element src
            video_element = await page.query_selector("video source")
            if video_element:
                video_url = await video_element.get_attribute("src")

            if not video_url:
                video_element = await page.query_selector("video")
                if video_element:
                    video_url = await video_element.get_attribute("src")

            # Method 2: Search in page content for MP4 URLs
            if not video_url:
                content = await page.content()
                mp4_patterns = [
                    r'https?://[^"\'<>\s]+\.mp4[^"\'<>\s]*',
                    r'"videoUrl"\s*:\s*"([^"]+)"',
                    r'"playUrl"\s*:\s*"([^"]+)"',
                    r'"url"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"',
                ]
                for pattern in mp4_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        video_url = matches[0] if isinstance(matches[0], str) else matches[0]
                        break

            # Method 3: Intercept network requests
            if not video_url:
                video_urls = []

                async def handle_response(response):
                    url = response.url
                    if ".mp4" in url or "video" in url.lower():
                        video_urls.append(url)

                page.on("response", handle_response)
                await page.reload(wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)

                if video_urls:
                    video_url = video_urls[0]

            if not video_url:
                return VideoInfo(
                    success=False,
                    title=title,
                    error="Could not find video URL",
                    platform="baijiahao"
                )

            # Clean video URL
            if video_url.startswith("//"):
                video_url = "https:" + video_url

            return VideoInfo(
                success=True,
                title=title,
                video_url=video_url,
                platform="baijiahao"
            )

        finally:
            await context.close()
