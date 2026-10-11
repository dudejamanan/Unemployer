# @ashishcode source audit

On October 11, 2026, ten recent videos on [Ashish Kumar's channel](https://www.youtube.com/@ashishcode/videos) were inspected. Eight had extractable public descriptions. Only published links were used as evidence; the channel's private discovery workflow, scraper, or API usage cannot be established from those links.

| Video | Identifiable opportunity sources | Integration result |
| --- | --- | --- |
| [Zscaler Hiring Summer Interns](https://www.youtube.com/watch?v=SDeo-9MzVLI) | LinkedIn short link and Google Form | Zscaler's separately verified official Greenhouse board added; Form ownership not assumed |
| [Accenture Hiring Interns](https://www.youtube.com/watch?v=4r-SVaBa_Wk) | LinkedIn short link, Jio Careers, Naukri | Jio's verified graduate trainee page added; LinkedIn/Naukri not scraped |
| [CRED Internship Hiring](https://www.youtube.com/watch?v=_l1ZJhuaj0o) | CodeChef START260 and LinkedIn short link | A coding contest does not establish an active internship; no vacancy fabricated |
| [JAR Hiring Interns](https://www.youtube.com/watch?v=5ps-GDBNKL0) | NIIT Careers, Urbanizer Careers, Google Forms | NIIT associate software engineer and Urbanizer intern/engineer pages added; Forms require ownership/role verification |
| [Infosys Hiring Interns](https://www.youtube.com/watch?v=oN1INOx7kUA) | LinkedIn post, HackerRank Careers, Virtusa Careers, LSEG Workday, Google Form | HackerRank official board and Virtusa structured page added; LSEG job endpoint returned 403 and was not integrated |
| [HP Hiring Interns](https://www.youtube.com/watch?v=R3NEf2BAer0) | Unstop's HP Power Lab competition | Unstop's public internship catalogue added; the linked competition is not represented as an internship vacancy |

Other inspected videos concerned interview preparation or had no extractable description. Educative affiliate, Topmate mentoring, YouTube memberships, and similar promotional links were excluded from opportunity collection. Their referral parameters are not copied into our source listings.

## Recurring employer pages

`config/sources.yaml` includes five explicitly configured pages:

- Urbanizer: Software Engineer Intern and Software Engineer.
- NIIT: Associate Software Engineer, request ID 3760.
- Virtusa: Associate, CREQ261742.
- Reliance Jio: Graduate Engineer Trainee, job ID 87210862.

The adapter reads JobPosting JSON-LD where supplied, and explicitly configured employer HTML fields for NIIT and Jio. A missing job schema or HTTP error is a collection failure, never a fabricated listing. Visible closure notices close the single-page target; hidden expired-page templates are ignored. Virtusa's link produced conflicting availability signals across clients, so its stored metadata remains unverified and must be checked before publication. LSEG's 403 was not bypassed.

These are current individual vacancies, not complete NIIT/Jio/Virtusa company feeds. HackerRank and Zscaler use their complete public company boards. The channel also publishes links to LinkedIn, Naukri, and Google Forms, which are discovery leads rather than verified employer feeds.

To repeat the description-link audit without downloading videos:

```powershell
python scripts/channel_sources.py --limit 10
```

The extracted URL report is saved to `data/source_probes/channel_sources.json`. New links still require source validation before adding them to collection. No API key is required for this public metadata audit.
