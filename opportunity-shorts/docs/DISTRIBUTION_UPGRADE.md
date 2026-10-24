# Autonomous distribution upgrade — 24 October 2026

This upgrade keeps content publishing fully autonomous. Missing evidence is deferred or quarantined; there is no human approval queue. One-time Google account consent and service configuration are access requirements, not editorial approval gates.

## Audited baseline

Inspected the audience report/runbook, media hosting, growth strategy, content format, production instructions, collector facts, both platform outboxes, scheduled worker, dashboard, SQLite schema, career configuration, hosted routes and source manifest. Baseline was 191 passed / 6 skipped, with 44 recorded YouTube publications. The task was running with normal spacing and LinkedIn weekday rules. A fresh online SQLite backup was saved as `data/backups/before-distribution-20261024-101734.db`; no queues, secrets or publication IDs were reset.

The gaps verified in code were seeded/manual discovery, latest/public-only analytics, deployment-snapshot guides, log-only website actions and limited revenue records. Historical docs describing those gaps are retained as dated records; this document supersedes their current-status statements.

## Implemented

### Owner Analytics

`shorts/analytics.py` adds a separate read-only OAuth token in `secrets/youtube_analytics_token.json`, using yt-analytics.readonly plus youtube.readonly for channel identity verification. Upload credentials/scopes remain unchanged. Google consent succeeded, the owner enabled the Analytics API, and real collection succeeded.

Verified live in one successful refresh: 304 per-video observations covering views, engaged views, average view duration, average percentage viewed, likes, comments, shares and subscribers gained. Average percentage requires single-video queries here; other metrics use bounded known-video batches and pagination. Unsupported metrics remain unavailable. Reports request a rolling period ending three days ago to allow for reporting delay; this requested end is not a guarantee of YouTube's final reporting completeness.

Observations retain capture timestamps, metric provenance and requested period. Public lifetime counts are kept separate from Analytics/CSV periods; period views never overwrite lifetime views. Owner Analytics is collected every six hours on its own background thread, with persistent leases/backoff. Revocation or API errors do not block publishing. Additional traffic-source and retention-curve queries are bounded to five eligible videos and are reported only when rows are returned. Public channel counters are captured separately when available.

Official references: https://developers.google.com/youtube/analytics/channel_reports and https://developers.google.com/youtube/analytics/metrics . Monetary/revenue Analytics scopes were not requested; no ad-revenue figures are invented.

### Discovery and source evidence

`shorts/growth/discovery.py` adds cached official-career-service discovery, employer-opening signals from collected ATS listings, keyless public Academia Stack Exchange question-title/link discovery, optional public Google Trends RSS where robots permit, configured FAQs and follow-ups from published content. Questions/discussions indicate demand; they never become factual evidence by themselves. Question provenance, timestamps, category, demand signal, expiry, supporting URLs and duplicate fingerprints are stored.

The live pass recorded 35 signals across ten categories and created 25 deduplicated topics beyond the original seeds. Categories include applications, interviews, outreach, research, remote, verification, eligibility, deadlines, paid internships and early-career questions. Only categories with at least two registered authoritative sources can enter research. Inaccessible sources remain unavailable; trends may legitimately produce no relevant signals. Search suggestions still have no documented provider configured, and there is no verified website-question submission endpoint.

Harvard interview evidence plus MIT interview guidance were successfully retrieved and used by real Ollama research, drafting and video building for topic `888c0f33e0093961`. The completed video is `out/growth/guide-888c0f33e0093961/video.mp4`. Two-source quote pairs are constructed by the application before model selection, preventing a model from selecting two same-source quotes. Exact quote, attribution, freshness, content-length and publication checks remain. Consequential legal/financial/scam advice stays deferred outside the current source policy.

### Autonomous selection and experiments

Discovery priority uses underrepresented published categories, bounded demand signals and public-view evidence at comparable measured ages when at least five videos exist. Hook experiments record hypothesis, single variable, variants, target audience, format, window, stable assignments and results. Cohort comparisons retain category/format/age bands and minimum samples. Only matched cohorts with at least five videos per variant and a material descriptive difference can change allocation to a bounded 60/40 exploration mix. That is not a statistical or causal winner claim. Insufficient data leaves allocation unchanged. Posting cadence and caps are untouched.

### Live guide synchronization

`shorts/growth/sync.py` synchronizes validated, confirmed-published guides through authenticated runtime upserts into the existing Sites R2 bucket. No routine deployment is needed for new guides. Stable IDs, version timestamps, content hashes, persistent attempts and backoff survive restarts. The hosted writer validates bounded public fields, known source domains, two-source attribution, freshness, published timestamps and version ordering. Conditional writes prevent stale/concurrent overwrites. Invalid updates do not replace a valid guide. The prior deployed website remains intact if a future build/deployment fails.

The live authenticated write/read/delete probe returned 200 with `visible_guides_changed: false`; it did not create a fake public guide. The public endpoint now reports `storage: live`. The first existing guide was locally ready, not published, so it no longer appears as if it were already public. The first normal guide publication will exercise the real published-guide positive sync automatically, normally within roughly six minutes, subject to retries. That end-to-end public publication has not been forced merely for testing.

### Funnel and reports

Consented first-party events are persisted as daily aggregate counters with conditional writes and a bounded reporting/retention window, then pulled through a private API into SQLite. No visitor identifiers, emails, raw search text or arbitrary content IDs are collected. Standard hosting request logs have provider-controlled retention. The existing opt-in checkbox and privacy explanation are preserved/updated.

Campaign-level actions can distinguish direct, YouTube and LinkedIn. These are action counts, not unique people or confirmed applications. Returning visitors, per-content website conversion, confirmed applications and unobserved revenue remain null/unavailable. Public channel subscriber counters are channel-level; per-video subscribers gained are limited to what the owner report exposes. Sponsored distribution is identified only from explicit existing promoted/sponsored markers, with attributable real per-video public counts when available.

`out/growth/daily-report.json` and `weekly-report.json` contain metric history/provenance, periods, comparable cohorts, bounded breakdowns, jobs, actionable failure/retry alerts, channel counters, consented aggregate events, revenue evidence and follow-ups. Dated daily/weekly records are also stored in SQLite. Reports update hourly; they do not send unsolicited messages.

### Revenue validation

`shorts/growth/revenue.py` prepares a bounded number of employer prospects from existing official ATS sources, records actual contact/reply/meeting/offer events with private provenance, schedules follow-up reminders, and records payments only with amount, currency, actual date and receipt/reference evidence. Currency totals remain separate; proposed offers are not revenue. Existing sponsorship disclosure checks remain independent of payment. The live preparation recorded eight prospects and zero automated sends; no confirmed payments were fabricated.

`growth.prospect_preparation_limit` defaults to 15. Automated outbound sending remains zero; no mailbox/reply connector, payment processor or marketplace was introduced. Recording a payment reference is founder-supplied evidence, not an independent bank audit.

## Reliability and storage

Additive SQLite objects: growth_jobs, discovery_signals, discovery_cache, guide_sync, growth_reports, experiment_details, experiment_assignments, outreach_activity, revenue_records, funnel_daily, channel_observations and analytics_breakdowns. Migration markers 2/3 are additive; existing outboxes, history and source records are retained. Independent growth operations use a database lease, restart recovery and exponential bounded backoff. The existing single-worker lock, hidden scheduled task, YouTube spacing/cooldowns, Buffer budgets, image retention/deletion and text-only fallback are preserved.

The laptop must still be awake, online and logged in for local generation, publishing, synchronization and cleanup. The hosted hub and stored media/guides remain available independently. Jobs do not pretend to run while the laptop is off.

## Commands

Run from `M:\opportunity-shorts\opportunity-shorts`:

```powershell
python -m shorts.analytics sync
python -m shorts.analytics auth
python -m shorts.growth.operations
python -m shorts growth status
python -m shorts growth brief 888c0f33e0093961
python -m shorts growth validate 888c0f33e0093961
python -m shorts growth report --output out/growth/performance.json
python -m shorts.growth.revenue status
python -m shorts.growth.revenue prepare
python -m shorts.growth.revenue activity CONTACT_ID --kind contacted --provenance "actual-message-reference"
python -m shorts.growth.revenue revenue CONTACT_ID --amount 1000 --currency INR --paid-at 2026-10-24T15:00:00+05:30 --evidence "actual-receipt-reference"
Get-Content data/growth-health.json
Get-Content data/worker-health.json
Get-Content data/linkedin-health.json
python -m pytest -q
```

The activity/revenue examples are commands for actual events only; they were not used to invent live activity. Existing validated Studio CSV import is still supported. Optional `YOUTUBE_ANALYTICS_TOKEN_FILE` changes only the separate Analytics token path. No new paid dependency or additional public credential is needed. The existing MEDIA_HOST_URL/MEDIA_WRITE_KEY secure guide sync and private funnel reads; credentials remain in ignored local settings and hosted secrets.

At `sites/unemployer`, run `node scripts/test-distribution.mjs` for writer authorization, published-only visibility, idempotency, conflicting versions and aggregate counters. Existing hub/search/media tests continue to apply.

## Remaining boundaries and next three actions

1. Let the normal cadence publish the ready guides, then inspect guide_sync and the public list for the first confirmed-positive publication/sync. No cadence bypass or duplicate post was used for testing.
2. Run the single-variable experiment long enough to populate comparable cohorts; inspect real private metrics and aggregate campaign actions before expanding formats or changing the cadence.
3. Conduct a few deliberate founder-led conversations using the eight researched prospects, record actual replies/offers/payment evidence, and validate demand before building payment processing.

Email signup remains disabled. Activation still needs a sending provider, private subscriber storage, explicit consent, double-opt-in policy where applicable, unsubscribe handling, retention/access rules and delivery tests. No suitable provider was configured in this project. Search suggestions, verified website-question intake, broader authoritative evidence for some categories, unique/returning visitor tracking, full per-content web attribution and inbox/payment ingestion remain unavailable or deliberately unimplemented. DEV community research integration was previously unavailable; no community findings were invented.
## Final verification and changed-file inventory

- Baseline: 191 passed, 6 skipped. Expanded full suite: **203 passed, 6 skipped**. New regressions cover additive/idempotent migrations, period-vs-lifetime isolation, known-video metric pagination, revoked authorization, persistent leases/backoff, discussion/evidence separation, source insufficiency, stable experiment assignment, actual-payment evidence/idempotency, published-only guide sync and retry recovery.
- Hosted build/ESM validation and existing hub, guide/privacy, search and media tests passed. New Node distribution tests cover authenticated writes, rejection of unpublished guides, same-version idempotency, version conflict preservation and durable aggregate counters.
- Live owner OAuth succeeded; the owner enabled the Google Analytics API. One refresh retrieved all eight requested metrics with 304 observations. Two successful distinct snapshots currently total 570 owner observations. Channel view/subscriber/video counters were also verified. Five traffic-source breakdowns were retrieved; retention curves returned no available rows and are not claimed available.
- New interview research, drafting and a real video build succeeded against Harvard and MIT. Existing opportunity/LinkedIn outboxes and image fallback were not reset.
- Website **version 7** deployed successfully at https://unemployer.syrupytide17.chatgpt.site . The live authenticated storage probe passed write/read/delete without changing visible guides; anonymous funnel reads return 401. Privacy text and disabled email signup were checked on the mobile page without JavaScript/layout errors.
- Current visible guide list is empty because there has not yet been a confirmed public career-guide publication. No fake publication was inserted and no upload was forced around configured spacing. Positive real-guide synchronization will follow the normal first publication; the write policy, storage path and retry behavior are verified separately.
- Worker restarted and Running. Daily/weekly reports generated successfully with zero active job-failure alerts at the final check. No outbound campaign or payment was initiated.

New Python modules: `shorts/analytics.py`, `shorts/growth/operations_store.py`, `discovery.py`, `sync.py`, `experiments.py`, `operations.py`, `revenue.py`. Modified Python: `shorts/growth/store.py`, `research.py`, `model.py`, `content.py`, `workflow.py`, `export.py`, `reporting.py`, `dashboard.py`, plus `shorts/scheduler.py` and `scripts/prepare_hub.py`. New test: `tests/test_distribution.py`.

Hosted changes: `sites/unemployer/worker/distribution.js`, route integration in `runtime.js`, privacy/guide empty-state text in `page.html`, generated `index.js`, and `scripts/test-distribution.mjs`. Configuration/docs: `config/career.yaml`, `config/shorts.yaml`, `.env.example`, `README.md`, `docs/AUDIENCE_ENGINE.md` and this report. The hosted media key/storage binding were reused. The only new credential is the successfully authorized private Analytics token; nothing needs to be pasted into chat.
