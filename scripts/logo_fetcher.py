"""
logo_fetcher.py – Download the brand logo.

Strategy (in order):
  1. Clearbit Logo API (free, no key needed) — cleanest logos.
  2. Scrape homepage for logo-specific images:
       a. <img> tags with "logo" in src or alt
       b. <link> tags with "logo" in href
       c. apple-touch-icon (higher res than favicon, often brand icon)
       d. og:image (last resort — often a lifestyle/hero photo, not a logo)
  3. Try Clearbit with a guessed domain.
  4. Fallback: None — logged for manual review.
"""

import logging
import os
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

CLEARBIT_URL = "https://logo.clearbit.com/{domain}?size=512"


def _domain_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    parsed = urlparse(url)
    netloc = parsed.netloc or url
    return netloc.replace("www.", "").split(":")[0]


def _try_clearbit(domain: str, dest_path: str, timeout: int = 10) -> bool:
    """Try downloading logo from Clearbit."""
    url = CLEARBIT_URL.format(domain=domain)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code == 200 and resp.headers.get("Content-Type", "").startswith("image"):
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            logger.info("  Logo via Clearbit: %s", url)
            return True
    except Exception as e:
        logger.debug("Clearbit failed for %s: %s", domain, e)
    return False


def _download_image(url: str, dest_path: str, timeout: int = 10) -> bool:
    """Download an image URL to dest_path. Returns True on success."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        ct = resp.headers.get("Content-Type", "")
        if resp.status_code == 200 and ct.startswith("image"):
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception:
        pass
    return False


def _try_site_logo(consumer_url: str, dest_path: str, timeout: int = 10) -> bool:
    """
    Scrape the homepage for the best logo image.

    Priority order (lower = better):
      1. <img> with "logo" in src or alt
      2. <link> with "logo" in href
      3. apple-touch-icon (high-res brand icon)
      4. og:image (last resort — often a hero/lifestyle photo)
    """
    try:
        resp = requests.get(consumer_url, headers=HEADERS, timeout=timeout)
        soup = BeautifulSoup(resp.text, "html.parser")

        candidates = []  # (priority, url)

        # Priority 1: <img src="...logo..."> or alt="...logo..."
        for img in soup.find_all("img", src=True):
            src = img.get("src", "")
            alt = img.get("alt", "").lower()
            if "logo" in src.lower() or "logo" in alt:
                full = urljoin(consumer_url, src)
                candidates.append((1, full))

        # Priority 2: <link href="...logo...">
        for link in soup.find_all("link", href=True):
            href = link.get("href", "")
            if "logo" in href.lower():
                full = urljoin(consumer_url, href)
                candidates.append((2, full))

        # Priority 3: apple-touch-icon
        for rel in ["apple-touch-icon", "apple-touch-icon-precomposed"]:
            icon = soup.find("link", rel=lambda r: r and rel in r)
            if icon and icon.get("href"):
                full = urljoin(consumer_url, icon["href"])
                candidates.append((3, full))

        # Priority 4: og:image (last resort)
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            candidates.append((4, og["content"]))

        # Try in priority order (stable sort by priority)
        candidates.sort(key=lambda x: x[0])
        for priority, img_url in candidates:
            if _download_image(img_url, dest_path, timeout):
                logger.info("  Logo via site scrape (priority=%d): %s", priority, img_url)
                return True

    except Exception as e:
        logger.debug("Site logo scrape failed for %s: %s", consumer_url, e)
    return False


def fetch_logo(brand: str, consumer_url: Optional[str], output_dir: str, slug: str) -> Optional[str]:
    """
    Download logo for a brand.
    Returns the local file path on success, None on failure.
    """
    os.makedirs(output_dir, exist_ok=True)
    dest_path = os.path.join(output_dir, f"{slug}_logo.png")

    domain = _domain_from_url(consumer_url)

    # Strategy 1: Clearbit (cleanest result)
    if domain and _try_clearbit(domain, dest_path):
        return dest_path

    # Strategy 2: Scrape site, logo-first priority
    if consumer_url and _try_site_logo(consumer_url, dest_path):
        return dest_path

    # Strategy 3: Clearbit with guessed domain
    guessed = brand.lower().replace(" ", "").replace("-", "") + ".com"
    if guessed != domain and _try_clearbit(guessed, dest_path):
        return dest_path

    logger.warning("  Could not fetch logo for %s — manual review needed.", brand)
    return None
