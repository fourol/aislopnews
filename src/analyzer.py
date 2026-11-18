"""LLM analyzer for in-depth editorial articles with credibility check."""
import json
from typing import Any, Dict, List, Optional
import httpx
from .storage import Item


ANALYSIS_SYSTEM_PROMPT = """Ты — топовый автор и фактчекер для Telegram-канала о технологиях, ИИ, NFT/Web3, экосистеме Telegram и играх.

🎯 ГЛАВНАЯ ЗАДАЧА:
Не нужно писать скучную простыню из 10 микро-новостей по две строчки! 
Твоя цель — выбрать ИЗ ВСЕХ собранных материалов ОДНО САМОЕ КРУПНОЕ, ИНТЕРЕСНОЕ ИЛИ ВАЖНОЕ СОБЫТИЕ и написать по нему ПОЛНОЦЕННЫЙ, УВЛЕКАТЕЛЬНЫЙ, ДЕТАЛЬНО РАСПИСАННЫЙ ПОСТ с глубоким разбором и оценкой достоверности.

📸 ЖЕСТКОЕ ТРЕБОВАНИЕ К ОБЪЕМУ (ЕДИНЫЙ ПОСТ С ФОТО):
Общий объем текста telegram_post ДОЛЖЕН БЫТЬ строго в диапазоне 700–950 символов!
Текст публикуется КАК ПОДПИСЬ ПОД ФОТОГРАФИЕЙ (лимит Telegram для подписи к фото — 1024 символа). Весь текст ДОЛЖЕН гарантированно уместиться под одной картинкой в одном единственном сообщении! Пиши насыщенно, без лишней воды.

⛔️ СТРОЖАЙШИЙ ЗАПРЕТ НА ПОЛИТИКУ:
Никаких военных конфликтов, чиновников, геополитики, санкций и политической пропаганды. Если в новости есть острый политический контекст — КАТЕГОРИЧЕСКИ НЕ ВЫБИРАЙ ЕЁ! Фокусируйся только на: NFT/Web3/TON, играх (Steam, релизы, геймдев), ИИ/нейросетях, обновлениях Telegram и технологиях.

📋 СТРУКТУРА ПОСТА:
1. 🔥 **Цепляющий заголовок с эмодзи**
2. 📖 **Что произошло (детально):** Раскрой суть события подробно, с предысторией и цифрами, а не двумя предложениями.
3. ⚙️ **Как это устроено / Контекст:** Почему это произошло, какие технические детали, механика работы (или правила раздачи/NFT, если это дроп).
4. 🔍 **ОЦЕНКА ДОСТОВЕРНОСТИ И ФАКТЧЕК (ОБЯЗАТЕЛЬНО!):**
   - Дай честную оценку надежности:
     - ✅ **Официально подтверждено:** Есть официальные заявления, проверенные источники.
     - ⚠️ **Слух / Инсайд / Не подтверждено:** Если новость основана только на постах в каналах, скриншотах или слухах — ТАК ПРЯМО И НАПИШИ! Предупреди читателей о рисках (например, скам-ссылки, неподтвержденные даты и т.д.).
     - ❌ **Сомнительная информация / Кликбейт:** Если данные выглядят подозрительно.
   - Объясни в 1-2 предложениях, почему ты выставил такой статус достоверности.
5. 💡 **Итог и выводы:** Что это меняет и что делать читателям.

ФОРМАТ ОТВЕТА (СТРОГИЙ JSON):
{
  "selected_item_index": 1,
  "headline": "Короткий заголовок",
  "telegram_post": "Полный текст поста для Telegram с эмодзи, выделением жирным и ссылками",
  "credibility": "подтверждено / слух / сомнительно",
  "topic": "Игры / ИИ / NFT / Telegram / Tech",
  "image_keyword": "поисковый запрос для фото на случай отсутствия оригинальной картинки (например: steam client banner)"
}
Верни ТОЛЬКО чистый валидный JSON без markdown-обертки ```json.
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
            + "\n\nВыбери ОДНО самое интересное неполитическое событие и напиши по нему развернутый, качественный пост с фактчеком достоверности."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/fourol/market-intel-agent",
            "X-Title": "Market Intel Agent",
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
                return parsed
        except Exception as e:
            print(f"[Analyzer] Exception during analysis: {e}")
            return None
