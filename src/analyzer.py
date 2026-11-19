"""LLM analyzer for in-depth editorial articles with credibility check and clean paragraph formatting."""
import json
import re
from typing import Any, Dict, List, Optional
import httpx
from .storage import Item


ANALYSIS_SYSTEM_PROMPT = """Ты — опытный автор, редактор и техно-блогер для премиального Telegram-канала о технологиях, нейросетях/ИИ, играх, экосистеме Telegram и Web3.

🎯 ГЛАВНАЯ ЦЕЛЬ:
Выбери ИЗ ВСЕХ собранных материалов ОДНО САМОЕ ИНТЕРЕСНОЕ ИЛИ ВАЖНОЕ СОБЫТИЕ и напиши по нему УВЛЕКАТЕЛЬНЫЙ, ЖИВОЙ, ЧИТАЕМЫЙ ПОСТ.
Не пытайся пересказать несколько тем по верхам — сфокусируйся на одной и раскрой её качественно.

✨ ПРЕМИУМ-ВЕРСТКА TELEGRAM (УРОВЕНЬ КАНАЛА 8+):
Канал имеет высокий уровень бустов и поддерживает премиальное форматирование Telegram:
1. Заголовок: 1-я строка поста — яркий заголовок жирным шрифтом с тематическим эмодзи: 🔥 <b>Заголовок новости</b>.
2. Основной текст: 1-2 емких, легко читаемых абзаца, объясняющих суть события и почему это важно.
3. СВОРАЧИВАЕМАЯ ЦИТАТА (<blockquote expandable>):
   ОБЯЗАТЕЛЬНО используй тег <blockquote expandable>...</blockquote> для подробностей, цитат разработчиков, списков изменений, характеристик или технических нюансов.
   В Telegram эта плашка отображается фирменным цветом канала и аккуратно сворачивается под кнопку «Читать далее», сохраняя пост компактным и стильным!
   Пример:
   <blockquote expandable>⚙️ <b>Ключевые детали:</b>
   • Первая важная деталь или фича с контекстом.
   • Вторая важная деталь или цитата разработчика.</blockquote>
4. Спойлеры (<tg-spoiler>): если уместно скрыть интригу, цену или дату релиза — используй <tg-spoiler>скрытый текст</tg-spoiler>.

✍️ СТИЛЬ И ФОРМАТ (БЕЗ ШАБЛОНОВ И КЛИШЕ):
- Пиши разнообразно и живо, как крутой авторский Telegram-канал (в стиле Код Дурова, Wylsacom Red, Rozetked, The Verge).
- Никаких одинаковых штампованных плашек!
- Оценка достоверности НЕ обязательна отдельной строкой — упоминай статус только если это действительно слух, утечка или спорный инсайд.

⌨️ ВЕРСТКА И ЧИТАЕМОСТЬ В TELEGRAM:
- Между абзацами и блоками ОБЯЗАТЕЛЬНО должна быть пустая строка (двойной перенос строки \\n\\n), чтобы текст не слипался!
- Важные факты, названия, цифры выделяй жирным (<b>текст</b>).
- Длина чистого текста (без учета тегов) строго 650–920 символов, чтобы текст гарантированно уместился в подписи к фото в одном сообщении.

⛔️ СТРОЖАЙШИЙ ЗАПРЕТ НА ПОЛИТИКУ:
Никаких военных действий, чиновников, геополитики, санкций, законов и пропаганды. Только технологии, игры, ИИ/нейросети, гаджеты, Telegram, Web3/NFT.

ФОРМАТ ОТВЕТА (ЧИСТЫЙ JSON):
{
  "selected_item_index": 1,
  "headline": "Яркий заголовок темы",
  "telegram_post": "Полный HTML-текст поста для Telegram с <blockquote expandable>, <b>, пустыми строками между абзацами",
  "credibility": "официально / слух / инсайд",
  "topic": "ИИ / Игры / Telegram / Web3 / Tech",
  "image_keyword": "2-3 поисковых слова на английском для поиска картинки при необходимости"
}
Верни ТОЛЬКО валидный JSON без markdown-тегов ```json.
"""


class Analyzer:
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1", model: str = "openai/gpt-4o-mini"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def analyze(self, items: List[Item]) -> Optional[Dict[str, Any]]:
        if not items:
            return None

        items_text = []
        for i, item in enumerate(items, 1):
            source_tag = f" [{item.source_name}]"
            has_photo = " (Есть фото в посте)" if item.image_url else ""
            items_text.append(
                f"[{i}] {item.title}{source_tag}{has_photo}\n"
                f"    URL: {item.url}\n"
                f"    Текст: {item.content[:600]}\n"
            )

        user_content = (
            f"Вот {len(items)} собранных материалов из каналов и лент:\n\n"
            + "\n".join(items_text)
            + "\n\nВыбери ОДНО самое интересное неполитическое событие. "
            "Напиши премиум-пост для Telegram с использованием сворачиваемой цитаты <blockquote expandable>...</blockquote> для глубоких деталей или списка фич. "
            "Обязательно делай пустые строки (двойной enter) между абзацами!"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/fourol/aislopnews",
            "X-Title": "AI Slop News Agent",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.4,
        }

        try:
            url = f"{self.base_url}/chat/completions"
            with httpx.Client(timeout=90.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code != 200:
                    print(f"[Analyzer] API Error: {res.status_code} - {res.text}")
                    return None

                response_data = res.json()
                raw_text = response_data["choices"][0]["message"]["content"].strip()

                if raw_text.startswith("```"):
                    raw_text = raw_text.split("\n", 1)[1]
                    if raw_text.endswith("```"):
                        raw_text = raw_text.rsplit("```", 1)[0]
                raw_text = raw_text.strip()

                parsed = json.loads(raw_text)

                # Post-processing: strictly guarantee clean paragraph separation and valid HTML
                if "telegram_post" in parsed and isinstance(parsed["telegram_post"], str):
                    post = parsed["telegram_post"].strip().replace("\r\n", "\n")

                    # Convert any markdown bold **text** to <b>text</b>
                    post = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', post)

                    lines = post.split("\n")
                    # If line 0 (headline) is immediately followed by text on line 1, insert empty line
                    if len(lines) >= 2 and lines[0].strip() and lines[1].strip() and not lines[1].strip().startswith("<blockquote"):
                        lines.insert(1, "")
                        post = "\n".join(lines)

                    # Ensure clear headline at top if first line is a long narrative
                    first_line = post.split("\n", 1)[0].strip()
                    hl = parsed.get("headline", "").strip()
                    plain_first = re.sub(r'<[^>]+>', '', first_line)
                    if hl and hl.lower() not in plain_first.lower() and len(plain_first) > 90 and not first_line.startswith("<"):
                        post = f"🔥 <b>{hl}</b>\n\n{post}"

                    # Ensure empty line between sentence ends and capital letters / lists (outside tags)
                    post = re.sub(r'([.!?»\)])\n([A-ZА-ЯЁ0-9\*\#\-\•])', r'\1\n\n\2', post)
                    # Normalize excessive newlines
                    post = re.sub(r'\n{3,}', '\n\n', post)
                    parsed["telegram_post"] = post.strip()

                return parsed
        except Exception as e:
            print(f"[Analyzer] Exception during analysis: {e}")
            return None
