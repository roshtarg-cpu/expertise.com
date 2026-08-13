from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.expertise.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

MAX_RETRIES = 3
RETRY_DELAY = 2.0
REQUEST_DELAY = 1.0


async def fetch_page(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Fetch a URL with retry logic. Returns HTML or None on failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await asyncio.sleep(REQUEST_DELAY if attempt == 1 else RETRY_DELAY * attempt)
            response = await client.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                return response.text
            if response.status_code == 404:
                logger.warning("404 for %s", url)
                return None
            logger.warning("HTTP %s for %s (attempt %d)", response.status_code, url, attempt)
        except httpx.TimeoutException:
            logger.warning("Timeout for %s (attempt %d)", url, attempt)
        except httpx.RequestError as exc:
            logger.warning("Request error for %s: %s (attempt %d)", url, exc, attempt)
    logger.error("Failed to fetch %s after %d attempts", url, MAX_RETRIES)
    return None


def build_client(proxy_url: Optional[str] = None) -> httpx.AsyncClient:
    """Create an async httpx client with optional proxy."""
    kwargs: dict = {"follow_redirects": True, "timeout": 30}
    if proxy_url:
        kwargs["proxies"] = {"all://": proxy_url}
    return httpx.AsyncClient(**kwargs)


def extract_city_slug(href: str) -> str:
    """Extract city slug from /state/city href."""
    parts = href.strip("/").split("/")
    return parts[-1] if parts else ""
