# Data contract: what Stage 1 hands to Stage 2

## Card JSON (`python -m collector export`), a list of:
```json
{
  "id": "83856b4619525938",          // stable 16-hex id; use as the key everywhere
  "type": "internship",              // internship | job | hackathon | fellowship | scholarship | other
  "role": "Example Software Engineering Intern",
  "company": "Example Corp",
  "location": "Bengaluru, India",    // "Remote" if remote with no location
  "is_india": true,
  "is_remote": false,
  "stipend": "Rs 25,000 per month",  // "" when unknown, never invent one
  "batch_years": [2027, 2028],       // [] when unknown
  "experience": "",                  // e.g. "0-2 years", "Freshers welcome", ""
  "deadline": "2026-11-30",          // YYYY-MM-DD or null (null = say "apply soon", never invent a date)
  "apply_url": "https://...",        // the ONLY link that may go in the video description
  "description": "plain text, max 6000 chars",
  "posted_at": "2026-10-03T09:00:00Z",
  "score": 80.0,
  "verified": true,                  // true = hand-added; false = from a public feed
  "source": "manual | greenhouse | lever | ashby | rss | himalayas | remotive",
  "status": "approved"               // new | approved | rejected | posted
}
```
Rules for consumers: every on-screen / spoken fact must come from these fields. Empty/null means "don't mention".

## SQLite table `opportunities` (data/opportunities.db)
Columns: id (PK), source, board, external_id, title, company, location, is_india, is_remote, opp_type, description,
apply_url, posted_at, deadline, stipend_text, batch_years (JSON text), experience_text, department, score, verified,
status, is_open (0 = vanished from source), content_hash, first_seen_at, last_seen_at, updated_at.

Stage 2+ must NOT alter this table. Use a separate table (e.g. `posts`) keyed by `opportunity_id`.

## Status lifecycle
`new` -> (human review) -> `approved` or `rejected` -> (after upload) `posted`.
Use `python -m collector set-status <id> <status>` or call `Database.set_status()` from Python.

## Python API for the next stages
```python
from collector.config import load_settings
from collector.db import Database, row_to_card
db = Database(load_settings()["db_path"])
cards = [row_to_card(r) for r in db.list(status="approved", limit=10)]   # best first, open + unexpired only
db.set_status(card["id"], "posted")
```
