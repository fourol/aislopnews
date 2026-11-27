"""Main entry point for Competitor, Tech & Web3 Intelligence Agent."""
import argparse
import io
from pathlib import Path
import sys
import time
from datetime import datetime
from src.analyzer import Analyzer, is_advertisement
from src.charts import ChartGenerator
from src.collectors import RSSCollector, TelegramPreviewCollector, WebPageCollector
from src.config import load_config
from src.image_manager import ImageManager
from src.storage import Storage
from src.telegram_bot import TelegramPublisher


def run_pipeline(dry_run: bool = False):
    config = load_config()
    storage = Storage()
    image_mgr = ImageManager()

    print("=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Запуск цикла мониторинга...")
    print("=" * 60)

    # 1. Сбор данных из источников
    total_new = 0
    for src in config.sources:
        print(f"-> Сбор: {src.name} ({src.type})...")
        collector = None
        if src.type == "rss":
            collector = RSSCollector(name=src.name, url=src.url, competitor=src.competitor)
        elif src.type == "telegram":
            collector = TelegramPreviewCollector(name=src.name, channel_username=src.url, competitor=src.competitor)
        elif src.type == "web":
            collector = WebPageCollector(name=src.name, url=src.url, competitor=src.competitor)

        if collector:
            items = collector.collect()
            new_in_src = 0
            for item in items:
                if storage.add_item(item):
                    new_in_src += 1
            print(f"   Собрано {len(items)} шт, новых для базы: {new_in_src}")
            total_new += new_in_src

    print(f"\nВсего добавлено новых материалов: {total_new}")

    # 2. Получение и предфильтрация необработанных материалов (отсев рекламы и пустых постов)
    unprocessed = storage.get_unprocessed_items(limit=config.max_items_per_run)
    if not unprocessed:
        print("Нет новых материалов для анализа. Публикация не требуется.")
        return

    clean_items = []
    skipped_items = []
    for item in unprocessed:
        if not item.content.strip() or is_advertisement(item.title, item.content):
            skipped_items.append(item)
        else:
            clean_items.append(item)

    if skipped_items:
        print(f"Отфильтровано рекламы и пустых материалов: {len(skipped_items)} шт.")
        if not dry_run:
            skipped_ids = [item.id for item in skipped_items if item.id]
            storage.mark_items_processed(skipped_ids)

    if not clean_items:
        print("После фильтрации рекламы нет подходящих новостей для публикации.")
        return

    print(f"Готово к анализу через LLM: {len(clean_items)} материалов.")

    # 3. Анализ через LLM и выбор главного события
    if not config.llm_api_key and not dry_run:
        print("[Внимание] Не указан LLM_API_KEY в .env! Укажите ключ OpenRouter / OpenAI.")
        return

    analyzer = Analyzer(
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        model=config.llm_model,
        fallback_models=config.llm_fallback_models,
    )

    print(f"Отправка запроса в LLM ({config.llm_model}) для детального разбора...")
    analysis_result = analyzer.analyze(clean_items, allow_quote=False)
    if not analysis_result:
        print("[Ошибка] Не удалось получить результат анализа от модели.")
        return

    post_text = analysis_result.get("telegram_post", "Пост не сформирован.")
    headline = analysis_result.get("headline", "Главное событие")
    topic = analysis_result.get("topic", "Tech")
    credibility = analysis_result.get("credibility", "")
    image_keyword = analysis_result.get("image_keyword", "")

    # 4. Подбор изображения (из оригинального поста, из сети или стильная обложка)
    selected_idx = analysis_result.get("selected_item_index", 1) - 1
    selected_item = clean_items[selected_idx] if 0 <= selected_idx < len(clean_items) else clean_items[0]

    final_image_path = None
    if selected_item.image_url:
        print(f"Загрузка оригинального фото из Telegram-поста: {selected_item.image_url[:60]}...")
        final_image_path = image_mgr.download_image(selected_item.image_url)

    if not final_image_path and image_keyword:
        print(f"Поиск релевантной картинки в сети по запросу: '{image_keyword}'...")
        final_image_path = image_mgr.search_web_image(image_keyword)

    if not final_image_path:
        print("Генерация стильной карточки-обложки для поста...")
        final_image_path = image_mgr.create_cover_card(headline, topic, credibility)

    print(f"Изображение для публикации готово: {final_image_path}")

    # 5. Публикация в Telegram или Dry-run вывод
    if dry_run:
        print("\n" + "=" * 25 + " [DRY-RUN ДЕТАЛЬНЫЙ ПОСТ] " + "=" * 25)
        print(post_text)
        print("=" * 60)
        print(f"Фото: {final_image_path}")
        print("В режиме --dry-run статус в БД не меняется, в Telegram не отправляется.")
    else:
        publisher = TelegramPublisher(
            bot_token=config.telegram_bot_token,
            channel_id=config.telegram_channel_id,
        )
        print("Публикация детального поста с фото в Telegram-канал...")
        success = publisher.send_digest(text=post_text, chart_path=final_image_path, headline=headline)
        if success:
            print("Пост успешно опубликован в канале!")
            # Помечаем материалы обработанными
            item_ids = [item.id for item in clean_items if item.id]
            storage.mark_items_processed(item_ids)
            storage.record_digest(post_text, final_image_path, len(clean_items), status="sent")
        else:
            print("[Ошибка] Не удалось опубликовать пост в Telegram. Проверьте токен и доступ бота к каналу.")


class _TeeStream(io.TextIOBase):
    """Mirrors stdout/stderr to a rotating local log file for container/non-systemd viewing."""

    def __init__(self, orig, log_path: Path, max_bytes: int = 256_000):
        self.orig = orig
        self.log_path = log_path
        self.max_bytes = max_bytes

    def write(self, s: str) -> int:
        self.orig.write(s)
        self.orig.flush()
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            if self.log_path.exists() and self.log_path.stat().st_size > self.max_bytes:
                tail = self.log_path.read_text(encoding="utf-8", errors="ignore")[-self.max_bytes // 2 :]
                self.log_path.write_text(tail, encoding="utf-8")
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(s)
        except Exception:
            pass
        return len(s)

    def flush(self):
        self.orig.flush()


def _write_heartbeat(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(datetime.now().isoformat(), encoding="utf-8")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Агент углубленного мониторинга технологий, Web3 и ИИ в Telegram")
    parser.add_argument("--run-once", action="store_true", help="Запустить один цикл сбора и отправки")
    parser.add_argument("--dry-run", action="store_true", help="Собрать и проанализировать без отправки в TG")
    parser.add_argument("--test-tg", action="store_true", help="Отправить тестовое сообщение в канал для проверки")
    parser.add_argument("--schedule", action="store_true", help="Запустить в режиме демона по расписанию")
    args = parser.parse_args()

    config = load_config()

    if args.test_tg:
        publisher = TelegramPublisher(bot_token=config.telegram_bot_token, channel_id=config.telegram_channel_id)
        msg = "🤖 **Тест связи:** Бот настроен на разбор ключевых тем из @lalyounft, @GeodemaNews и мирового теха!"
        ok = publisher.send_digest(text=msg)
        print("Результат отправки:", "УСПЕШНО" if ok else "ОШИБКА")
        sys.exit(0 if ok else 1)

    if args.schedule:
        log_path = Path("data/agent.log")
        heartbeat_path = Path("data/agent_heartbeat")
        sys.stdout = _TeeStream(sys.stdout, log_path)
        sys.stderr = _TeeStream(sys.stderr, log_path)

        hours = config.digest_schedule_hours
        print(f"Агент запущен в фоновом режиме. Цикл каждые {hours} ч. (Ctrl+C для остановки)")
        while True:
            _write_heartbeat(heartbeat_path)
            try:
                run_pipeline(dry_run=args.dry_run)
            except Exception as e:
                print(f"[Ошибка в цикле]: {e}")

            hours = load_config().digest_schedule_hours
            print(f"Ожидание следующего цикла ({hours} ч.)...")
            elapsed = 0
            while elapsed < hours * 3600:
                _write_heartbeat(heartbeat_path)
                time.sleep(min(30, max(1, hours * 3600 - elapsed)))
                elapsed += 30
                new_hours = load_config().digest_schedule_hours
                if new_hours != hours:
                    hours = new_hours
                    print(f"Интервал обновлён на {hours} ч.")

    # По умолчанию запускаем один раз
    run_pipeline(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
