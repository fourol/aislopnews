# 🕵️ Market & Competitor Intelligence Agent (Telegram Edition)

Автономный ИИ-агент для непрерывного мониторинга рынка, конкурентов и новостей с синтезом инсайтов через LLM, генерацией аналитических графиков и автоматической публикацией дайджестов в Telegram-канал.

---

## 🏗 Архитектура решения

```
┌────────────────────────────────┐
│  Источники данных              │
│  - RSS / Atom ленты новостей   │
│  - Telegram-каналы (t.me/s/..) │
│  - Веб-страницы / блоги        │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  Слой хранения (SQLite)        │
│  - Хеширование URL/заголовков  │
│  - Дедупликация (без повторов) │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  LLM Аналитик (OpenAI-compat)  │
│  - Выжимка сути (без воды)     │
│  - Кластеризация по темам      │
│  - Оценка влияния и инсайты    │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  Генератор графиков            │
│  - Стильный dark-mode чарт     │
│  - Распределение по темам      │
│  - Активность конкурентов      │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  Публикатор в Telegram         │
│  - Фото графика + дайджест     │
│  - Готово для команды/руковод- │
│    ства в вашем ТГ-канале      │
└────────────────────────────────┘
```

---

## 🚀 Быстрый старт

### 1. Настройка окружения
В проекте уже создано виртуальное окружение `.venv` и установлены все необходимые библиотеки:
```bash
source .venv/bin/activate
```

### 2. Настройка переменных окружения (`.env`)
Скопируйте пример или отредактируйте созданный `.env`:
```env
# Telegram:
TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_CHANNEL_ID="@your_channel_name"   # или -100xxxxxxxxxx

# LLM:
LLM_API_KEY="sk-..."                       # Ключ OpenAI, OpenRouter, DeepSeek или Groq
LLM_BASE_URL="https://api.openai.com/v1"   # или https://api.deepseek.com / https://openrouter.ai/api/v1
LLM_MODEL="gpt-4o-mini"                    # или deepseek-chat, mistralai/mistral-large
```

> **Важно по Telegram:**
> 1. Создайте бота через [@BotFather](https://t.me/BotFather) и скопируйте токен.
> 2. Создайте канал и **добавьте созданного бота в администраторы канала** с правом публикации сообщений.

### 3. Настройка источников (`config.yaml`)
В [config.yaml](file:///home/deck/Documents/ai/config.yaml) настраиваются цели для мониторинга:
```yaml
settings:
  schedule_hours: 12      # Периодичность проверки
  max_items_per_run: 25   # Лимит материалов на один дайджест

sources:
  - name: "Новости технологий"
    type: "rss"
    url: "https://..."
    competitor: "Конкурент 1"

  # Мониторинг публичных Telegram-каналов (без сессий и риска банов)
  - name: "Канал конкурента"
    type: "telegram"
    url: "durov"          # юзернейм канала (без @)
    competitor: "Telegram"

  # Мониторинг блогов или страниц релизов
  - name: "Блог конкурента"
    type: "web"
    url: "https://competitor.com/blog"
    competitor: "Competitor B"
```

---

## 🛠 Запуск агента

1. **Проверка подключения к Telegram:**
   Отправляет тестовое приветствие в ваш канал:
   ```bash
   .venv/bin/python main.py --test-tg
   ```

2. **Тестовый сбор без отправки в канал (Dry-Run):**
   Собирает данные, анализирует через ИИ, строит график и выводит дайджест прямо в терминал:
   ```bash
   .venv/bin/python main.py --dry-run
   ```

3. **Одиночный боевой запуск:**
   Собирает новые материалы, генерирует пост с графиком и отправляет в канал:
   ```bash
   .venv/bin/python main.py --run-once
   ```

4. **Запуск в режиме демона (фоновый сервис):**
   Работает непрерывно по расписанию из `config.yaml`:
   ```bash
   nohup .venv/bin/python main.py --schedule > agent.log 2>&1 &
   ```

---

## 📊 Структура проекта
* [main.py](file:///home/deck/Documents/ai/main.py) — Главная точка входа и CLI интерфейс.
* [src/collectors/](file:///home/deck/Documents/ai/src/collectors/) — Модули сбора (RSS, Web scraper, Telegram preview).
* [src/storage.py](file:///home/deck/Documents/ai/src/storage.py) — База данных SQLite с защитой от дублирования.
* [src/analyzer.py](file:///home/deck/Documents/ai/src/analyzer.py) — ИИ-модуль синтеза и выделения инсайтов.
* [src/charts.py](file:///home/deck/Documents/ai/src/charts.py) — Генератор графиков в тёмной теме.
* [src/telegram_bot.py](file:///home/deck/Documents/ai/src/telegram_bot.py) — Модуль отправки в Telegram.
