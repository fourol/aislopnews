"""Storage layer using SQLite for tracking parsed items and digest history."""
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Item:
    url: str
    title: str
    source_name: str
    source_type: str
    content: str
    competitor: Optional[str] = None
    published_at: Optional[str] = None
    item_hash: str = ""
    id: Optional[int] = None
    is_processed: bool = False


class Storage:
    def __init__(self, db_path: str = "data/intel_agent.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_hash TEXT UNIQUE,
                    url TEXT,
                    title TEXT,
                    source_name TEXT,
                    source_type TEXT,
                    competitor TEXT,
                    content TEXT,
                    published_at TEXT,
                    discovered_at TEXT,
                    is_processed INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS digests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    summary_text TEXT,
                    chart_path TEXT,
                    item_count INTEGER,
                    status TEXT
                )
                """
            )
            conn.commit()

    @staticmethod
    def compute_hash(url: str, title: str) -> str:
        text = f"{url.strip()}:{title.strip()}".encode("utf-8")
        return hashlib.sha256(text).hexdigest()

    def add_item(self, item: Item) -> bool:
        """Saves item if it doesn't already exist. Returns True if inserted."""
        item_hash = item.item_hash or self.compute_hash(item.url, item.title)
        now = datetime.utcnow().isoformat()
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO items (
                        item_hash, url, title, source_name, source_type,
                        competitor, content, published_at, discovered_at, is_processed
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        item_hash,
                        item.url,
                        item.title,
                        item.source_name,
                        item.source_type,
                        item.competitor,
                        item.content,
                        item.published_at or now,
                        now,
                    ),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            # Already exists
            return False

    def get_unprocessed_items(self, limit: int = 50) -> List[Item]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, item_hash, url, title, source_name, source_type,
                       competitor, content, published_at, is_processed
                FROM items
                WHERE is_processed = 0
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                Item(
                    id=row["id"],
                    item_hash=row["item_hash"],
                    url=row["url"],
                    title=row["title"],
                    source_name=row["source_name"],
                    source_type=row["source_type"],
                    competitor=row["competitor"],
                    content=row["content"],
                    published_at=row["published_at"],
                    is_processed=bool(row["is_processed"]),
                )
                for row in rows
            ]

    def mark_items_processed(self, item_ids: List[int]):
        if not item_ids:
            return
        placeholders = ",".join("?" for _ in item_ids)
        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE items SET is_processed = 1 WHERE id IN ({placeholders})",
                item_ids,
            )
            conn.commit()

    def record_digest(self, summary_text: str, chart_path: Optional[str], item_count: int, status: str = "sent"):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO digests (created_at, summary_text, chart_path, item_count, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(),
                    summary_text,
                    chart_path,
                    item_count,
                    status,
                ),
            )
            conn.commit()
