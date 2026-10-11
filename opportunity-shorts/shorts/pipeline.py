"""Shared orchestration for CLI, review dashboard, and scheduled runs."""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from collector.config import load_settings
from collector.db import Database, row_to_card
from collector.filters import SCAM_RE
from .models import PostRecord, ScriptDoc
from .settings import load_shorts_settings
from .store import PostStore
from .script_gen import generate_script
from .validate_script import validate_script
from .tts import generate_tts, get_voice_for_post
from .render.render_scenes import render_all_scenes
from .assemble import assemble_with_captions

IST = timezone(timedelta(hours=5, minutes=30))


def fact_digest(card):
    return hashlib.sha256(json.dumps({k: card.get(k) for k in
        ('company', 'role', 'location', 'stipend', 'batch_years', 'experience',
         'deadline', 'apply_url', 'description')}, sort_keys=True).encode()).hexdigest()


class Pipeline:
    def __init__(self, config_dir=None):
        self.settings = load_shorts_settings(config_dir)
        self.collector_settings = load_settings(config_dir)
        self.db = Database(self.collector_settings['db_path'])
        self.posts = PostStore(self.collector_settings['db_path'])

    def close(self):
        self.posts.close()
        self.db.close()

    def card(self, opportunity_id, approved=False):
        row = self.db.get(opportunity_id)
        if row is None:
            raise ValueError('Opportunity not found or ID is ambiguous')
        card = row_to_card(row)
        if not row['is_open'] or (card['deadline'] and card['deadline'] < datetime.now(IST).date().isoformat()):
            raise ValueError('Opportunity is closed or expired')
        if card['status'] == 'rejected':
            raise ValueError('Opportunity was rejected')
        if approved and card['status'] != 'approved' and not self.settings['automation']['enabled']:
            raise ValueError('Explicit opportunity approval is required')
        if approved and self.settings['automation']['enabled']:
            checked = row['last_seen_at']
            limit = int(self.settings['automation'].get('max_source_age_hours', 24))
            if not checked or datetime.fromisoformat(checked.replace('Z', '+00:00')) < datetime.now(timezone.utc) - timedelta(hours=limit):
                raise ValueError('Source listing is stale; refresh the collector before publishing')
        if SCAM_RE.search(card['role'] + '\n' + card['description']):
            raise ValueError('Suspicious fee, deposit, or messaging-only listing')
        url = urlparse(card['apply_url'])
        if url.scheme not in ('http', 'https') or not url.netloc:
            raise ValueError('A valid official application URL is required')
        return card

    def script(self, opportunity_id, edited=None):
        card = self.card(opportunity_id)
        existing = self.posts.get(card['id'])
        if existing and (existing.youtube_id or existing.status == 'uploading'):
            raise ValueError('Uploaded or unresolved uploading posts cannot be regenerated')
        script = edited or generate_script(card, self.settings)
        labels = {'himalayas': 'Himalayas', 'remotive': 'Remotive', 'unstop': 'Unstop', 'aicte': 'AICTE National Internship Portal'}
        if card['source'] in labels:
            credit = 'Source: ' + labels[card['source']]
            if credit not in script.description:
                script.description += '\n' + credit
        valid, errors = validate_script(script, card)
        if not valid:
            raise ValueError('; '.join(errors))
        self.posts.upsert(PostRecord(card['id'], json.dumps(script.to_dict(), ensure_ascii=False)))
        return script

    def build(self, opportunity_id, force=False, audio_path=None):
        card = self.card(opportunity_id)
        post = self.posts.get(card['id'])
        if post and post.youtube_id:
            return post
        if post and post.status == 'uploading':
            raise ValueError('Resolve previous upload in YouTube Studio before retrying')
        existing_manifest = Path(self.settings['paths']['output_dir']) / card['id'] / 'manifest.json'
        changed = (existing_manifest.exists() and
                   json.loads(existing_manifest.read_text())['facts'] != fact_digest(card))
        llm_identity = {key: self.settings['llm'].get(key) for key in ('provider', 'model')}
        llm_identity['hinglish'] = self.settings['script'].get('hinglish_enabled', False)
        from .editorial import VERSION, hook_variant
        llm_identity['editorial'] = VERSION
        changed_generator = (self.settings['automation']['enabled'] and existing_manifest.exists() and
                             json.loads(existing_manifest.read_text()).get('llm') != llm_identity)
        script = ScriptDoc.from_dict(json.loads(post.script_json)) if post and post.script_json != '{}' and not changed and not changed_generator else self.script(card['id'])
        valid, errors = validate_script(script, card)
        if not valid:
            raise ValueError('; '.join(errors))
        folder = Path(self.settings['paths']['output_dir']) / card['id']
        folder.mkdir(parents=True, exist_ok=True)
        templates = Path(__file__).parent / 'render' / 'templates'
        renderer_digest = hashlib.sha256(b''.join(
            path.read_bytes() for path in sorted(templates.glob('*.html')))).hexdigest()
        digest = hashlib.sha256(json.dumps({'facts': fact_digest(card), 'llm': llm_identity, 'renderer': renderer_digest, 'script': script.to_dict(), 'settings': {
            key: self.settings[key] for key in ('voices', 'theme', 'assembly', 'captions')},
            'audio': str(audio_path) if audio_path else None}, sort_keys=True).encode()).hexdigest()
        manifest = folder / 'manifest.json'
        if not force and post and post.video_path and Path(post.video_path).exists() and manifest.exists():
            if json.loads(manifest.read_text())['digest'] == digest:
                if self.settings['automation']['enabled'] and post.status == 'generated':
                    self.posts.update_status(card['id'], 'ready')
                    post.status = 'ready'
                return post
        post = PostRecord(card['id'], json.dumps(script.to_dict(), ensure_ascii=False), status='generating')
        self.posts.upsert(post)
        try:
            voice_index = int(hashlib.sha256(card['id'].encode()).hexdigest()[:8], 16)
            if audio_path:
                from .assemble import _get_audio_duration
                from .tts import _estimate_word_timestamps, TTSResult
                duration = _get_audio_duration(Path(audio_path))
                audio = TTSResult(str(Path(audio_path).resolve()), duration,
                    _estimate_word_timestamps(' '.join(l.text for l in script.voiceover_lines), duration))
            else:
                audio = asyncio.run(generate_tts(' '.join(l.text for l in script.voiceover_lines),
                    get_voice_for_post(voice_index, self.settings), self.settings))
            scenes = render_all_scenes(script, folder / 'scenes', card['apply_url'], self.settings, voice_index)
            music = self.settings['assembly'].get('music_file')
            if music and not Path(music).is_absolute():
                from collector.config import ROOT
                music = ROOT / music
            video = assemble_with_captions(scenes, Path(audio.audio_path), folder / 'video.mp4',
                                          audio.word_timestamps, music_path=music, settings=self.settings)
            post.video_path = str(video)
            post.status = 'ready' if self.settings['automation']['enabled'] else 'generated'
            (folder / 'script.json').write_text(json.dumps(script.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
            manifest.write_text(json.dumps({'digest': digest, 'facts': fact_digest(card), 'duration': audio.duration_seconds,
                                           'llm': llm_identity, 'hook_variant': hook_variant(card)}), encoding='utf-8')
            self.posts.upsert(post)
            return post
        except Exception as exc:
            post.status, post.error_message = 'failed', str(exc)
            self.posts.upsert(post)
            raise

    def approve_video(self, opportunity_id):
        card = self.card(opportunity_id, approved=True)
        post = self.posts.get(card['id'])
        if not post or post.status != 'generated' or not post.video_path or not Path(post.video_path).is_file():
            raise ValueError('Generate and preview the video before approving it')
        self.posts.update_status(card['id'], 'ready')

    def upload(self, opportunity_id, manual_export=False, dry_run=False):
        from .upload import export_manual, upload_video
        row = self.db.get(opportunity_id)
        if row:
            previous = self.posts.get(row['id'])
            if previous and previous.youtube_id:
                self.db.set_status(row['id'], 'posted')
                return previous.youtube_id
        card = self.card(opportunity_id, approved=True)
        post = self.posts.get(card['id'])
        if not post or post.status != 'ready' or not post.video_path or not Path(post.video_path).is_file():
            raise ValueError('Explicit video approval is required before export/upload')
        manifest = Path(self.settings['paths']['output_dir']) / card['id'] / 'manifest.json'
        if not manifest.exists() or json.loads(manifest.read_text())['facts'] != fact_digest(card):
            raise ValueError('Listing changed since generation; regenerate and approve the video again')
        script = ScriptDoc.from_dict(json.loads(post.script_json))
        valid, errors = validate_script(script, card)
        if not valid:
            raise ValueError('; '.join(errors))
        if manual_export:
            return export_manual(post, script, self.settings)
        if dry_run:
            return {'video': post.video_path, 'title': script.title, 'privacy': self.settings['upload'].get('privacy', 'private')}
        now = datetime.now(IST)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
        end = (now.replace(hour=0, minute=0, second=0, microsecond=0)+timedelta(days=1)).astimezone(timezone.utc).isoformat()
        # Reserve quota before networking; a lost response must never cause an automatic duplicate.
        conn = self.posts.conn
        conn.execute('BEGIN IMMEDIATE')
        try:
            count = conn.execute('SELECT COUNT(*) FROM upload_attempts WHERE attempted_at>=? AND attempted_at<?', (start, end)).fetchone()[0]
            cfg = self.settings['upload']
            limit = min(int(cfg['daily_limit']), int(cfg.get('api_daily_upload_limit', 100)))
            if count >= limit:
                raise ValueError('Daily upload attempt limit reached')
            cutoff = (now-timedelta(days=30)).astimezone(timezone.utc).isoformat()
            duplicate = conn.execute("SELECT 1 FROM upload_attempts a JOIN posts p ON p.opportunity_id=a.opportunity_id WHERE a.company=? AND a.role=? AND a.attempted_at>=? AND p.status IN ('uploading', 'posted')",
                (card['company'].casefold(), card['role'].casefold(), cutoff)).fetchone()
            if duplicate:
                raise ValueError('This company and role already has an upload attempt within 30 days')
            cur = conn.execute("UPDATE posts SET status='uploading' WHERE opportunity_id=? AND status='ready'", (card['id'],))
            if cur.rowcount != 1:
                raise ValueError('Post is already being uploaded')
            conn.execute('INSERT INTO upload_attempts VALUES (?, ?, ?, ?)',
                (card['id'], card['company'].casefold(), card['role'].casefold(), now.astimezone(timezone.utc).isoformat()))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        # Leave uncertain uploads locked for manual reconciliation rather than retrying videos.insert.
        try:
            youtube_id = upload_video(post, script, self.settings)
        except Exception as exc:
            # Explicit rejection is safe to defer; a lost response remains locked.
            from googleapiclient.errors import HttpError
            if isinstance(exc, HttpError) and 400 <= exc.resp.status < 500 and exc.resp.status != 408:
                self.posts.update_status(card['id'], 'ready', str(exc))
                deferred = now + timedelta(hours=1)
                if b'quotaExceeded' in exc.content or b'uploadLimitExceeded' in exc.content:
                    deferred = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                conn.execute('INSERT OR REPLACE INTO upload_retries VALUES (?, ?, ?)',
                             (card['id'], deferred.isoformat(), str(exc)[:500]))
                conn.commit()
            else:
                self.posts.update_status(card['id'], 'uploading', str(exc))
            raise
        conn.execute('DELETE FROM upload_retries WHERE opportunity_id=?', (card['id'],))
        conn.commit()
        self.posts.set_youtube_id(card['id'], youtube_id)
        self.db.set_status(card['id'], 'posted')
        return youtube_id
