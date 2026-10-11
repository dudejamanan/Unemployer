# Unemployer operations and revenue

## Live product

Public hub: https://unemployer.syrupytide17.chatgpt.site

The hub runs in hosted Workers independently of the laptop. It fetches 15 configured employer boards plus Unstop, AICTE and Himalayas on demand. Public catalogues use bounded pages, not exhaustive market coverage. Cached responses are up to 15 minutes old; per-isolate cache reuse is best effort. Recently collected fallback listings retain a visible check timestamp and expire after 24 hours. The five individually configured employer pages are snapshot-only fallback on this hub. Cloud providers may rate-limit or block some feeds; unavailable sources are reported. Source links are rechecked against current feed/fallback state before redirecting.

The local Python collector still supports all 23 configured targets. Generating videos needs the awake, logged-in laptop and local Ollama. The public website does not run Ollama or upload videos.

Add the hub URL to YouTube Studio → Customization → Profile → Links. Label it **Find internships & fresher jobs**. Upload-only OAuth cannot modify these profile links, and the browser-control runtime was unavailable during this task. This one-time channel setup remains manual. URLs in Shorts descriptions are text, not clickable buttons. The official source URL remains the first description line; the hub is also included. Copying the source URL works before the channel profile link is configured.

## Editorial and growth

Source facts determine titles, eligibility, deadlines and compensation. Narration uses local Ollama, with responsibilities-focused context and a clearly labelled general application recommendation. Raw historical dates and unnormalized durations are excluded from narration context rather than treated as graduation or eligibility facts. A hook returned separately by the model is moved into the opening narration if the employer would otherwise be absent.

New videos use the logo, section labels, a visible application tip, karaoke-style caption highlighting and subtle movement. These improvements are hypotheses to measure, not proof of virality or monetization approval. Changing colours alone is not substantive originality. Review actual viewer feedback and source quality; automated validation cannot establish every prose claim.

Public YouTube views, likes, comments, visibility and processing status sync every six hours. Run `python -m shorts metrics --refresh` to refresh manually. The dashboard shows the latest observations. Retention, swipe-away rate, CTR and revenue are not accessible through these public counts. No causal ranking or automatic winner claims are made. Use YouTube Studio to compare similar videos at similar ages and keep original educational value as the main criterion.

## Revenue path

The live hub has a functioning sponsorship contact: **mananndudeja@gmail.com**. Employer collaborations and career-product sponsors can enquire through a mailto link. Accept suitable offers, agree deliverables and prices, and disclose paid coverage. The pipeline's existing promoted-listing designation triggers disclosure and YouTube paid-product placement metadata. Applications remain free.

The free downloadable application checklist provides useful value and a reason to visit. Payment processing, paid downloads, automatic invoicing, affiliate contracts and advertiser acquisition are not configured. No income has been verified. Those require the owner's provider accounts and actual commercial agreements. YouTube ad revenue depends on current YPP eligibility and review, not this software's completion. See https://support.google.com/youtube/answer/1311392 and https://support.google.com/youtube/answer/12504220.

## Reliability and recovery

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
