# Opportunity Shorts

An end-to-end pipeline for turning reviewed internship, fresher-job, and hackathon listings into captioned YouTube Shorts.

Collect official feeds or import listings -> review and approve opportunities -> generate scripts, narration, and video -> preview and approve the video -> export for Studio or upload through the YouTube API.

## Start here

Run commands from this directory (the inner `opportunity-shorts` folder):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
python -m shorts doctor
python -m pytest -q
```

FFmpeg and FFprobe must be on PATH. Anthropic is optional; template scripts work without a key. Edge TTS needs internet. YouTube uploads require your own OAuth credentials and default to private.

## Try a complete video

```powershell
python scripts/demo.py
```

This uses a fictional Example Corp listing and an isolated demo database. The result is `out/83856b4619525938/video.mp4`; it never uploads.

## Daily workflow

```powershell
python -m collector validate-boards
python -m collector run
python -m shorts review
```

The local dashboard supports opportunity approval/rejection, script editing, video generation and preview, video approval, manual export, upload, and scheduling. Nothing publishes without explicit video approval.

See [the source inventory](docs/SOURCES.md) for every configured company board, additional internship platforms, public API options, and which services require credentials.

For manual imports, use `python -m collector manual config/manual_example.yaml`. Replace the example fields with details from an official listing. Do not post the fictional example.

## CLI workflow

```powershell
python -m collector list
python -m collector set-status <id> approved
python -m shorts generate <id> --save
python -m shorts build <id>
# Preview out/<id>/video.mp4, then:
python -m shorts approve-video <id>
python -m shorts upload <id> --manual-export
# Or configure OAuth and authorize:
python -m shorts auth
python -m shorts upload <id> --dry-run
python -m shorts upload <id>
# Choose the next configured IST slot:
python -m shorts schedule <id>
python -m shorts run-daily --no-collect --upload
```

Manual exports include video, title, description, and disclosure settings. Exporting does not mark a listing posted. Upload attempts are limited, tracked, and protected against automatic duplicates after uncertain responses.

## What is implemented

- Collector: Greenhouse, Lever, Ashby, Unstop and AICTE public catalogues, Himalayas, structured employer pages, RSS, optional Remotive, and manual imports; Indian-applicant eligibility and early-career filtering, scoring, SQLite persistence, and change/closure tracking.
- Scripts: configurable Anthropic generation, validated template fallback, exact source-field checks and unsupported-number/date/URL detection.
- Media: Indian-English TTS voices with cached word boundaries, four HTML scenes, three layout variations, two color themes, safe-area overflow checks, normalized narration, ASS captions, and optional licensed background music.
- Review/publication: Streamlit dashboard, resumable OAuth upload, manual Studio export, two approval stages, IST schedules, configurable daily limits, stale-listing protection, and upload reconciliation.

## Layout and details

- `collector/`: ingestion and source adapters.
- `shorts/`: shared pipeline, scripts, voice, rendering, assembly, storage, upload, scheduler, and CLI.
- `shorts/review_app/`: local dashboard.
- `config/`: sources, filtering, voices, themes, and publishing settings.
- `tests/`: offline unit/workflow/dashboard tests.
- [Operating guide](docs/END_TO_END.md): setup, OAuth, scheduling, recovery, current YouTube API policies, and verification.
- [Card contract](docs/DATA_CONTRACT.md): collector interface and schema.

The collector schema is unchanged; posts, schedules, and attempt records use separate tables in the same database. Optional Telegram, analytics, and link-in-bio features are not included. Real channel publication must be verified after connecting your credentials. Review remains necessary: automated checks cannot establish the truth of arbitrary prose.
