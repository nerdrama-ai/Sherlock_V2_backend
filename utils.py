import re
from typing import Optional
import httpx
import json

# Parse leniently
def safe_json_loads(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None

META_IMG_PATTERNS = [
    # og:image
    re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I),
    # twitter:image
    re.compile(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', re.I),
    # twitter:image:src
    re.compile(r'<meta[^>]+name=["\']twitter:image:src["\'][^>]+content=["\']([^"\']+)["\']', re.I),
]

FAVICON_PATTERN = re.compile(
    r'<link[^>]+rel=["\'](?:shortcut icon|icon|apple-touch-icon(?:-precomposed)?)["\'][^>]+href=["\']([^"\']+)["\']',
    re.I,
)

async def fetch_profile_pic_async(url: str, timeout: float = 6.0) -> Optional[str]:
    """
    Best-effort: fetch profile page and try to extract an image.
    Returns absolute URL or None.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; Sherlock-Backend/1.0)"
        }) as client:
            r = await client.get(url)
            if r.status_code >= 400:
                return None
            html = r.text

        # Try meta images first
        for pat in META_IMG_PATTERNS:
            m = pat.search(html)
            if m:
                img = m.group(1).strip()
                return httpx.URL(img, base=url).human_repr()

        # Fallback to favicon
        m = FAVICON_PATTERN.search(html)
        if m:
            fav = m.group(1).strip()
            return httpx.URL(fav, base=url).human_repr()

        return None
    except Exception:
        return None
