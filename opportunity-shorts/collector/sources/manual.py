from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from ..models import Opportunity, OPP_TYPES


def _as_years(v) -> list:
    if not v:
        return []
    if isinstance(v, (int, float)):
        return [int(v)]
    if isinstance(v, str):
        v = [x for x in v.replace(";", ",").split(",") if x.strip()]
    return sorted({int(x) for x in v})


def load_manual(path) -> list:
    """YAML list, JSON list, or CSV with columns: title, company, apply_url, [opp_type, location,
    deadline, stipend_text, batch_years, description, posted_at]. Manual items are marked verified."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
    elif p.suffix.lower() == ".json":
        rows = json.loads(text)
    else:
        rows = yaml.safe_load(text)
    if isinstance(rows, dict):
        rows = rows.get("items", [])
    out = []
    for i, r in enumerate(rows or [], start=1):
        missing = [k for k in ("title", "company", "apply_url") if not str(r.get(k, "")).strip()]
        if missing:
            raise ValueError(f"manual item #{i}: missing {', '.join(missing)}")
        opp_type = str(r.get("opp_type") or "job").lower()
        if opp_type not in OPP_TYPES:
            raise ValueError(f"manual item #{i}: opp_type must be one of {OPP_TYPES}")
        url = str(r["apply_url"]).strip()
        out.append(Opportunity(
            source="manual", board="manual", external_id=hashlib.sha1(url.encode()).hexdigest()[:12],
            title=str(r["title"]).strip(), company=str(r["company"]).strip(), apply_url=url,
            location=str(r.get("location") or ""), opp_type=opp_type,
            description=str(r.get("description") or ""), posted_at=r.get("posted_at") or None,
            deadline=str(r["deadline"]) if r.get("deadline") else None,
            stipend_text=str(r.get("stipend_text") or ""), batch_years=_as_years(r.get("batch_years")),
            verified=True,
        ))
    return out
