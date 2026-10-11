"""One-shot runner intended for Windows Task Scheduler or cron."""
from datetime import datetime, timedelta
from collector.config import load_boards, load_sources_cfg
from collector.pipeline import run_collection
from collector.http_client import HttpClient
from .pipeline import Pipeline, IST


def schedule(pipeline, opportunity_id, when):
    card = pipeline.card(opportunity_id, approved=True)
    post = pipeline.posts.get(card['id'])
    if not post or post.status != 'ready':
        raise ValueError('Approve the generated video before scheduling')
    if when == 'next':
        now = datetime.now(IST)
        candidates = []
        for days in (0, 1):
            for slot in pipeline.settings['upload']['ist_slots']:
                hour, minute = map(int, slot.split(':'))
                candidate = (now+timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                if candidate > now:
                    candidates.append(candidate)
        if not candidates:
            raise ValueError('Configure at least one IST slot')
        timestamp = min(candidates)
    else:
        timestamp = datetime.fromisoformat(when)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=IST)
    if timestamp <= datetime.now(IST):
        raise ValueError('Schedule must be in the future')
    if card['deadline'] and timestamp.astimezone(IST).date().isoformat() > card['deadline']:
        raise ValueError('Schedule is after the application deadline')
    pipeline.posts.conn.execute('INSERT INTO schedules VALUES (?, ?) ON CONFLICT(opportunity_id) DO UPDATE SET scheduled_at=excluded.scheduled_at',
                               (card['id'], timestamp.astimezone(IST).isoformat()))
    pipeline.posts.conn.commit()


def run_daily(config_dir=None, collect=True, upload=False, manual_export=False):
    pipeline = Pipeline(config_dir)
    result = {'collected': None, 'generated': [], 'uploaded': [], 'errors': []}
    try:
        if collect:
            cfg = pipeline.collector_settings
            client = HttpClient(cfg['user_agent'], cfg['request_timeout'], cfg['min_delay_seconds'])
            stats = run_collection(pipeline.collector_settings, load_boards(config_dir),
                                   load_sources_cfg(config_dir), pipeline.db, client)
            result['collected'] = {'kept': stats.kept, 'errors': stats.errors}
            result['errors'].extend(stats.errors)
            client.session.close()
        for row in pipeline.db.list(status='approved', limit=100, today=datetime.now(IST).date()):
            post = pipeline.posts.get(row['id'])
            if post and post.status in ('ready', 'uploading', 'posted'):
                continue
            try:
                pipeline.build(row['id'])
                result['generated'].append(row['id'])
            except Exception as exc:
                result['errors'].append(f"{row['id']}: {exc}")
        if upload or manual_export:
            now = datetime.now(IST)
            # A schedule is explicit permission to publish that reviewed video at that time.
            for row in pipeline.posts.conn.execute('SELECT * FROM schedules ORDER BY scheduled_at').fetchall():
                if datetime.fromisoformat(row['scheduled_at']) > now:
                    continue
                try:
                    value = pipeline.upload(row['opportunity_id'], manual_export=manual_export)
                    result['uploaded'].append(str(value))
                    pipeline.posts.conn.execute('DELETE FROM schedules WHERE opportunity_id=?', (row['opportunity_id'],))
                    pipeline.posts.conn.commit()
                except Exception as exc:
                    result['errors'].append(f"{row['opportunity_id']}: {exc}")
        return result
    finally:
        pipeline.close()
