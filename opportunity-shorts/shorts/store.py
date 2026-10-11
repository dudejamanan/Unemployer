from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import PostRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    opportunity_id TEXT NOT NULL,
    script_json TEXT NOT NULL,
    video_path TEXT,
    youtube_id TEXT,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TEXT,
    updated_at TEXT,
    posted_at TEXT,
    PRIMARY KEY (opportunity_id)
);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_youtube ON posts(youtube_id);
CREATE TABLE IF NOT EXISTS upload_attempts (
    opportunity_id TEXT, company TEXT, role TEXT, attempted_at TEXT
);
CREATE TABLE IF NOT EXISTS schedules (
    opportunity_id TEXT PRIMARY KEY, scheduled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS upload_retries (
    opportunity_id TEXT PRIMARY KEY, retry_after TEXT NOT NULL, reason TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PostStore:
    """Store for tracking post generation and upload status."""

    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def upsert(self, post: PostRecord) -> str:
        """Insert or update a post record."""
        now = _now()
        post.updated_at = now
        vals = (
            post.opportunity_id,
            post.script_json,
            post.video_path,
            post.youtube_id,
            post.status,
            post.error_message,
            post.created_at,
            post.updated_at,
            post.posted_at,
        )
        self.conn.execute(
            """
            INSERT INTO posts (opportunity_id, script_json, video_path, youtube_id, status, error_message, created_at, updated_at, posted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(opportunity_id) DO UPDATE SET
                script_json=excluded.script_json,
                video_path=excluded.video_path,
                youtube_id=excluded.youtube_id,
                status=excluded.status,
                error_message=excluded.error_message,
                updated_at=excluded.updated_at,
                posted_at=excluded.posted_at
            """,
            vals,
        )
        self.conn.commit()
        return "upserted"

    def get(self, opportunity_id: str) -> Optional[PostRecord]:
        row = self.conn.execute("SELECT * FROM posts WHERE opportunity_id=?", (opportunity_id,)).fetchone()
        if not row:
            return None
        return PostRecord(
            opportunity_id=row["opportunity_id"],
            script_json=row["script_json"],
            video_path=row["video_path"],
            youtube_id=row["youtube_id"],
            status=row["status"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            posted_at=row["posted_at"],
        )

    def list(self, status: Optional[str] = None, limit: int = 50) -> list[PostRecord]:
        q = "SELECT * FROM posts WHERE 1=1"
        p: list = []
        if status:
            q += " AND status=?"
            p.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"
        p.append(limit)
        rows = self.conn.execute(q, p).fetchall()
        return [
            PostRecord(
                opportunity_id=r["opportunity_id"],
                script_json=r["script_json"],
                video_path=r["video_path"],
                youtube_id=r["youtube_id"],
                status=r["status"],
                error_message=r["error_message"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                posted_at=r["posted_at"],
            )
            for r in rows
        ]

    def update_status(self, opportunity_id: str, status: str, error_message: Optional[str] = None) -> bool:
        """Update status and optionally error message."""
        now = _now()
        q = "UPDATE posts SET status=?, updated_at=?"
        p = [status, now]
        if error_message is not None:
            q += ", error_message=?"
            p.append(error_message)
        q += " WHERE opportunity_id=?"
        p.append(opportunity_id)
        cur = self.conn.execute(q, p)
        self.conn.commit()
        return cur.rowcount > 0

    def set_youtube_id(self, opportunity_id: str, youtube_id: str) -> bool:
        """Set YouTube ID after successful upload."""
        now = _now()
        cur = self.conn.execute(
            "UPDATE posts SET youtube_id=?, status='posted', posted_at=?, updated_at=? WHERE opportunity_id=?",
            (youtube_id, now, now, opportunity_id),
        )
        self.conn.commit()
        return cur.rowcount > 0
