"""Collector for public Telegram channels via web preview (t.me/s/<channel>)."""
import re
from typing import List
from bs4 import BeautifulSoup
import httpx
from ..storage import Item


class TelegramPreviewCollector:
    def __init__(self, name: str, channel_username: str, competitor: str = None):
        self.name = name
        # Clean username from URL or @
        clean_name = channel_username.strip().replace("https://t.me/", "").replace("t.me/", "").replace("@", "").split("/")[0]
        self.channel = clean_name
        self.url = f"https://t.me/s/{self.channel}"
        self.competitor = competitor

    def collect(self) -> List[Item]:
        items: List[Item] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }

        try:
            with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
                response = client.get(self.url)
                if response.status_code != 200:
                    print(f"[TelegramCollector] Failed to fetch {self.url}, status: {response.status_code}")
                    return items

                soup = BeautifulSoup(response.text, "html.parser")
                messages = soup.find_all("div", class_="tgme_widget_message")

                for msg in messages[-15:]:  # Last 15 messages
                    # Extract link
                    link_tag = msg.find("a", class_="tgme_widget_message_date")
                    msg_url = link_tag.get("href") if link_tag else f"{self.url}#{msg.get('data-post', '')}"

                    # Extract time
                    time_tag = msg.find("time")
                    published_at = time_tag.get("datetime") if time_tag else None

                    # Extract text
                    text_tag = msg.find("div", class_="tgme_widget_message_text")
                    if not text_tag:
                        continue
                    text = text_tag.get_text(separator="\n").strip()
                    if not text:
                        continue

                    # Generate title from first line
                    first_line = text.split("\n")[0][:100].strip()
                    title = f"[{self.channel}] {first_line}"

                    items.append(
                        Item(
                            url=msg_url,
                            title=title,
                            source_name=self.name,
                            source_type="telegram",
                            competitor=self.competitor or self.channel,
                            content=text[:4000],
                            published_at=published_at,
                        )
                    )
        except Exception as e:
            print(f"[TelegramCollector] Error fetching {self.url}: {e}")

        return items
