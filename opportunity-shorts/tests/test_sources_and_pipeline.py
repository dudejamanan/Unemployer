from datetime import date

from collector.db import Database
from collector.filters import passes
from collector.http_client import FetchError
from collector.normalize import enrich
from collector.pipeline import build_targets, import_manual, run_collection
from collector.sources import ATS_SOURCES, OTHER_SOURCES
from collector.sources.rss import parse_feed

TODAY = date(2026, 10, 5)
BOARDS = [
    {"ats": "greenhouse", "token": "acme", "company": "Acme"},
    {"ats": "lever", "token": "globex", "company": "Globex"},
    {"ats": "ashby", "token": "initech", "company": "Initech"},
]


def test_greenhouse_parse(fake_client):
    jobs = ATS_SOURCES["greenhouse"].fetch(fake_client, BOARDS[0])
    assert len(jobs) == 3
    j = jobs[0]
    assert j.title == "Software Engineering Intern" and j.company == "Acme"
    assert j.location == "Bengaluru, India" and j.department == "Engineering"
    assert "<" not in j.description and "- Build things" in j.description
    assert j.posted_at == "2026-09-28T12:00:00Z"


def test_lever_parse(fake_client):
    jobs = ATS_SOURCES["lever"].fetch(fake_client, BOARDS[1])
    assert jobs[0].apply_url == "https://jobs.lever.co/globex/aaa-1"
    assert "Python" in jobs[0].description and "Apply by 10/11/2026" in jobs[0].description
    assert jobs[1].opp_type == "internship" and jobs[1].is_remote


def test_ashby_parse_skips_unlisted(fake_client):
    jobs = ATS_SOURCES["ashby"].fetch(fake_client, BOARDS[2])
    assert len(jobs) == 1 and jobs[0].opp_type == "internship"
    assert "Pune" in jobs[0].location and "Mumbai" in jobs[0].location
    assert "30K" in jobs[0].stipend_text


def test_rss_parse(fake_client):
    items = parse_feed(fake_client.get_text("https://example.org/feed.xml"))
    assert items[0]["title"].startswith("Hack for Bharat")
    cfg = {"name": "hack", "url": "https://example.org/feed.xml", "company": "Org", "opp_type": "hackathon",
           "location": "India"}
    opps = OTHER_SOURCES["rss"].fetch(fake_client, cfg)
    enrich(opps[0], TODAY)
    assert opps[0].deadline == "2026-10-20" and opps[0].is_india and opps[0].opp_type == "hackathon"


def test_filters_keep_india_early_career_only(fake_client, settings):
    db = Database(":memory:")
    stats = run_collection(settings, BOARDS, {}, db, fake_client, today=TODAY)
    titles = {r["title"] for r in db.list(status="new", limit=50, today=TODAY)}
    assert titles == {"Software Engineering Intern", "Associate Software Engineer (New Grad)", "ML Research Intern"}
    assert stats.dropped["not_india"] >= 2          # SF intern + US remote design intern
    assert stats.dropped["not_early_career"] >= 1 or stats.dropped["excluded_title"] >= 1
    assert stats.new == 3 and stats.boards_ok == 3


def test_enrichment_end_to_end(fake_client, settings):
    db = Database(":memory:")
    run_collection(settings, BOARDS, {}, db, fake_client, today=TODAY)
    row = [r for r in db.list(limit=50, today=TODAY) if r["title"] == "Software Engineering Intern"][0]
    assert row["deadline"] == "2026-10-25" and "40,000" in row["stipend_text"] and row["is_india"] == 1
    assert row["batch_years"] == "[2027]"
    assert row["score"] == 70.0   # india30 + internship20 + stipend10 + batch5 + recent5


def test_rerun_is_idempotent_and_keeps_status(fake_client, settings):
    db = Database(":memory:")
    run_collection(settings, BOARDS, {}, db, fake_client, today=TODAY)
    first = db.list(limit=1, today=TODAY)[0]
    db.set_status(first["id"], "approved")
    stats = run_collection(settings, BOARDS, {}, db, fake_client, today=TODAY)
    assert stats.new == 0 and stats.unchanged == 3
    assert db.get(first["id"])["status"] == "approved"


def test_vanished_listing_is_closed(fake_client, settings):
    db = Database(":memory:")
    run_collection(settings, BOARDS[:1], {}, db, fake_client, today=TODAY)
    assert len(db.list(limit=50, today=TODAY)) == 1
    import conftest
    saved = list(conftest.GREENHOUSE["jobs"])
    conftest.GREENHOUSE["jobs"] = [j for j in saved if j["id"] != 101]
    try:
        stats = run_collection(settings, BOARDS[:1], {}, db, fake_client, today=TODAY)
    finally:
        conftest.GREENHOUSE["jobs"] = saved
    assert stats.closed == 1 and db.list(limit=50, today=TODAY) == []


def test_failed_board_does_not_close_or_crash(settings):
    from conftest import FakeClient
    db = Database(":memory:")
    run_collection(settings, BOARDS[:1], {}, db, FakeClient(), today=TODAY)
    stats = run_collection(settings, BOARDS, {}, db, FakeClient(fail=["greenhouse"]), today=TODAY)
    assert stats.boards_failed == 1 and stats.closed == 0 and stats.boards_ok == 2
    assert len(db.list(limit=50, today=TODAY)) >= 1


def test_dry_run_writes_nothing(fake_client, settings):
    db = Database(":memory:")
    stats = run_collection(settings, BOARDS, {}, db, fake_client, dry_run=True, today=TODAY)
    assert stats.kept == 3 and db.counts() == {}


def test_only_filter_and_targets():
    t = build_targets(BOARDS, {"himalayas": {"enabled": True}}, only=None)
    assert [s.name for s, _ in t] == ["greenhouse", "lever", "ashby", "himalayas"]
    assert [s.key(c) for s, c in build_targets(BOARDS, {}, only="lever:globex")] == ["lever:globex"]


def test_expired_deadline_hidden_from_list(fake_client, settings):
    db = Database(":memory:")
    run_collection(settings, BOARDS, {}, db, fake_client, today=TODAY)
    assert any(r["deadline"] == "2026-10-25" for r in db.list(limit=50, today=TODAY))
    assert not any(r["deadline"] == "2026-10-25" for r in db.list(limit=50, today=date(2026, 11, 1)))


def test_manual_import(tmp_path, settings):
    f = tmp_path / "m.yaml"
    f.write_text("""
- title: "Campus Ambassador"
  company: "Org"
  apply_url: "https://example.com/x"
  opp_type: internship
  location: "Delhi"
  description: "Register by 30 November 2026. Stipend: Rs 5,000 per month. 2027 batch eligible."
""", encoding="utf-8")
    db = Database(":memory:")
    stats = import_manual(f, settings, db, today=TODAY)
    row = db.list(limit=5, today=TODAY)[0]
    assert stats.new == 1 and row["verified"] == 1 and row["deadline"] == "2026-11-30"
    assert import_manual(f, settings, db, today=TODAY).unchanged == 1


def test_manual_validation(tmp_path, settings):
    import pytest
    f = tmp_path / "bad.yaml"
    f.write_text("- title: x\n  company: y\n", encoding="utf-8")
    with pytest.raises(ValueError):
        import_manual(f, settings, Database(":memory:"), today=TODAY)


def test_passes_reason_codes(settings):
    from collector.models import Opportunity
    o = Opportunity("greenhouse", "g:x", "1", "Senior Engineer", "X", "https://x", location="Pune, India",
                    description="d" * 200)
    enrich(o, TODAY)
    assert passes(o, settings["filters"]) == (False, "not_early_career")
    settings["filters"]["mode"] = "all"
    assert passes(o, settings["filters"]) == (False, "excluded_title")


def test_scam_listing_is_dropped(settings):
    from collector.models import Opportunity
    o = Opportunity("rss", "rss:x", "1", "Data Entry Intern", "Shady", "https://x", location="Delhi, India",
                    description="Pay a refundable security deposit of Rs 2000 to confirm your seat. " * 3)
    enrich(o, TODAY)
    assert passes(o, settings["filters"]) == (False, "suspicious")
