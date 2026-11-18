"""Collector for public Telegram channels via web preview (t.me/s/<channel>) with photo support."""
import re
from typing import List
from bs4 import BeautifulSoup
import httpx
from ..storage import Item


class TelegramPreviewCollector:
    def __init__(self, name: str, channel_username: str, competitor: str = None):
        self.name = name
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

                for msg in messages[-20:]:  # Last 20 messages
                    # Extract link
                    link_tag = msg.find("a", class_="tgme_widget_message_date")
                    msg_url = link_tag.get("href") if link_tag else f"{self.url}#{msg.get('data-post', '')}"

                    # Extract time
                    time_tag = msg.find("time")
                    published_at = time_tag.get("datetime") if time_tag else None

                    # Extract text
                    text_tag = msg.find("div", class_="tgme_widget_message_text")
                    text = text_tag.get_text(separator="\n").strip() if text_tag else ""

                    # Extract image URL if available
                    image_url = None
                    photo_wrap = msg.find(["a", "div", "i"], class_=re.compile(r"photo_wrap|link_preview_image|video_thumb"))
                    if photo_wrap and "style" in photo_wrap.attrs:
                        match = re.search(r"url\('([^']+)'\)", photo_wrap["style"])
                        if match:
                            image_url = match.group(1)

                    if not text and not image_url:
                        continue

                    # If no text but image exists, provide placeholder title
                    first_line = text.split("\n")[0][:100].strip() if text else "Фото-событие"
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
                            image_url=image_url,
                        )
                    )
        except Exception as e:
            print(f"[TelegramCollector] Error fetching {self.url}: {e}")

        return items
