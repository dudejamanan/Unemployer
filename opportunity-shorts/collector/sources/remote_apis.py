"""Public remote-job APIs. Eligibility uses provider applicant-location restrictions."""
from __future__ import annotations

from ..models import Opportunity
from ..http_client import FetchError
from ..normalize import html_to_text, parse_any_datetime
from .base import Source, first


class HimalayasSource(Source):
    name = "himalayas"
    closes_missing = False

    def key(self, cfg):
        return "himalayas"

    def fetch(self, client, cfg):
        out, page_size = [], 20
        cursor = None
        seen = set()
        for page in range(int(cfg.get("max_pages", 3))):
            params = {'limit': page_size}
            if cfg.get('country') or cfg.get('employment_type') or cfg.get('search'):
                endpoint = 'https://himalayas.app/jobs/api/search'
                params['page'] = page + 1
                for name in ('country', 'employment_type'):
                    if cfg.get(name):
                        params[name] = cfg[name]
                if cfg.get('search'):
                    params['q'] = cfg['search']
            else:
                endpoint = 'https://himalayas.app/jobs/api'
                if cursor:
                    params['cursor'] = cursor
            data = client.get_json(endpoint, params=params)
            if not isinstance(data, dict) or not isinstance(data.get('jobs'), list):
                raise FetchError('Himalayas public jobs response schema changed')
            jobs = (data or {}).get("jobs", []) if isinstance(data, dict) else []
            if not jobs:
                break
            for j in jobs:
                restr = j.get("locationRestrictions") or []
                restr = [restr] if isinstance(restr, str) else list(restr)
                restr = [first(r.get('name'), r.get('alpha2'), r.get('slug')) if isinstance(r, dict) else str(r) for r in restr]
                restr = ['India' if r.upper() == 'IN' else r for r in restr]
                external_id = str(first(j.get('guid'), j.get('applicationLink'), j.get('title')))
                if external_id in seen:
                    continue
                seen.add(external_id)
                lo, hi, cur = j.get("minSalary"), j.get("maxSalary"), j.get("currency") or ""
                pay = f"{cur} {lo}-{hi}".strip() if lo and hi else ""
                if pay and j.get('salaryPeriod'):
                    pay += ' / ' + str(j['salaryPeriod'])
                out.append(Opportunity(
                    source=self.name, board=self.key(cfg),
                    external_id=external_id,
                    title=(j.get("title") or "").strip(),
                    company=j.get("companyName") or "",
                    apply_url=first(j.get("applicationLink"), j.get("guid")),
                    location="Remote - " + (", ".join(restr) if restr else "Worldwide"),
                    is_remote=True,
                    opp_type='internship' if 'intern' in str(j.get('employmentType', '')).lower() else 'job',
                    description=html_to_text(j.get("description", "")) or (j.get("excerpt") or ""),
                    posted_at=parse_any_datetime(j.get("pubDate")),
                    deadline=(parse_any_datetime(j.get('expiryDate')) or '')[:10] or None,
                    stipend_text=pay,
                ))
            if len(jobs) < page_size:
                break
            cursor = data.get('nextCursor')
            if endpoint.endswith('/api') and not cursor:
                break
        return out


class RemotiveSource(Source):
    name = "remotive"
    closes_missing = False

    def key(self, cfg):
        return "remotive"

    def fetch(self, client, cfg):
        params = {"limit": int(cfg.get("limit", 50))}
        if cfg.get("category"):
            params["category"] = cfg["category"]
        if cfg.get('search'):
            params['search'] = cfg['search']
        data = client.get_json("https://remotive.com/api/remote-jobs", params=params)
        out = []
        for j in (data or {}).get("jobs", []):
            req = j.get("candidate_required_location") or "Worldwide"
            out.append(Opportunity(
                source=self.name, board=self.key(cfg), external_id=str(j.get("id")),
                title=(j.get("title") or "").strip(), company=j.get("company_name") or "",
                apply_url=j.get("url") or "", location=f"Remote - {req}", is_remote=True,
                opp_type="internship" if "intern" in str(j.get("job_type", "")).lower() else "job",
                description=html_to_text(j.get("description", "")),
                posted_at=parse_any_datetime(j.get("publication_date")),
                stipend_text=j.get("salary") or "",
            ))
        return out
