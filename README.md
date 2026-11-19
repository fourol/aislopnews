# 🤖 AI Slop News (`aislopnews`) v1.0.0

Автономный мультиплатформенный ИИ-новостник и аналитический агент для Telegram-каналов с современной веб-панелью управления. 

Агент в реальном времени мониторит новости технологий, искусственного интеллекта, видеоигр, экосистемы Telegram и Web3/NFT, отфильтровывает политику, анализирует материал через LLM, подбирает визуальное оформление (оригинальные фото из каналов или арт) и публикует стильные, живые посты единым сообщением под фотографией.

---

## 🌟 Ключевые возможности

* **Живой авторский стиль публикации**: Никаких роботизированных скучных шаблонов. Посты пишутся легким языком в стиле топовых техно-каналов (The Verge, Код Дурова, Rozetked).
* **Единый пост с фото (Single Message Delivery)**: Текст гарантированно умещается в лимит подписи к фотографии в Telegram (до 1024 символов) с чистым разделением абзацев пустыми строками (`\n\n`).
* **Умный сбор графики (Image Pipeline)**:
  1. Автоматическое скачивание оригинальных фото высокого разрешения из постов Telegram-каналов (`cdn4.telesco.pe`).
  2. Интеллектуальный поиск иллюстраций в Wikimedia Commons при отсутствии фото в источнике.
  3. Автоматическая генерация минималистичной dark-mode обложки карточки при необходимости.
* **Строгая фильтрация политики**: Полный запрет на военные сводки, чиновников, геополитику, санкции и пропаганду — только чистые технологии, геймдев, ИИ и Web3.
* **Современная веб-панель управления (FastAPI + Tailwind CSS)**:
  - Мгновенная публикация по кнопке *(«🚀 Опубликовать сейчас»)*.
  - Управление источниками (Telegram, RSS, Web) без ручного редактирования конфигов.
  - Настройка таймингов и интервала автопостинга.
  - Журнал последних собранных материалов и статус фоновых сервисов.
  - Защита сессий администратора по паролю.
* **Надежное хранилище (SQLite + SHA-256)**: Исключает любые повторные публикации одних и тех же новостей.
* **Полная совместимость с LLM**: Поддержка OpenRouter, OpenAI, Groq, DeepSeek и любых OpenAI-compatible API.

---

## 🏗 Архитектура

```
┌──────────────────────────────────────┐
│          Источники данных            │
│  • Публичные каналы Telegram         │
│  • RSS / Atom ленты                  │
│  • Веб-страницы и блоги              │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│    Слой хранения (SQLite / SHA-256)  │
│  • Защита от дублей новостей         │
│  • Хранение URL оригинальных фото    │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│         LLM Редактор (OpenRouter)    │
│  • Выбор ключевого инфоповода        │
│  • Фильтрация политики               │
│  • Верстка с красивыми абзацами      │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│        Менеджер изображений          │
│  • Загрузка из Telegram CDN          │
│  • Поиск в сети / Генерация обложки  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│         Публикация в Telegram        │
│  • sendPhoto с полным текстом        │
│  • Канал: @your_channel              │
└──────────────────────────────────────┘
                   ▲
                   │ Управление через
┌──────────────────┴───────────────────┐
│        Веб-панель (FastAPI)          │
│  • HTTPS (Let's Encrypt / Nginx)     │
│  • Кнопка ручного запуска            │
│  • Статистика и источники            │
└──────────────────────────────────────┘
```

---

## 🚀 Быстрый запуск

### 1. Клонирование и установка зависимостей
```bash
git clone https://github.com/fourol/aislopnews.git
cd aislopnews

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Конфигурация `.env`
Создайте файл `.env`:
```env
# Telegram Bot
TELEGRAM_BOT_TOKEN="your_bot_token_here"
TELEGRAM_CHANNEL_ID="@your_channel_name"

# LLM API (OpenRouter / OpenAI)
LLM_API_KEY="sk-or-v1-..."
LLM_BASE_URL="https://openrouter.ai/api/v1"
LLM_MODEL="openai/gpt-4o-mini"

# Admin Web Panel
ADMIN_PASSWORD="your_secure_password"
```

### 3. Настройка источников (`config.yaml`)
```yaml
settings:
  schedule_hours: 2
  max_items_per_run: 25

sources:
  - name: "Lalyou NFT & Web3"
    type: "telegram"
    url: "lalyounft"

  - name: "Geodema News"
    type: "telegram"
    url: "GeodemaNews"

  - name: "TG Info"
    type: "telegram"
    url: "tginfo"

  - name: "Хабр: ИИ"
    type: "rss"
    url: "https://habr.com/ru/rss/hub/artificial_intelligence/all/?fl=ru"
```

---

## 💻 Режимы запуска

```bash
# Тестовый прогон (вывод поста и фото в консоль без отправки в канал):
python main.py --dry-run

# Одиночный сбор и отправка в канал:
python main.py --run-once

# Запуск фонового планировщика:
python main.py --schedule

# Запуск веб-панели управления:
uvicorn panel:app --host 0.0.0.0 --port 8888
```

---

## 🌐 Развертывание в продакшене (systemd)

Сервисы для демонизации на Linux-сервере:

* `/etc/systemd/system/market-intel.service` — планировщик регулярного мониторинга:
```ini
[Unit]
Description=AI Slop News Agent Scheduler
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/aislopnews
ExecStart=/root/aislopnews/.venv/bin/python main.py --schedule
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

* `/etc/systemd/system/market-intel-panel.service` — веб-панель управления:
```ini
[Unit]
Description=AI Slop News Admin Panel
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/aislopnews
ExecStart=/root/aislopnews/.venv/bin/uvicorn panel:app --host 127.0.0.1 --port 8888
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

---

## 📦 Релизы и версионирование

* **v1.0.0 (Релиз)**:
  - Первоначальный стабильный релиз проекта **AI Slop News**.
  - Веб-панель администратора с SSL (`aislop.fourol.eu.cc`).
  - Парсинг Telegram CDN фото и дедупликация через SQLite.
  - Гибкий стиль генерации постов без шаблонных плашек.
  - Автоматическая верстка с отступами между абзацами.

---

## 📄 Лицензия
MIT License.
