"""One-shot runner intended for Windows Task Scheduler or cron."""
from datetime import datetime, timedelta, timezone
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
        if pipeline.settings['automation']['enabled']:
            return run_automatic(pipeline, result, upload=upload, manual_export=manual_export)
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


def run_automatic(pipeline, result, upload=False, manual_export=False):
    """Bounded unattended queue: no human approvals, no rejected or duplicate posts."""
    from .pipeline import fact_digest
    from .upload import youtube_service, reconcile_pending
    from pathlib import Path
    import json
    now = datetime.now(IST)
    immediate = pipeline.settings['automation'].get('publishing_mode') == 'immediate'
    from .priority import priority_key, compensation
    priority = pipeline.settings['automation'].get('priority', {})
    # Remove invalid queue entries even while channel access is unavailable.
    for scheduled in pipeline.posts.conn.execute('SELECT opportunity_id FROM schedules').fetchall():
        row = pipeline.db.get(scheduled['opportunity_id'])
        if not row or row['status'] in ('rejected', 'posted') or not row['is_open'] or (row['deadline'] and row['deadline'] < now.date().isoformat()):
            pipeline.posts.conn.execute('DELETE FROM schedules WHERE opportunity_id=?', (scheduled['opportunity_id'],))
    pipeline.posts.conn.commit()
    # Check channel access before consuming generation/upload quota.
    if upload:
        try:
            service = youtube_service(pipeline.settings)
            result['uploaded'].extend(reconcile_pending(pipeline, service))
        except Exception as exc:
            result['errors'].append('YouTube connection: ' + str(exc))
            upload = False
    for row in pipeline.posts.conn.execute('SELECT * FROM schedules ORDER BY scheduled_at').fetchall():
        if immediate:
            break  # Ready and new candidates share the same stipend priority below.
        retry = pipeline.posts.conn.execute('SELECT retry_after FROM upload_retries WHERE opportunity_id=?', (row['opportunity_id'],)).fetchone()
        if retry and datetime.fromisoformat(retry['retry_after']) > now:
            continue
        if (not immediate and datetime.fromisoformat(row['scheduled_at']) > now) or not (upload or manual_export):
            continue
        try:
            card = pipeline.card(row['opportunity_id'])
            manifest = Path(pipeline.settings['paths']['output_dir']) / card['id'] / 'manifest.json'
            pipeline.build(card['id'])
            value = pipeline.upload(card['id'], manual_export=manual_export)
            result['uploaded'].append(str(value))
            pipeline.posts.conn.execute('DELETE FROM schedules WHERE opportunity_id=?', (card['id'],))
            pipeline.posts.conn.commit()
        except Exception as exc:
            result['errors'].append(f"{row['opportunity_id']}: {exc}")
    if immediate:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        end = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).astimezone(timezone.utc)
        attempted = pipeline.posts.conn.execute(
            'SELECT COUNT(*) FROM upload_attempts WHERE attempted_at>=? AND attempted_at<?',
            (start.isoformat(), end.isoformat())).fetchone()[0]
        limit = min(int(pipeline.settings['upload']['daily_limit']),
                    int(pipeline.settings['upload'].get('api_daily_upload_limit', 100)))
        if attempted >= limit:
            return result
    if pipeline.settings['llm'].get('provider') == 'ollama':
        import requests
        try:
            cfg = pipeline.settings['llm']
            response = requests.get(cfg['base_url'].rstrip('/') + '/api/tags', timeout=5)
            response.raise_for_status()
            if cfg['model'] not in {model['name'] for model in response.json()['models']}:
                raise ValueError('Ollama model is still downloading or not installed: ' + cfg['model'])
        except (requests.RequestException, ValueError, KeyError) as exc:
            result['errors'].append(str(exc))
            return result
    maximum = int(pipeline.settings['automation']['max_builds_per_run'])
    queued = pipeline.posts.conn.execute('SELECT COUNT(*) FROM schedules').fetchone()[0]
    capacity = maximum if immediate else max(0, maximum - queued)
    occupied = {r[0] for r in pipeline.posts.conn.execute('SELECT scheduled_at FROM schedules')}
    used_roles = {(r[0], r[1]) for r in pipeline.posts.conn.execute(
        "SELECT lower(o.company), lower(o.title) FROM opportunities o JOIN posts p ON o.id=p.opportunity_id "
        "WHERE p.status IN ('ready','uploading','posted')")}
    attempts = 0
    candidates = pipeline.db.list(status=None, limit=10000, today=now.date())
    candidates.sort(key=lambda row: priority_key(row, now.date(), int(priority.get('urgent_deadline_days', 3))))
    for row in candidates:
        if attempts >= capacity:
            break
        if row['status'] not in ('new', 'approved'):
            continue
        if priority.get('skip_unpaid', True) and compensation(row['stipend_text'])[0] == 0:
            continue
        retry = pipeline.posts.conn.execute('SELECT retry_after FROM upload_retries WHERE opportunity_id=?', (row['id'],)).fetchone()
        if retry and datetime.fromisoformat(retry['retry_after']) > now:
            continue
        post = pipeline.posts.get(row['id'])
        if post and post.status == 'failed':
            if datetime.fromisoformat(post.updated_at) > now - timedelta(hours=1):
                continue
        if post and post.status in ('uploading', 'posted'):
            continue
        if not immediate and pipeline.posts.conn.execute('SELECT 1 FROM schedules WHERE opportunity_id=?', (row['id'],)).fetchone():
            continue
        role_key = (row['company'].lower(), row['title'].lower())
        if role_key in used_roles and not (post and post.status == 'ready'):
            continue
        slots = [now] if immediate else []
        for days in range(8):
            if immediate:
                break
            for slot in pipeline.settings['upload']['ist_slots']:
                hour, minute = map(int, slot.split(':'))
                candidate = (now + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
                if candidate > now and candidate.isoformat() not in occupied:
                    if not row['deadline'] or candidate.date().isoformat() <= row['deadline']:
                        slots.append(candidate)
        if not slots:
            continue
        attempts += 1
        try:
            pipeline.build(row['id'])
            timestamp = min(slots)
            if immediate:
                pipeline.posts.conn.execute(
                    'INSERT INTO schedules VALUES (?, ?) ON CONFLICT(opportunity_id) DO UPDATE SET scheduled_at=excluded.scheduled_at',
                    (row['id'], timestamp.isoformat()))
                pipeline.posts.conn.commit()
            else:
                schedule(pipeline, row['id'], timestamp.isoformat())
            occupied.add(timestamp.isoformat())
            used_roles.add(role_key)
            result['generated'].append(row['id'])
            if immediate and (upload or manual_export):
                try:
                    value = pipeline.upload(row['id'], manual_export=manual_export)
                    result['uploaded'].append(str(value))
                    pipeline.posts.conn.execute('DELETE FROM schedules WHERE opportunity_id=?', (row['id'],))
                    pipeline.posts.conn.commit()
                except Exception as exc:
                    result['errors'].append(f"{row['id']}: {exc}")
        except Exception as exc:
            from .models import PostRecord
            previous = pipeline.posts.get(row['id'])
            pipeline.posts.upsert(PostRecord(row['id'], previous.script_json if previous else '{}',
                status='failed', error_message=str(exc)))
            result['errors'].append(f"{row['id']}: {exc}")
    return result


def run_daemon(config_dir=None, upload=True):
    """Single local worker with configurable collection and immediate publishing."""
    import json
    import logging
    import time
    import os
    from logging.handlers import RotatingFileHandler
    from .production import atomic_json, backup_database, sync_statistics
    from pathlib import Path
    from .settings import load_shorts_settings
    from collector.config import load_settings
    # OS advisory lock is released on process death (no stale lockfile deadlock).
    lock_path = Path(load_settings(config_dir)['db_path']).with_suffix('.worker.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as lock:
        lock.seek(0)
        lock.write(b'0')
        lock.flush()
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        settings = load_shorts_settings(config_dir)
        if not settings['automation']['enabled']:
            raise ValueError('Enable automation in shorts.yaml before starting the daemon')
        log = logging.getLogger('shorts.worker')
        log_path = lock_path.with_suffix('.log')
        handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=3, encoding='utf-8')
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.info('Worker started: automatic mode, model=%s, public upload requested=%s',
                 settings['llm']['model'], upload)
        next_collection = 0
        next_maintenance = 0
        health_path = lock_path.parent / 'worker-health.json'
        while True:
            collect = time.monotonic() >= next_collection
            atomic_json(health_path, {'state': 'working', 'cycle_started_at': datetime.now(timezone.utc).isoformat(), 'collecting': collect})
            try:
                if time.monotonic() >= next_maintenance:
                    backup_database(load_settings(config_dir)['db_path'])
                    metrics_pipeline = Pipeline(config_dir)
                    try:
                        if upload:
                            report = sync_statistics(metrics_pipeline)
                            atomic_json(lock_path.parent / 'performance.json', report)
                    except Exception as exc:
                        log.warning('Metrics sync unavailable: %s', exc)
                    finally:
                        metrics_pipeline.close()
                    next_maintenance = time.monotonic() + 6*60*60
                if collect:
                    # Publish pending videos before a potentially slow source refresh.
                    pending = run_daily(config_dir, collect=False, upload=upload)
                    log.info(json.dumps(pending))
                result = run_daily(config_dir, collect=collect, upload=upload)
                log.info(json.dumps(result))
                atomic_json(health_path, {'state': 'idle', 'last_completed_at': datetime.now(timezone.utc).isoformat(),
                                         'generated': len(result['generated']), 'uploaded': len(result['uploaded']), 'errors': result['errors']})
                import sys
                if sys.stdout is not None:
                    print(json.dumps(result), flush=True)
            except Exception:
                log.exception('Worker cycle failed; retrying next minute')
                atomic_json(health_path, {'state': 'error', 'last_completed_at': datetime.now(timezone.utc).isoformat(),
                                         'message': 'Worker cycle failed; see rotating worker log.'})
            if collect:
                next_collection = time.monotonic() + max(1, int(settings['automation'].get('collection_interval_minutes', 15))) * 60
            time.sleep(60)
