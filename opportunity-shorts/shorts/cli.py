from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from collector.config import load_settings
from collector.db import Database, row_to_card
from .script_gen import generate_script
from .validate_script import validate_script
from .settings import load_shorts_settings
from .store import PostStore
from .tts import generate_tts, get_voice_for_post
from .render.render_scenes import render_all_scenes, get_scene_specs
from .assemble import check_ffmpeg, check_ffprobe
from .models import PostRecord


def cmd_generate(args):
    from .pipeline import Pipeline
    pipeline = Pipeline(args.config)
    try:
        card = pipeline.card(args.id)
        script = pipeline.script(card['id']) if args.save else generate_script(card, pipeline.settings)
        valid, errors = validate_script(script, card)
        print(json.dumps(script.to_dict(), ensure_ascii=True, indent=2))
        if not valid:
            print("Validation failed: " + "; ".join(errors), file=sys.stderr)
        return 0 if valid else 1
    finally:
        pipeline.close()


async def cmd_tts(args):
    """Generate TTS for a given text string."""
    settings = load_shorts_settings(args.config)
    voice = args.voice or settings["voices"]["male"]

    print(f"Generating TTS for: {args.text}")
    print(f"Voice: {voice}")

    result = await generate_tts(args.text, voice, settings, use_cache=not args.no_cache)

    print(f"\n--- TTS Result ---")
    print(f"Audio path: {result.audio_path}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Word timestamps: {len(result.word_timestamps)} words")
    for ts in result.word_timestamps[:5]:  # Show first 5
        print(f"  {ts['word']}: {ts['start']:.2f}s - {ts['end']:.2f}s")
    if len(result.word_timestamps) > 5:
        print(f"  ... and {len(result.word_timestamps) - 5} more")

    return 0


def cmd_render(args):
    """Render scenes for a script."""
    settings = load_shorts_settings(args.config)

    # Load script from JSON file or generate from card
    if args.script_json:
        import json
        from .models import ScriptDoc
        with open(args.script_json, "r", encoding="utf-8") as f:
            script_data = json.load(f)
        script = ScriptDoc.from_dict(script_data)
        apply_url = script_data.get("apply_url") or script.description.splitlines()[0]
    else:
        print("Error: --script-json required for render command")
        return 1

    output_dir = Path(args.output) if args.output else Path(settings["paths"]["output_dir"]) / "scenes"

    print(f"Rendering scenes to: {output_dir}")
    scene_paths = render_all_scenes(script, output_dir, apply_url, settings, theme_index=args.theme_index)

    print(f"\nRendered {len(scene_paths)} scenes:")
    for path in scene_paths:
        print(f"  - {path}")

    return 0


def cmd_doctor(args):
    """Check dependencies and configuration."""
    print("Checking dependencies...")

    issues = []

    # Check FFmpeg
    if check_ffmpeg():
        print("OK ffmpeg found")
    else:
        issues.append("ffmpeg not found on PATH (needed for M4: Assembly)")

    # Check FFprobe
    if check_ffprobe():
        print("OK ffprobe found")
    else:
        issues.append("ffprobe not found on PATH (needed for audio duration)")

    # Check Playwright
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            browser.close()
        print("OK Playwright Chromium available")
    except Exception as exc:
        issues.append(f"Playwright Chromium unavailable: {exc}")

    # Check local Ollama
    settings = load_shorts_settings(args.config)
    import requests
    try:
        response = requests.get(settings['llm']['base_url'].rstrip('/') + '/api/tags', timeout=5)
        response.raise_for_status()
        names = {model['name'] for model in response.json()['models']}
        if settings['llm']['model'] not in names:
            issues.append('Configured Ollama model is not installed')
        else:
            print('OK local Ollama model: ' + settings['llm']['model'])
    except (requests.RequestException, KeyError, ValueError):
        issues.append('Ollama is unavailable; start Ollama')

    # Check YouTube client secrets
    if settings.get("youtube_client_secrets_file"):
        secrets_path = Path(settings["youtube_client_secrets_file"])
        if secrets_path.exists():
            print(f"OK YouTube client secrets file found: {secrets_path}")
        else:
            issues.append(f"YouTube client secrets file not found: {secrets_path}")
    else:
        print("NOTE YOUTUBE_CLIENT_SECRETS_FILE not set (needed for M6: Upload)")

    # Check edge-tts
    try:
        import edge_tts
        print("OK edge-tts installed")
    except ImportError:
        issues.append("edge-tts not installed (needed for M2: Voice). Run: pip install edge-tts")

    # Check fonts directory
    fonts_dir = Path(settings["paths"]["fonts_dir"])
    if fonts_dir.exists():
        print(f"OK Fonts directory exists: {fonts_dir}")
    else:
        print(f"NOTE Fonts directory not found: {fonts_dir} (will create)")

    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(f"  ERROR {issue}")
        return 1
    else:
        print("\nAll checks passed!")
        return 0


def cmd_pipeline(args):
    import subprocess
    from .pipeline import Pipeline
    from .scheduler import schedule, run_daily
    if args.cmd == 'review':
        import os
        app = Path(__file__).parent / 'review_app' / 'app.py'
        environment = os.environ.copy()
        if args.config:
            environment['SHORTS_CONFIG_DIR'] = str(Path(args.config).resolve())
        return subprocess.call([sys.executable, '-m', 'streamlit', 'run', str(app),
                                '--server.address', '127.0.0.1', '--server.headless', 'true',
                                '--browser.gatherUsageStats', 'false'], env=environment)
    if args.cmd == 'run-daily':
        result = run_daily(args.config, not args.no_collect, args.upload, args.manual_export)
        print(json.dumps(result, indent=2))
        return 1 if result['errors'] else 0
    if args.cmd == 'daemon':
        from .scheduler import run_daemon
        run_daemon(args.config, upload=not args.no_upload)
        return 0
    pipeline = Pipeline(args.config)
    try:
        if args.cmd == 'auth':
            from .upload import youtube_service
            youtube_service(pipeline.settings, interactive=True)
            print('YouTube authorization saved')
        elif args.cmd == 'build':
            print(pipeline.build(args.id, args.force, args.audio).video_path)
        elif args.cmd == 'approve-video':
            pipeline.approve_video(args.id)
            print('Video approved')
        elif args.cmd == 'upload':
            print(pipeline.upload(args.id, args.manual_export, args.dry_run))
        elif args.cmd == 'schedule':
            schedule(pipeline, args.id, args.when)
            print('Scheduled')
        elif args.cmd == 'reset-upload':
            row = pipeline.db.get(args.id)
            post = pipeline.posts.get(row['id']) if row else None
            if not post or post.status != 'uploading':
                raise ValueError('Only an unresolved upload can be reset')
            pipeline.posts.update_status(row['id'], 'generated', '')
            print('Upload reset; approve the video again before retrying')
        elif args.cmd == 'reconcile-upload':
            import re
            row = pipeline.db.get(args.id)
            if not row or not re.fullmatch(r'[A-Za-z0-9_-]{11}', args.youtube_id):
                raise ValueError('Provide an exact existing YouTube video ID')
            post = pipeline.posts.get(row['id'])
            if not post or post.status != 'uploading':
                raise ValueError('Only an unresolved upload can be reconciled')
            pipeline.posts.set_youtube_id(row['id'], args.youtube_id)
            pipeline.db.set_status(row['id'], 'posted')
            print('Upload reconciled')
        return 0
    finally:
        pipeline.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="shorts", description="YouTube Shorts generation pipeline")
    p.add_argument("--config", help="config dir (default: ./config)")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ('build', 'approve-video', 'upload', 'schedule', 'reconcile-upload', 'reset-upload'):
        command = sub.add_parser(name)
        command.add_argument('id')
        if name == 'build':
            command.add_argument('--force', action='store_true')
            command.add_argument('--audio', help='Use a supplied voiceover audio file')
        if name == 'upload':
            command.add_argument('--manual-export', action='store_true')
            command.add_argument('--dry-run', action='store_true')
        if name == 'schedule':
            command.add_argument('when', nargs='?', default='next', help='ISO date/time or next configured IST slot')
        if name == 'reset-upload':
            command.add_argument('--confirmed-absent', action='store_true', required=True,
                                 help='Confirm that you checked YouTube Studio and no video was created')
        if name == 'reconcile-upload':
            command.add_argument('--youtube-id', required=True, help='Existing video ID verified in YouTube Studio')
        command.set_defaults(fn=cmd_pipeline)
    command = sub.add_parser('auth', help='Authorize the YouTube channel interactively')
    command.set_defaults(fn=cmd_pipeline)
    command = sub.add_parser('run-daily', help='Collect and generate; optionally upload due reviewed schedules')
    command.add_argument('--no-collect', action='store_true')
    command.add_argument('--upload', action='store_true')
    command.add_argument('--manual-export', action='store_true')
    command.set_defaults(fn=cmd_pipeline)
    command = sub.add_parser('review', help='Launch local review dashboard')
    command.set_defaults(fn=cmd_pipeline)
    command = sub.add_parser('daemon', help='Continuously collect, build, schedule and publish without approvals')
    command.add_argument('--no-upload', action='store_true', help='Generate and schedule without publishing')
    command.set_defaults(fn=cmd_pipeline)

    s = sub.add_parser("generate", help="generate script for an opportunity")
    s.add_argument("id", help="opportunity ID (16-char hex)")
    s.add_argument("--save", action="store_true", help="save script to posts table")
    s.set_defaults(fn=cmd_generate)

    s = sub.add_parser("tts", help="generate text-to-speech audio")
    s.add_argument("text", help="text to convert to speech")
    s.add_argument("--voice", help="edge-tts voice name")
    s.add_argument("--no-cache", action="store_true", help="bypass cache")
    s.set_defaults(fn=cmd_tts)

    s = sub.add_parser("render", help="render visual scenes from script")
    s.add_argument("--script-json", required=True, help="path to script JSON file")
    s.add_argument("--output", help="output directory for rendered scenes")
    s.add_argument("--theme-index", type=int, default=0, help="starting theme index")
    s.set_defaults(fn=cmd_render)

    s = sub.add_parser("doctor", help="check dependencies and configuration")
    s.set_defaults(fn=cmd_doctor)

    args = p.parse_args(argv)

    # Handle async commands
    try:
        if asyncio.iscoroutinefunction(args.fn):
            return asyncio.run(args.fn(args))
        return args.fn(args)
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
