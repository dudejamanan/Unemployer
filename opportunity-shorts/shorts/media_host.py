"""Private upload / public read / confirmed-publication cleanup for LinkedIn cards."""
import hashlib
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime,timezone,timedelta
import requests

SCHEMA='''CREATE TABLE IF NOT EXISTS linkedin_media(
 opportunity_id TEXT NOT NULL,author TEXT NOT NULL,url TEXT NOT NULL,local_path TEXT NOT NULL,
 state TEXT NOT NULL,created_at TEXT NOT NULL,deleted_at TEXT,error TEXT,retry_after TEXT,
 PRIMARY KEY(opportunity_id,author));'''
log=logging.getLogger(__name__)


def mark_text_only(conn,row,cfg):
    conn.execute('CREATE TABLE IF NOT EXISTS linkedin_media_fallback(opportunity_id TEXT,author TEXT,reason TEXT,PRIMARY KEY(opportunity_id,author))')
    conn.execute('INSERT OR REPLACE INTO linkedin_media_fallback VALUES (?,?,?)',(row['id'],cfg['author'],'Image unavailable after retries; publish text only'))
    conn.commit()


def prepare_optional(conn,row,cfg):
    conn.execute('CREATE TABLE IF NOT EXISTS linkedin_media_fallback(opportunity_id TEXT,author TEXT,reason TEXT,PRIMARY KEY(opportunity_id,author))')
    conn.commit()
    if conn.execute('SELECT 1 FROM linkedin_media_fallback WHERE opportunity_id=? AND author=?',(row['id'],cfg['author'])).fetchone():return None
    for attempt in range(3):
        try:return prepare(conn,row,cfg)
        except Exception:
            log.warning('LinkedIn card preparation failed (%s/3); image remains optional',attempt+1)
    mark_text_only(conn,row,cfg)
    return None


def cleanup_optional(conn,cfg):
    try:cleanup(conn,cfg)
    except Exception:log.warning('LinkedIn image cleanup unavailable; publication remains independent')


def settings():
    base=os.getenv('MEDIA_HOST_URL','').rstrip('/')
    token=os.getenv('MEDIA_WRITE_KEY','')
    u=urlsplit(base)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.path not in ('','/') or u.query or u.fragment:
        raise ValueError('MEDIA_HOST_URL must be an HTTPS origin')
    if not token:raise ValueError('MEDIA_WRITE_KEY is missing')
    return base,{'Authorization':'Bearer '+token}


def prepare(conn,row,cfg,http=requests):
    if not cfg.get('image_cards',False) or not dict(row).get('title'):return None
    conn.executescript(SCHEMA)
    old=conn.execute('SELECT * FROM linkedin_media WHERE opportunity_id=? AND author=?',(row['id'],cfg['author'])).fetchone()
    base,headers=settings()
    if old and old['state']=='hosted':
        if not old['url'].startswith(base+'/media/'):raise ValueError('Unexpected media origin')
        check=http.head(old['url'],timeout=(10,20),allow_redirects=False)
        if check.status_code==200:return old['url']
        if check.status_code!=404:raise ValueError('Cannot verify hosted card availability')
    from .linkedin_card import render_card
    from collector.config import ROOT
    path=ROOT/'out'/'linkedin'/row['id']/'card.png'
    render_card(row,path)
    data=path.read_bytes();digest=hashlib.sha256(data).hexdigest();url=base+'/media/'+digest+'.png'
    # Save first: an upload timeout must retain its stable URL for recovery, not leak an orphan.
    conn.execute('INSERT INTO linkedin_media VALUES (?,?,?,?,?,?,NULL,NULL,NULL) ON CONFLICT(opportunity_id,author) DO UPDATE SET url=excluded.url,local_path=excluded.local_path,state=excluded.state,error=NULL',
                 (row['id'],cfg['author'],url,str(path),'uploading',datetime.now(timezone.utc).isoformat()));conn.commit()
    try:
        response=http.put(url,data=data,headers={**headers,'Content-Type':'image/png'},timeout=(10,30),allow_redirects=False)
        if response.status_code not in (200,201):raise ValueError('Media upload failed (HTTP '+str(response.status_code)+')')
        conn.execute("UPDATE linkedin_media SET state='hosted',error=NULL WHERE opportunity_id=? AND author=?",(row['id'],cfg['author']));conn.commit()
    except Exception:
        conn.execute("UPDATE linkedin_media SET error='Upload failed; retained for retry' WHERE opportunity_id=? AND author=?",(row['id'],cfg['author']));conn.commit();raise
    return url


def cleanup(conn,cfg,http=requests):
    conn.executescript(SCHEMA)
    base,headers=settings()
    rows=conn.execute("SELECT m.* FROM linkedin_media m JOIN linkedin_posts p ON p.opportunity_id=m.opportunity_id AND p.author=m.author WHERE m.author=? AND m.state!='deleted' AND p.status='posted' AND (m.retry_after IS NULL OR m.retry_after<=?)",(cfg['author'],datetime.now(timezone.utc).isoformat())).fetchall()
    for row in rows:
        # A public card can be shared by deliveries; do not break a still-pending one.
        if conn.execute("SELECT 1 FROM linkedin_media m JOIN linkedin_posts p ON p.opportunity_id=m.opportunity_id AND p.author=m.author WHERE m.url=? AND m.state!='deleted' AND p.status!='posted' LIMIT 1",(row['url'],)).fetchone():continue
        try:
            if not row['url'].startswith(base+'/media/'):raise ValueError('Unexpected media origin')
            response=http.delete(row['url'],headers=headers,timeout=(10,20),allow_redirects=False)
            if response.status_code not in (200,204,404):raise ValueError('Media delete failed')
            conn.execute("UPDATE linkedin_media SET state='deleted',deleted_at=?,error=NULL,retry_after=NULL WHERE opportunity_id=? AND author=?",(datetime.now(timezone.utc).isoformat(),row['opportunity_id'],row['author']))
        except Exception:
            conn.execute("UPDATE linkedin_media SET error='Cleanup pending; will retry',retry_after=? WHERE opportunity_id=? AND author=?",((datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(),row['opportunity_id'],row['author']))
        conn.commit()
