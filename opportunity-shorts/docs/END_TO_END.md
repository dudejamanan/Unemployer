# Operating notes

Current production defaults changed to unattended Ollama generation for @unemployerr. See [AUTOMATION.md](AUTOMATION.md) for active setup and [GROWTH.md](GROWTH.md) for the channel audit. Approval instructions below apply only with `automation.enabled: false`.

The collector and stages M1–M3 existed. Assembly was incomplete and could not import;
captions, review, upload, and scheduling were missing. Stages M4–M6 now share
`shorts.pipeline.Pipeline` so dashboard and CLI use the same approval and validation rules.
Optional Telegram, analytics, and link-in-bio growth features remain outside the core workflow.

## Setup

Use Python 3.11 or newer. From this project's directory:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
python -m shorts doctor
python -m pytest -q
```

FFmpeg and FFprobe must be on PATH. FFmpeg must include libass for captions.
Chromium, FFmpeg, and the live Edge TTS service were verified on the development machine.
Edge TTS needs internet; `build --audio narration.wav` accepts a human-recorded alternative.
Do not use silent audio as a production fallback. When narration is outside 20–40 seconds,
the build fails with its measured duration; adjust the script or supply another recording.

Script generation now uses local Ollama, not Anthropic. No paid LLM API key is used.
The active model is the installed qwen3:8b with a 4,096-token context and CPU mode.
After freeing memory, CPU inference and a real video build succeeded; GPU inference failed
with a CUDA/PTX error. The smaller-model download was stopped. Hinglish is preferred,
with English permitted for clarity. Failed scripts are deferred automatically. Numeric and
field validation cannot establish all unrestricted prose claims as true.

Place an optional licensed TTF in `assets/fonts/`; rendering embeds the first TTF found.
Otherwise rendering uses system fonts. Fonts are not redistributed with this project.
Optional licensed background music: set `assembly.music_file: assets/music/track.mp3`.
Music loops, is attenuated between -22 and -18 dB, and mixes beneath normalized voice.
This is fixed attenuation rather than speech-reactive sidechain ducking.

## Review and generation

```powershell
python -m collector run
python -m shorts review
```

The dashboard shows queue entries by score, official links, unknown-field warnings,
scripts, video previews, opportunity approval/rejection, video approval, exports, and schedules.
Generation does not publish anything. Opportunity approval and approval of the rendered
video are separate actions. Saving edits invalidates the video approval.

Equivalent CLI workflow:

```powershell
python -m collector manual config/manual_example.yaml
python -m collector list
python -m shorts generate <id> --save
python -m shorts build <id>
python -m collector set-status <id> approved
python -m shorts approve-video <id>
python -m shorts upload <id> --dry-run
python -m shorts upload <id> --manual-export
```

Preview `out/<id>/video.mp4` before approving it. Manual exports contain the MP4,
title, description, and upload settings in `out/exports/<IST-date>/<id>/`.
Export does not mark an opportunity posted. After manually publishing in Studio, use
`python -m collector set-status <id> posted` to remove it from the posting queue.

Posts, upload attempts, and schedules use new tables in the collector's SQLite file.
The opportunities schema remains unchanged. Any old standalone `data/posts.db` is a
historical artifact; regenerate drafts through the new workflow rather than assuming
old video paths and approvals are valid.

## YouTube authorization and publication

Enable YouTube Data API v3 in your Google Cloud project. Create an OAuth Desktop app,
configure its consent screen and add your account as a test user if applicable.
Save the downloaded client JSON as `secrets/client_secret.json`, configure
`YOUTUBE_CLIENT_SECRETS_FILE` in `.env`, then run:

```powershell
python -m shorts auth
python -m shorts upload <id>
```

Authorization is interactive once; tokens refresh locally when supported. The active configuration requests **public** uploads to the verified @unemployerr channel ID.
The code sets Education, not-made-for-kids, and synthetic-media disclosure by default.
No real channel upload was performed during development: credentials were unavailable.
Resumable upload success/failure and approval guards are covered with mocked services.

Current official docs checked October 11, 2026 differ from the old project prompt:
[`videos.insert`](https://developers.google.com/youtube/v3/docs/videos/insert) now documents
100 calls/day and 1 unit per call in a separate Video Uploads quota bucket. It also says
unverified API projects are no longer restricted to private viewing. Check the actual
project limits in Cloud Console; the application now requests public visibility and keeps a conservative
3 attempts per IST day. `upload.api_daily_upload_limit` is a configurable additional ceiling,
not a live query of remaining Google quota shared with other applications.

YouTube requires disclosure for meaningfully altered, realistic synthetic content.
The [official disclosure guidance](https://support.google.com/youtube/answer/14328491)
distinguishes production assistance from realistic depictions and voice impersonation.
This project conservatively sets `containsSyntheticMedia: true` for generated narration;
manual export settings ask for the corresponding Studio disclosure. For a sponsored manual
listing, start its source description with `Promoted:` or `Sponsored:`. Generated scenes
show Promoted, descriptions include a disclosure, and uploads set the API's
[paid-placement flag](https://developers.google.com/youtube/v3/docs/videos#paidProductPlacementDetails.hasPaidProductPlacement).
This uses the existing description field rather than changing the collector schema.

## Scheduling

```powershell
python -m shorts schedule <id>
python -m shorts schedule <id> "2026-10-12T13:00:00+05:30"
python -m shorts run-daily
python -m shorts run-daily --no-collect --upload
```

Without a time, scheduling selects the next slot from `upload.ist_slots` (08:00, 13:00,
19:00 by default). Manual mode requires approvals; automatic mode schedules successfully generated videos without human approval.
The runner uploads due schedules only when `--upload` is present; otherwise it collects
and generates drafts. `--manual-export` exports due schedules instead of API uploads.
Expired, closed, scam-pattern, and changed listings cannot be published. The application
blocks the same company and role for 30 days after an upload or unresolved attempt.

Use Windows Task Scheduler: set **Start in** to the project directory and use the venv's
absolute Python executable. Create collection/generation triggers twice daily (e.g. 06:00
and 18:00 IST) with arguments `-m shorts run-daily`. Create a runner every 15 minutes
with arguments `-m shorts run-daily --no-collect --upload`. Set the task to avoid concurrent
instances. The current-user UnemployerWorker task is now installed; use that daemon instead of installing these older manual-mode tasks.
Keep the machine awake and network connected for scheduled runs.

## Recovery and idempotency

Generation reuses the built video when its script, source facts, and relevant settings match.
`--force` rebuilds it. Uploaded records cannot be regenerated automatically. Successful uploads
persist the video ID before marking the opportunity posted; a rerun reconciles those statuses.
An upload attempt reserves the post in a SQLite transaction before sending any video.

A lost response may mean YouTube accepted the video. The post therefore stays `uploading`;
it is never retried automatically. Check YouTube Studio, then either:

```powershell
python -m shorts reconcile-upload <id> --youtube-id <existing-11-character-id>
# Only after verifying no video exists:
python -m shorts reset-upload <id> --confirmed-absent
python -m shorts approve-video <id>
```

Reset preserves the daily attempt count. API quota failures remain visible, and nothing is
marked posted without a returned or explicitly reconciled video ID.

## Local demonstration

```powershell
python scripts/demo.py
```

This imports a fictional Example Corp listing into an isolated demo database, generates
real narration, renders four safe-area scenes, and assembles a captioned video. It never
uploads. The verified example output is `out/83856b4619525938/video.mp4` (34.344 seconds,
1080×1920, 30 fps, H.264/AAC). Six old integration placeholders remain skipped in the
unit suite; the demo exercises real TTS, Chromium, FFmpeg, and captions instead.

Initial completion verification on October 11, 2026: **65 tests passed, 6 historical placeholders
skipped**. The suite includes a real FFmpeg caption/music assembly check, dashboard
review, mocked resumable upload metadata and errors, script fallback/retries, stale-source
protection, quotas, and scheduling. All five configured live job feeds responded; 1,982
listings were fetched and three passed the configured filters. A real collected Stripe
internship draft was generated at `out/d35245fee74c8fe4/video.mp4` (33.467 seconds,
1080×1920, 30 fps, H.264/AAC), without approving or uploading it.

After the source/eligibility expansion on October 11: **88 tests passed, 6 placeholders skipped**.
All 23 configured targets were fetched successfully across the full 22-target refresh and
the subsequent Jio addition. The database contains 350 open, unexpired cards, including
326 internships. All 350 pass template-script fact validation. The review queue now has
pagination and source/eligibility evidence. The source inventory and the @ashishcode link
audit are in `docs/SOURCES.md` and `docs/CHANNEL_SOURCES.md`.

A newly collected Unstop card produced `out/3f5d3ed030876302/video.mp4`: 31.9 seconds,
1080×1920, H.264/AAC, using the template fallback, real Edge TTS, Chromium rendering,
captions and FFmpeg. No LLM key was configured, and this preview was not approved or uploaded.
