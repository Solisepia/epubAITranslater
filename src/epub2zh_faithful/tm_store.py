from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .utils import ensure_dir


@dataclass(slots=True)
class CacheEntry:
    segment_id: str
    source_hash: str
    config_hash: str
    draft_text: str | None
    revise_text: str | None


class TMStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        ensure_dir(Path(db_path).parent)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                input_epub TEXT NOT NULL,
                output_epub TEXT NOT NULL,
                provider TEXT NOT NULL,
                config_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS translations (
                segment_id TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                config_hash TEXT NOT NULL,
                draft_text TEXT,
                revise_text TEXT,
                provider TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(segment_id, source_hash, config_hash)
            );

            CREATE TABLE IF NOT EXISTS segments (
                segment_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                node_selector TEXT NOT NULL,
                order_index INTEGER NOT NULL,
                source_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                segment_id TEXT,
                stage TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def create_run(self, run_id: str, input_epub: str, output_epub: str, provider: str, config_hash: str) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            INSERT OR REPLACE INTO runs(run_id, started_at, input_epub, output_epub, provider, config_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, now, input_epub, output_epub, provider, config_hash),
        )
        self.conn.commit()

    def record_segment(self, segment_id: str, file_path: str, node_selector: str, order_index: int, source_hash: str) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO segments(segment_id, file_path, node_selector, order_index, source_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (segment_id, file_path, node_selector, order_index, source_hash),
        )

    def get_cached(self, segment_id: str, source_hash: str, config_hash: str, prefer_revise: bool) -> str | None:
        row = self.conn.execute(
            """
            SELECT draft_text, revise_text
            FROM translations
            WHERE segment_id = ? AND source_hash = ? AND config_hash = ?
            """,
            (segment_id, source_hash, config_hash),
        ).fetchone()
        if not row:
            return None
        revise = row["revise_text"]
        draft = row["draft_text"]
        if prefer_revise and revise:
            return str(revise)
        if draft:
            return str(draft)
        return None

    def upsert_translation(
        self,
        segment_id: str,
        source_hash: str,
        config_hash: str,
        provider: str,
        draft_text: str | None,
        revise_text: str | None,
    ) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            INSERT INTO translations(segment_id, source_hash, config_hash, draft_text, revise_text, provider, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(segment_id, source_hash, config_hash)
            DO UPDATE SET
                draft_text=excluded.draft_text,
                revise_text=excluded.revise_text,
                provider=excluded.provider,
                updated_at=excluded.updated_at
            """,
            (segment_id, source_hash, config_hash, draft_text, revise_text, provider, now),
        )

    def record_error(self, run_id: str, stage: str, message: str, segment_id: str | None = None) -> None:
        self.conn.execute(
            """
            INSERT INTO errors(run_id, segment_id, stage, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, segment_id, stage, message, _utc_now()),
        )

    def commit(self) -> None:
        self.conn.commit()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
