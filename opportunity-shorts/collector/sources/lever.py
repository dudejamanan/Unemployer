from __future__ import annotations

from ..models import Opportunity
from ..normalize import html_to_text, parse_any_datetime
from .base import Source, first


class LeverSource(Source):
    name = "lever"
    closes_missing = True

    def key(self, cfg):
        return f"lever:{cfg['token']}"

    def fetch(self, client, cfg):
        token = cfg["token"]
        host = "api.eu.lever.co" if str(cfg.get("region", "")).lower() == "eu" else "api.lever.co"
        data = client.get_json(f"https://{host}/v0/postings/{token}", params={"mode": "json"})
        out = []
        for j in data or []:
            cats = j.get("categories") or {}
            locs = [cats.get("location", "")] + list(cats.get("allLocations") or []) + [j.get("country", "")]
            location = "; ".join(dict.fromkeys(l for l in locs if l))
            parts = [j.get("descriptionPlain") or html_to_text(j.get("description", ""))]
            for sec in j.get("lists") or []:
                parts.append(f"{sec.get('text', '')}\n{html_to_text(sec.get('content', ''))}")
            parts.append(j.get("additionalPlain") or html_to_text(j.get("additional", "")))
            commitment = (cats.get("commitment") or "").lower()
            out.append(Opportunity(
                source=self.name, board=self.key(cfg), external_id=str(j.get("id")),
                title=(j.get("text") or "").strip(),
                company=first(cfg.get("company"), token),
                apply_url=first(j.get("hostedUrl"), j.get("applyUrl")),
                location=location,
                is_remote=str(j.get("workplaceType", "")).lower() == "remote",
                opp_type="internship" if "intern" in commitment else "job",
                description="\n\n".join(p for p in parts if p).strip(),
                posted_at=parse_any_datetime(j.get("createdAt")),
                department=first(cats.get("department"), cats.get("team")),
            ))
        return out
