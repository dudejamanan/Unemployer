# Audience engine implementation report — 24 October 2026

## A. Repository findings

Inspected collector adapters and source inventory; opportunity facts/eligibility/stipend ranking; script, TTS, scene and assembly stages; scheduler; YouTube upload/reconciliation; independent LinkedIn/Buffer outbox; metrics; Streamlit; configuration; tests; production, content, data-contract and growth docs; and the hosted Sites worker.

Already implemented: SQLite collection with Indian eligibility filtering, original source links, local Ollama generation, Edge TTS, 1080×1920 rendered Shorts, OAuth uploads, Buffer company-page posts, hidden Windows worker, locks, backups, provider cooldowns and ambiguous-delivery reconciliation. Baseline: 147 passed, 6 skipped.

Main gaps were a separate evidence-backed research workflow, a cross-format publication history, historical measurements instead of latest counts only, comparable-age reporting, lower experimental cadence, operational research views, and a guide/digest conversion boundary on the hub.

Prioritized checklist:

- Done: preserve and back up the existing queue/history; additive migration and regression baseline.
- Done: autonomous evidence-constrained guide research/draft/build workflow and independent format scheduling.
- Done: configurable shared spacing and employer/role diversity; original stipend priority retained.
- Done: public metric history, validated optional Studio CSV import, cohorts and experiment records.
- Done: hub filters, source-backed guide section, checklist, privacy controls, deployed website.
- Done: private outreach records/templates and documented employer-submission security foundation.
- Dependency boundary: email delivery, owner-only Analytics authorization, automatic hosted-guide synchronization and broader topic-source adapters.

## B. Changes made

`shorts/growth/` contains additive store/migration, safe research retrieval, staged local-model prompts, exact claim mapping, bounded script generation, media building, cross-format policy, durable deliveries/reconciliation, maintenance, CLI, reporting, public guide export and dashboard. Schema additions: career_topics, career_sources, career_claims, content_items, content_deliveries, content_publications, metric_observations, growth_experiments, outreach_contacts, research_runs and growth_migrations.

Integrated through `shorts/pipeline.py`, `scheduler.py`, `production.py`, `linkedin.py`, `buffer_api.py`, `cli.py`, `settings.py` and `review_app/app.py`. Added `shorts/render/templates/guide_scene.html` and registered its renderer. `config/career.yaml` lists three public university sources and two initial questions. `config/shorts.yaml` enables hourly bounded research, guides every two days, Friday roundups, YouTube 720-minute spacing, LinkedIn 1440-minute spacing/weekdays and employer/role cooldowns.

Hub changes are in `scripts/prepare_hub.py`, `sites/unemployer/worker/page.html`, `runtime.js`, generated `index.js`, and `scripts/test-growth.mjs`. The source repository was saved and version 3 deployed successfully at https://unemployer.syrupytide17.chatgpt.site (commit b6081dff6bd8dcbacd840759f1d41d72dfef6ea0). No cloud database or paid service was introduced.

Added `tests/test_growth.py`, `docs/AUDIENCE_ENGINE.md`, `docs/OUTREACH.md`, this report, and README/growth guidance. No new secret environment variables are needed. Existing credentials were reused without printing or changing them. Pre-upgrade backup: `data/backups/unemployer-2026-10-24.db`.

## C. Audience impact

Opportunity alerts still prioritize disclosed pay and approaching deadlines. Guides and roundups have independent eligibility so stipend ranking does not consume every slot. Employer/role spacing reduces repetition. Guides answer application questions using attributed recommendations and a practical exercise, with one useful save action and no hiring guarantees. Their readable vertical scenes preserve the brand and source context. Lower cadence creates room to compare outcomes rather than maximize volume.

The hub makes original applications easier to find and adds a practical reason to return through guides/checklists. Its email section accurately explains that signup is unavailable. Measurements retain provenance and missing values, while format/category/age cohorts reduce misleading comparisons. None of this guarantees reach, virality, monetization or selection.

## D. Verification

- Original baseline: **147 passed, 6 skipped**.
- Expanded full Python suite: **174 passed, 6 skipped** after evidence isolation, metric and configuration tests. Skipped tests remain skipped; no live-account success is inferred from them.
- Hub build and ESM artifact validation passed.
- Original Node hub safety tests passed; new guide, digest, same-origin event, payload/privacy and inline script syntax tests passed.
- Real local Ollama research succeeded against MIT/Yale/Berkeley retrieval. Early invalid quotations/IDs were rejected; the bounded candidate-ID approach resolved generation without weakening evidence checks.
- Real guide draft, TTS, browser scene rendering and FFmpeg assembly succeeded: `out/growth/guide-0726f16213a6afc3/video.mp4`, **1080×1920, 35.4 seconds**. Thumbnail visually inspected.
- Playwright: guide expansion works, email control is disabled, no JavaScript page errors, mobile width 390/390 with no horizontal overflow. Desktop and mobile screenshots saved in `out/growth/`. An initial assertion targeted the fieldset rather than its email control; checking the disabled input confirmed expected behavior.
- Production website checks: homepage 200, guides API 200 with one validated guide, digest API 200 with `enabled: false`. Deployment succeeded.
- Public metrics refresh succeeded; initial report: **44 videos, 131 dated observations, 2,398 observed lifetime views**, latest capture `2026-10-24T08:46:47.259951+00:00`. These are a dated snapshot, not revenue or subscriber attribution. Report: `out/growth/performance.json`.
- Windows worker was restored: task enabled and Running, worker health working, LinkedIn health spacing under the weekday rule. Its latest opportunity YouTube publication at inspection was `2026-10-24T06:27:55Z`. The new guide is ready, not falsely reported as publicly uploaded; its next publication follows the shared cadence.
- No fresh live YouTube/Buffer create was forced merely as a test. Existing quota, spacing and ambiguous-delivery protections remain active.

Community research was attempted through the installed DevRelay integration, which returned “Not connected to MLH.” No community findings or citations were invented and no account connection was required to implement the project.

## E. Manual actions required

There is **no content approval action**. Check the hub link in the YouTube channel's visible profile from a phone; API descriptions do not establish profile-link placement. For private retention/feed/subscriber metrics, export a Studio CSV or separately authorize an owner Analytics integration. For email, select/configure a provider and subscriber storage with consent, unsubscribe and retention before enabling signup. New hosted guides require authenticated rebuild/redeployment until a secure unattended sync mechanism is configured. Keep the worker laptop awake/online/logged in.

No additional LLM API key is required. No paid integration, outreach send, email campaign or employer charge was launched.

## F. Known limitations

Automatic guide research is deliberately scoped to configured public university application guidance and two seed questions. Other domains, Reddit/search-suggestion adapters and automated trend-driven topic expansion are not implemented. Stage prompt definitions do not mean every stage is automatically invoked: discovery is seeded/manual, revision re-enters evidence drafting and analytics summaries are deterministic. Repeated failures remain deferred rather than creating filler. High-consequence topics are deferred outside the autonomous source policy.

The site guide section is a deployment snapshot with age filtering, not a live local database mirror. Optional website events are coarse hosting logs, not durable per-video attribution or a reporting dashboard. Email signup is disabled. Owner-only analytics and monetization/revenue data are unavailable without access. Cohorts are descriptive and experiment records do not automatically randomize assignments, prove significance or promote winners. Outreach tracking is private and lightweight; no full CRM edit workflow or employer/payment portal was built. No self-sustaining revenue or viral-growth claim is made.

## G. Next five actions

1. Verify the channel profile → hub → original application flow on a phone.
2. Let the worker run the current cadence; inspect the ready guide and actual delivery results rather than forcing bursts.
3. Import a dated Studio per-video CSV and compare matching formats and age bands before changing a single experimental variable.
4. Add verified student questions and authoritative source adapters in small batches; refresh and redeploy the public guide snapshot.
5. Choose the weekly-email provider/privacy setup, then conduct deliberate founder-led outreach using the saved templates and actual measured audience figures.

## H. Operational commands

All commands run from `M:\opportunity-shorts\opportunity-shorts`:

```powershell
python -m shorts growth status
python -m shorts growth brief 0726f16213a6afc3
python -m shorts growth validate 0726f16213a6afc3
python -m shorts growth publish 0726f16213a6afc3 --platform youtube --dry-run
python -m shorts growth run
python -m shorts metrics --refresh
python -m shorts growth report --output out/growth/performance.json
python -m pytest -q
Get-ScheduledTask -TaskName UnemployerWorker | Select-Object TaskName,State
Get-Content data/worker-health.json
Get-Content data/linkedin-health.json
```

Approval is replaced by automated evidence validation and build readiness. For researched drafts use `growth draft TOPIC_ID`, then `growth build TOPIC_ID`; do not edit delivery states. Inspect failures in `growth status`, fix the dependency and refresh/rebuild as documented in [AUDIENCE_ENGINE.md](AUDIENCE_ENGINE.md). That runbook includes optional revision/rejection, CSV/experiment examples, hub packaging, task recovery and backup precautions.


