"""
screenshot_taker.py – Capture screenshots for a brand.

  capture_image_searches() – Google Images results for 3 search queries.
  capture_website()        – Brand's own homepage (used for style guide input).

Uses Playwright (async, headless Chromium).
"""

import asyncio
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

GOOGLE_IMAGES_URL = "https://www.google.com/search?q={query}&tbm=isch&safe=off"

DEFAULT_WIDTH = 1600
DEFAULT_HEIGHT = 900
DEFAULT_WAIT_MS = 3000


async def _take_screenshot(
    query: str,
    dest_path: str,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    wait_ms: int = DEFAULT_WAIT_MS,
) -> bool:
    """Take a screenshot of Google Images results for a query."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            encoded_query = query.replace(" ", "+")
            url = GOOGLE_IMAGES_URL.format(query=encoded_query)

            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(wait_ms)

            # Try to dismiss consent dialogs (EU / cookie prompts)
            for selector in [
                'button:has-text("Accept all")',
                'button:has-text("I agree")',
                'button:has-text("Reject all")',
                '[aria-label="Accept all"]',
            ]:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await page.wait_for_timeout(1000)
                        break
                except Exception:
                    pass

            # Scroll down slightly to load more images
            await page.evaluate("window.scrollBy(0, 300)")
            await page.wait_for_timeout(500)

            await page.screenshot(path=dest_path, full_page=False)
            await browser.close()
            logger.info("  Screenshot saved: %s", dest_path)
            return True

    except Exception as e:
        logger.error("Screenshot failed for query '%s': %s", query, e)
        return False


def capture_image_searches(
    brand: str,
    output_dir: str,
    queries: List[str],
    filenames: List[str],
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    wait_ms: int = DEFAULT_WAIT_MS,
) -> List[Optional[str]]:
    """
    Capture screenshot for each image search query.

    Returns list of saved file paths (None if failed).
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for query_tmpl, filename in zip(queries, filenames):
        query = query_tmpl.format(brand=brand)
        dest_path = os.path.join(output_dir, filename)
        logger.info("  Screenshotting Google Images: '%s'", query)
        success = asyncio.run(_take_screenshot(query, dest_path, width, height, wait_ms))
        results.append(dest_path if success else None)

    return results


async def _take_url_screenshot(
    url: str,
    dest_path: str,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    wait_ms: int = 2000,
) -> bool:
    """Take a full-viewport screenshot of any URL."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(wait_ms)
            await page.screenshot(path=dest_path, full_page=False)
            await browser.close()
            logger.info("  Website screenshot saved: %s", dest_path)
            return True
    except Exception as e:
        logger.error("Website screenshot failed for '%s': %s", url, e)
        return False


def capture_website(
    url: str,
    output_dir: str,
    filename: str = "website_screenshot.png",
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> Optional[str]:
    """
    Capture a screenshot of the brand's homepage for use as style guide input.
    Returns the saved file path, or None on failure.
    """
    if not url:
        return None
    os.makedirs(output_dir, exist_ok=True)
    dest_path = os.path.join(output_dir, filename)
    logger.info("  Screenshotting homepage: %s", url)
    success = asyncio.run(_take_url_screenshot(url, dest_path, width, height))
    return dest_path if success else None
