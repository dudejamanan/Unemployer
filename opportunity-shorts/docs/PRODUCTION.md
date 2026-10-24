# Unemployer operations and revenue

## Live product

Public hub: https://unemployer.syrupytide17.chatgpt.site

The hub runs in hosted Workers independently of the laptop. It fetches 15 configured employer boards plus Unstop, AICTE and Himalayas on demand. Public catalogues use bounded pages, not exhaustive market coverage. Cached responses are up to 15 minutes old; per-isolate cache reuse is best effort. Recently collected fallback listings retain a visible check timestamp and expire after 24 hours. The five individually configured employer pages are snapshot-only fallback on this hub. Cloud providers may rate-limit or block some feeds; unavailable sources are reported. Source links are rechecked against current feed/fallback state before redirecting.

The local Python collector still supports all 23 configured targets. Generating videos needs the awake, logged-in laptop and local Ollama. The public website does not run Ollama or upload videos.

Add the hub URL to YouTube Studio → Customization → Profile → Links. Label it **Find internships & fresher jobs**. Upload-only OAuth cannot modify these profile links, and the browser-control runtime was unavailable during this task. This one-time channel setup remains manual. URLs in Shorts descriptions are text, not clickable buttons. The official source URL remains the first description line; the hub is also included. Copying the source URL works before the channel profile link is configured.

## Editorial and growth

Automatic generation and immediate uploads share one priority order, including already queued videos: disclosed INR monthly-equivalent pay first, with paid openings closing within three days promoted ahead of other paid openings; otherwise pay descends from high to low. Ranges use their lower bound, annual pay is divided by 12, and deadlines break pay ties. Unknown periods and foreign currencies remain unranked rather than using invented exchange rates. Undisclosed/unranked compensation follows ranked pay. Explicit unpaid opportunities are skipped by default (`automation.priority.skip_unpaid: true`); set false to include them last. Expired and closed listings remain excluded. Manual single-video uploads follow the requested ID.

Source facts determine titles, eligibility, deadlines and compensation. Narration uses local Ollama, with responsibilities-focused context and a clearly labelled general application recommendation. Raw historical dates and unnormalized durations are excluded from narration context rather than treated as graduation or eligibility facts. A hook returned separately by the model is moved into the opening narration if the employer would otherwise be absent.

New videos use the logo, section labels, a visible application tip, karaoke-style caption highlighting and subtle movement. These improvements are hypotheses to measure, not proof of virality or monetization approval. Changing colours alone is not substantive originality. Review actual viewer feedback and source quality; automated validation cannot establish every prose claim.

Public YouTube views, likes, comments, visibility and processing status sync every six hours. Run `python -m shorts metrics --refresh` to refresh manually. The dashboard shows the latest observations. Retention, swipe-away rate, CTR and revenue are not accessible through these public counts. No causal ranking or automatic winner claims are made. Use YouTube Studio to compare similar videos at similar ages and keep original educational value as the main criterion.

## Revenue path

The live hub has a functioning sponsorship contact: **mananndudeja@gmail.com**. Employer collaborations and career-product sponsors can enquire through a mailto link. Accept suitable offers, agree deliverables and prices, and disclose paid coverage. The pipeline's existing promoted-listing designation triggers disclosure and YouTube paid-product placement metadata. Applications remain free.

The free downloadable application checklist provides useful value and a reason to visit. Payment processing, paid downloads, automatic invoicing, affiliate contracts and advertiser acquisition are not configured. No income has been verified. Those require the owner's provider accounts and actual commercial agreements. YouTube ad revenue depends on current YPP eligibility and review, not this software's completion. See https://support.google.com/youtube/answer/1311392 and https://support.google.com/youtube/answer/12504220.

## Reliability and recovery

Resource management: Ollama chat requests set `keep_alive: 0`, unloading the model immediately after each response. The lightweight Ollama server remains available; the next script request reloads the same model, preserving output quality at the cost of load latency. FFmpeg/FFprobe child processes use Windows `CREATE_NO_WINDOW`. Stale listings are skipped before generation. YouTube channel-limit rejections impose a durable channel-wide cooldown, stopping further generation/upload attempts until retry time while collection and the independent LinkedIn publisher continue. A successful manual upload clears this cooldown. The health report includes `youtube_paused_until` when publication is deferred.

- The current-user `UnemployerWorker` starts at Windows login. Immediate mode bypasses fixed slots for active pending videos; the worker waits a minute between cycles and refreshes sources 15 minutes after the last collection finishes. Rendering and collection can delay checks.
- SQLite uses WAL and a 30-second busy timeout. Keep one publishing worker; the local lock only prevents duplicates on the same computer. Stop the first worker before migrating to a second laptop.
- The worker uses rotating logs (5 MB, three previous logs), writes `data/worker-health.json` at cycle start/end, and retries failed cycles. A long-running cycle has a `working` heartbeat, not a claim of minute-by-minute liveness.
- Daily consistent SQLite backups use the online backup API and retain seven files in `data/backups`. The same-day backup is created once, not overwritten every cycle. OAuth secrets are intentionally excluded; back them up separately and securely. Run `python -m shorts backup` to create today's database backup.
- Explicit 4xx upload rejections return to the ready queue with a cooldown; quota rejection waits until the next IST day. Network failures or uncertain responses remain locked and are reconciled with channel uploads before retrying. Definitive quota limits may reset on a different timezone; another rejection is safely deferred.
- FFmpeg has a ten-minute timeout; YouTube requests have a 30-second network timeout. Ollama's configured timeout is five minutes per attempt. Automatic fact checks, expiry checks and duplicate prevention remain active.
- Automatic uploads require a source check within the last 24 hours. Refresh collection before publishing an older stored listing, including after resuming a laptop.

## Install and check

Use a virtual environment and `python -m pip install -r requirements.lock.txt` for the tested direct dependency versions. The lock records direct packages; indirect dependency versions are not fully frozen. Install FFmpeg/FFprobe and Playwright Chromium, keep Ollama running, and securely copy your own OAuth client/token and database.

```
python -m shorts doctor
python -m shorts health
python -m shorts metrics --refresh
python -m shorts backup
python -m pytest -q --basetemp data/pytest-local
```

To restore, stop the scheduled worker, preserve the current database and its WAL/SHM files, close all dashboard/CLI connections, and restore a verified backup to the configured database path. Resume the worker and reconcile uploads before retrying uncertain items. Never blindly reset an accepted-but-unconfirmed upload.

The hosted site source is in `sites/unemployer`. Rebuild its public-only snapshot with `python scripts/prepare_hub.py`, then follow the Sites skill's authenticated source/package/deploy workflow. On Windows prepend Git Bash to PATH and use `TAR_OPTIONS=--force-local` plus forward-slash archive paths. No deployment credential is saved in the project. Future redeployment requires renewed Sites access; on-demand hosted feeds continue without it.


Release validation: 107 Python tests passed (six historical placeholders skipped), including the copy-link CTA and stale-source publishing guard. Hub safety/route tests passed, and desktop/mobile search was exercised in Chromium. The deployed public API returned 443 openings from 18 successful sources and a source redirect returned HTTP 302. The new HackerRank Short rendered at 33.072 seconds, 1080x1920, H.264/AAC and uploaded as PMGllSvFWdc. Job-specific Greenhouse location now takes precedence over company-office metadata.

## Publishing cadence

Automatic YouTube and LinkedIn publishing are each spaced by a minimum of 144 minutes (2 hours 24 minutes). Timing persists through the database: YouTube uses the most recent successful publication, LinkedIn uses its most recent create attempt. Each automatic cycle sends at most one post when spacing is enabled; high-stipend/deadline priority still determines which candidate goes next. Limits, failures, source freshness, laptop sleep and generation time can delay publication beyond the interval. Missed time slots do not accumulate into a burst. Manual single-video uploads are explicit overrides. Adjust `automation.min_upload_interval_minutes` and `linkedin.min_post_interval_minutes` in `config/shorts.yaml`. Daily caps still apply independently.

## Recovery update — 23 October 2026

The worker task now has a repeating five-minute recovery trigger in addition to login startup, with IgnoreNew preventing overlapping task instances. Startup waits up to 30 seconds for a previous worker to release its OS lock and never starts a duplicate publisher. The laptop must still be awake and logged in. LinkedIn checks its persisted spacing window before calling external APIs, and unresolved Buffer posts are reconciled at most hourly with a persisted timestamp, including failed checks. This prevents a single uncertain post draining the free request budget.
