"""Image manager: downloads images from Telegram posts, searches web images, or creates styled cards."""
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


class ImageManager:
    def __init__(self, output_dir: str = "data/images"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_image(self, url: str) -> Optional[str]:
        """Downloads an image from a URL (e.g. Telegram CDN)."""
        if not url:
            return None
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = self.output_dir / f"image_{timestamp}.jpg"
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
                res = client.get(url)
                if res.status_code == 200 and len(res.content) > 1000:
                    with open(file_path, "wb") as f:
                        f.write(res.content)
                    return str(file_path)
        except Exception as e:
            print(f"[ImageManager] Error downloading image from {url}: {e}")
        return None

    def search_web_image(self, query: str) -> Optional[str]:
        """Searches for a relevant public image on Wikimedia Commons by query."""
        if not query:
            return None
        try:
            api_url = "https://commons.wikimedia.org/w/api.php"
            params = {
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": "3",
                "prop": "imageinfo",
                "iiprop": "url|mime",
                "format": "json",
            }
            headers = {"User-Agent": "MarketIntelBot/1.0 (contact@marketintel.local)"}
            with httpx.Client(timeout=15.0, headers=headers) as client:
                res = client.get(api_url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    pages = data.get("query", {}).get("pages", {})
                    for page_id, page in pages.items():
                        image_info = page.get("imageinfo", [])
                        if image_info:
                            img_url = image_info[0].get("url")
                            mime = image_info[0].get("mime", "")
                            if img_url and ("jpeg" in mime or "png" in mime or "jpg" in mime):
                                return self.download_image(img_url)
        except Exception as e:
            print(f"[ImageManager] Web image search failed for '{query}': {e}")
        return None

    def create_cover_card(self, title: str, topic: str, credibility: str = "") -> str:
        """Generates a stylish dark-themed news cover card if no photo is available."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        card_path = self.output_dir / f"cover_{timestamp}.png"

        bg_color = "#181825"
        text_color = "#cdd6f4"
        accent_color = "#89b4fa"

        fig, ax = plt.subplots(figsize=(10, 5.5), facecolor=bg_color)
        ax.set_facecolor(bg_color)
        ax.axis("off")

        # Category badge
        ax.text(
            0.08,
            0.85,
            f"⚡️ {topic.upper()} | ДЕТАЛЬНЫЙ РАЗБОР",
            color=accent_color,
            fontsize=13,
            fontweight="bold",
            va="center",
        )

        # Wrap title nicely
        import textwrap
        wrapped_title = "\n".join(textwrap.wrap(title, width=38))
        ax.text(
            0.08,
            0.55,
            wrapped_title,
            color=text_color,
            fontsize=18,
            fontweight="bold",
            va="center",
            linespacing=1.3,
        )

        # Credibility badge
        if credibility:
            cred_color = "#a6e3a1" if "подтвер" in credibility.lower() else "#fab387"
            ax.text(
                0.08,
                0.22,
                f"Статус: {credibility}",
                color=cred_color,
                fontsize=11,
                fontweight="bold",
                va="center",
            )

        # Footer
        ax.text(
            0.08,
            0.10,
            "AI & Web3 Intelligence • Fact-Checked Edition",
            color="#6c7086",
            fontsize=9,
            va="center",
        )

        plt.tight_layout()
        plt.savefig(card_path, dpi=200, bbox_inches="tight", facecolor=bg_color)
        plt.close(fig)

        return str(card_path)
