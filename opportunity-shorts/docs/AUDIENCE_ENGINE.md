# Audience engine operations

The worker publishes autonomously. There is no human approval gate. `approved` on a career topic means the automated evidence validator passed. Unverifiable, stale, consequential or malformed content is deferred automatically. This is a quality boundary, not a request for approval.

## Architecture and policy

The existing opportunity collector, stipend ranking, source refresh, rendering, YouTube OAuth, Buffer company-page transport and durable outboxes remain in place. A separate `shorts/growth` package adds career topics, versioned source excerpts, exact claim mappings, briefs, structured scripts, scene plans, content deliveries, publication history, metric observations, experiments and a private outreach tracker. Migration is additive and versioned; it never clears the old queue or posted history. A pre-upgrade backup is in `data/backups`.

Formats are `opportunity_alert`, `career_guide` and `weekly_roundup`. The initial policy in `config/shorts.yaml` spaces YouTube publications by 720 minutes and LinkedIn by 1440 minutes, with LinkedIn limited to weekdays in India time. This is at most about two YouTube posts daily, not a promise of exactly two. Provider limits, evidence freshness, failures and source availability still apply. A ready career guide is eligible every two days; a roundup is eligible on Friday and requires three fresh credible paid openings from distinct employers. Opportunities retain compensation/deadline ranking. Configurable employer and exact-role cooldowns reduce repetition. This is a controlled starting policy, not an algorithm for guaranteed virality.

Research currently supports a small HTTPS allowlist of public university career guidance in `config/career.yaml`: MIT, Yale and Berkeley. The fetcher checks robots, bounds redirects/body size and removes page chrome and contact lines. URLs are configuration, never model inventions. Sources are untrusted data. The application extracts bounded exact candidate quotes, Ollama chooses IDs, and validators require evidence from two sources. Models cannot add factual prose or application URLs. Selected quotes are attributed, capped per source, and combined with a clearly labelled general exercise. Evidence older than 14 days cannot publish. New model topics must fit this adapter's applications domain; adding other domains requires new verified sources and validation rules.

Each automatic maintenance step does one research/draft/build action, at most hourly. Ollama uses the existing local model with `keep_alive: 0`, so memory is released after requests. Separate structured prompts exist for discovery, extraction, synthesis, drafting, validation, revision and analysis. The automatic implementation currently uses extraction, synthesis, drafting and validation; discovery is seeded/manual, revisions re-enter verified drafting and performance reporting is deterministic. No unattended Reddit/search harvesting or model-driven performance conclusions are claimed.

State flow: discovered → researching → researched → drafted → automatically approved/ready → published. Failures become deferred with bounded retries. Rejection and revision tools are optional operational controls, not required gates. A published item or uncertain platform delivery is immutable. A network timeout may mean the platform accepted a post: keep it uncertain and reconcile its real status instead of resetting it to pending.

## Commands

Run from `M:\opportunity-shorts\opportunity-shorts`:

```powershell
python -m shorts growth status
python -m shorts growth discover
python -m shorts growth research TOPIC_ID
python -m shorts growth brief TOPIC_ID
python -m shorts growth draft TOPIC_ID
python -m shorts growth validate TOPIC_ID
python -m shorts growth build TOPIC_ID
python -m shorts growth publish TOPIC_ID --platform youtube --dry-run
python -m shorts growth run
python -m shorts growth report --output out/growth/performance.json
python -m shorts metrics --refresh
python -m pytest -q
```

There is deliberately no `approve` command. `validate` inspects evidence; `build` validates then makes content ready for the autonomous publisher. Explicit `publish --platform youtube` or `linkedin` still respects cadence, provider cooldowns and delivery reconciliation. To request an optional revision: `python -m shorts growth revise TOPIC_ID --reason "Refresh the evidence"`; reject with the same syntax using `reject`. Never edit source claims or posted IDs to force a retry. Missing/stale research should be refreshed, drafted and built again. Deferred automatic jobs retry after six hours; inspect their saved error first.

The dashboard (`streamlit run shorts/review_app/app.py`) includes research evidence, scripts, video preview, delivery state, metrics, experiments and private outreach records.

## Measurement

The public YouTube API supplies views, likes, comments and processing/privacy state. Each refresh appends dated observations while preserving the legacy latest-metrics table. Missing metrics remain null. No retention, subscriber attribution, impressions, feed exposure, shares or causal growth claims are inferred from public counts.

Export a per-video YouTube Studio CSV and import only actual published IDs:

```powershell
python -m shorts growth import-metrics studio.csv --captured-at 2026-10-24T18:00:00+05:30 --period-start 2026-10-17 --period-end 2026-10-24
python -m shorts growth experiment --hypothesis "A specific application hook improves viewing" --variable hook --variants specific general --starts-at 2026-10-25T00:00:00+05:30 --ends-at 2026-11-08T00:00:00+05:30
```

Supported CSV headings include Content / Video ID / video_id, Views, Likes, Comments, Shares, Subscribers gained, Average view duration, Average percentage viewed (%), Shown in feed and Stayed to watch (%). Entire imports are validated before writing. Provenance and capture time are retained. Comparisons expose format, category and video-age bands; they are descriptive, not significance tests. The experiment table records one variable/two variants/windows but does not randomly assign videos or claim statistically proven winners. Owner Analytics API access and new OAuth consent have not been added; CSV is the integration boundary.

## Hub, privacy and conversion

The hub searches original application sources with internship/fresher/research, remote and deadline filters, plus a downloadable checklist. Career guides show validated takeaways, attribution and caveats. Listings use live public feeds plus fresh dated fallback. The new guide payload is a validated deployment snapshot: new local guides require rebuilding and redeploying the hub. It is not a live connection to the laptop database.

Optional audience events require an explicit checkbox. Only fixed event/category/campaign enums are accepted; raw search text, emails, visitor IDs and arbitrary query parameters are not collected. Events are bounded, same-origin and rate-limited and emitted as sanitized hosting log entries. Retention/access depend on hosting; there is no durable attribution dashboard or cross-device tracking. Newsletter signup is disabled and POST returns 503: no email provider or subscriber store is configured and no addresses are collected. Before activation choose a provider, consent/unsubscribe flow, retention and access controls. Do not pretend a form has subscribed someone.

To rebuild: `python scripts/prepare_hub.py`, then in `sites/unemployer` run `node scripts/build.mjs`, `node scripts/validate-artifact.mjs`, `node scripts/test.mjs`, `node scripts/test-growth.mjs`. Publish through the existing Sites authenticated source workflow; never commit short-lived credentials or `.env`.

Channel setup still requires checking YouTube Studio → Customization → Profile, adding the hub as a visible link, and checking the mobile About/profile view. Description URLs do not prove that a profile link exists; Shorts descriptions are not a dependable clickable conversion path. Use a spoken/profile CTA and test it on a phone. Existing OAuth is reused, not silently expanded.

## Recovery and founder workflow

```powershell
Get-ScheduledTask -TaskName UnemployerWorker | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName UnemployerWorker
Enable-ScheduledTask -TaskName UnemployerWorker
Start-ScheduledTask -TaskName UnemployerWorker
```

The laptop must be awake, online and logged in for its scheduled worker and local model. Do not start a second worker; retain its existing lock. Inspect local worker health/logs and delivery errors before restarting. An API quota reset or token reauthorization cannot be replaced by deleting uncertain delivery records. Back up SQLite with the existing backup routine before changes; restore a backup only with the worker stopped and after accounting for any real posts since that backup, or reconciliation could duplicate them.

Weekly: inspect real metrics and source failures; compare similarly aged formats; change one experimental variable; verify a sample of application links; refresh guide snapshots; research a small set of relevant organizations; send only deliberate founder-authorized outreach. See [OUTREACH.md](OUTREACH.md) for templates, prospecting targets and future employer submission security. No outreach messages, paid services, paid listings, email campaigns or employer portal were launched by this implementation.


## Current autonomous distribution upgrade

For the separate owner Analytics integration, source-backed discovery adapters, live published-guide synchronization, private funnel aggregates, experiments and revenue records, see [DISTRIBUTION_UPGRADE.md](DISTRIBUTION_UPGRADE.md). This supersedes earlier snapshot-only guide and public-only analytics limitations where explicitly verified.
