import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest

from collector.http_client import FetchError

GREENHOUSE = {"jobs": [
    {"id": 101, "title": "Software Engineering Intern", "updated_at": "2026-10-01T10:00:00-04:00",
     "first_published": "2026-09-28T08:00:00-04:00",
     "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
     "location": {"name": "Bengaluru, India"}, "departments": [{"name": "Engineering"}],
     "content": "&lt;p&gt;Join us as an intern. Stipend: &lt;b&gt;₹40,000 per month&lt;/b&gt;. "
                "Open to 2027 batch graduates. Last date to apply: 25 October 2026.&lt;/p&gt;"
                "&lt;ul&gt;&lt;li&gt;Build things&lt;/li&gt;&lt;li&gt;Learn a lot of things every day&lt;/li&gt;&lt;/ul&gt;"},
    {"id": 102, "title": "Senior Backend Engineer", "updated_at": "2026-10-02T10:00:00Z",
     "absolute_url": "https://boards.greenhouse.io/acme/jobs/102",
     "location": {"name": "Bengaluru, India"}, "departments": [],
     "content": "&lt;p&gt;" + "Seasoned engineer needed. " * 10 + "5+ years of experience required.&lt;/p&gt;"},
    {"id": 103, "title": "Data Science Intern", "updated_at": "2026-10-02T10:00:00Z",
     "absolute_url": "https://boards.greenhouse.io/acme/jobs/103",
     "location": {"name": "San Francisco, CA"}, "departments": [],
     "content": "&lt;p&gt;" + "Great internship in the Bay Area. " * 6 + "&lt;/p&gt;"},
]}

LEVER = [
    {"id": "aaa-1", "text": "Associate Software Engineer (New Grad)", "createdAt": 1790000000000,
     "hostedUrl": "https://jobs.lever.co/globex/aaa-1", "applyUrl": "https://jobs.lever.co/globex/aaa-1/apply",
     "categories": {"location": "Hyderabad", "allLocations": ["Hyderabad"], "commitment": "Full-time",
                    "team": "Platform"},
     "workplaceType": "hybrid", "country": "IN",
     "descriptionPlain": "Freshers can apply. " * 6,
     "lists": [{"text": "Requirements", "content": "<li>Python</li><li>0-1 years experience</li>"}],
     "additionalPlain": "Apply by 10/11/2026."},
    {"id": "aaa-2", "text": "Product Design Intern", "createdAt": 1790000000000,
     "hostedUrl": "https://jobs.lever.co/globex/aaa-2",
     "categories": {"location": "Remote - US", "commitment": "Intern"}, "workplaceType": "remote",
     "descriptionPlain": "Design things. " * 10},
]

ASHBY = {"jobs": [
    {"id": "ash-1", "title": "ML Research Intern", "department": "Research", "employmentType": "Intern",
     "location": "Pune, India", "secondaryLocations": [{"location": "Mumbai, India"}], "isRemote": False,
     "isListed": True, "publishedAt": "2026-10-03T09:00:00.000+00:00",
     "jobUrl": "https://jobs.ashbyhq.com/initech/ash-1", "applyUrl": "https://jobs.ashbyhq.com/initech/ash-1/application",
     "descriptionPlain": "Work on ML. " * 12,
     "compensation": {"compensationTierSummary": "₹30K – ₹50K / month"}},
    {"id": "ash-2", "title": "Hidden Role", "isListed": False, "location": "Pune, India",
     "jobUrl": "https://jobs.ashbyhq.com/initech/ash-2", "descriptionPlain": "x" * 200},
]}

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>
<item><title>Hack for Bharat 2026 Hackathon</title><link>https://example.org/hack</link>
<pubDate>Mon, 05 Oct 2026 06:00:00 GMT</pubDate><guid>g1</guid>
<description>&lt;p&gt;Registrations close on 20 Oct 2026. Open to students across India. Prize pool ₹5 lakh.&lt;/p&gt;</description></item>
</channel></rss>"""


class FakeClient:
    """Stands in for HttpClient. Routes by URL substring; raises FetchError for unknown boards."""

    def __init__(self, fail=()):
        self.fail = set(fail)
        self.calls = []

    def get_json(self, url, params=None, headers=None):
        self.calls.append(url)
        if any(f in url for f in self.fail):
            raise FetchError(f"{url}: HTTP 404")
        if "greenhouse.io" in url:
            return GREENHOUSE
        if "lever.co" in url:
            return LEVER
        if "ashbyhq.com" in url:
            return ASHBY
        raise FetchError(f"{url}: HTTP 404")

    def get_text(self, url, params=None, headers=None):
        self.calls.append(url)
        if "example.org/feed" in url:
            return RSS
        raise FetchError(f"{url}: HTTP 404")


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture
def settings():
    from collector.config import DEFAULT_SETTINGS
    import copy
    return copy.deepcopy(DEFAULT_SETTINGS)
