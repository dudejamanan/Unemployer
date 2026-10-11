# Opportunity Shorts

An end-to-end system that collects Indian-eligible internships and fresher jobs, writes original scripts with local Ollama, produces captioned vertical videos, and schedules YouTube uploads.

The current configuration uses automatic processing for **@unemployerr**: collection -> selection -> Ollama narration -> TTS -> rendered scenes/captions -> scheduled public upload. No listing or video approval is required in automatic mode. Automatic validation, expiry checks, duplicate prevention and upload caps remain.

## Current setup

The Windows **OpportunityShortsWorker** task is installed and started. YouTube authorization has not been supplied, so nothing has been uploaded. The installed 8B local model ran out of memory; a smaller `qwen3:1.7b` download was started. Free sufficient RAM and finish the model download to enable live inference.

See [automatic setup and YouTube connection](docs/AUTOMATION.md), [reference-channel growth audit](docs/GROWTH.md), and [source inventory](docs/SOURCES.md).

## Start here

Run from the inner opportunity-shorts directory:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
ollama pull qwen3:1.7b
python -m shorts doctor
python -m pytest -q
```

FFmpeg and FFprobe must be on PATH. Ollama runs locally without an LLM API key. Edge TTS and source collection require internet. YouTube needs your own Google OAuth Desktop client JSON and one-time channel consent.

```powershell
# Set YOUTUBE_CLIENT_SECRETS_FILE=secrets/client_secret.json in .env first:
python -m shorts auth
# The installed worker publishes automatically after connection.
python -m shorts review
```

The dashboard can show opportunities and video previews, edit scripts, reject listings and export videos. Manual approvals are available only when automation.enabled is false.

## Components

- Collector: 23 configured company-board/public-catalogue/employer-page targets, Indian-applicant eligibility and early-career filtering, scoring, SQLite storage, change/closure tracking.
- Scripts: local Ollama JSON responses, light Hinglish preference, varied factual openings, original contextual guidance, relevant hashtags and automatic validation.
- Media: cached Indian voices, four HTML scenes, layout/color variations, safe areas, ASS captions, normalized audio and FFmpeg H.264/AAC output.
- Automation: six-hour collection, bounded generation queue, minute-by-minute due publishing, three IST slots, daily caps, cached builds, stale-content regeneration, channel identity checks and uncertain-upload recovery.

## Commands

```powershell
python -m collector run
python -m shorts generate <id> --save
python -m shorts build <id>
python -m shorts upload <id> --dry-run
python -m shorts run-daily --upload
python -m shorts daemon
```

The installed worker and foreground daemon must not run together. Keep the computer awake and connected. Public-upload visibility and live OAuth publication still need verification after authorization. There is no promise of channel growth, monetization approval or earnings.

- [Operating notes](docs/END_TO_END.md)
- [Growth findings](docs/GROWTH.md)
- [Automatic operation](docs/AUTOMATION.md)
- [Card contract](docs/DATA_CONTRACT.md)
- [Earlier @ashishcode source audit](docs/CHANNEL_SOURCES.md)
