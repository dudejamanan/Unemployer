from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .models import Opportunity, STATUSES

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    board TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT DEFAULT '',
    is_india INTEGER DEFAULT 0,
    is_remote INTEGER DEFAULT 0,
    opp_type TEXT DEFAULT 'job',
    description TEXT DEFAULT '',
    apply_url TEXT NOT NULL,
    posted_at TEXT,
    deadline TEXT,
    stipend_text TEXT DEFAULT '',
    batch_years TEXT DEFAULT '[]',
    experience_text TEXT DEFAULT '',
    department TEXT DEFAULT '',
    score REAL DEFAULT 0,
    verified INTEGER DEFAULT 0,
    status TEXT DEFAULT 'new',
    is_open INTEGER DEFAULT 1,
    content_hash TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_status ON opportunities(status, is_open, score);
CREATE INDEX IF NOT EXISTS idx_board ON opportunities(board);
CREATE INDEX IF NOT EXISTS idx_apply ON opportunities(apply_url);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Database:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    # ---- write
    def upsert(self, opp: Opportunity) -> str:
        """-> 'new' | 'updated' | 'unchanged'. Never overwrites an existing human-set status."""
        now = _now()
        row = self.conn.execute("SELECT content_hash FROM opportunities WHERE id=?", (opp.id,)).fetchone()
        vals = dict(
            source=opp.source, board=opp.board, external_id=opp.external_id, title=opp.title,
            company=opp.company, location=opp.location, is_india=int(opp.is_india),
            is_remote=int(opp.is_remote), opp_type=opp.opp_type, description=opp.description,
            apply_url=opp.apply_url, posted_at=opp.posted_at, deadline=opp.deadline,
            stipend_text=opp.stipend_text, batch_years=json.dumps(opp.batch_years),
            experience_text=opp.experience_text, department=opp.department, score=opp.score,
            verified=int(opp.verified), content_hash=opp.content_hash,
        )
        if row is None:
            cols = list(vals) + ["id", "status", "is_open", "first_seen_at", "last_seen_at", "updated_at"]
            params = list(vals.values()) + [opp.id, "new", 1, now, now, now]
            self.conn.execute(
                f"INSERT INTO opportunities ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", params)
            self.conn.commit()
            return "new"
        changed = row["content_hash"] != opp.content_hash
        sets = ", ".join(f"{k}=?" for k in vals) + ", last_seen_at=?, is_open=1"
        params = list(vals.values()) + [now]
        if changed:
            sets += ", updated_at=?"
            params.append(now)
        params.append(opp.id)
        self.conn.execute(f"UPDATE opportunities SET {sets} WHERE id=?", params)
        self.conn.commit()
        return "updated" if changed else "unchanged"

    def mark_missing_closed(self, board: str, seen_ids: Iterable[str]) -> int:
        """Listings that vanished from a board we just fetched successfully are no longer open."""
        seen = set(seen_ids)
        rows = self.conn.execute("SELECT id FROM opportunities WHERE board=? AND is_open=1", (board,)).fetchall()
        gone = [r["id"] for r in rows if r["id"] not in seen]
        for gid in gone:
            self.conn.execute("UPDATE opportunities SET is_open=0, updated_at=? WHERE id=?", (_now(), gid))
        self.conn.commit()
        return len(gone)

    def set_status(self, opp_id: str, status: str) -> bool:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        cur = self.conn.execute("UPDATE opportunities SET status=?, updated_at=? WHERE id=?",
                                (status, _now(), opp_id))
        self.conn.commit()
        return cur.rowcount > 0

    # ---- read
    def get(self, opp_id: str) -> Optional[sqlite3.Row]:
        rows = self.conn.execute("SELECT * FROM opportunities WHERE id LIKE ?", (opp_id + "%",)).fetchall()
        return rows[0] if len(rows) == 1 else None

    def list(self, status: Optional[str] = "new", limit: int = 50, only_open: bool = True,
             min_score: Optional[float] = None, today: Optional[date] = None, offset: int = 0) -> list:
        today = (today or date.today()).isoformat()
        q = "SELECT * FROM opportunities WHERE 1=1"
        p: list = []
        if status:
            q += " AND status=?"
            p.append(status)
        if only_open:
            q += " AND is_open=1 AND (deadline IS NULL OR deadline>=?)"
            p.append(today)
        if min_score is not None:
            q += " AND score>=?"
            p.append(min_score)
        q += " ORDER BY score DESC, posted_at DESC, id ASC LIMIT ? OFFSET ?"
        p.extend([limit, max(0, offset)])
        return self.conn.execute(q, p).fetchall()

    def queue_count(self, status='new', only_open=True, today=None):
        query = 'SELECT COUNT(*) FROM opportunities WHERE status=?'
        params = [status]
        if only_open:
            query += ' AND is_open=1 AND (deadline IS NULL OR deadline>=?)'
            params.append((today or date.today()).isoformat())
        return self.conn.execute(query, params).fetchone()[0]

    def counts(self) -> dict:
        out = {}
        for r in self.conn.execute("SELECT status, is_open, COUNT(*) c FROM opportunities GROUP BY status, is_open"):
            out[f"{r['status']}{'' if r['is_open'] else ' (closed)'}"] = r["c"]
        return out


def row_to_card(row) -> dict:
    d = dict(row)
    return {
        "id": d["id"], "type": d["opp_type"], "role": d["title"], "company": d["company"],
        "location": d["location"] or ("Remote" if d["is_remote"] else ""),
        "is_india": bool(d["is_india"]), "is_remote": bool(d["is_remote"]),
        "stipend": d["stipend_text"], "batch_years": json.loads(d["batch_years"] or "[]"),
        "experience": d["experience_text"], "deadline": d["deadline"], "apply_url": d["apply_url"],
        "description": d["description"], "posted_at": d["posted_at"], "score": round(d["score"], 1),
        "verified": bool(d["verified"]), "source": d["source"], "status": d["status"],
    }
