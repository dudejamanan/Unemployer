# Unemployer: public channel audit and content strategy

Audited October 11, 2026: 12 recent public video pages from each of the five requested channels plus Ashishcode (72 videos). This sample is predominantly long-form content. It is not a complete history, a Shorts-only study, a thumbnail review, or access to private click-through, retention, revenue or traffic-source analytics. View totals depend on video age and existing audiences; they do not prove which title or hashtag caused growth.

| Reference | Observed pattern | What this pipeline uses |
| --- | --- | --- |
| [Aman Jindal](https://www.youtube.com/@talkprowithaman) | Specific government programmes, eligibility, deadlines, full guides, career benefits; paid resume/workshop offers and community links appear in descriptions | Specific programme/employer names, genuine deadlines and useful application guidance; no copied earnings promises |
| [Apna College](https://www.youtube.com/@ApnaCollegeOfficial) | Hiring-process interviews, student outcomes, complete technical courses; only one hashtag across the sampled descriptions | Clear student audience and practical usefulness; hashtags are not treated as a growth formula |
| [Love Babbar](https://www.youtube.com/@LoveBabbar) | Placement preparation, roadmaps, projects and coding topics; #coding on 8/12 descriptions, #programming on 6/12 | Role-relevant technology and career tags, avoiding unrelated trending tags |
| [Internshala](https://www.youtube.com/@InternshalaOfficial) | Employer + role + disclosed compensation + work arrangement; #fresherjobs on 7/12, #internship on 5/12 | Precise employer/role titles; salary and remote-work hooks only when source facts support them |
| [Saumya Singh](https://www.youtube.com/@saumya1singh) | Exam/interview outcomes, sequenced courses, internship calendars, communication guidance | A useful student outcome and contextual application tip in the narration |

Example evidence: [government internship guide](https://www.youtube.com/watch?v=IDOl65FvABA), [off-campus application guide](https://www.youtube.com/watch?v=KlfuFFGWw64), [placement aptitude strategy](https://www.youtube.com/watch?v=biifu9R9DQM), [remote data-science internship](https://www.youtube.com/watch?v=TfQ7q5KFRQU), [winter internship calendar](https://www.youtube.com/watch?v=8aFbjn7UGLY). We examined their titles and descriptions, not the complete audiovisual content. Their scripts, video clips, voices and branding are not reused.

## Implementation

- Local Ollama receives the source card and generates original narration. The preferred language is light Hinglish, with permission in the prompt to use clear English when uncertain. This is a language preference, not a guarantee of perfect pronunciation or Hindi quality.
- Four opening approaches vary by listing: employer/role, student question, location/remote work, or disclosed compensation. Facts control what can be claimed.
- Titles remain within 100 characters, with 3â€“5 relevant hashtags rather than a copied keyword dump. The prompt excludes fabricated salaries, guaranteed selection, fake scarcity and unrelated creator branding.
- Immediate mode publishes active queued videos and newly generated videos without waiting for fixed time slots. Sources refresh every 15 minutes after the previous refresh completes. The local worker checks queues between runs; generation, network time and YouTube quota affect delay. The configured limit is 100 attempts per IST day, subject to lower channel/project limits. YouTube sends at most three upload/live notifications per channel per 24 hours: https://support.google.com/youtube/answer/7457584.
- Generation remains automatically checked for known facts, dates, numeric claims, URLs, layout and media duration. A failed item is deferred automatically; people do not need to approve it.

The public metadata identifies [Unemployer](https://www.youtube.com/@unemployerr) as channel `UCh9aBTHwc9QyIhe5SflYtBQ`. No public video entries could be extracted from its `/videos` response, so no historical performance baseline or claim that the channel has zero content is made. OAuth verifies this exact channel ID before publishing.

## Growth and monetization limits

Shorts can attract viewers, but a feed of minimally varied listing readings may be judged repetitive or mass-produced. Add original explanation and meaningful educational value; neither AI generation nor removing approvals guarantees acceptance. See [YouTube's monetization policy](https://support.google.com/youtube/answer/1311392).

Currently ad-revenue eligibility generally requires 1,000 subscribers plus either 4,000 qualifying public watch hours over 12 months or 10 million qualifying Shorts views over 90 days, followed by review. Shorts Feed watch hours do not count toward the 4,000-hour path. The lower expanded-YPP threshold unlocks some features, not full ad revenue. See [YPP eligibility](https://support.google.com/youtube/answer/72851) and [expanded YPP](https://support.google.com/youtube/answer/13429240). There is no promised monetization date or earnings figure.

The samples include long-form guides and products/community funnels; this implementation still generates opportunity Shorts. Original longer guides, analytics-driven experiments and paid products are potential later expansion, not implemented revenue streams.

External URLs in Shorts descriptions/comments are **not clickable**. The source URL is included as text, but conversion needs a useful application hub in a channel-profile link or an appropriate related long-form video. A hosted application hub has not been deployed. See [YouTube link behavior](https://support.google.com/youtube/answer/13748639).

Diagnostic metadata is saved locally under ignored `data/source_probes/{talkpro,apna,babbar,internshala,saumya}.json`; rerun `scripts/channel_sources.py` deliberately rather than continuously scraping reference channels.


## Refreshed audit and implemented attention patterns

The six-channel public audit was refreshed during this change. Ashishcode's 12 sampled descriptions had no hashtags; titles emphasize employer + hiring + role. Apna College's 12 descriptions contain just one hashtag in total. These observations are evidence against treating a large hashtag list as necessary.

Internshala uses #FresherJobs (7/12) and #Internship (5/12), plus narrow degree/role/work tags. Love Babbar uses #Coding (8/12), #Programming (6/12) and #SoftwareEngineering (4/12), matching the topic. Aman uses programme names, real deadlines and benefits. Saumya uses outcome-led titles and topic-specific tags alongside a personal brand tag.

Applied: employer-led searchable titles; factual remote/compensation details; role tags including Python and DataAnalytics; #Unemployer as our own brand tag; source-linked descriptions; varied factual narration openings. No competitor brand tags, unsupported salary promises or invented scarcity. View counts are not causal evidence; private retention/CTR analytics remain unavailable. This is a titles/descriptions audit, not a full thumbnail or audiovisual review.

Live publishing proof: five uploads were verified public and fully processed on YouTube: 5nSH7LjOFeA, YzIPxnhsm1c, LUIdpKQ-HKg, ywEyjdAeF_o and J0wdENm-Jrs.


Production release: the live public hub is https://unemployer.syrupytide17.chatgpt.site. New narration is shortened using complete generated sentences, a factual employer/role opening and an original general application recommendation; source facts remain checked. New visual treatment adds the logo, section labels, word highlighting and gentle motion. Public metrics report observations only; no viral winner or causal performance claim is made. See PRODUCTION.md for operating and commercial limits.
