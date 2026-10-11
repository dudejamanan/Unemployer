from datetime import date
import pytest

from collector.db import Database
from collector.filters import india_eligibility, passes
from collector.http_client import FetchError
from collector.models import Opportunity
from collector.normalize import enrich
from collector.sources import OTHER_SOURCES
from collector.pipeline import build_targets


def opportunity(location='', description='A software internship with real engineering responsibilities.', remote=False):
    job = Opportunity('test', 'test', '1', 'Software Intern', 'Example', 'https://example.com/job',
                      location=location, description=description, is_remote=remote, opp_type='internship')
    return enrich(job, date(2026, 10, 11))


@pytest.mark.parametrize('location,remote,eligible', [
    ('Bengaluru, India', False, True), ('Remote - Worldwide', True, True),
    ('Remote Globally', True, True), ('Remote - Asia', True, True),
    ('Remote - United States', True, False), ('Remote', True, False),
    ('Remote - Europe', True, False), ('New York', False, False),
])
def test_applicant_region(location, remote, eligible):
    assert india_eligibility(opportunity(location, remote=remote))[0] == eligible


def test_explicit_exclusions_and_international_eligibility():
    assert not india_eligibility(opportunity('Remote - Worldwide', 'Worldwide except India.', True))[0]
    assert not india_eligibility(opportunity('India', 'Not open to candidates in India.'))[0]
    assert india_eligibility(opportunity('Geneva', 'Open to applicants of all nationalities.'))[0]
    assert not india_eligibility(opportunity('New York',
        'Open to applicants of all nationalities. Must be authorized to work in the United States.'))[0]


def test_eligibility_filter_keeps_worldwide_but_not_us_remote():
    cfg = {'india_eligible_only': True, 'india_only': False}
    assert passes(opportunity('Remote - Worldwide', remote=True), cfg)[0]
    assert passes(opportunity('Remote - US', remote=True), cfg) == (False, 'not_india_eligible')


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        return next(self.responses)


def test_himalayas_current_schema():
    client = Client([{'jobs': [{'guid': 'abc', 'title': 'Engineering Intern', 'companyName': 'Example',
        'applicationLink': 'https://himalayas.app/jobs/abc', 'locationRestrictions': [{'alpha2': 'IN', 'name': 'India'}],
        'employmentType': 'Intern', 'description': '<p>Real internship responsibilities.</p>',
        'expiryDate': '2026-11-12T18:00:00Z'}]}])
    job = OTHER_SOURCES['himalayas'].fetch(client, {'country': 'IN', 'employment_type': 'Intern'})[0]
    assert job.location == 'Remote - India'
    assert job.opp_type == 'internship' and job.deadline == '2026-11-12'
    assert client.calls[0][1]['country'] == 'IN' and client.calls[0][1]['page'] == 1


def test_himalayas_cursor_and_duplicate_prevention():
    job = {'guid': 'abc', 'title': 'Intern', 'companyName': 'Example', 'applicationLink': 'https://example.com/job'}
    client = Client([{'jobs': [dict(job, guid=str(i)) for i in range(20)], 'nextCursor': 'opaque'},
                     {'jobs': [dict(job, guid='0')]}])
    jobs = OTHER_SOURCES['himalayas'].fetch(client, {})
    assert len(jobs) == 20 and client.calls[1][1]['cursor'] == 'opaque'


def test_unstop_public_schema_and_local_deadline():
    record = {'id': 1, 'status': 'LIVE', 'regn_open': 1, 'title': 'Engineering Internship',
        'organisation': {'name': 'Example'}, 'public_url': 'internships/example-1',
        'details': '<p>A real internship with engineering responsibilities.</p>',
        'jobDetail': {'type': 'wfh', 'paid_unpaid': 'unpaid'},
        'regnRequirements': {'end_regn_dt': '2026-11-12T00:00:00+05:30',
                            'eligibility': '{"studentPassoutYearsSelected":[2027,"all"]}'}}
    client = Client([{'data': {'data': [record], 'last_page': 1}}])
    job = OTHER_SOURCES['unstop'].fetch(client, {})[0]
    assert job.deadline == '2026-11-12' and job.batch_years == [2027]
    assert job.stipend_text == 'Unpaid' and job.location == 'Remote - India'
    assert not job.verified and job.apply_url == 'https://unstop.com/internships/example-1'


def test_aicte_skips_closed_and_retains_review_requirement():
    item = {'id': 'abc', 'isOpen': True, 'title': 'Engineering Intern', 'organization': 'Example',
        'location': 'Pan India', 'mode': 'Remote', 'description': 'Real internship duties.',
        'stipendDisplay': 'INR 10,000 / month', 'deadline': '2026-12-12', 'verified': True}
    client = Client([{'items': [item, dict(item, id='closed', isOpen=False)], 'totalPages': 1}])
    jobs = OTHER_SOURCES['aicte'].fetch(client, {})
    assert len(jobs) == 1 and jobs[0].stipend_text == 'INR 10,000 / month'
    assert not jobs[0].verified and not OTHER_SOURCES['aicte'].closes_missing


@pytest.mark.parametrize('source', ['himalayas', 'unstop', 'aicte'])
def test_changed_schema_is_reported_as_failure(source):
    with pytest.raises(FetchError, match='schema changed'):
        OTHER_SOURCES[source].fetch(Client([{'message': 'changed'}]), {})


def test_paginated_queue_does_not_hide_later_cards():
    db = Database(':memory:')
    try:
        for i in range(3):
            job = opportunity('India')
            job.external_id = str(i)
            db.upsert(job)
        assert db.queue_count() == 3
        first, second = db.list(limit=2), db.list(limit=2, offset=2)
        assert len(first) == 2 and len(second) == 1
        assert not {r['id'] for r in first} & {r['id'] for r in second}
    finally:
        db.close()


def test_source_selection_accepts_multiple_providers():
    targets = build_targets([], {'unstop': {'enabled': True}, 'aicte': {'enabled': True}}, only='unstop,aicte')
    assert [source.name for source, config in targets] == ['unstop', 'aicte']


def test_official_job_page_structure_and_closure():
    from collector.sources.official_pages import OfficialPageSource
    cfg = {'name': 'example', 'url': 'https://example.com/careers/intern'}
    posting = {'@context': 'https://schema.org', '@graph': [{'@type': 'JobPosting',
        'title': 'Software Intern', 'hiringOrganization': {'name': 'Example'},
        'jobLocation': {'address': {'addressLocality': 'Dewas', 'addressCountry': 'India'}},
        'description': '<p>Engineering work with senior developers.</p>'}]}
    class PageClient:
        def get_text(self, url):
            return '<script type="application/ld+json">' + __import__('json').dumps(posting) + '</script>' + self.banner
    client = PageClient()
    client.banner = '<div hidden>This job has been filled.</div>'
    job = OfficialPageSource().fetch(client, cfg)[0]
    assert job.company == 'Example' and job.location == 'Dewas; India'
    client.banner = '<p>This job has been filled.</p>'
    assert OfficialPageSource().fetch(client, cfg) == []
    client.banner = '<h1>Access denied</h1>'
    # An access-denied response never counts as a successful empty snapshot.
    client.get_text = lambda url: '<h1>Access denied</h1>'
    with pytest.raises(FetchError):
        OfficialPageSource().fetch(client, cfg)


def test_employer_html_selectors_include_eligibility():
    from collector.sources.official_pages import OfficialPageSource
    class PageClient:
        def get_text(self, url):
            return '<h1>Graduate Trainee (123)</h1><div id="location">Mumbai</div><p class="detail">Network duties.</p><p class="detail">Experience: Fresher</p>'
    job = OfficialPageSource().fetch(PageClient(), {'name': 'example', 'url': 'https://example.com/job',
        'company': 'Example', 'title_selector': 'h1', 'description_selector': '.detail',
        'location_selector': '#location', 'title_remove_pattern': r'\s*\(\d+\)$'})[0]
    assert job.title == 'Graduate Trainee' and 'Fresher' in job.description
    assert job.location == 'Mumbai'
