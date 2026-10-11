from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .config import ROOT, load_boards, load_settings, load_sources_cfg
from .db import Database, row_to_card
from .http_client import FetchError, HttpClient
from .models import STATUSES, dumps
from .pipeline import build_targets, import_manual, run_collection

BOARD_URL_PATTERNS = [
    ("greenhouse", re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_\-]+)")),
    ("lever", re.compile(r"jobs(\.eu)?\.lever\.co/([A-Za-z0-9_\-.]+)")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_\-.%]+)")),
]


def parse_board_url(url: str):
    """careers URL -> {'ats':..., 'token':..., ['region': 'eu']} or None."""
    for ats, pat in BOARD_URL_PATTERNS:
        m = pat.search(url)
        if not m:
            continue
        if ats == "lever":
            cfg = {"ats": "lever", "token": m.group(2)}
            if m.group(1):
                cfg["region"] = "eu"
            return cfg
        return {"ats": ats, "token": m.group(1)}
    return None


def _client(settings):
    return HttpClient(settings["user_agent"], settings["request_timeout"], settings["min_delay_seconds"])


def _print_rows(rows):
    if not rows:
        print("(nothing)")
        return
    for r in rows:
        dl = r["deadline"] or "-"
        print(f"{r['id']}  [{r['score']:5.1f}] {r['opp_type']:<10} {r['company'][:22]:<22} | "
              f"{r['title'][:55]:<55} | {(r['location'] or '-')[:28]:<28} | deadline {dl} | {r['status']}")


def cmd_run(a):
    settings, boards, sc = load_settings(a.config), load_boards(a.config), load_sources_cfg(a.config)
    db = Database(":memory:" if a.dry_run else settings["db_path"])
    targets = build_targets(boards, sc, a.source)
    print(f"Collecting from {len(targets)} source(s)" + (" [dry-run]" if a.dry_run else "") + " ...")
    stats = run_collection(settings, boards, sc, db, _client(settings), only=a.source,
                           apply_filters=not a.no_filter, dry_run=a.dry_run)
    print(stats.summary())
    if a.dry_run and stats.sample:
        print("\nSample of what would be kept:")
        for o in stats.sample:
            print(f"  - {o.company}: {o.title} | {o.location or '-'} | deadline {o.deadline or '-'} | {o.apply_url}")
    return 0 if stats.boards_ok or not targets else 1


def cmd_manual(a):
    settings = load_settings(a.config)
    db = Database(":memory:" if a.dry_run else settings["db_path"])
    stats = import_manual(a.file, settings, db, dry_run=a.dry_run)
    print(stats.summary())
    return 0


def cmd_list(a):
    settings = load_settings(a.config)
    db = Database(settings["db_path"])
    _print_rows(db.list(status=None if a.status == "any" else a.status, limit=a.limit,
                        only_open=not a.include_closed, min_score=a.min_score))
    return 0


def cmd_show(a):
    db = Database(load_settings(a.config)["db_path"])
    row = db.get(a.id)
    if not row:
        print("No unique match for that id (use more characters?)")
        return 1
    print(dumps(row_to_card(row)))
    return 0


def cmd_set_status(a):
    db = Database(load_settings(a.config)["db_path"])
    ok = db.set_status(a.id, a.status)
    print("updated" if ok else "id not found")
    return 0 if ok else 1


def cmd_export(a):
    settings = load_settings(a.config)
    db = Database(settings["db_path"])
    cards = [row_to_card(r) for r in db.list(status=None if a.status == "any" else a.status, limit=a.limit,
                                              min_score=a.min_score)]
    out = dumps(cards)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
        print(f"wrote {len(cards)} cards -> {a.out}")
    else:
        print(out)
    return 0


def cmd_stats(a):
    db = Database(load_settings(a.config)["db_path"])
    counts = db.counts()
    print(dumps(counts) if counts else "database is empty")
    return 0


def cmd_validate(a):
    settings, boards = load_settings(a.config), load_boards(a.config)
    sc = load_sources_cfg(a.config)
    client = _client(settings)
    bad = 0
    for src, cfg in build_targets(boards, sc, a.source):
        try:
            n = len(src.fetch(client, cfg))
            print(f"OK    {src.key(cfg):<32} {n} listings")
        except Exception as e:
            bad += 1
            print(f"FAIL  {src.key(cfg):<32} {e}")
    return 1 if bad else 0


def cmd_add_board(a):
    settings = load_settings(a.config)
    parsed = parse_board_url(a.url)
    if not parsed:
        print("Could not recognise that URL. Supported: boards.greenhouse.io/<t>, jobs.lever.co/<t>, jobs.ashbyhq.com/<t>")
        return 1
    parsed["company"] = a.company or parsed["token"].replace("-", " ").title()
    from .sources import ATS_SOURCES
    src = ATS_SOURCES[parsed["ats"]]
    try:
        n = len(src.fetch(_client(settings), parsed))
    except FetchError as e:
        print(f"Board did not respond as expected, not added: {e}")
        return 1
    path = Path(a.config) / "boards.yaml" if a.config else ROOT / "config" / "boards.yaml"
    text = path.read_text(encoding="utf-8") if path.exists() else "boards:\n"
    if re.search(rf"token:\s*{re.escape(parsed['token'])}\b", text) and parsed["ats"] in text:
        print("Already in boards.yaml")
        return 0
    extra = f", region: {parsed['region']}" if parsed.get("region") else ""
    line = (f"  - {{ats: {parsed['ats']}, token: {parsed['token']}, company: \"{parsed['company']}\"{extra}, "
            f"priority: {str(bool(a.priority)).lower()}}}\n")
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + line, encoding="utf-8")
    print(f"Added {parsed['ats']}:{parsed['token']} ({n} open listings right now)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="collector", description="Internship/job opportunity collector")
    p.add_argument("--config", help="config dir (default: ./config)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run", help="fetch, filter, score and store opportunities")
    s.add_argument("--source", help="comma-separated source names (including unstop, aicte, official_pages) or board keys like lever:spotify")
    s.add_argument("--dry-run", action="store_true", help="fetch and report, don't write to the DB")
    s.add_argument("--no-filter", action="store_true", help="skip India/early-career filters (good for smoke tests)")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("manual", help="import hand-picked listings from YAML/JSON/CSV")
    s.add_argument("file")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_manual)

    s = sub.add_parser("list", help="show stored opportunities, best first")
    s.add_argument("--status", default="new", choices=list(STATUSES) + ["any"])
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--min-score", type=float)
    s.add_argument("--include-closed", action="store_true")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="print one opportunity as JSON")
    s.add_argument("id")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("set-status", help="mark an opportunity new/approved/rejected/posted")
    s.add_argument("id")
    s.add_argument("status", choices=STATUSES)
    s.set_defaults(fn=cmd_set_status)

    s = sub.add_parser("export", help="export video-ready JSON cards (the contract for the next stage)")
    s.add_argument("--status", default="approved", choices=list(STATUSES) + ["any"])
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--min-score", type=float)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("stats", help="counts by status")
    s.set_defaults(fn=cmd_stats)

    s = sub.add_parser("validate-boards", help="check that every configured source responds")
    s.add_argument("--source")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("add-board", help="add a company from its careers URL (validates first)")
    s.add_argument("url")
    s.add_argument("--company")
    s.add_argument("--priority", action="store_true")
    s.set_defaults(fn=cmd_add_board)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
