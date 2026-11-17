"""LLM analyzer for intelligence synthesis, clustering, and insight generation."""
import json
import os
from typing import Any, Dict, List, Optional
import httpx
from .storage import Item


ANALYSIS_SYSTEM_PROMPT = """Ты — ведущий аналитик по конкурентной разведке и мониторингу рынка.
Твоя задача — изучить собранные новости, обновления конкурентов и посты из каналов, и подготовить сжатый, качественный дайджест для публикации в Telegram-канале для руководства и продуктовой команды.

Требования к ответу:
1. Выдели только СУТЬ и реальные изменения (запуски фич, изменения цен, крупные инфоповоды, новые партнерства, технические апдейты). Отфильтруй шум и воду.
2. Сформируй готовый текст для Telegram (telegram_digest) на русском языке с использованием эмодзи, списков и жирного шрифта.
3. Верни строгий JSON-объект следующей структуры:
{
  "telegram_digest": "Готовый текст поста для Telegram канала с заголовком #ДайджестРынка, блоками по конкурентам и разделом 'Ключевые инсайты'",
  "topic_distribution": {
    "Фичи и Продукт": 3,
    "Маркетинг и PR": 2,
    "Цены и Тарифы": 1,
    "Технологии и ИИ": 4
  },
  "competitor_mentions": {
    "CompetitorA": 2,
    "CompetitorB": 1
  },
  "impact_rating": {
    "Высокое влияние": 1,
    "Среднее влияние": 3,
    "Низкое влияние": 2
  }
}
Ответ ДОЛЖЕН БЫТЬ только валидным JSON без markdown обертки ```json.
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
            comp = f" [Конкурент/Источник: {item.competitor or item.source_name}]"
            items_text.append(
                f"{i}. {item.title}{comp}\n"
                f"   URL: {item.url}\n"
                f"   Текст: {item.content[:500]}\n"
            )

        user_content = (
            f"Проанализируй следующие {len(items)} собранных материалов за последнее время:\n\n"
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
