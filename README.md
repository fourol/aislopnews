# AI Slop News (`aislopnews`) v1.0.1

Автономный сервис мониторинга, фильтрации и публикации технологических новостей для Telegram-каналов с веб-панелью управления.

Система собирает материалы из публичных Telegram-каналов, RSS-лент и веб-страниц, исключает дубликаты и рекламный контент, анализирует новости с помощью LLM (OpenRouter / OpenAI-совместимые API), подбирает или генерирует графику и публикует итоговый материал единым сообщением в Telegram.

---

## Основные возможности

- **Сбор данных из нескольких типов источников**:
  - Публичные Telegram-каналы через веб-предпросмотр (`t.me/s/<channel>`) с извлечением оригинальных изображений (`cdn4.telesco.pe`).
  - RSS и Atom ленты с повторными попытками при сетевых и TLS-ошибках.
  - Произвольные веб-страницы.
- **Фильтрация контента и дедупликация**:
  - Хранение истории в SQLite с SHA-256 хешированием URL для исключения повторных публикаций.
  - Предварительный отсев рекламных и партнерских постов (`erid`, `#реклама`, промокоды, `ИНН`/`ОГРН`, розыгрыши, пустые медиапосты) до отправки в языковую модель.
  - Строгая фильтрация нежелательной тематики и отказ от искусственных цитат в системном промпте и пост-обработке.
- **Отказоустойчивый LLM-анализ**:
  - Поддержка OpenRouter, OpenAI, Groq, DeepSeek и любых OpenAI-совместимых API.
  - Автоматическое переключение на список резервных моделей (`LLM_FALLBACK_MODELS`, включая `:free`-роутинг OpenRouter) при сбоях, лимитах (429) или исчерпании средств (402) на основной модели.
- **Подготовка изображений**:
  - Загрузка оригинального фото из источника, поиск в Wikimedia Commons или генерация обложки через `matplotlib`.
- **Публикация в Telegram**:
  - Отправка поста единым сообщением через `sendPhoto` / `sendMessage` с HTML-форматированием и соблюдением лимита подписи (до 1024 символов).
- **Веб-панель администрирования (FastAPI + Tailwind CSS)**:
  - Авторизация по паролю (`PANEL_PASSWORD`).
  - Ручной запуск внеплановой публикации.
  - Управление списком источников и интервалом планировщика без ручной правки файлов на сервере.
  - Просмотр журналов работы (поддержка `systemd`/`journalctl` и файловых логов в Docker).
- **Контейнеризация**:
  - Готовые `Dockerfile` и `docker-compose.yml` для раздельного запуска планировщика и веб-панели.

---

## Архитектура

```
+------------------------------------------+
|             Источники данных             |
|  - Публичные каналы Telegram             |
|  - RSS / Atom ленты                      |
|  - Веб-страницы                          |
+--------------------+---------------------+
                     |
                     v
+------------------------------------------+
|     Хранилище и предфильтрация           |
|  - SQLite + SHA-256 дедупликация         |
|  - Отсев рекламы и пустых публикаций     |
+--------------------+---------------------+
                     |
                     v
+------------------------------------------+
|        LLM-анализатор (OpenRouter)       |
|  - Выбор ключевого события               |
|  - Резервные модели (LLM_FALLBACK_MODELS)|
|  - Форматирование HTML-поста             |
+--------------------+---------------------+
                     |
                     v
+------------------------------------------+
|           Менеджер изображений           |
|  - Загрузка из Telegram CDN              |
|  - Поиск в Wikimedia Commons / обложка   |
+--------------------+---------------------+
                     |
                     v
+------------------------------------------+
|          Публикация в Telegram           |
|  - Bot API (sendPhoto / sendMessage)     |
+------------------------------------------+
                     ^
                     | Управление
+--------------------+---------------------+
|         Веб-панель (FastAPI)             |
|  - Обратный прокси Nginx + HTTPS         |
|  - Мониторинг логов и управление         |
+------------------------------------------+
```

---

## Быстрый старт (локально)

### 1. Клонирование и установка зависимостей

```bash
git clone https://github.com/fourol/aislopnews.git
cd aislopnews

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Конфигурация `.env`

Создайте файл `.env` на основе `.env.example`:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN="your_bot_token_here"
TELEGRAM_CHANNEL_ID="@your_channel_name"

# LLM API (OpenRouter / OpenAI-compatible)
LLM_API_KEY="sk-or-v1-..."
LLM_BASE_URL="https://openrouter.ai/api/v1"
LLM_MODEL="openai/gpt-4o-mini"
LLM_FALLBACK_MODELS="openrouter/free,nvidia/nemotron-3-ultra-550b-a55b:free,nvidia/nemotron-3.5-lightning:free"

# Веб-панель администратора
PANEL_PASSWORD="your_secure_password"
```

### 3. Настройка источников (`config.yaml`)

```yaml
settings:
  schedule_hours: 6
  max_items_per_run: 25

sources:
  - name: "TG Info"
    type: "telegram"
    url: "tginfo"

  - name: "Хабр: Искусственный Интеллект"
    type: "rss"
    url: "https://habr.com/ru/rss/hub/artificial_intelligence/all/?fl=ru"
```

---

## Режимы запуска

```bash
# Тестовый прогон без отправки в Telegram и без изменения статуса БД:
python main.py --dry-run

# Одиночный цикл сбора и публикации:
python main.py --run-once

# Запуск фонового планировщика:
python main.py --schedule

# Запуск веб-панели управления:
uvicorn panel:app --host 0.0.0.0 --port 8888
```

---

## Развертывание в Docker

Репозиторий содержит `Dockerfile`, `.dockerignore` и `docker-compose.yml`, разделяющий планировщик (`bot`) и веб-панель (`panel`) с общими томами `./data` и `./config.yaml`.

```bash
docker compose up -d --build
```

После запуска панель доступна на порту `8888`. При необходимости проксирования по HTTPS используется внешний Nginx с проксированием на `http://127.0.0.1:8888`.

---

## Развертывание через systemd (Linux)

- `/etc/systemd/system/market-intel.service` — фоновый планировщик:

```ini
[Unit]
Description=AI Slop News Agent Scheduler
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/market-intel-agent
ExecStart=/root/market-intel-agent/.venv/bin/python main.py --schedule
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

- `/etc/systemd/system/market-intel-panel.service` — веб-панель управления:

```ini
[Unit]
Description=AI Slop News Admin Panel
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/market-intel-agent
ExecStart=/root/market-intel-agent/.venv/bin/python panel.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

---

## Релизы

### v1.0.1
- Добавлена предварительная и промптовая фильтрация рекламных и партнерских материалов (`erid`, `#реклама`, промокоды, `ИНН`/`ОГРН`, розыгрыши).
- Удалены принудительные цитаты разработчиков и `blockquote`-блоки в конце публикаций.
- Реализовано автоматическое переключение на резервные LLM-модели (`LLM_FALLBACK_MODELS`) при ошибках 402/429/5xx.
- Добавлены повторные попытки при временных сетевых и TLS-ошибках в `RSSCollector`.
- Добавлены `Dockerfile`, `.dockerignore`, `docker-compose.yml` и поддержка работы панели/планировщика без `systemd`.
- Документация `README.md` переведена в строгий технический формат.

### v1.0.0
- Первоначальный релиз автономного новостного агента и веб-панели управления.
- Поддержка сбора Telegram CDN фото, дедупликации через SQLite и гибкой HTML-верстки постов.

---

## Лицензия

MIT License.
