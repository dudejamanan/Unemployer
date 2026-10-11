# PROMPT FOR WINDSURF AGENT (paste everything below into Cascade)

You are a senior Python engineer helping me finish an automated **YouTube Shorts channel that posts internships,
fresher jobs and hackathons for Indian students**. Stage 1 (the collector) is already built and tested in this repo.
Your job is to build Stages 2-6 on top of it, in small verified milestones.

## 0. First, do this before writing any code
1. Read `README.md`, `docs/DATA_CONTRACT.md`, `config/*.yaml`, and skim `collector/` (models, db, pipeline, cli).
2. Run `pip install -r requirements.txt && python -m pytest -q` and confirm all tests pass.
3. Summarise back to me in 10 lines what exists, then propose the folder plan below (adjust only if you have a strong reason)
   and wait for my "go" before Milestone 1.

## 1. Product goal
Every day: collect fresh opportunities -> I approve the best ones in a small dashboard -> the system generates a 20-40 s
vertical video (screen with all details + natural Indian-English/Hinglish voiceover covering role, company, eligibility,
stipend, deadline) -> uploads to YouTube Shorts with the official apply link in the description -> marks it posted.
Audience: Indian college students and freshers. The channel earns through sponsors/affiliates/promoted listings and
(later) ads, so **trust is the product**: no fabricated facts, no scam listings, always the official link.

## 2. What already exists (DO NOT rewrite; extend only through its interfaces)
- `collector/`: fetches Greenhouse/Lever/Ashby public JSON feeds (+ optional RSS, remote APIs, manual YAML/CSV import),
  enriches (deadline, stipend, batch years, India/remote), filters (India, early-career, scam patterns), scores, stores
  in SQLite (`data/opportunities.db`, table `opportunities`), exports "cards".
- CLI: `python -m collector run | manual | list | show | set-status | export | stats | validate-boards | add-board`.
- Card JSON + Python API are defined in `docs/DATA_CONTRACT.md`. **That contract is the only input to later stages.**
- Do not modify the `opportunities` table. Create new tables (e.g. `posts`) in the same SQLite file or a separate one.
- If you find a bug in `collector/`, fix it with a test and tell me; do not silently change behaviour.

## 3. Folder plan to build (new code goes in `shorts/`, collector stays untouched)
```
shorts/
  __init__.py
  settings.py            # loads .env + config/shorts.yaml (voices, theme, slots, limits)
  models.py              # ScriptDoc, SceneSpec, PostRecord (dataclasses/pydantic)
  store.py               # `posts` table: opportunity_id, script_json, video_path, youtube_id, status, error, timestamps
  script_gen.py          # card -> ScriptDoc via LLM (Anthropic API), strict JSON, validated
  validate_script.py     # fact-check: every number/date/url in script must exist in the card
  tts.py                 # edge-tts voiceover + word-level timestamps
  captions.py            # word timestamps -> burned-in captions (ASS or drawn in the HTML scenes)
  render/
    templates/           # 2-3 HTML/CSS scene layouts (1080x1920), theme tokens, Noto/Inter fonts bundled
    render_scenes.py     # Playwright screenshots (or video capture) of each scene
  assemble.py            # FFmpeg: scenes + voice + music (ducked) -> mp4
  upload.py              # YouTube Data API v3 uploader (OAuth), with dry-run and manual-export fallback
  review_app/            # Streamlit app: queue, edit script, preview video, approve/reject/schedule
  scheduler.py           # run collect -> generate -> upload on IST slots (APScheduler or plain cron entrypoints)
  telegram_post.py       # OPTIONAL: mirror each card to a Telegram channel
  cli.py                 # `python -m shorts generate <id> | upload <id> | run-daily | doctor`
assets/                  # fonts, logo, background music (royalty-free only), color palette
tests/shorts/            # unit tests; no network in tests
config/shorts.yaml
.env.example             # extend with new keys (never commit real ones)
```

## 4. Milestones (do them in order; stop after each and show me the result)
**M1: Script generation.** `script_gen.py` takes a card and returns a validated `ScriptDoc`:
`{hook, voiceover_lines[], on_screen:{role,company,location,stipend,eligibility,deadline_badge,cta}, title, description, hashtags[]}`.
- 55-85 spoken words (about 20-35 s). Hook in the first 2 s ("Google internship, apply before Friday"). Simple Indian English;
  option for light Hinglish in Latin script. Ends with "Apply link is in the description."
- LLM call: Anthropic API, model name read from config (don't hardcode), `temperature` low, JSON-only output, retries on
  invalid JSON. Provide a deterministic **template fallback** when the API is unavailable so the pipeline still runs.
- `validate_script.py` rejects a script if it contains any amount, date, company, URL or batch year not present in the card,
  or if a field the card has as empty/null is mentioned. Missing deadline => the script says "apply soon", never a date.
- Description format: line 1 = apply URL, then role/company/eligibility/deadline, then "Always verify details on the
  official site", then hashtags incl. #Shorts. Title <= 100 chars.
- Tests: golden tests with 3 sample cards (internship with stipend, job without deadline, hackathon).

**M2: Voice.** `tts.py` using `edge-tts`. Default voices: an Indian-English male and female (list them with
`edge-tts --list-voices` and pick `en-IN-*`; make voice a config value and alternate between posts for variety).
Return mp3 + word-boundary timestamps. Cache by hash of text+voice. Normalise loudness (ffmpeg `loudnorm`).

**M3: Visuals.** HTML/CSS scene templates at 1080x1920 rendered with Playwright (Chromium). Scenes: (1) hook + company +
role, (2) key facts card (location, stipend, eligibility, batch), (3) deadline countdown badge, (4) "Apply link in description" CTA.
- Keep text inside Shorts safe zones: leave bottom ~22% and right ~12% free of important text (YouTube UI overlays).
- Min font 56 px for body, high contrast, <= 7 words per line, one idea per scene, subtle animation (CSS) only if cheap.
- 3 interchangeable layouts + 2 color themes, rotated automatically (variety protects against "mass-produced content" flags).
- Show the apply URL on screen as a short readable form (domain only), not a long tracking link.

**M4: Assembly.** `assemble.py` builds the mp4 with FFmpeg: scene durations driven by voiceover timestamps, captions burned in,
optional royalty-free background music ducked under voice (-18 to -22 dB). Output H.264 + AAC, 1080x1920, 30 fps,
target 20-40 s. Add `doctor` command that checks ffmpeg, playwright browsers, fonts, API keys.

**M5: Review dashboard.** Streamlit app: queue of `new` cards sorted by score (reuse `Database.list`), card details,
generate/preview video, edit script text then re-render, buttons Approve / Reject (-> `set-status`), schedule slot.
Show warnings (no deadline, no stipend, `verified=false`, validation failures). Nothing uploads without explicit approval.

**M6: Upload + scheduling.** `upload.py` with YouTube Data API v3 `videos.insert` (resumable), OAuth installed-app flow, token
stored locally and git-ignored. Set title/description/tags, `categoryId` for Education, not-made-for-kids.
- **Important platform constraints to handle and tell me about:** (a) API projects that haven't passed YouTube's API
  compliance audit may only be able to upload videos as *private*; (b) `videos.insert` is expensive in daily API quota
  (default quota allows only a handful of uploads/day). Check the current official docs and implement: a `--manual-export`
  mode that writes `out/<date>/<id>/{video.mp4,title.txt,description.txt}` so I can upload through YouTube Studio when the
  API isn't usable, and a quota-aware daily limit.
- Review YouTube's current policy on disclosing AI-generated/synthetic voice or content and tell me what's required.
- After a successful upload store `youtube_id`, call `set_status(id, "posted")`. Failures never mark posted.
- `scheduler.py`: collect twice a day, generate for approved items, upload in IST slots from config (e.g. 08:00, 13:00, 19:00),
  max N per day, never post the same company+title within 30 days, skip expired deadlines.

**M7 (optional): Growth hooks.** Telegram channel mirror, link-in-bio page listing all open opportunities, simple analytics
export (views per post from YouTube Analytics) feeding back into scoring.

## 5. Hard rules (these matter more than speed)
- **Truthfulness:** only use fields from the card. Never invent stipend, deadline, eligibility, company, or links.
  Unknown = omit. Always keep "verify on the official site" in the description.
- **Trust & safety:** respect the collector's scam filter; additionally refuse to render items whose text contains
  fees/deposits/"WhatsApp only" patterns. Sponsored/promoted items must be labelled "Promoted" on screen and in the description.
- **No scraping of sites whose terms forbid it.** Do not add Internshala/Unstop/LinkedIn scrapers. Manual import is the path for those.
- **Originality:** vary hooks, layouts, voices and add one human-value line per video ("Good for 2027 batch", "Beginner friendly").
- **Engineering:** Python 3.11+, type hints, small modules, `pathlib`, logging (no print), config in YAML/.env, no secrets in git,
  every network/LLM/TTS/FFmpeg call behind a function that tests can mock. Idempotent: re-running must not duplicate videos or posts.
- Each milestone ends with: tests passing, a short `docs/` note, and an example command I can run.
- If a requirement is ambiguous or an external service behaves differently from what you assumed, stop and ask me
  one precise question instead of guessing.

## 6. External things I will set up (tell me exactly what you need and where to put it)
Python 3.11+, FFmpeg on PATH, Playwright Chromium (`playwright install chromium`), an Anthropic API key,
a Google Cloud project with YouTube Data API v3 + OAuth client (Desktop app) + my channel authorised,
optional Telegram bot token + channel id, royalty-free music in `assets/music/`, fonts in `assets/fonts/`.
Put all keys in `.env`; list every variable you add in `.env.example` with a comment.

Start with step 0 now.
