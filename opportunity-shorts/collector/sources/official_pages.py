"""Read structured JobPosting data from explicitly configured employer career pages."""
import json
import re
from bs4 import BeautifulSoup

from ..http_client import FetchError
from ..models import Opportunity
from ..normalize import html_to_text, parse_any_datetime
from .base import Source
from .public_portals import deadline_date


def job_postings(value):
    if isinstance(value, dict):
        types = value.get('@type') or []
        types = [types] if isinstance(types, str) else types
        if 'JobPosting' in types:
            yield value
        for child in value.values():
            yield from job_postings(child)
    elif isinstance(value, list):
        for child in value:
            yield from job_postings(child)


class OfficialPageSource(Source):
    name = 'official_pages'
    closes_missing = True  # Each target is one complete, explicitly configured job page.

    def key(self, cfg):
        return 'official_pages:' + cfg['name']

    def fetch(self, client, cfg):
        soup = BeautifulSoup(client.get_text(cfg['url']), 'html.parser')
        visible = BeautifulSoup(str(soup), 'html.parser')
        for tag in visible.select('[hidden], [aria-hidden="true"], .phw-d-none, [style*="display: none"], script, style'):
            tag.decompose()
        text = visible.get_text(' ', strip=True)
        if re.search(r'\b(?:this|the) (?:job|position)(?: you are trying to apply for)? (?:has been|is) (?:filled|closed|no longer available)\b', text, re.I):
            return []
        postings = []
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                postings.extend(job_postings(json.loads(script.get_text())))
            except ValueError:
                continue
        if not postings and cfg.get('description_selector'):
            title = soup.select_one(cfg.get('title_selector', '[itemprop="title"]'))
            descriptions = soup.select(cfg['description_selector'])
            location = soup.select_one(cfg.get('location_selector', '[itemprop="jobLocation"]'))
            if title and descriptions:
                role = title.get_text(' ', strip=True)
                if cfg.get('title_remove_pattern'):
                    role = re.sub(cfg['title_remove_pattern'], '', role).strip()
                postings = [{'title': role, 'description': '\n'.join(str(tag) for tag in descriptions),
                             'jobLocation': {'address': {'addressLocality': location.get_text(' ', strip=True) if location else ''}}}]
        if not postings:
            raise FetchError('Official page no longer contains recognizable job posting data')
        out = []
        for job in postings:
            employer = job.get('hiringOrganization') or {}
            employer = employer.get('name') if isinstance(employer, dict) else str(employer)
            company = employer or cfg.get('company') or ''
            title = job.get('title') or ''
            if not title or not company:
                raise FetchError('Official job posting is missing its title or employer')
            locations = job.get('jobLocation') or []
            locations = [locations] if isinstance(locations, dict) else locations
            names = []
            for location in locations:
                address = location.get('address') or {} if isinstance(location, dict) else {}
                for field in ('addressLocality', 'addressRegion', 'addressCountry'):
                    value = address.get(field)
                    if isinstance(value, dict):
                        value = value.get('name') or ''
                    if value:
                        names.append(str(value))
            remote = job.get('jobLocationType') == 'TELECOMMUTE'
            restrictions = job.get('applicantLocationRequirements') or []
            restrictions = [restrictions] if isinstance(restrictions, dict) else restrictions
            if remote:
                names += [r.get('name', '') for r in restrictions if isinstance(r, dict)]
            location = '; '.join(dict.fromkeys(names))
            if remote:
                location = 'Remote - ' + location if location else 'Remote (applicant countries not specified)'
            identifier = job.get('identifier') or {}
            external_id = str(identifier.get('value') or cfg['url']) if isinstance(identifier, dict) else str(identifier)
            out.append(Opportunity(self.name, self.key(cfg), external_id, title, company, cfg['url'],
                location=location, is_remote=remote, description=html_to_text(job.get('description', '')),
                deadline=deadline_date(job.get('validThrough')), posted_at=parse_any_datetime(job.get('datePosted'))))
        return out
