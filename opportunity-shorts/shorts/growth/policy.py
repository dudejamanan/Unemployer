"""Persistent cross-format cadence and independent format eligibility."""
from datetime import datetime,timedelta,timezone
import re


def published(conn,id,platform,format,category='',company='',role='',hook='',external_id=None):
    from .store import now
    conn.execute('INSERT OR IGNORE INTO content_publications VALUES (?,?,?,?,?,?,?,?,?)',
        (id,platform,format,category,company,role,hook,now(),external_id));conn.commit()


def latest_time(conn,platform):
    times=[r[0] for r in conn.execute('SELECT published_at FROM content_publications WHERE platform=?',(platform,))]
    if platform=='youtube':times += [r[0] for r in conn.execute("SELECT posted_at FROM posts WHERE status='posted' AND posted_at IS NOT NULL")]
    return max((datetime.fromisoformat(t.replace('Z','+00:00')) for t in times),default=None)


def interval(settings,platform):
    return int(settings['automation'].get('min_upload_interval_minutes',0)) if platform=='youtube' else int(settings['linkedin'].get('min_post_interval_minutes',0))


def due(conn,settings,platform,now=None):
    from ..pipeline import IST
    now=now or datetime.now(timezone.utc)
    if platform=='linkedin' and settings.get('growth',{}).get('linkedin_weekdays_only',False) and now.astimezone(IST).weekday()>4:return False
    last=latest_time(conn,platform)
    return not last or now>=last+timedelta(minutes=interval(settings,platform))


def diverse(conn,row,platform,settings,now=None):
    now=now or datetime.now(timezone.utc)
    cfg=settings.get('growth',{}).get('diversity',{})
    for field,key,hours in [('company','company',cfg.get('company_hours',0)),('role','title',cfg.get('role_hours',0))]:
        if hours and conn.execute('SELECT 1 FROM content_publications WHERE platform=? AND lower('+field+')=lower(?) AND published_at>=? LIMIT 1',
            (platform,row[key],(now-timedelta(hours=hours)).isoformat())).fetchone():return False
    return True


def content_due(conn,item,platform,settings,now=None):
    from ..pipeline import IST
    now=now or datetime.now(timezone.utc);cfg=settings.get('growth',{})
    if item['format']=='weekly_roundup':
        if now.astimezone(IST).weekday()!=int(cfg.get('roundup_weekday',4)):return False
        days=7
    else:days=int(cfg.get('guide_every_days',2))
    row=conn.execute('SELECT MAX(published_at) FROM content_publications WHERE platform=? AND format=?',(platform,item['format'])).fetchone()[0]
    return not row or now-datetime.fromisoformat(row.replace('Z','+00:00'))>=timedelta(days=days)
