"""Keyless public listing endpoints observed in the providers' own web applications.

These endpoints are undocumented and may change. Results are publisher listings,
not independently verified employer vacancies. Human review is always required.
"""
from datetime import date
import json
from urllib.parse import urljoin

from ..http_client import FetchError
from ..models import Opportunity
from ..normalize import html_to_text, parse_any_datetime
from .base import Source


def deadline_date(value):
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


class UnstopSource(Source):
    name = 'unstop'
    closes_missing = False  # A bounded/filtered catalogue is not a full-board snapshot.

    def key(self, cfg):
        return self.name

    def fetch(self, client, cfg):
        out, seen = [], set()
        for page in range(1, int(cfg.get('max_pages', 10)) + 1):
            response = client.get_json('https://unstop.com/api/public/opportunity/search-result', params={
                'opportunity': 'internships', 'oppstatus': 'open', 'page': page, 'per_page': 18})
            data = response.get('data') if isinstance(response, dict) else None
            if not isinstance(data, dict) or not isinstance(data.get('data'), list):
                raise FetchError('Unstop public listing response schema changed')
            jobs = data['data']
            for job in jobs:
                if str(job.get('status', '')).upper() not in ('LIVE', 'OPEN') or not job.get('regn_open'):
                    continue
                external_id = str(job['id'])
                if external_id in seen:
                    continue
                seen.add(external_id)
                detail = job.get('jobDetail') or {}
                address = job.get('address_with_country_logo') or {}
                locations = detail.get('locations') or job.get('locations') or []
                location_names = [loc.get('name', '') if isinstance(loc, dict) else str(loc) for loc in locations]
                location_names += [address.get('city', ''), address.get('state', ''), address.get('country', '')]
                location = '; '.join(dict.fromkeys(name for name in location_names if name))
                remote = detail.get('type') == 'wfh'
                # The public catalogue is labelled "Internships in India" by Unstop.
                # Use that scope only when the record does not supply another location.
                if not location:
                    location = 'Remote - India' if remote else 'India (exact location not supplied)'
                requirements = job.get('regnRequirements') or {}
                description = html_to_text(job.get('details', ''))
                eligibility = requirements.get('eligibility')
                try:
                    eligibility = json.loads(eligibility) if isinstance(eligibility, str) else eligibility or {}
                except ValueError:
                    eligibility = {}
                years = []
                for key in ('fresherPassoutYearsSelected', 'studentPassoutYearsSelected'):
                    years.extend(y for y in eligibility.get(key, []) if isinstance(y, int))
                salary = ''
                if detail.get('paid_unpaid') == 'unpaid':
                    salary = 'Unpaid'
                elif detail.get('show_salary') and not detail.get('not_disclosed') and detail.get('min_salary') is not None:
                    lo, hi = detail['min_salary'], detail.get('max_salary')
                    amount = str(lo) if hi in (None, lo) else f'{lo}-{hi}'
                    currency = 'INR' if detail.get('currency') == 'fa-rupee' else str(detail.get('currency', ''))
                    salary = f"{currency} {amount} / {detail.get('pay_in', 'period not specified')}".strip()
                url = urljoin('https://unstop.com/', job.get('seo_url') or job.get('public_url') or '')
                if not url.startswith('https://unstop.com/internships/'):
                    continue
                out.append(Opportunity(self.name, self.key(cfg), external_id, job.get('title', ''),
                    (job.get('organisation') or {}).get('name', ''), url,
                    location=location, is_remote=remote, opp_type='internship',
                    description=description, stipend_text=salary, batch_years=sorted(set(years)),
                    deadline=deadline_date(requirements.get('end_regn_dt') or job.get('end_date')),
                    posted_at=parse_any_datetime(job.get('approved_date') or job.get('updated_at'))))
            if not jobs or page >= int(data.get('last_page', page)):
                break
        return out


class AicteSource(Source):
    name = 'aicte'
    closes_missing = False

    def key(self, cfg):
        return self.name

    def fetch(self, client, cfg):
        out, seen = [], set()
        for page in range(1, int(cfg.get('max_pages', 10)) + 1):
            data = client.get_json('https://internship.aicte-india.org/api/v1/catalogue/internships',
                params={'sort': 'newest', 'page': page, 'pageSize': 12})
            if not isinstance(data, dict) or not isinstance(data.get('items'), list):
                raise FetchError('AICTE public catalogue response schema changed')
            jobs = data['items']
            for job in jobs:
                if not job.get('isOpen') or str(job.get('id')) in seen:
                    continue
                external_id = str(job['id'])
                seen.add(external_id)
                description = html_to_text(job.get('description', ''))
                eligibility = job.get('eligibility') or []
                if eligibility:
                    description += '\nEligibility: ' + '; '.join(str(item) for item in eligibility)
                out.append(Opportunity(self.name, self.key(cfg), external_id, job.get('title', ''),
                    job.get('organization', ''), 'https://internship.aicte-india.org/internships/' + external_id,
                    location=job.get('location') or '', is_remote=str(job.get('mode', '')).lower() in ('remote', 'virtual'),
                    opp_type='internship', description=description, stipend_text=job.get('stipendDisplay') or '',
                    deadline=deadline_date(job.get('deadline')), posted_at=parse_any_datetime(job.get('postedDate'))))
            if not jobs or page >= int(data.get('totalPages', page)):
                break
        return out
