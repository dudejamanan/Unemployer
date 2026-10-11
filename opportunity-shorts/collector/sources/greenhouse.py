from __future__ import annotations

from ..models import Opportunity
from ..normalize import html_to_text, parse_any_datetime
from .base import Source, first


class GreenhouseSource(Source):
    name = "greenhouse"
    closes_missing = True

    def key(self, cfg):
        return f"greenhouse:{cfg['token']}"

    def fetch(self, client, cfg):
        token = cfg["token"]
        data = client.get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                               params={"content": "true"})
        out = []
        for j in (data or {}).get("jobs", []):
            # Office metadata describes company offices, not necessarily this job's work arrangement.
            location = ((j.get("location") or {}).get("name") or '').strip()
            if not location:
                location = '; '.join(dict.fromkeys(o.get('name', '') for o in (j.get('offices') or [])
                                                   if isinstance(o, dict) and o.get('name')))
            depts = ", ".join(d.get("name", "") for d in (j.get("departments") or []) if isinstance(d, dict))
            out.append(Opportunity(
                source=self.name, board=self.key(cfg), external_id=str(j.get("id")),
                title=(j.get("title") or "").strip(),
                company=first(cfg.get("company"), j.get("company_name"), token),
                apply_url=j.get("absolute_url") or f"https://boards.greenhouse.io/{token}/jobs/{j.get('id')}",
                location=location,
                description=html_to_text(j.get("content", "")),
                posted_at=parse_any_datetime(first(j.get("first_published"), j.get("updated_at"), default=None)),
                department=depts,
            ))
        return out
