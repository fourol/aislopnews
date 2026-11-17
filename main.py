"""Main entry point for Competitor & Market Intelligence Agent."""
import argparse
import sys
import time
from datetime import datetime
from src.analyzer import Analyzer
from src.charts import ChartGenerator
from src.collectors import RSSCollector, TelegramPreviewCollector, WebPageCollector
from src.config import load_config
from src.storage import Storage
from src.telegram_bot import TelegramPublisher


def run_pipeline(dry_run: bool = False):
    config = load_config()
    storage = Storage()
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

    # 2. Получение необработанных материалов для дайджеста
    unprocessed = storage.get_unprocessed_items(limit=config.max_items_per_run)
    if not unprocessed:
        print("Нет новых материалов для анализа. Дайджест не требуется.")
        return

    print(f"Готово к анализу через LLM: {len(unprocessed)} материалов.")

    # 3. Анализ через LLM
    if not config.llm_api_key and not dry_run:
        print("[Внимание] Не указан LLM_API_KEY в .env! Укажите ключ OpenAI / OpenRouter / DeepSeek.")
        return

    analyzer = Analyzer(
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        model=config.llm_model,
    )

    print(f"Отправка запроса в LLM ({config.llm_model})...")
    analysis_result = analyzer.analyze(unprocessed)
    if not analysis_result:
        print("[Ошибка] Не удалось получить результат анализа от модели.")
        return

    digest_text = analysis_result.get("telegram_digest", "Дайджест не сформирован.")
    topic_distribution = analysis_result.get("topic_distribution", {})
    competitor_mentions = analysis_result.get("competitor_mentions", {})

    # 4. Генерация графиков
    chart_gen = ChartGenerator()
    chart_path = chart_gen.generate_digest_chart(
        topic_counts=topic_distribution,
        competitor_counts=competitor_mentions,
    )
    if chart_path:
        print(f"График успешно сгенерирован: {chart_path}")

    # 5. Публикация в Telegram или Dry-run вывод
    if dry_run:
        print("\n" + "=" * 25 + " [DRY-RUN ДАЙДЖЕСТ] " + "=" * 25)
        print(digest_text)
        print("=" * 60)
        print(f"График сохранен в: {chart_path}")
        print("В режиме --dry-run статус в БД не меняется, в Telegram не отправляется.")
    else:
        publisher = TelegramPublisher(
            bot_token=config.telegram_bot_token,
            channel_id=config.telegram_channel_id,
        )
        print("Публикация дайджеста в Telegram-канал...")
        success = publisher.send_digest(text=digest_text, chart_path=chart_path)
        if success:
            print("Дайджест успешно отправлен в канал!")
            # Помечаем обработанными только при успешной отправке
            item_ids = [item.id for item in unprocessed if item.id]
            storage.mark_items_processed(item_ids)
            storage.record_digest(digest_text, chart_path, len(unprocessed), status="sent")
        else:
            print("[Ошибка] Не удалось опубликовать пост в Telegram. Проверьте токен и доступ бота к каналу.")


def main():
    parser = argparse.ArgumentParser(description="Агент мониторинга рынка и конкурентов в Telegram")
    parser.add_argument("--run-once", action="store_true", help="Запустить один цикл сбора и отправки")
    parser.add_argument("--dry-run", action="store_true", help="Собрать и проанализировать без отправки в TG")
    parser.add_argument("--test-tg", action="store_true", help="Отправить тестовое сообщение в канал для проверки")
    parser.add_argument("--schedule", action="store_true", help="Запустить в режиме демона по расписанию")
    args = parser.parse_args()

    config = load_config()

    if args.test_tg:
        publisher = TelegramPublisher(bot_token=config.telegram_bot_token, channel_id=config.telegram_channel_id)
        msg = "🤖 **Тест связи:** Агент мониторинга и конкурентной разведки успешно подключен к каналу!"
        ok = publisher.send_digest(text=msg)
        print("Результат отправки:", "УСПЕШНО" if ok else "ОШИБКА")
        sys.exit(0 if ok else 1)

    if args.schedule:
        hours = config.digest_schedule_hours
        print(f"Агент запущен в фоновом режиме. Цикл каждые {hours} ч. (Ctrl+C для остановки)")
        while True:
            try:
                run_pipeline(dry_run=args.dry_run)
            except Exception as e:
                print(f"[Ошибка в цикле]: {e}")
            print(f"Ожидание следующего цикла ({hours} ч.)...")
            time.sleep(hours * 3600)

    # По умолчанию запускаем один раз
    run_pipeline(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
