"""RSS/Atom feed collector with robust HTTP timeout, retries, image extraction, and User-Agent."""
import re
import time
from typing import List, Optional
from urllib.parse import urljoin
import feedparser
import httpx
from ..storage import Item


def _extract_entry_image(entry, base_url: str, raw_html: str) -> Optional[str]:
    for key in ("media_content", "media_thumbnail"):
        media = entry.get(key)
        if isinstance(media, list):
            for item in media:
                url = item.get("url") if isinstance(item, dict) else None
                if url and not url.lower().endswith(".svg"):
                    return urljoin(base_url, url)

    for key in ("enclosures", "links"):
        links = entry.get(key)
        if isinstance(links, list):
            for item in links:
                if not isinstance(item, dict):
                    continue
                mime = (item.get("type") or "").lower()
                href = item.get("href") or item.get("url") or ""
                if href and mime.startswith("image/") and "svg" not in mime:
                    return urljoin(base_url, href)

    if raw_html:
        for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', raw_html, flags=re.IGNORECASE):
            src = match.group(1).strip()
            if src and not src.startswith("data:") and not src.lower().endswith(".svg"):
                if any(bad in src.lower() for bad in ("1x1", "pixel", "counter", "favicon", "emoji")):
                    continue
                return urljoin(base_url, src)
    return None


class RSSCollector:
    def __init__(self, name: str, url: str, competitor: str = None):
        self.name = name
        self.url = url
        self.competitor = competitor

    def collect(self) -> List[Item]:
        items: List[Item] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        feed_content = None
        last_error = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
                    res = client.get(self.url)
                    if res.status_code != 200:
                        print(f"[RSSCollector] Failed to fetch {self.url}, status code: {res.status_code}")
                        return items
                    feed_content = res.text
                    break
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))

        if not feed_content:
            print(f"[RSSCollector] Error fetching {self.url}: {last_error}")
            return items

        try:
            feed = feedparser.parse(feed_content)
            for entry in feed.entries[:15]:  # Take latest 15 entries
                title = entry.get("title", "Untitled")
                link = entry.get("link", "")
                published = entry.get("published", entry.get("updated", ""))

                # Extract summary / content
                content = ""
                if "summary" in entry:
                    content = entry.summary
                elif "description" in entry:
                    content = entry.description
                elif "content" in entry and len(entry.content) > 0:
                    content = entry.content[0].get("value", "")

                if not link or not title:
                    continue

                image_url = _extract_entry_image(entry, link or self.url, content)

                items.append(
                    Item(
                        url=link,
                        title=title,
                        source_name=self.name,
                        source_type="rss",
                        competitor=self.competitor,
                        content=content[:4000],  # Truncate overly long text
                        published_at=published,
                        image_url=image_url,
                    )
                )
        except Exception as e:
            print(f"[RSSCollector] Error fetching {self.url}: {e}")

        return items
