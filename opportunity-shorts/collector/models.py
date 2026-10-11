from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

OPP_TYPES = ("internship", "job", "hackathon", "fellowship", "scholarship", "other")
STATUSES = ("new", "approved", "rejected", "posted")


@dataclass
class Opportunity:
    source: str                 # greenhouse | lever | ashby | himalayas | remotive | rss | manual
    board: str                  # e.g. "greenhouse:stripe"; "manual" for manual imports
    external_id: str
    title: str
    company: str
    apply_url: str
    location: str = ""
    is_india: bool = False
    is_remote: bool = False
    opp_type: str = "job"
    description: str = ""
    posted_at: Optional[str] = None      # ISO-8601 UTC
    deadline: Optional[str] = None       # YYYY-MM-DD
    stipend_text: str = ""
    batch_years: list = field(default_factory=list)
    experience_text: str = ""
    department: str = ""
    score: float = 0.0
    verified: bool = False               # True for manual / hand-checked items

    @property
    def id(self) -> str:
        raw = f"{self.source}:{self.board}:{self.external_id}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    @property
    def content_hash(self) -> str:
        raw = "|".join([self.title, self.location, self.deadline or "", self.stipend_text,
                        self.apply_url, self.description])
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def to_card(self) -> dict:
        """Compact, video-ready facts. This is the contract the next pipeline stage consumes."""
        return {
            "id": self.id,
            "type": self.opp_type,
            "role": self.title,
            "company": self.company,
            "location": self.location or ("Remote" if self.is_remote else ""),
            "is_india": self.is_india,
            "is_remote": self.is_remote,
            "stipend": self.stipend_text,
            "batch_years": list(self.batch_years),
            "experience": self.experience_text,
            "deadline": self.deadline,
            "apply_url": self.apply_url,
            "description": self.description,
            "posted_at": self.posted_at,
            "score": round(self.score, 1),
            "verified": self.verified,
            "source": self.source,
        }

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
