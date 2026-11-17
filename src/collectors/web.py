"""Generic Web page scraper for blogs, release notes, or competitor news pages."""
import re
from typing import List
from bs4 import BeautifulSoup
import httpx
from ..storage import Item


class WebPageCollector:
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

        try:
            with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
                response = client.get(self.url)
                if response.status_code != 200:
                    print(f"[WebCollector] Status {response.status_code} for {self.url}")
                    return items

                soup = BeautifulSoup(response.text, "html.parser")

                # Remove scripts, styles
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()

                # Find article elements or main content
                articles = soup.find_all(["article", "div.post", "div.news-item", "div.entry"])
                if not articles:
                    # Fallback: grab main body text
                    main_body = soup.find(["main", "div#content", "body"])
                    text = main_body.get_text(separator="\n").strip() if main_body else ""
                    # Compress whitespace
                    text = re.sub(r"\n\s*\n+", "\n\n", text)
                    if text:
                        page_title = soup.title.string.strip() if soup.title else self.name
                        items.append(
                            Item(
                                url=self.url,
                                title=page_title,
                                source_name=self.name,
                                source_type="web",
                                competitor=self.competitor,
                                content=text[:3000],
                            )
                        )
                else:
                    for art in articles[:10]:
                        title_el = art.find(["h1", "h2", "h3", "h4", "a"])
                        link_el = art.find("a", href=True)
                        if not title_el:
                            continue
                        title = title_el.get_text().strip()
                        link = link_el["href"] if link_el else self.url
                        if link.startswith("/"):
                            from urllib.parse import urljoin
                            link = urljoin(self.url, link)
                        text = art.get_text(separator=" ").strip()
                        text = re.sub(r"\s+", " ", text)
                        items.append(
                            Item(
                                url=link,
                                title=title,
                                source_name=self.name,
                                source_type="web",
                                competitor=self.competitor,
                                content=text[:2000],
                            )
                        )
        except Exception as e:
            print(f"[WebCollector] Error fetching {self.url}: {e}")

        return items
