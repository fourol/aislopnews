"""RSS/Atom feed collector with robust HTTP timeout, retries, and User-Agent."""
import time
from typing import List
import feedparser
import httpx
from ..storage import Item


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

                items.append(
                    Item(
                        url=link,
                        title=title,
                        source_name=self.name,
                        source_type="rss",
                        competitor=self.competitor,
                        content=content[:4000],  # Truncate overly long text
                        published_at=published,
                    )
                )
        except Exception as e:
            print(f"[RSSCollector] Error fetching {self.url}: {e}")

        return items
