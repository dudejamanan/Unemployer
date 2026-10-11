# Opportunity sources and credentials

The collector reads company career boards, public internship catalogues, and explicitly configured employer pages. It does not discover every employer automatically, and it has no three-result cap. The review queue is paginated in groups of 50 so every stored matching listing is accessible. CLI `list` defaults to 20; use `--limit` to increase it.

The active filter is **Indian applicant eligibility**, not office country. It accepts India locations, explicitly worldwide/Asia/APAC remote applicant regions, and descriptions explicitly accepting Indian applicants or all nationalities. Remote alone, US-only remote, and unknown foreign eligibility do not qualify. Explicit India exclusions take precedence. This is evidence for review, not a guarantee of citizenship, residency, visa, timezone, or academic eligibility; verify the individual listing before approval.

The original five boards returned 1,982 listings in the initial collection. India and early-career filters kept three: 1,888 were outside India, 89 were not early-career matches, one matched the senior-title exclusion, and one matched a scam pattern. These are counts from that run, not permanent coverage totals.

After expansion on October 11, 2026, all 13 configured feeds fetched successfully across two collection runs. They returned 3,571 listings and kept 45 matching opportunities: 27 internships and 18 other early-career jobs. The database contains 42 new cards plus the three previously approved cards. Source totals change with vacancies; rerun the local source report for current counts.

The subsequent portal/channel expansion on the same day increased coverage to **23 configured targets**: 15 company boards, three public catalogues, and five individual employer pages. A complete refresh of the first 22 targets succeeded (4,296 fetched, 346 kept); Jio was then added and collected separately. The current database snapshot contains **350 open, unexpired opportunities: 326 internships and 24 jobs**, with 347 new and three approved cards. Bounded catalogues can retain older still-open cards, so database totals need not equal a single refresh's kept count.

## Configured company boards

`config/boards.yaml` is the source of truth. A feed being enabled does not mean it currently has internship vacancies. Listings remain subject to location, early-career, scam, and deadline checks and human review.

| Company | Official career board | API |
| --- | --- | --- |
| Stripe | https://job-boards.greenhouse.io/stripe | Greenhouse |
| GitLab | https://job-boards.greenhouse.io/gitlab | Greenhouse |
| Spotify | https://jobs.lever.co/spotify | Lever |
| Notion | https://jobs.ashbyhq.com/notion | Ashby |
| OpenAI | https://jobs.ashbyhq.com/openai | Ashby |
| Paytm | https://jobs.lever.co/paytm | Lever |
| Instawork | https://job-boards.greenhouse.io/instawork | Greenhouse |
| Cialfo | https://job-boards.greenhouse.io/cialfo | Greenhouse |
| MPOWER Financing | https://job-boards.greenhouse.io/mpowerfinancing | Greenhouse |
| Almabase | https://jobs.ashbyhq.com/almabase | Ashby |
| Aleph | https://jobs.lever.co/aleph | Lever |
| Dun & Bradstreet | https://jobs.lever.co/dnb | Lever |
| Paytm Payments Services | https://jobs.lever.co/paytmpayments | Lever |
| HackerRank | https://job-boards.greenhouse.io/hackerrank | Greenhouse |
| Zscaler | https://job-boards.greenhouse.io/zscaler | Greenhouse |

Additional verified boards are appended by `collector add-board`; consult the configuration for the current complete list.

Run `python scripts/source_report.py` for the enabled source list, active filters, and open, unexpired opportunity counts by source, type, and review status. This report uses the local database without any API call or credentials.

Run `python scripts/check_queue_scripts.py` to check every current card against template-script fact validation without an LLM call or saving posts. All 350 cards in the October 11 snapshot passed. This check found and fixed a date-validator bug that mistook Marketing/Juniper word prefixes after URL IDs for dates; invented deadline years remain rejected.

## Public API endpoints used

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html): `https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true`. GET endpoints need no authentication.
- [Lever Postings API](https://github.com/lever/postings-api): `https://api.lever.co/v0/postings/{company}?mode=json`. Public published postings; EU boards use `api.eu.lever.co`.
- [Ashby Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api): `https://api.ashbyhq.com/posting-api/job-board/{company}?includeCompensation=true`. Public published postings.

The `token` in boards.yaml is the public company board slug (for example `paytm`), **not an API secret**. These APIs require a known company board; they do not offer a universal directory of all employers.

To add another supported official board, validate and save it with:

```powershell
python -m collector add-board https://jobs.lever.co/company-slug --company "Company name"
python -m collector run
```

## Other sources and coverage

| Source | Access and scope | Project integration |
| --- | --- | --- |
| [Himalayas](https://himalayas.app/docs/remote-jobs-api) | Documented public API, no key | Enabled, searches India-eligible internships; current country-object schema, search pagination, salary periods, expiry dates and internship types supported |
| [Remotive](https://github.com/remotive-com/remote-jobs-api) | Public API responded successfully without a key | Adapter exists but remains disabled: its terms restrict submission to third-party websites and require attribution; provider permission should precede channel redistribution |
| RSS/Atom | Public feeds from individual publishers | Supported, no feeds configured |
| [Jobicy](https://github.com/Jobicy/remote-jobs-api) | Public remote jobs API, no key; limited feed window, no all-company guarantee | Researched, no adapter installed |
| [Arbeitnow](https://www.arbeitnow.com/blog/job-board-api) | Free API without a key; Europe-focused rather than an India internship feed | Researched, no adapter installed |
| [Adzuna](https://developer.adzuna.com/overview) | Job search API; requires registration, app_id and app_key | Not configured; no key supplied |
| [Jooble](https://jooblehelpcenter.freshdesk.com/en/support/solutions/articles/60001448238-rest-api-documentation) | Job search API; requires an API key | Not configured; no key supplied |
| [AICTE National Internship Portal](https://internship.aicte-india.org/internships) | Anonymous catalogue endpoint observed in the portal itself | Enabled: up to ten pages / 120 current listings per run; independently unverified even if the provider labels an employer verified |
| [Internshala](https://internshala.com/internships/) | Public page loaded successfully | Disabled: [terms](https://internshala.com/terms) specifically prohibit data gathering/extraction without a written agreement; no automated importer |
| [Unstop](https://unstop.com/internship?oppstatus=open) | Anonymous `/api/public/` endpoint observed in the portal; [robots.txt](https://unstop.com/robots.txt) explicitly allows `/api/public/*` | Enabled: up to ten pages / 180 records per run; normalizes stipend, eligibility years and local deadlines, keeps only live open listings |
| [Wellfound](https://wellfound.com/terms) | Public page loaded; terms restrict harvesting/content redistribution | No automated importer |
| [LinkedIn](https://www.linkedin.com/jobs/) | Channel links identified, no authenticated integration | No scraper or public general-job API configured |
| [National Career Service](https://ncs.gov.in/Pmis-jobList) | Rendered portal tested; underlying PMIS listing API returned HTTP 401 | Not integrated; the empty anonymous page is not evidence that the scheme has zero opportunities |
| [Simplify/Pitt CSC internship list](https://github.com/SimplifyJobs/Summer2027-Internships) | Community discovery list, largely US-oriented; can help find employer career links | No importer installed; validate individual official board links before adding |

There is no verified free service in this research that guarantees all company career pages or all internship listings. Broader coverage needs additional company boards, publisher feeds, and permitted platform integrations. Remote listings require eligibility checks; a remote label alone does not establish that an Indian student can apply.

Unstop and AICTE endpoints are public but undocumented developer interfaces. Changes in their response schemas are reported as source failures, rather than interpreted as an empty catalogue. These bounded feeds do not close previously collected cards merely because an item falls outside the current page window. Source links and credits are retained; a platform link is not presented as an employer-owned career page.

The current public catalogue URLs are:

- `https://unstop.com/api/public/opportunity/search-result?opportunity=internships&page=1&per_page=18&oppstatus=open`
- `https://internship.aicte-india.org/api/v1/catalogue/internships?sort=newest&page=1&pageSize=12`
- `https://himalayas.app/jobs/api/search?country=IN&employment_type=Intern&page=1`

See [the channel source audit](CHANNEL_SOURCES.md) for verified application links from @ashishcode and the five employer-page targets. Increase `max_pages` in sources.yaml for wider catalogue coverage; defaults are intentionally bounded and do not collect every portal record.

## Which credentials were used?

No API key was used for the completed live collection or generated example videos:

- Collection: public company job-board endpoints.
- Earlier demonstration scripts: built-in validated templates. The active configuration now uses local Ollama with no paid API key; see AUTOMATION.md for model readiness and unattended operation.
- Narration: Edge TTS, which needs internet but no user-supplied API key.
- YouTube: OAuth authorization is saved and the configured channel ID was verified. Five real uploads were verified public and processed on October 11, 2026.

No Adzuna, Jooble, RapidAPI, or other third-party job API key has been provided or configured as part of this work.
