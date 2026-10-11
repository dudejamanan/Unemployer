from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .filters import passes
from .http_client import FetchError
from .normalize import enrich
from .scoring import score
from .sources import ATS_SOURCES, OTHER_SOURCES
from .sources.manual import load_manual


@dataclass
class RunStats:
    boards_ok: int = 0
    boards_failed: int = 0
    fetched: int = 0
    kept: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    closed: int = 0
    dropped: Counter = field(default_factory=Counter)
    errors: list = field(default_factory=list)
    sample: list = field(default_factory=list)   # a few kept items, for dry-runs

    def summary(self) -> str:
        drop = ", ".join(f"{k}={v}" for k, v in self.dropped.most_common()) or "none"
        lines = [
            f"sources ok/failed : {self.boards_ok}/{self.boards_failed}",
            f"fetched           : {self.fetched}",
            f"kept after filter : {self.kept}   (dropped: {drop})",
            f"new/updated/same  : {self.new}/{self.updated}/{self.unchanged}",
            f"closed (vanished) : {self.closed}",
        ]
        for e in self.errors:
            lines.append(f"  ! {e}")
        return "\n".join(lines)


def build_targets(boards: list, sources_cfg: dict, only: Optional[str] = None) -> list:
    """-> list of (source_obj, cfg). `only` = source name (greenhouse|lever|ashby|himalayas|remotive|rss)
    or a full board key like 'lever:spotify'."""
    targets = []
    for b in boards:
        src = ATS_SOURCES.get(str(b.get("ats", "")).lower())
        if src and b.get("enabled", True) and b.get("token"):
            targets.append((src, b))
    for name in ("himalayas", "remotive", 'unstop', 'aicte'):
        cfg = (sources_cfg or {}).get(name) or {}
        if cfg.get("enabled"):
            targets.append((OTHER_SOURCES[name], cfg))
    for feed in (sources_cfg or {}).get("feeds") or []:
        if feed.get("name") and feed.get("url"):
            targets.append((OTHER_SOURCES["rss"], feed))
    pages_cfg = (sources_cfg or {}).get('official_pages') or {}
    if pages_cfg.get('enabled'):
        for page in pages_cfg.get('pages') or []:
            if page.get('enabled', True) and page.get('name') and page.get('url'):
                targets.append((OTHER_SOURCES['official_pages'], page))
    if only:
        requested = {name.strip() for name in only.split(',') if name.strip()}
        targets = [(s, c) for s, c in targets if s.name in requested or s.key(c) in requested]
    return targets


def run_collection(settings: dict, boards: list, sources_cfg: dict, db, client, only: Optional[str] = None,
                   apply_filters: bool = True, dry_run: bool = False, today: Optional[date] = None) -> RunStats:
    today = today or date.today()
    stats = RunStats()
    fcfg = settings.get("filters", {})
    priority = settings.get("priority_companies", [])
    max_desc = int(settings.get("max_description_chars", 6000))

    for src, cfg in build_targets(boards, sources_cfg, only):
        key = src.key(cfg)
        try:
            items = src.fetch(client, cfg)
        except FetchError as e:
            stats.boards_failed += 1
            stats.errors.append(f"{key}: {e}")
            continue
        except Exception as e:   # a parser bug in one source must not kill the whole run
            stats.boards_failed += 1
            stats.errors.append(f"{key}: unexpected {type(e).__name__}: {e}")
            continue
        stats.boards_ok += 1
        stats.fetched += len(items)
        seen_ids = []
        for opp in items:
            if not opp.title or not opp.apply_url:
                stats.dropped["missing_title_or_url"] += 1
                continue
            seen_ids.append(opp.id)
            enrich(opp, today, max_desc)
            if apply_filters:
                keep, reason = passes(opp, fcfg)
                if not keep:
                    stats.dropped[reason] += 1
                    continue
            opp.score = score(opp, today, priority)
            stats.kept += 1
            if len(stats.sample) < 5:
                stats.sample.append(opp)
            if dry_run:
                continue
            result = db.upsert(opp)
            setattr(stats, result, getattr(stats, result) + 1)
        if src.closes_missing and not dry_run:
            stats.closed += db.mark_missing_closed(key, seen_ids)
    return stats


def import_manual(path, settings: dict, db, today: Optional[date] = None, dry_run: bool = False) -> RunStats:
    today = today or date.today()
    stats = RunStats()
    items = load_manual(path)
    stats.fetched = len(items)
    stats.boards_ok = 1
    for opp in items:
        enrich(opp, today, int(settings.get("max_description_chars", 6000)))
        opp.score = score(opp, today, settings.get("priority_companies", []))
        stats.kept += 1
        if len(stats.sample) < 5:
            stats.sample.append(opp)
        if not dry_run:
            result = db.upsert(opp)
            setattr(stats, result, getattr(stats, result) + 1)
    return stats
