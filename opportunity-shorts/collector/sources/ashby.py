from __future__ import annotations

from ..models import Opportunity
from ..normalize import html_to_text, parse_any_datetime
from .base import Source, first


def _loc_str(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return first(v.get("location"), v.get("name"))
    return ""


class AshbySource(Source):
    name = "ashby"
    closes_missing = True

    def key(self, cfg):
        return f"ashby:{cfg['token']}"

    def fetch(self, client, cfg):
        token = cfg["token"]
        data = client.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}",
                               params={"includeCompensation": "true"})
        out = []
        for j in (data or {}).get("jobs", []):
            if j.get("isListed") is False:
                continue
            postal = ((j.get("address") or {}).get("postalAddress") or {})
            locs = [_loc_str(j.get("location")), postal.get("addressLocality", ""), postal.get("addressCountry", "")]
            locs += [_loc_str(x) for x in (j.get("secondaryLocations") or [])]
            location = "; ".join(dict.fromkeys(l for l in locs if l))
            comp = (j.get("compensation") or {}).get("compensationTierSummary", "") if isinstance(
                j.get("compensation"), dict) else ""
            etype = str(j.get("employmentType", "")).lower()
            out.append(Opportunity(
                source=self.name, board=self.key(cfg), external_id=str(j.get("id")),
                title=(j.get("title") or "").strip(),
                company=first(cfg.get("company"), token),
                apply_url=first(j.get("jobUrl"), j.get("applyUrl")),
                location=location,
                is_remote=bool(j.get("isRemote")),
                opp_type="internship" if "intern" in etype else "job",
                description=first(j.get("descriptionPlain"), html_to_text(j.get("descriptionHtml", ""))),
                posted_at=parse_any_datetime(first(j.get("publishedAt"), j.get("publishedDate"), default=None)),
                department=first(j.get("department"), j.get("team")),
                stipend_text=comp or "",
            ))
        return out
