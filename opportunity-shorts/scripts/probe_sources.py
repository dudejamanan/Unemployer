"""Read-only public source diagnostics; never logs credentials or bypasses access controls."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    'himalayas': 'https://himalayas.app/jobs/api/search?country=IN&employment_type=Intern',
    'remotive': 'https://remotive.com/api/remote-jobs?search=intern&limit=100',
    'internshala': 'https://internshala.com/internships/',
    'unstop': 'https://unstop.com/internships',
    'unstop_terms': 'https://unstop.com/terms-and-conditions',
    'unstop_legal': 'https://unstop.com/legal/terms-of-use',
    'aicte': 'https://internship.aicte-india.org/',
    'wellfound': 'https://wellfound.com/jobs',
    'linkedin': 'https://www.linkedin.com/robots.txt',
    'ncs': 'https://www.ncs.gov.in/Pmis-jobList',
    'jooble': 'https://jooble.org/api/about',
    'unstop_api': 'https://unstop.com/api/public/opportunity/search-result?opportunity=internships&page=1&per_page=18&oppstatus=open',
    'aicte_api': 'https://internship.aicte-india.org/api/v1/catalogue/internships?sort=best&page=1&pageSize=12',
    'ncs_api': 'https://api.ncs.gov.in/api/pmis/sso/internships?page=1&size=10',
    'urbanizer': 'https://urbanizer.in/careers/software-engineer-intern/',
    'niit': 'https://jobs.niit.com/NIITMTS/job/Gurgaon,-Haryana-ASSOCIATE-SOFTWARE-ENGINEER/60339044/',
    'virtusa': 'https://www.virtusa.com/careers/job-search/global/en/job/CREQ261742/Associate',
    'lseg': 'https://lseg.wd3.myworkdayjobs.com/Graduate_Careers/job/IND-BLR-Divyasree-Technopolis/Business-Graduate-Associate--Data---Analytics-_R0123974',
}


def probe(item):
    name, url = item
    try:
        response = requests.get(url, timeout=20, headers={'User-Agent': 'UnemployerBot/0.1', 'Accept': '*/*'})
        suffix = 'json' if 'json' in response.headers.get('Content-Type', '') else 'html'
        folder = ROOT / 'data' / 'source_probes'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f'{name}.{suffix}').write_text(response.text, encoding='utf-8')
        soup = BeautifulSoup(response.text, 'html.parser')
        result = {'source': name, 'status': response.status_code, 'url': response.url,
                  'title': soup.title.get_text(strip=True) if soup.title else '', 'bytes': len(response.content)}
        if suffix == 'json':
            data = response.json()
            result['keys'] = list(data)[:15] if isinstance(data, dict) else ['list']
            jobs = data.get('jobs', []) if isinstance(data, dict) else data
            result['jobs'] = len(jobs)
            result['first_job_keys'] = list(jobs[0]) if jobs else []
        else:
            result['structured_data'] = len(soup.select('script[type="application/ld+json"]'))
            result['interesting_links'] = [a.get('href') for a in soup.select('a[href]')
                if any(term in a.get('href', '').lower() for term in ('term', 'internship-details', '/internship/', 'api/', 'pmi'))][:15]
        return result
    except requests.RequestException as exc:
        return {'source': name, 'error': type(exc).__name__}


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=4) as executor:
        for result in executor.map(probe, TARGETS.items()):
            print(json.dumps(result), flush=True)
