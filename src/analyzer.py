"""LLM analyzer for intelligence synthesis, clustering, and insight generation."""
import json
import os
from typing import Any, Dict, List, Optional
import httpx
from .storage import Item


ANALYSIS_SYSTEM_PROMPT = """Ты — ведущий аналитик и редактор дайджеста для Telegram-канала.
Твоя тематика: Искусственный Интеллект (AI), NFT / Web3 / TON, экосистема Telegram (обновления, Stars, мини-аппы), игровая индустрия (гейминг) и глобальные технологии.

⛔️ СТРОЖАЙШЕЕ ПРАВИЛО ФИЛЬТРАЦИИ (БЕЗ ПОЛИТИКИ):
Полностью исключай любые политические новости: военные конфликты, геополитику, высказывания чиновников, санкционные споры, госпропаганду и любые токсичные политические темы. 
Дайджест должен быть строго про ТЕХНОЛОГИИ, ИИ, ИГРЫ, ОБНОВЛЕНИЯ, ПРОДУКТЫ И ИНСАЙТЫ. Если новость имеет политический окрас — полностью пропусти её!

Требования к оформлению дайджеста (telegram_digest):
1. Яркий заголовок с эмодзи: например, «🌐 TECH & AI DIGEST | Ключевые события»
2. Разделение по тематическим блокам:
   - 🤖 **Искусственный Интеллект & Нейросети**
   - 💎 **Telegram, TON & NFT/Web3**
   - 🎮 **Гейминг & Игровая индустрия**
   - ⚡️ **Глобальный Tech & Гаджеты**
   - 💡 **Главный инсайт / тренд дня**
3. Пиши живо, емко, без воды, только реальную суть изменений и почему это важно. Ссылки оставляй кликабельными, если есть URL.

Верни строгий JSON-объект следующего формата:
{
  "telegram_digest": "Готовый текст поста для Telegram канала с форматированием Markdown",
  "topic_distribution": {
    "ИИ и Нейросети": 3,
    "Telegram & TON/NFT": 2,
    "Игры и Геймдев": 2,
    "Глобальный Tech": 1
  },
  "competitor_mentions": {
    "Источник/Компания 1": 2,
    "Источник/Компания 2": 1
  },
  "impact_rating": {
    "Высокое влияние": 2,
    "Среднее влияние": 3
  }
}
Ответ ДОЛЖЕН БЫТЬ только валидным JSON без лишних префиксов и без markdown обертки ```json.
"""


class Analyzer:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def analyze(self, items: List[Item]) -> Optional[Dict[str, Any]]:
        if not items:
            return None

        # Build prompt content from items
        items_text = []
        for i, item in enumerate(items, 1):
            source_tag = f" [{item.competitor or item.source_name}]"
            items_text.append(
                f"{i}. {item.title}{source_tag}\n"
                f"   URL: {item.url}\n"
                f"   Текст: {item.content[:500]}\n"
            )

        user_content = (
            f"Проанализируй следующие {len(items)} собранных материалов. "
            "Отфильтруй всю политику и сформируй технологический дайджест:\n\n"
            + "\n".join(items_text)
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
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

                # Clean possible markdown fence if model added it
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
