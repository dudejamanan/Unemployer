"""Operational health, consistent backups, and observable public YouTube metrics."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def backup_database(db_path, retention=7):
    """SQLite's online backup includes committed WAL transactions."""
    source = Path(db_path)
    folder = source.parent / 'backups'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ('unemployer-' + datetime.now(timezone.utc).date().isoformat() + '.db')
    if not target.exists():
        temporary = target.with_suffix('.tmp')
        src, dst = sqlite3.connect(str(source)), sqlite3.connect(str(temporary))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        temporary.replace(target)
    for old in sorted(folder.glob('unemployer-*.db'), reverse=True)[retention:]:
        old.unlink()
    return str(target)


def sync_statistics(pipeline, service=None):
    from .growth.store import migrate
    migrate(pipeline.posts.conn)
    from .upload import youtube_service
    service = service or youtube_service(pipeline.settings)
    pipeline.posts.conn.execute('''CREATE TABLE IF NOT EXISTS video_metrics (
        youtube_id TEXT PRIMARY KEY, captured_at TEXT, views INTEGER, likes INTEGER,
        comments INTEGER, privacy TEXT, upload_status TEXT)''')
    ids = [r[0] for r in pipeline.posts.conn.execute("SELECT youtube_id FROM posts WHERE youtube_id IS NOT NULL")]
    ids += [r[0] for r in pipeline.posts.conn.execute("SELECT external_id FROM content_deliveries WHERE platform='youtube' AND external_id IS NOT NULL")]
    ids = list(dict.fromkeys(ids))
    now = datetime.now(timezone.utc).isoformat()
    for offset in range(0, len(ids), 50):
        data = service.videos().list(part='statistics,status', id=','.join(ids[offset:offset+50])).execute()
        for video in data.get('items', []):
            stats, status = video.get('statistics', {}), video.get('status', {})
            pipeline.posts.conn.execute('INSERT OR REPLACE INTO video_metrics VALUES (?, ?, ?, ?, ?, ?, ?)',
                (video['id'], now, int(stats['viewCount']) if 'viewCount' in stats else None, int(stats['likeCount']) if 'likeCount' in stats else None,
                 int(stats['commentCount']) if 'commentCount' in stats else None, status.get('privacyStatus'), status.get('uploadStatus')))
            values={key:int(stats[field]) if field in stats else None for key,field in [('views','viewCount'),('likes','likeCount'),('comments','commentCount')]}
            pipeline.posts.conn.execute('INSERT OR IGNORE INTO metric_observations VALUES (?,?,?,?,?,?)',
                (video['id'],now,'youtube_data_api',json.dumps(values),None,None))
    pipeline.posts.conn.commit()
    return performance_report(pipeline)


def performance_report(pipeline):
    try:
        rows = pipeline.posts.conn.execute('''SELECT m.*, o.company, o.title, p.posted_at FROM video_metrics m
            JOIN posts p ON m.youtube_id=p.youtube_id JOIN opportunities o ON o.id=p.opportunity_id
            ORDER BY m.views DESC''').fetchall()
    except sqlite3.OperationalError:
        rows = []
    return {'captured_at': datetime.now(timezone.utc).isoformat(),
            'videos': [dict(row) for row in rows],
            'limits': 'Public counts only. Retention, swipe-away rate, revenue and causal attribution require additional owner analytics.'}
