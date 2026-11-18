"""FastAPI Web Admin Panel for Market, Tech & Web3 Intelligence Agent."""
import collections
import html
import json
import os
import secrets
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.config import load_config
from src.storage import Storage

load_dotenv()

app = FastAPI(title="AI Slop Intel Panel")

# Secret token for simple admin session
ADMIN_PASSWORD = os.getenv("PANEL_PASSWORD", "admin123")
ACTIVE_SESSIONS = set()

# Ensure images dir exists and mount static route
images_path = Path("data/images")
images_path.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(images_path)), name="images")

CONFIG_PATH = Path("config.yaml")

# State for trigger & real-time logs
IS_RUNNING_JOB = False
LAST_JOB_STATUS = "Готов к работе"
RECENT_LOGS = collections.deque(maxlen=400)


def log_event(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    RECENT_LOGS.append(formatted)
    sys.__stdout__.write(formatted + "\n")
    sys.__stdout__.flush()


def get_service_logs(lines: int = 60) -> str:
    try:
        res = subprocess.run(
            ["journalctl", "-u", "market-intel", "-n", str(lines), "--no-pager"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=4,
        )
        out = res.stdout.strip()
        return out if out else "Логи службы пока пусты."
    except Exception as e:
        return f"Не удалось получить логи systemd: {e}"


def is_authenticated(session_token: Optional[str] = Cookie(None)) -> bool:
    if not session_token or session_token not in ACTIVE_SESSIONS:
        return False
    return True


def get_service_status() -> str:
    try:
        res = subprocess.run(
            ["systemctl", "is-active", "market-intel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def background_pipeline():
    global IS_RUNNING_JOB, LAST_JOB_STATUS
    IS_RUNNING_JOB = True
    LAST_JOB_STATUS = f"Сбор и анализ запущен [{datetime.now().strftime('%H:%M:%S')}]..."
    log_event("🚀 [МГНОВЕННЫЙ ВЫПУСК] Старт цикла мониторинга и публикации...")

    class CaptureStream:
        def write(self, s):
            sys.__stdout__.write(s)
            sys.__stdout__.flush()
            for line in s.splitlines():
                clean = line.strip()
                if clean:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    RECENT_LOGS.append(f"[{timestamp}] {clean}")

        def flush(self):
            sys.__stdout__.flush()

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    capture = CaptureStream()
    sys.stdout = capture
    sys.stderr = capture

    try:
        from main import run_pipeline
        run_pipeline(dry_run=False)
        LAST_JOB_STATUS = f"Успешно опубликовано [{datetime.now().strftime('%H:%M:%S')}]"
        log_event("✅ Цикл успешно завершен! Пост опубликован в Telegram.")
    except Exception as e:
        tb = traceback.format_exc()
        LAST_JOB_STATUS = f"Ошибка: {str(e)[:60]}"
        log_event(f"❌ ОШИБКА ВЫПОЛНЕНИЯ: {e}\n{tb}")
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        IS_RUNNING_JOB = False


@app.get("/login", response_class=HTMLResponse)
async def login_page(error: Optional[str] = None):
    error_html = f'<div class="p-3 mb-4 text-sm text-red-400 bg-red-950/50 border border-red-800 rounded-xl">{error}</div>' if error else ''
    return f"""
    <!DOCTYPE html>
    <html lang="ru" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Вход в панель управления | AI Slop News</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>body {{ font-family: 'Inter', sans-serif; }}</style>
    </head>
    <body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen px-4">
        <div class="w-full max-w-md p-8 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl">
            <div class="flex items-center justify-center gap-3 mb-6">
                <span class="text-3xl">🤖</span>
                <h1 class="text-2xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">AI Slop Intel Panel</h1>
            </div>
            <p class="text-slate-400 text-sm text-center mb-6">Панель управления новостным ИИ-ботом</p>
            {error_html}
            <form action="/login" method="post" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-1">Пароль администратора</label>
                    <input type="password" name="password" required autofocus placeholder="••••••••" 
                           class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <button type="submit" class="w-full py-2.5 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 font-semibold rounded-xl transition duration-200 shadow-lg shadow-blue-500/25">
                    Войти в панель
                </button>
            </form>
        </div>
    </body>
    </html>
    """


@app.post("/login")
async def login_submit(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        token = secrets.token_hex(16)
        ACTIVE_SESSIONS.add(token)
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=86400 * 30)
        return response
    return RedirectResponse(url="/login?error=Неверный%20пароль", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="session_token")
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session_token: Optional[str] = Cookie(None)):
    if not is_authenticated(session_token):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    config = load_config()
    storage = Storage()
    service_status = get_service_status()

    # Get recent posts
    recent_posts = []
    total_posts = 0
    try:
        with storage._get_connection() as conn:
            total_posts = conn.execute("SELECT COUNT(*) FROM digests").fetchone()[0]
            rows = conn.execute("SELECT * FROM digests ORDER BY id DESC LIMIT 10").fetchall()
            for r in rows:
                chart = r["chart_path"] or ""
                img_url = ""
                if chart and Path(chart).exists():
                    img_url = f"/images/{Path(chart).name}"
                recent_posts.append({
                    "id": r["id"],
                    "created_at": r["created_at"][:16].replace("T", " "),
                    "text": r["summary_text"],
                    "image": img_url,
                    "items_count": r["item_count"]
                })
    except Exception as e:
        print("Error fetching digests:", e)

    # Build sources table HTML
    sources_html = ""
    for idx, s in enumerate(config.sources):
        badge_color = "bg-blue-500/10 text-blue-400 border-blue-500/20" if s.type == "telegram" else "bg-amber-500/10 text-amber-400 border-amber-500/20"
        sources_html += f"""
        <tr class="border-b border-slate-800/60 hover:bg-slate-800/30 transition">
            <td class="py-3 px-4 font-medium text-slate-200">{s.name}</td>
            <td class="py-3 px-4">
                <span class="px-2.5 py-1 text-xs rounded-full border {badge_color} uppercase font-semibold">{s.type}</span>
            </td>
            <td class="py-3 px-4 text-slate-400 font-mono text-sm">{s.url}</td>
            <td class="py-3 px-4 text-slate-300 text-sm">{s.category}</td>
            <td class="py-3 px-4 text-right">
                <form action="/api/delete-source" method="post" onsubmit="return confirm('Удалить источник {s.name}?')" class="inline">
                    <input type="hidden" name="source_name" value="{s.name}">
                    <button type="submit" class="text-xs text-red-400 hover:text-red-300 font-medium py-1 px-2.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 transition">Удалить</button>
                </form>
            </td>
        </tr>
        """

    # Build posts cards HTML
    posts_html = ""
    for p in recent_posts:
        img_tag = f'<img src="{p["image"]}" class="w-full h-48 object-cover rounded-xl mb-3 border border-slate-700/50">' if p["image"] else ''
        text_preview = p["text"].replace("\n", "<br>")
        posts_html += f"""
        <div class="p-5 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-sm hover:border-slate-700 transition">
            <div class="flex items-center justify-between text-xs text-slate-400 mb-3">
                <span class="font-medium">📅 {p['created_at']}</span>
                <span class="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">Собрано из {p['items_count']} мат.</span>
            </div>
            {img_tag}
            <div class="text-sm text-slate-200 space-y-2 max-h-60 overflow-y-auto pr-2 leading-relaxed">
                {text_preview}
            </div>
        </div>
        """
    if not posts_html:
        posts_html = '<div class="col-span-2 text-center py-10 text-slate-500">Пока нет опубликованных постов</div>'

    # Interval options
    intervals = [1, 2, 3, 4, 6, 8, 12, 24]
    interval_options = "".join(
        f'<option value="{i}" {"selected" if config.digest_schedule_hours == i else ""}>Каждые {i} ч.</option>'
        for i in intervals
    )

    status_badge = (
        '<span class="px-3 py-1 text-xs rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5 font-medium"><span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>Активен (24/7)</span>'
        if service_status == "active"
        else f'<span class="px-3 py-1 text-xs rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center gap-1.5 font-medium"><span class="w-2 h-2 rounded-full bg-rose-400"></span>{service_status}</span>'
    )

    pipeline_logs_text = "\n".join(RECENT_LOGS) if RECENT_LOGS else "Логи ручного запуска пока пусты. Нажмите «Опубликовать прямо сейчас» для запуска."
    service_logs_text = get_service_logs(50)
    pipeline_logs_escaped = html.escape(pipeline_logs_text)
    pipeline_logs_json = json.dumps(pipeline_logs_text)
    service_logs_json = json.dumps(service_logs_text)

    return f"""
    <!DOCTYPE html>
    <html lang="ru" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Slop | Панель управления</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>body {{ font-family: 'Inter', sans-serif; }}</style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen pb-16">
        <!-- Top Navigation -->
        <header class="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-50">
            <div class="max-w-6xl mx-auto px-4 py-3.5 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <span class="text-2xl">🤖</span>
                    <div>
                        <h1 class="font-bold text-lg bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">AI Slop News Bot</h1>
                        <p class="text-xs text-slate-400">Панель управления новостным каналом</p>
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    <a href="https://t.me/NewsAiSlop" target="_blank" class="text-xs flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 text-blue-400 border border-blue-500/30 rounded-xl hover:bg-blue-500/20 transition">
                        ✈️ Перейти в канал
                    </a>
                    <a href="/logout" class="text-xs text-slate-400 hover:text-white transition">Выйти</a>
                </div>
            </div>
        </header>

        <main class="max-w-6xl mx-auto px-4 py-8 space-y-8">
            <!-- Stats / Quick actions card -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- Status & Action Card -->
                <div class="p-6 bg-slate-900 border border-slate-800 rounded-2xl flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between mb-4">
                            <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Служба бота</span>
                            {status_badge}
                        </div>
                        <h2 class="text-xl font-bold mb-1">Мгновенный выпуск</h2>
                        <p class="text-sm text-slate-400 mb-6">Собрать свежие новости прямо сейчас, проанализировать через ИИ и выложить в Telegram с фото.</p>
                    </div>
                    <form action="/api/publish-now" method="post" onsubmit="setTimeout(refreshLogs, 500)">
                        <button type="submit" id="publish-btn" {"disabled" if IS_RUNNING_JOB else ""} 
                                class="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 font-semibold rounded-xl transition duration-200 flex items-center justify-center gap-2 shadow-lg shadow-blue-500/25 disabled:opacity-50">
                            <span>🚀</span>
                            <span id="publish-btn-text">{"Идет публикация..." if IS_RUNNING_JOB else "Опубликовать пост прямо сейчас"}</span>
                        </button>
                        <p id="job-status-text" class="text-xs text-center text-slate-500 mt-2">{LAST_JOB_STATUS}</p>
                    </form>
                </div>

                <!-- Schedule Card -->
                <div class="p-6 bg-slate-900 border border-slate-800 rounded-2xl flex flex-col justify-between">
                    <div>
                        <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Расписание выпусков</span>
                        <h2 class="text-xl font-bold mt-2 mb-1">Периодичность</h2>
                        <p class="text-sm text-slate-400 mb-6">Как часто бот автоматически собирает каналы и выкладывает дайджест в канал.</p>
                    </div>
                    <form action="/api/set-interval" method="post" class="space-y-3">
                        <select name="hours" class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white font-medium focus:outline-none focus:ring-2 focus:ring-blue-500">
                            {interval_options}
                        </select>
                        <button type="submit" class="w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium rounded-xl border border-slate-700 transition">
                            💾 Сохранить интервал
                        </button>
                    </form>
                </div>

                <!-- Metrics Card -->
                <div class="p-6 bg-slate-900 border border-slate-800 rounded-2xl flex flex-col justify-between">
                    <div>
                        <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Канал & Статистика</span>
                        <h2 class="text-xl font-bold mt-2 mb-1">@NewsAiSlop</h2>
                        <p class="text-sm text-slate-400 mb-6">Тематика: ИИ, Web3, Telegram, игры без политики с проверкой достоверности.</p>
                    </div>
                    <div class="p-4 bg-slate-950/60 border border-slate-800/80 rounded-xl space-y-2">
                        <div class="flex justify-between text-sm">
                            <span class="text-slate-400">Выпусков в базе:</span>
                            <span class="font-bold text-white">{total_posts}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-slate-400">Модель ИИ:</span>
                            <span class="font-mono text-xs text-blue-400">{config.llm_model}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-slate-400">Источников:</span>
                            <span class="font-bold text-emerald-400">{len(config.sources)}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Live Logs / Console Section -->
            <div class="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-4">
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                    <div>
                        <div class="flex items-center gap-2">
                            <span class="text-xl">📟</span>
                            <h2 class="text-lg font-bold">Журнал событий и логи</h2>
                            <span id="log-running-spinner" class="{'hidden' if not IS_RUNNING_JOB else ''} text-xs px-2.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30 animate-pulse font-medium">Выполняется процесс...</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-0.5">Детальный вывод шагов сбора, работы LLM, подбора фото и ошибок</p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="switchLogTab('pipeline')" id="tab-btn-pipeline" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 text-white transition">Ручной запуск</button>
                        <button onclick="switchLogTab('service')" id="tab-btn-service" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-400 hover:text-white transition">Служба (systemd)</button>
                        <button onclick="refreshLogs()" title="Обновить логи" class="p-1.5 px-2.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition flex items-center gap-1">
                            <span>🔄</span> Обновить
                        </button>
                        <form action="/api/clear-logs" method="post" class="inline">
                            <button type="submit" title="Очистить буфер" class="p-1.5 px-2.5 text-xs bg-slate-800 hover:bg-red-950/40 text-red-400 rounded-lg border border-slate-700 hover:border-red-800 transition">
                                Очистить
                            </button>
                        </form>
                    </div>
                </div>

                <!-- Terminal Box -->
                <div class="relative">
                    <pre id="console-output" class="bg-black/90 font-mono text-xs rounded-xl p-4 border border-slate-800 text-slate-300 h-72 overflow-y-auto whitespace-pre-wrap leading-relaxed shadow-inner selection:bg-blue-600 selection:text-white">{pipeline_logs_escaped}</pre>
                </div>
            </div>

            <!-- Sources Section -->
            <div class="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-6">
                <div class="flex items-center justify-between">
                    <div>
                        <h2 class="text-lg font-bold">📡 Подключенные каналы и источники</h2>
                        <p class="text-xs text-slate-400 mt-0.5">Откуда бот собирает материалы для анализа</p>
                    </div>
                    <button onclick="document.getElementById('add-source-modal').classList.toggle('hidden')" class="px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-xs font-semibold rounded-xl transition flex items-center gap-1.5 shadow">
                        <span>➕</span> Добавить источник
                    </button>
                </div>

                <!-- Add Source Modal / Inline Form -->
                <div id="add-source-modal" class="hidden p-5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-4">
                    <h3 class="text-sm font-semibold text-slate-200">Добавление нового канала или RSS</h3>
                    <form action="/api/add-source" method="post" class="grid grid-cols-1 md:grid-cols-4 gap-3">
                        <input type="text" name="name" required placeholder="Название (напр. Durov)" class="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none">
                        <select name="type" class="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none">
                            <option value="telegram">Telegram-канал</option>
                            <option value="rss">RSS лента</option>
                        </select>
                        <input type="text" name="url" required placeholder="Юзернейм (@channel) или RSS URL" class="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none">
                        <input type="text" name="category" placeholder="Категория (Tech, Games, NFT)" class="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none">
                        <div class="md:col-span-4 flex justify-end gap-2 mt-2">
                            <button type="button" onclick="document.getElementById('add-source-modal').classList.add('hidden')" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-medium rounded-lg text-slate-300">Отмена</button>
                            <button type="submit" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-xs font-semibold rounded-lg text-white">Добавить источник</button>
                        </div>
                    </form>
                </div>

                <!-- Sources Table -->
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
                                <th class="py-3 px-4">Источник</th>
                                <th class="py-3 px-4">Тип</th>
                                <th class="py-3 px-4">URL / Юзернейм</th>
                                <th class="py-3 px-4">Тематика</th>
                                <th class="py-3 px-4 text-right">Действие</th>
                            </tr>
                        </thead>
                        <tbody>
                            {sources_html}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Recent Posts Section -->
            <div class="space-y-4">
                <div class="flex items-center justify-between">
                    <div>
                        <h2 class="text-lg font-bold">📝 Лента выпущенных постов в канале</h2>
                        <p class="text-xs text-slate-400 mt-0.5">История последних публикаций с проверкой достоверности</p>
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {posts_html}
                </div>
            </div>
        </main>

        <script>
        let currentTab = 'pipeline';
        let cachedLogs = {{
            pipeline: {pipeline_logs_json},
            service: {service_logs_json}
        }};

        function switchLogTab(tab) {{
            currentTab = tab;
            const btnP = document.getElementById('tab-btn-pipeline');
            const btnS = document.getElementById('tab-btn-service');
            const out = document.getElementById('console-output');
            if (tab === 'pipeline') {{
                btnP.className = "px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 text-white transition";
                btnS.className = "px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-400 hover:text-white transition";
                out.textContent = cachedLogs.pipeline;
            }} else {{
                btnS.className = "px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 text-white transition";
                btnP.className = "px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-400 hover:text-white transition";
                out.textContent = cachedLogs.service;
            }}
            out.scrollTop = out.scrollHeight;
        }}

        async function refreshLogs() {{
            try {{
                const res = await fetch('/api/logs');
                if (res.ok) {{
                    const data = await res.json();
                    cachedLogs.pipeline = data.pipeline_logs;
                    cachedLogs.service = data.service_logs;
                    
                    const out = document.getElementById('console-output');
                    if (currentTab === 'pipeline') {{
                        out.textContent = data.pipeline_logs;
                    }} else {{
                        out.textContent = data.service_logs;
                    }}
                    out.scrollTop = out.scrollHeight;

                    const spinner = document.getElementById('log-running-spinner');
                    const jobStatus = document.getElementById('job-status-text');
                    const publishBtn = document.getElementById('publish-btn');
                    const publishBtnText = document.getElementById('publish-btn-text');

                    if (jobStatus) jobStatus.textContent = data.last_status;

                    if (data.is_running) {{
                        if (spinner) spinner.classList.remove('hidden');
                        if (publishBtn) publishBtn.disabled = true;
                        if (publishBtnText) publishBtnText.textContent = "Идет публикация...";
                    }} else {{
                        if (spinner) spinner.classList.add('hidden');
                        if (publishBtn) publishBtn.disabled = false;
                        if (publishBtnText) publishBtnText.textContent = "Опубликовать пост прямо сейчас";
                    }}
                }}
            }} catch (e) {{
                console.error('Failed to refresh logs:', e);
            }}
        }}

        setInterval(refreshLogs, 3000);
        document.addEventListener('DOMContentLoaded', () => {{
            const out = document.getElementById('console-output');
            if (out) out.scrollTop = out.scrollHeight;
        }});
        </script>
    </body>
    </html>
    """


@app.get("/api/logs")
async def get_logs(session_token: Optional[str] = Cookie(None)):
    if not is_authenticated(session_token):
        raise HTTPException(status_code=401)
    service_logs = get_service_logs(50)
    pipeline_logs = "\n".join(RECENT_LOGS) if RECENT_LOGS else "Логи ручного запуска пока пусты. Нажмите «Опубликовать прямо сейчас» для запуска."
    return JSONResponse({
        "is_running": IS_RUNNING_JOB,
        "last_status": LAST_JOB_STATUS,
        "pipeline_logs": pipeline_logs,
        "service_logs": service_logs,
    })


@app.post("/api/clear-logs")
async def clear_logs(session_token: Optional[str] = Cookie(None)):
    if not is_authenticated(session_token):
        raise HTTPException(status_code=401)
    RECENT_LOGS.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/api/publish-now")
async def trigger_publish(session_token: Optional[str] = Cookie(None)):
    if not is_authenticated(session_token):
        raise HTTPException(status_code=401)
    global IS_RUNNING_JOB
    if not IS_RUNNING_JOB:
        t = threading.Thread(target=background_pipeline, daemon=True)
        t.start()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/api/set-interval")
async def set_interval(hours: int = Form(...), session_token: Optional[str] = Cookie(None)):
    if not is_authenticated(session_token):
        raise HTTPException(status_code=401)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if "settings" not in data:
            data["settings"] = {}
        data["settings"]["schedule_hours"] = hours
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)

        # Restart service so interval changes immediately
        subprocess.run(["systemctl", "restart", "market-intel"], check=False)
    except Exception as e:
        print("Error saving interval:", e)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/api/add-source")
async def add_source(
    name: str = Form(...),
    type: str = Form(...),
    url: str = Form(...),
    category: str = Form("General"),
    session_token: Optional[str] = Cookie(None)
):
    if not is_authenticated(session_token):
        raise HTTPException(status_code=401)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if "sources" not in data:
            data["sources"] = []
        data["sources"].append({
            "name": name.strip(),
            "type": type.strip(),
            "url": url.strip().replace("https://t.me/", "").replace("@", ""),
            "category": category.strip() or "General",
            "competitor": name.strip()
        })
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)
    except Exception as e:
        print("Error adding source:", e)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/api/delete-source")
async def delete_source(source_name: str = Form(...), session_token: Optional[str] = Cookie(None)):
    if not is_authenticated(session_token):
        raise HTTPException(status_code=401)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        sources = data.get("sources", [])
        data["sources"] = [s for s in sources if s.get("name") != source_name]
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)
    except Exception as e:
        print("Error deleting source:", e)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8888)
