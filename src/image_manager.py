"""Image manager: downloads validated images, extracts article og:image, searches web photos, or renders HD Pillow editorial covers."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
import re
from typing import Optional, Tuple
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFilter, ImageFont


TOPIC_THEMES: dict[str, Tuple[Tuple[int, int, int], Tuple[int, int, int], str]] = {
    "ии": ((56, 189, 248), (99, 102, 241), "ИИ И НЕЙРОСЕТИ"),
    "ai": ((56, 189, 248), (99, 102, 241), "AI И ТЕХНОЛОГИИ"),
    "игры": ((168, 85, 247), (236, 72, 153), "ИГРЫ И ИНДУСТРИЯ"),
    "gaming": ((168, 85, 247), (236, 72, 153), "ИГРЫ И ИНДУСТРИЯ"),
    "telegram": ((59, 130, 246), (14, 165, 233), "TELEGRAM"),
    "web3": ((16, 185, 129), (20, 184, 166), "WEB3 И КРИПТО"),
    "tech": ((96, 165, 250), (129, 140, 248), "ТЕХНОЛОГИИ"),
}

BOLD_FONT_CANDIDATES = [
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]

REGULAR_FONT_CANDIDATES = [
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


class ImageManager:
    def __init__(self, output_dir: str = "data/images"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }

    def download_image(self, url: str, min_width: int = 320, min_height: int = 200) -> Optional[str]:
        """Downloads and validates a raster image, converting it to clean RGB JPEG."""
        if not url or url.lower().endswith(".svg"):
            return None
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True, headers=self.headers) as client:
                res = client.get(url)
                if res.status_code != 200 or len(res.content) < 2000:
                    return None

            img = Image.open(BytesIO(res.content))
            w, h = img.size
            if w < min_width or h < min_height:
                print(f"[ImageManager] Rejected low-res image ({w}x{h}) from {url[:60]}")
                return None

            # Reject extreme thin banners or tiny squares relative to article photos
            ratio = w / max(1, h)
            if ratio > 4.5 or ratio < 0.35:
                print(f"[ImageManager] Rejected abnormal aspect ratio ({w}x{h}) from {url[:60]}")
                return None

            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (15, 23, 42))
                converted = img.convert("RGBA")
                bg.paste(converted, mask=converted.split()[-1])
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            file_path = self.output_dir / f"image_{timestamp}.jpg"
            img.save(file_path, format="JPEG", quality=92, optimize=True)
            return str(file_path)
        except Exception as e:
            print(f"[ImageManager] Error downloading image from {url}: {e}")
        return None

    def extract_article_image(self, article_url: str) -> Optional[str]:
        """Extracts OpenGraph / Twitter hero image from an article URL."""
        if not article_url or "t.me/" in article_url:
            return None
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True, headers=self.headers) as client:
                res = client.get(article_url)
                if res.status_code != 200:
                    return None

            soup = BeautifulSoup(res.text, "html.parser")
            candidates: list[str] = []
            for attr, val in (
                ("property", "og:image"),
                ("property", "og:image:secure_url"),
                ("name", "twitter:image"),
                ("name", "twitter:image:src"),
            ):
                tag = soup.find("meta", attrs={attr: val})
                if tag and tag.get("content"):
                    candidates.append(urljoin(article_url, tag["content"].strip()))

            for img_url in candidates:
                saved = self.download_image(img_url, min_width=400, min_height=220)
                if saved:
                    return saved
        except Exception as e:
            print(f"[ImageManager] og:image extraction failed for {article_url}: {e}")
        return None

    def search_web_image(self, query: str) -> Optional[str]:
        """Searches for a relevant high-resolution photo via Wikipedia/Wikimedia thumbnails."""
        if not query:
            return None
        wiki_headers = {"User-Agent": "AiSlopNewsBot/1.0 (https://github.com/fourol/aislopnews)"}

        # 1. Try Wikipedia search pageimages (usually cleaner product/company hero images)
        try:
            with httpx.Client(timeout=12.0, headers=wiki_headers) as client:
                res = client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "generator": "search",
                        "gsrsearch": query,
                        "gsrlimit": "3",
                        "prop": "pageimages",
                        "pithumbsize": "1280",
                        "format": "json",
                    },
                )
                if res.status_code == 200:
                    pages = res.json().get("query", {}).get("pages", {})
                    for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
                        thumb = page.get("thumbnail", {})
                        img_url = thumb.get("source")
                        w = thumb.get("width", 0)
                        h = thumb.get("height", 0)
                        if img_url and w >= 600 and h >= 340 and ".svg" not in img_url.lower():
                            saved = self.download_image(img_url, min_width=600, min_height=340)
                            if saved:
                                return saved
        except Exception as e:
            print(f"[ImageManager] Wikipedia image search failed for '{query}': {e}")

        # 2. Fallback to Wikimedia Commons high-res thumbnails
        try:
            with httpx.Client(timeout=12.0, headers=wiki_headers) as client:
                res = client.get(
                    "https://commons.wikimedia.org/w/api.php",
                    params={
                        "action": "query",
                        "generator": "search",
                        "gsrsearch": f"{query} filetype:bitmap",
                        "gsrnamespace": "6",
                        "gsrlimit": "4",
                        "prop": "imageinfo",
                        "iiprop": "url|mime|size",
                        "iiurlwidth": "1280",
                        "format": "json",
                    },
                )
                if res.status_code == 200:
                    pages = res.json().get("query", {}).get("pages", {})
                    for page in pages.values():
                        info = (page.get("imageinfo") or [{}])[0]
                        mime = (info.get("mime") or "").lower()
                        img_url = info.get("thumburl") or info.get("url")
                        w = info.get("thumbwidth") or info.get("width") or 0
                        h = info.get("thumbheight") or info.get("height") or 0
                        if img_url and ("jpeg" in mime or "png" in mime) and w >= 600 and h >= 340:
                            saved = self.download_image(img_url, min_width=600, min_height=340)
                            if saved:
                                return saved
        except Exception as e:
            print(f"[ImageManager] Wikimedia search failed for '{query}': {e}")
        return None

    @staticmethod
    def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip() if current else word
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def create_cover_card(self, title: str, topic: str, credibility: str = "") -> str:
        """Generates a crisp 1280x720 HD editorial cover card with Pillow."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        card_path = self.output_dir / f"cover_{timestamp}.png"

        clean_title = re.sub(r"<[^>]+>", "", title or "")
        clean_title = re.sub(r"[*_`]", "", clean_title)
        clean_title = re.sub(r"\s+", " ", clean_title).strip() or "Новости технологий и ИИ"

        clean_topic = re.sub(r"<[^>]+>", "", topic or "Tech").strip()
        theme_key = clean_topic.lower()
        accent_a, accent_b, badge_label = TOPIC_THEMES.get(
            theme_key, ((96, 165, 250), (129, 140, 248), clean_topic.upper() or "ТЕХНОЛОГИИ")
        )

        width, height = 1280, 720
        base = Image.new("RGBA", (width, height), (10, 14, 26, 255))

        # Soft blurred gradient glow orbs
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(glow)
        g_draw.ellipse((740, -180, 1420, 480), fill=(*accent_a, 95))
        g_draw.ellipse((-180, 320, 520, 920), fill=(*accent_b, 70))
        glow = glow.filter(ImageFilter.GaussianBlur(115))
        base = Image.alpha_composite(base, glow)

        # Subtle architectural grid + geometric arcs
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        o_draw = ImageDraw.Draw(overlay)
        for x in range(0, width, 64):
            o_draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 9), width=1)
        for y in range(0, height, 64):
            o_draw.line([(0, y), (width, y)], fill=(255, 255, 255, 9), width=1)

        o_draw.ellipse((940, -110, 1390, 340), outline=(*accent_a, 55), width=2)
        o_draw.ellipse((1010, -40, 1320, 270), outline=(255, 255, 255, 30), width=1)

        # Left vertical accent bar
        o_draw.rounded_rectangle((78, 86, 86, 588), radius=4, fill=(*accent_a, 235))

        # Top category pill badge
        badge_font = _load_font(BOLD_FONT_CANDIDATES, 20)
        badge_bbox = o_draw.textbbox((0, 0), badge_label, font=badge_font)
        badge_tw = badge_bbox[2] - badge_bbox[0]
        badge_th = badge_bbox[3] - badge_bbox[1]
        badge_w = badge_tw + 44
        badge_h = 46
        badge_x, badge_y = 114, 88
        o_draw.rounded_rectangle(
            (badge_x, badge_y, badge_x + badge_w, badge_y + badge_h),
            radius=23,
            fill=(*accent_a, 38),
            outline=(*accent_a, 165),
            width=2,
        )
        o_draw.text(
            (badge_x + 22 - badge_bbox[0], badge_y + (badge_h - badge_th) // 2 - badge_bbox[1]),
            badge_label,
            font=badge_font,
            fill=(226, 232, 240, 255),
        )

        # Auto-fit headline size (from 54px down to 36px) so long titles fit cleanly in 4 lines
        max_text_w = 1040
        chosen_font = _load_font(BOLD_FONT_CANDIDATES, 50)
        lines: list[str] = []
        for font_size in (54, 48, 42, 36):
            candidate_font = _load_font(BOLD_FONT_CANDIDATES, font_size)
            candidate_lines = self._wrap_text(o_draw, clean_title, candidate_font, max_text_w)
            if len(candidate_lines) <= 4 or font_size == 36:
                chosen_font = candidate_font
                lines = candidate_lines[:4]
                if len(candidate_lines) > 4 and lines:
                    lines[-1] = lines[-1][: max(0, len(lines[-1]) - 3)].rstrip() + "..."
                break

        line_h = int(chosen_font.size * 1.32) if hasattr(chosen_font, "size") else 56
        total_text_h = line_h * len(lines)
        start_y = max(185, int(360 - total_text_h / 2))

        for i, line in enumerate(lines):
            y_pos = start_y + i * line_h
            o_draw.text((114, y_pos + 2), line, font=chosen_font, fill=(0, 0, 0, 120))
            o_draw.text((114, y_pos), line, font=chosen_font, fill=(248, 250, 252, 255))

        # Clean bottom footer strip (no artificial "Статус: официально" or "ДЕТАЛЬНЫЙ РАЗБОР")
        o_draw.line([(114, 594), (1180, 594)], fill=(255, 255, 255, 32), width=1)
        footer_bold = _load_font(BOLD_FONT_CANDIDATES, 21)
        footer_reg = _load_font(REGULAR_FONT_CANDIDATES, 20)

        brand_text = "AI SLOP NEWS"
        brand_bbox = o_draw.textbbox((0, 0), brand_text, font=footer_bold)
        brand_w = brand_bbox[2] - brand_bbox[0]

        o_draw.ellipse((114, 628, 126, 640), fill=(*accent_a, 255))
        o_draw.text((140, 621), brand_text, font=footer_bold, fill=(226, 232, 240, 240))
        o_draw.text((140 + brand_w + 20, 622), "@NewsAiSlop", font=footer_reg, fill=(148, 163, 184, 220))

        date_str = datetime.now().strftime("%d.%m.%Y")
        date_bbox = o_draw.textbbox((0, 0), date_str, font=footer_reg)
        o_draw.text((1180 - (date_bbox[2] - date_bbox[0]), 622), date_str, font=footer_reg, fill=(148, 163, 184, 200))

        final_img = Image.alpha_composite(base, overlay).convert("RGB")
        final_img.save(card_path, format="PNG", optimize=True)
        return str(card_path)
