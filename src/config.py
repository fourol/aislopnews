"""Configuration models and loader."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import os
import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SourceConfig:
    name: str
    type: str  # 'rss', 'telegram', 'web'
    url: str
    category: str = "general"
    competitor: Optional[str] = None


@dataclass
class AppConfig:
    telegram_bot_token: str
    telegram_channel_id: str
    llm_api_key: str
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    sources: List[SourceConfig] = field(default_factory=list)
    digest_schedule_hours: int = 24
    max_items_per_run: int = 30


def load_config(config_path: str = "config.yaml") -> AppConfig:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "")
    llm_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    llm_base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    sources: List[SourceConfig] = []
    schedule_hours = 24
    max_items = 30

    cfg_file = Path(config_path)
    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            schedule_hours = data.get("settings", {}).get("schedule_hours", 24)
            max_items = data.get("settings", {}).get("max_items_per_run", 30)

            for s in data.get("sources", []):
                sources.append(
                    SourceConfig(
                        name=s.get("name", "Unknown"),
                        type=s.get("type", "rss"),
                        url=s.get("url", ""),
                        category=s.get("category", "general"),
                        competitor=s.get("competitor"),
                    )
                )

    return AppConfig(
        telegram_bot_token=bot_token,
        telegram_channel_id=channel_id,
        llm_api_key=llm_key,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        sources=sources,
        digest_schedule_hours=schedule_hours,
        max_items_per_run=max_items,
    )
