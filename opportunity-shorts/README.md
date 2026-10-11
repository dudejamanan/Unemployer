# Unemployer

An end-to-end system that collects Indian-eligible internships and fresher jobs, writes original scripts with local Ollama, produces captioned vertical videos, and schedules YouTube uploads.

The current configuration uses automatic processing for **@unemployerr**: collection -> selection -> Ollama narration -> TTS -> rendered scenes/captions -> scheduled public upload. No listing or video approval is required in automatic mode. Automatic validation, expiry checks, duplicate prevention and upload caps remain.

## Current setup

The Windows **UnemployerWorker** task is installed. YouTube channel authorization is saved; the automatic worker handles scheduled uploads. After freeing memory, the installed `qwen3:8b` model successfully ran in CPU mode; GPU attempts failed with a CUDA/PTX error. The active configuration uses CPU mode and no paid LLM API key.

See [automatic setup and YouTube connection](docs/AUTOMATION.md), [reference-channel growth audit](docs/GROWTH.md), and [source inventory](docs/SOURCES.md).

## Start here

Run from the project directory:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
ollama list
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
- Automation: 15-minute source refreshes, bounded generation, immediate publishing of active queued/new videos, daily caps, cached builds, stale-content regeneration, channel identity checks and uncertain-upload recovery.

## Commands

```powershell
python -m collector run
python -m shorts generate <id> --save
python -m shorts build <id>
python -m shorts upload <id> --dry-run
python -m shorts run-daily --upload
python -m shorts daemon
```

The installed worker and foreground daemon must not run together. Keep the computer awake and connected. Real public uploads and live OAuth publishing have been verified. There is no promise of channel growth, monetization approval or earnings.

- [Operating notes](docs/END_TO_END.md)
- [Growth findings](docs/GROWTH.md)
- [Automatic operation](docs/AUTOMATION.md)
- [Card contract](docs/DATA_CONTRACT.md)
- [Earlier @ashishcode source audit](docs/CHANNEL_SOURCES.md)


## Production upgrade

The public application hub is live at https://unemployer.syrupytide17.chatgpt.site. It includes live employer/catalogue feeds, source redirects, a free application checklist and a sponsorship contact. Add it to your YouTube channel profile links so Shorts viewers can reach it.

New videos include the logo, responsibilities-focused narration, original role-specific application recommendations, caption highlighting and subtle motion. Production operations include rotating worker logs, cycle health reports, seven daily database backups, explicit upload-rejection cooldowns and public YouTube performance snapshots. Run `python -m shorts health`, `python -m shorts metrics --refresh`, or `python -m shorts backup`.

See [production and revenue operations](docs/PRODUCTION.md). Advertising approval, payments, sponsorship deals and revenue are not guaranteed or automatically activated by these changes.
