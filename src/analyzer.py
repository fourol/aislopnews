"""LLM analyzer for in-depth editorial articles with ad filtering and clean paragraph formatting."""
import json
import re
from typing import Any, Dict, List, Optional
import httpx
from .storage import Item


AD_PATTERNS = [
    re.compile(r"\berid\b", re.IGNORECASE),
    re.compile(r"#(?:реклама|партн[её]рск\w*|promo|ad)\b", re.IGNORECASE),
    re.compile(r"(?:на правах рекламы|рекламн(?:ый|ая|ое)\s+(?:пост|материал|интеграция)|партн[её]рский\s+материал)", re.IGNORECASE),
    re.compile(r"(?:по\s+промокоду|промокод\s*[:«\"'A-Z0-9_-]{3,}|скидк[аи]\s+по\s+(?:ссылке|промокоду))", re.IGNORECASE),
    re.compile(r"\b(?:ИНН|ОГРН)\s*:?\s*\d{10,15}\b"),
    re.compile(r"(?:лютой\s+выдаче|второй\s+занос|очередной\s+занос|pvp\s*[—–-]\s*без\s+комиссии|апгрейд\s+на\s+лютой)", re.IGNORECASE),
    re.compile(r"(?:подписывай(?:тесь|ся)\s+на\s+(?:канал|наш\s+канал|бота)|успей\s+(?:забрать|записаться)|бесплатн(?:ый|ом)\s+(?:вебинар|интенсив|марафон))", re.IGNORECASE),
    re.compile(r"(?:при\s+поддержке\s+(?:партн[её]ра|спонсора)|рекламодател[ья]|токен\s+рекламы)", re.IGNORECASE),
]


def is_advertisement(title: str, content: str) -> bool:
    """Returns True if the collected item is an obvious advertisement or promo integration."""
    combined = f"{title or ''}\n{content or ''}".strip()
    if not combined:
        return True
    return any(pattern.search(combined) for pattern in AD_PATTERNS)


ANALYSIS_SYSTEM_PROMPT = """Ты — опытный автор, редактор и техно-блогер для премиального Telegram-канала о технологиях, нейросетях/ИИ, играх, экосистеме Telegram и Web3.

🎯 ГЛАВНАЯ ЦЕЛЬ:
Выбери ИЗ ВСЕХ собранных материалов ОДНУ САМУЮ ИНТЕРЕСНУЮ ИЛИ ВАЖНУЮ НАСТОЯЩУЮ НОВОСТЬ и напиши по ней УВЛЕКАТЕЛЬНЫЙ, ЖИВОЙ, ЧИТАЕМЫЙ ПОСТ.
Не пытайся пересказать несколько тем по верхам — сфокусируйся на одной и раскрой её качественно.

✨ ПРЕМИУМ-ВЕРСТКА TELEGRAM (УРОВЕНЬ КАНАЛА 8+):
1. Заголовок: 1-я строка поста — яркий заголовок жирным шрифтом с тематическим эмодзи: 🔥 <b>Заголовок новости</b>.
2. Основной текст: 1-2 емких, легко читаемых абзаца, объясняющих суть события и почему это важно.
3. БЕЗ ВЫДУМАННЫХ ИЛИ ФОРМАЛЬНЫХ ЦИТАТ В КОНЦЕ:
   НИКОГДА не добавляй в конце поста блок вроде «💬 Цитата разработчиков: ...», «Представители компании: ...», теги <blockquote> / <blockquote expandable> или строки с '>'. Передавай все факты и реакцию своими словами прямо в основном тексте!
4. Спойлеры (<tg-spoiler>): если уместно скрыть интригу, цену или дату релиза — используй <tg-spoiler>скрытый текст</tg-spoiler>.

✍️ СТИЛЬ И ФОРМАТ (БЕЗ ШАБЛОНОВ И КЛИШЕ):
- Пиши разнообразно и живо, как крутой авторский Telegram-канал (в стиле Код Дурова, Wylsacom Red, Rozetked, The Verge).
- Никаких одинаковых штампованных плашек и искусственных цитат в конце!
- Оценка достоверности НЕ обязательна отдельной строкой — упоминай статус только если это действительно слух, утечка или спорный инсайд.

⌨️ ВЕРСТКА И ЧИТАЕМОСТЬ В TELEGRAM:
- Между абзацами и блоками ОБЯЗАТЕЛЬНО должна быть пустая строка (двойной перенос строки \\n\\n), чтобы текст не слипался!
- Важные факты, названия, цифры выделяй жирным (<b>текст</b>).
- Длина чистого текста (без учета тегов) строго 600–900 символов, чтобы текст гарантированно уместился в подписи к фото в одном сообщении.

🚫 ПРАВИЛА ФИЛЬТРАЦИИ И ЦЕНЗУРЫ:
1. КАТЕГОРИЧЕСКИЙ ЗАПРЕТ НА ВОЕННУЮ ТЕМАТИКУ (СВО):
   Строго запрещены любые темы военных действий, боевых столкновений, СВО, мобилизации, фронта, военных сводок, армейской техники и военной пропаганды. Если в материале есть военный контекст — КАТЕГОРИЧЕСКИ НЕ ВЫБИРАЙ ЕГО!

2. КАТЕГОРИЧЕСКИЙ ЗАПРЕТ НА РЕКЛАМУ, ПРОМО И КОММЕРЧЕСКИЕ ИНТЕГРАЦИИ:
   Строго запрещено выбирать рекламные посты, партнёрские интеграции, промоакции, скидки, тарифы облаков/хостингов/VPN/ботов, рекламу курсов, крипто-рулеток, подарков/кейсов, реферальных программ, розыгрышей и материалы с пометками erid / #реклама / ИНН / ОГРН. НИКОГДА не пересказывай чужую рекламу как новость! Выбирай только реальные технологические, игровые или ИИ-события.

3. РАЗРЕШЕНЫ И ПРИВЕТСТВУЮТСЯ ТЕХНОЛОГИЧЕСКИЕ БЛОКИРОВКИ И ОГРАНИЧЕНИЯ:
   Новости о блокировках и замедлениях от Роскомнадзора (РКН), сбоях Рунета, ограничениях интернета, блокировках сервисов (Discord, YouTube, Steam, Telegram, Cloudflare, VPN, игровых серверов), IT-законах и цифровом суверенитете — РАЗРЕШЕНЫ! Подавай их объективно, с технической точки зрения (что произошло, как это влияет на пользователей), без военной агитации.

ФОРМАТ ОТВЕТА (ЧИСТЫЙ JSON):
{
  "selected_item_index": 1,
  "headline": "Яркий заголовок темы БЕЗ HTML-тегов и без эмодзи (чистый текст для обложки)",
  "telegram_post": "Полный HTML-текст поста для Telegram с <b> и пустыми строками между абзацами (БЕЗ <blockquote> и без цитат в конце)",
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

    def analyze(self, items: List[Item], allow_quote: bool = False) -> Optional[Dict[str, Any]]:
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
            + "\n\nВыбери ОДНУ самую интересную реальную новость. "
            "Категорически исключай СВО, любые военные темы, а также ЛЮБУЮ рекламу, промоакции, скидки, тарифы сервисов и интеграции! "
            "Темы блокировок РКН, ограничений интернета, сбоев сервисов, IT, игр и ИИ полностью разрешены. "
            "Напиши живой пост в авторском стиле без <blockquote> и без каких-либо «цитат разработчиков» или «представителей» в конце. "
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

                    # Deduplicate repeated bold headline tags if model duplicated them
                    post = re.sub(r'^(?:\s*🔥\s*)*(?:<b>\s*)*(?:\s*🔥\s*)*(?:<b>\s*)*', '🔥 <b>', post)
                    post = re.sub(r'</b>\s*</b>', '</b>', post)

                    # If first line has open <b> without closing </b>, close it at the end of the headline
                    lines = post.split("\n")
                    if lines and '<b>' in lines[0] and '</b>' not in lines[0]:
                        lines[0] = lines[0] + '</b>'
                        post = '\n'.join(lines)

                    lines = post.split("\n")
                    # If line 0 (headline) is immediately followed by text on line 1, insert empty line
                    if len(lines) >= 2 and lines[0].strip() and lines[1].strip() and not lines[1].strip().startswith("<blockquote"):
                        lines.insert(1, "")
                        post = "\n".join(lines)

                    # Ensure clear headline at top if first line is a long narrative
                    first_line = post.split("\n", 1)[0].strip()
                    hl = parsed.get("headline", "").strip()
                    plain_first = re.sub(r'<[^>]+>', '', first_line)
                    if hl and hl.lower() not in plain_first.lower() and len(plain_first) > 90 and not first_line.startswith("<") and not first_line.startswith("🔥"):
                        post = f"🔥 <b>{hl}</b>\n\n{post}"

                    # Always strip blockquotes, markdown quotes, and tacked-on developer quote footers
                    post = re.sub(r'<blockquote[^>]*>.*?</blockquote>', '', post, flags=re.S | re.I)
                    post = re.sub(r'^\s*>\s?.*(?:\n|$)', '', post, flags=re.M)
                    post = re.sub(
                        r'\n*\s*💬\s*(?:<b>)?\s*(?:Цитата\s+разработчиков|Представители\s+[^:\n]+)[^\n]*(?:\n\s*«[^»]*»)?',
                        '',
                        post,
                        flags=re.I,
                    )

                    # Normalize excessive newlines
                    post = re.sub(r'\n{3,}', '\n\n', post)
                    parsed["telegram_post"] = post.strip()

                if "headline" in parsed and isinstance(parsed["headline"], str):
                    hl = re.sub(r'<[^>]+>', '', parsed["headline"])
                    hl = re.sub(r'[*_`]', '', hl)
                    parsed["headline"] = hl.strip()

                return parsed
        except Exception as e:
            print(f"[Analyzer] Exception during analysis: {e}")
            return None
