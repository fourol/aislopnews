"""Telegram Channel Publisher using the official Bot API via HTTP with HTML & Premium styling support."""
from pathlib import Path
import re
from typing import Optional
import httpx


# Telegram Premium Custom Emoji mappings from NewsEmoji pack (https://t.me/addemoji/NewsEmoji)
NEWS_EMOJI_MAP = {
    "🔥": "5424972470023104089",
    "⚡️": "5456140674028019486",
    "⚡": "5456140674028019486",
    "🎮": "5361741454685256344",
    "⚙️": "5341715473882955310",
    "⚙": "5341715473882955310",
    "💡": "5422439311196834318",
    "💎": "5427168083074628963",
    "💬": "5443038326535759644",
    "💭": "5467538555158943525",
    "📊": "5231200819986047254",
    "📈": "5244837092042750681",
    "📉": "5246762912428603768",
    "🌐": "5447410659077661506",
    "🔍": "5231012545799666522",
    "🖥": "5282843764451195532",
    "🔒": "5296369303661067030",
    "🔗": "5271604874419647061",
    "✔️": "5206607081334906820",
    "❌": "5210952531676504517",
    "🚨": "5395695537687123235",
    "🆕": "5382357040008021292",
    "🔝": "5415655814079723871",
    "📌": "5397782960512444700",
    "✨": "5325547803936572038",
    "👑": "5217822164362739968",
    "⚠️": "5447644880824181073",
    "‼️": "5440660757194744323",
    "❗️": "5274099962655816924",
    "👀": "5210956306952758910",
    "🎉": "5461151367559141950",
    "🚩": "5460755126761312667",
    "🏠": "5416041192905265756",
    "🗓": "5413879192267805083",
    "💯": "5341498088408234504",
    "🔔": "5458603043203327669",
    "🛡": "5251203410396458957",
    "💵": "5409048419211682843",
    "💸": "5233326571099534068",
    "💱": "5402186569006210455",
    "🎙": "5294339927318739359",
    "📣": "5424818078833715060",
    "⭐️": "5438496463044752972",
    "⬇️": "5406745015365943482",
    "🔼": "5449683594425410231",
    "🔽": "5447183459602669338",
    "▶️": "5264919878082509254",
    "🔴": "5411225014148014586",
    "🟢": "5416081784641168838",
    "➡️": "5416117059207572332",
}


class TelegramPublisher:
    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token.strip()
        self.channel_id = channel_id.strip()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    @classmethod
    def inject_custom_emojis(cls, text: str) -> str:
        """Replaces standard emojis with custom emoji tags from NewsEmoji pack using single-pass regex."""
        tagged = {}

        def save_tagged(match):
            key = f"__TG_EMOJI_{len(tagged)}__"
            tagged[key] = match.group(0)
            return key

        text = re.sub(r"<tg-emoji[^>]*>.*?</tg-emoji>", save_tagged, text)

        pattern = "|".join(re.escape(em) for em in sorted(NEWS_EMOJI_MAP.keys(), key=len, reverse=True))
        text = re.sub(pattern, lambda m: f'<tg-emoji emoji-id="{NEWS_EMOJI_MAP[m.group(0)]}">{m.group(0)}</tg-emoji>', text)

        for key, val in tagged.items():
            text = text.replace(key, val)
        return text

    @classmethod
    def prepare_html(cls, text: str) -> str:
        """Converts markdown artifacts to Telegram HTML, injects NewsEmoji and balances tags."""
        # Convert markdown bold **text** to <b>text</b>
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

        # Convert markdown quotes > line to <blockquote expandable>...</blockquote>
        if '<blockquote' not in text and '>' in text:
            new_lines = []
            in_quote = False
            for line in text.split('\n'):
                if line.strip().startswith('>'):
                    cleaned = line.strip().lstrip('>').strip()
                    if not in_quote:
                        new_lines.append(f'<blockquote expandable>{cleaned}')
                        in_quote = True
                    else:
                        new_lines.append(cleaned)
                else:
                    if in_quote:
                        new_lines[-1] += '</blockquote>'
                        in_quote = False
                    new_lines.append(line)
            if in_quote:
                new_lines[-1] += '</blockquote>'
            text = '\n'.join(new_lines)

        # Inject custom emojis from NewsEmoji
        text = cls.inject_custom_emojis(text)

        # Auto-close open tags
        for tag in ['b', 'i', 'code', 'tg-spoiler', 'blockquote']:
            open_count = len(re.findall(rf'<{tag}[\s>]', text, re.IGNORECASE))
            close_count = len(re.findall(rf'</{tag}>', text, re.IGNORECASE))
            if open_count > close_count:
                text += f'</{tag}>' * (open_count - close_count)
        return text

    def send_digest(self, text: str, chart_path: Optional[str] = None, headline: Optional[str] = None) -> bool:
        """Sends the digest text and optional chart to the configured Telegram channel."""
        if not self.bot_token or not self.channel_id:
            print("[TelegramPublisher] Bot token or channel_id not configured. Skipping send.")
            return False

        formatted_html = self.prepare_html(text)

        try:
            with httpx.Client(timeout=30.0) as client:
                if chart_path and Path(chart_path).exists():
                    # Telegram caption limit is strictly 1024 visible chars
                    caption_text = formatted_html
                    plain_len = len(re.sub(r'<[^>]+>', '', caption_text))
                    if plain_len > 1020:
                        trimmed = caption_text[:1000]
                        last_break = max(
                            trimmed.rfind(". "),
                            trimmed.rfind("!\n"),
                            trimmed.rfind("?\n"),
                            trimmed.rfind("\n\n"),
                            trimmed.rfind("\n"),
                        )
                        if last_break > 400:
                            caption_text = trimmed[:last_break + 1]
                        else:
                            caption_text = trimmed
                        caption_text = self.prepare_html(caption_text)

                    with open(chart_path, "rb") as f:
                        files = {"photo": f}
                        data = {
                            "chat_id": self.channel_id,
                            "caption": caption_text,
                            "parse_mode": "HTML",
                        }
                        res = client.post(f"{self.base_url}/sendPhoto", data=data, files=files)
                        if res.status_code == 200:
                            return True
                        print(f"[TelegramPublisher] sendPhoto HTML mode error: {res.status_code} {res.text}. Trying plain text fallback...")
                        # Fallback without HTML formatting in case of malformed entities
                        data["caption"] = re.sub(r'<[^>]+>', '', caption_text)
                        data.pop("parse_mode", None)
                        f.seek(0)
                        res = client.post(f"{self.base_url}/sendPhoto", data=data, files=files)
                        return res.status_code == 200

                # If no photo, send as text message
                chunks = self._split_text(formatted_html, 4000)
                for chunk in chunks:
                    payload = {
                        "chat_id": self.channel_id,
                        "text": chunk,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    }
                    res = client.post(f"{self.base_url}/sendMessage", json=payload)
                    if res.status_code != 200:
                        # Fallback without HTML
                        payload["text"] = re.sub(r'<[^>]+>', '', chunk)
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
