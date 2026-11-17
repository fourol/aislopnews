"""Telegram Channel Publisher using the official Bot API via HTTP."""
from pathlib import Path
from typing import Optional
import httpx


class TelegramPublisher:
    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token.strip()
        self.channel_id = channel_id.strip()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_digest(self, text: str, chart_path: Optional[str] = None) -> bool:
        """Sends the digest text and optional chart to the configured Telegram channel."""
        if not self.bot_token or not self.channel_id:
            print("[TelegramPublisher] Bot token or channel_id not configured. Skipping send.")
            return False

        try:
            with httpx.Client(timeout=30.0) as client:
                if chart_path and Path(chart_path).exists():
                    # Telegram caption limit is 1024 chars
                    if len(text) <= 1000:
                        # Send together in one photo message
                        with open(chart_path, "rb") as f:
                            files = {"photo": f}
                            data = {
                                "chat_id": self.channel_id,
                                "caption": text,
                                "parse_mode": "Markdown",
                            }
                            res = client.post(f"{self.base_url}/sendPhoto", data=data, files=files)
                            if res.status_code == 200:
                                return True
                            # Fallback if markdown error
                            data.pop("parse_mode", None)
                            f.seek(0)
                            res = client.post(f"{self.base_url}/sendPhoto", data=data, files=files)
                            return res.status_code == 200
                    else:
                        # Caption limit exceeded: send photo first, then full digest message
                        with open(chart_path, "rb") as f:
                            files = {"photo": f}
                            data = {
                                "chat_id": self.channel_id,
                                "caption": "📊 **Аналитический срез рынка и активности конкурентов**",
                                "parse_mode": "Markdown",
                            }
                            client.post(f"{self.base_url}/sendPhoto", data=data, files=files)

                # Send text message (split if > 4000 chars)
                chunks = self._split_text(text, 4000)
                for chunk in chunks:
                    payload = {
                        "chat_id": self.channel_id,
                        "text": chunk,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    }
                    res = client.post(f"{self.base_url}/sendMessage", json=payload)
                    if res.status_code != 200:
                        # Fallback without markdown in case of unescaped chars
                        payload.pop("parse_mode", None)
                        res = client.post(f"{self.base_url}/sendMessage", json=payload)
                        if res.status_code != 200:
                            print(f"[TelegramPublisher] Error sending message: {res.status_code} {res.text}")
                            return False

                return True
        except Exception as e:
            print(f"[TelegramPublisher] Failed to post to Telegram: {e}")
            return False

    @staticmethod
    def _split_text(text: str, max_len: int = 4000) -> list[str]:
        if len(text) <= max_len:
            return [text]
        parts = []
        while text:
            if len(text) <= max_len:
                parts.append(text)
                break
            # Find last newline before max_len
            split_idx = text.rfind("\n", 0, max_len)
            if split_idx == -1:
                split_idx = max_len
            parts.append(text[:split_idx])
            text = text[split_idx:].lstrip()
        return parts
