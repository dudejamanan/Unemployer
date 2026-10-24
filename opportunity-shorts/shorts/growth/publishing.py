"""Reuse platform transports with a separate durable content outbox."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .store import now
from .research import config
from .content import validate_ready
from .policy import due,content_due,published
from ..models import ScriptDoc,PostRecord


def reconcile_youtube(pipeline,service):
    conn=pipeline.posts.conn
    rows=conn.execute("SELECT d.*,c.script FROM content_deliveries d JOIN content_items c ON c.id=d.content_id WHERE d.platform='youtube' AND d.status IN ('publishing','uncertain')").fetchall()
    if not rows:return
    channels=service.channels().list(part='contentDetails',mine=True).execute().get('items',[])
    ids=[]
    for channel in channels:
        ids += [v['contentDetails']['videoId'] for v in service.playlistItems().list(part='contentDetails',playlistId=channel['contentDetails']['relatedPlaylists']['uploads'],maxResults=50).execute().get('items',[])]
    videos=service.videos().list(part='snippet',id=','.join(ids[:50])).execute().get('items',[]) if ids else []
    for row in rows:
        script=json.loads(row['script'])
        matches=[v for v in videos if v['snippet'].get('title')==script['title'] and v['snippet'].get('description')==script['description']]
        if len(matches)==1:complete(pipeline,row['content_id'],'youtube',matches[0]['id'])


def complete(pipeline,id,platform,external_id):
    conn=pipeline.posts.conn
    item=conn.execute('SELECT * FROM content_items WHERE id=?',(id,)).fetchone()
    conn.execute("INSERT INTO content_deliveries(content_id,platform,status,external_id,published_at) VALUES (?,?,'published',?,?) ON CONFLICT(content_id,platform) DO UPDATE SET status='published',external_id=excluded.external_id,published_at=excluded.published_at,error=NULL",(id,platform,external_id,now()))
    conn.execute("UPDATE content_items SET status='published' WHERE id=?",(id,))
    if item['topic_id']:conn.execute("UPDATE career_topics SET status='published',updated_at=? WHERE id=?",(now(),item['topic_id']))
    conn.commit()
    published(conn,id,platform,item['format'],item['category'],hook=json.loads(item['script'])['hook'],external_id=external_id)


def try_publish(pipeline,platform,service=None,content_id=None):
    cfg=pipeline.settings.get('growth',{})
    if not cfg.get('enabled'):return {'handled':False}
    conn=pipeline.posts.conn
    if platform=='linkedin':
        from ..linkedin import configuration,SCHEMA
        conn.executescript(SCHEMA)
        channel=configuration(pipeline.settings);author=channel['author']
        if not channel.get('enabled'):return {'handled':True,'state':'disabled'}
        if channel.get('provider')!='buffer':return {'handled':True,'state':'unsupported_growth_provider'}
        if content_id:
            from ..linkedin import headers,reconcile
            from ..buffer_api import check
            headers(channel);check(channel);reconcile(conn,channel)
        if conn.execute("SELECT 1 FROM linkedin_posts WHERE author=? AND status='blocked' LIMIT 1",(author,)).fetchone():return {'handled':True,'state':'blocked'}
        for row in conn.execute("SELECT d.content_id,l.post_urn FROM content_deliveries d JOIN linkedin_posts l ON l.opportunity_id=d.content_id WHERE d.platform='linkedin' AND d.status!='published' AND l.author=? AND l.status='posted'",(author,)).fetchall():
            complete(pipeline,row['content_id'],platform,row['post_urn'])
        since=(datetime.now(timezone.utc)-timedelta(hours=24)).isoformat()
        count=conn.execute('SELECT COUNT(*) FROM linkedin_attempts WHERE author=? AND attempted_at>=?',(author,since)).fetchone()[0]
        if count>=int(channel.get('daily_limit',10)):return {'handled':True,'state':'posting_limit'}
        last=conn.execute('SELECT MAX(attempted_at) FROM linkedin_attempts WHERE author=?',(author,)).fetchone()[0]
        if last and datetime.now(timezone.utc)<datetime.fromisoformat(last)+timedelta(minutes=int(channel.get('min_post_interval_minutes',1440))):return {'handled':True,'state':'spacing'}
    if not due(conn,pipeline.settings,platform):return {'handled':True,'state':'spacing'}
    if platform=='youtube':
        gate=conn.execute('SELECT retry_after FROM youtube_backoff WHERE channel_id=?',(pipeline.settings['upload'].get('expected_channel_id',''),)).fetchone()
        if gate and datetime.fromisoformat(gate[0])>datetime.now(timezone.utc):return {'handled':True,'state':'platform_cooldown'}
        from ..upload import youtube_service
        service=service or youtube_service(pipeline.settings)
        reconcile_youtube(pipeline,service)
        if not due(conn,pipeline.settings,platform):return {'handled':True,'state':'reconciled'}
    items=conn.execute("SELECT * FROM content_items WHERE status IN ('ready','published') ORDER BY CASE format WHEN 'weekly_roundup' THEN 0 ELSE 1 END,created_at").fetchall()
    for item in items:
        if content_id and item['id']!=content_id:continue
        existing=conn.execute('SELECT * FROM content_deliveries WHERE content_id=? AND platform=?',(item['id'],platform)).fetchone()
        if existing and existing['status'] in ('published','publishing','uncertain','blocked'):continue
        if existing and existing['retry_after'] and datetime.fromisoformat(existing['retry_after'])>datetime.now(timezone.utc):continue
        if not content_due(conn,item,platform,pipeline.settings):continue
        try:validate_ready(conn,item,config())
        except ValueError as exc:
            conn.execute("UPDATE content_items SET status='deferred',error=? WHERE id=?",(str(exc),item['id']));conn.commit();continue
        script=ScriptDoc.from_dict(json.loads(item['script']))
        if platform=='linkedin':
            from ..linkedin import configuration
            from ..buffer_api import publish
            channel=configuration(pipeline.settings)
            text=script.title+'\n\n'+'\n\n'.join(l.text for l in script.voiceover_lines[1:])+'\n\n'+script.description.replace('#Shorts','')
            if len(text)>3000:continue
            state=publish(conn,{'id':item['id'],'content_text':text},channel)
            if state=='posted':complete(pipeline,item['id'],platform,conn.execute('SELECT post_urn FROM linkedin_posts WHERE opportunity_id=? AND author=?',(item['id'],channel['author'])).fetchone()[0])
            else:
                out=conn.execute('SELECT * FROM linkedin_posts WHERE opportunity_id=? AND author=?',(item['id'],channel['author'])).fetchone()
                conn.execute('INSERT OR REPLACE INTO content_deliveries VALUES (?,?,?,?,?,?,?,?)',(item['id'],platform,'uncertain' if state in ('uncertain','publishing','accepted') else 'pending',out['post_urn'],None,out['attempted_at'],out['retry_after'],out['error']));conn.commit()
            return {'handled':True,'state':state,'content_id':item['id']}
        if not item['video_path'] or not Path(item['video_path']).is_file():continue
        conn.execute('BEGIN IMMEDIATE')
        try:
            current=conn.execute('SELECT status FROM content_deliveries WHERE content_id=? AND platform=?',(item['id'],platform)).fetchone()
            if current and current[0] in ('published','publishing','uncertain','blocked'):
                conn.rollback();continue
            from ..pipeline import IST
            day=datetime.now(IST).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).isoformat()
            count=conn.execute('SELECT COUNT(*) FROM upload_attempts WHERE attempted_at>=?',(day,)).fetchone()[0]
            limit=min(int(pipeline.settings['upload']['daily_limit']),int(pipeline.settings['upload'].get('api_daily_upload_limit',100)))
            if count>=limit:conn.rollback();return {'handled':True,'state':'daily_limit'}
            conn.execute("INSERT INTO content_deliveries(content_id,platform,status,attempted_at) VALUES (?,?,'publishing',?) ON CONFLICT(content_id,platform) DO UPDATE SET status='publishing',attempted_at=excluded.attempted_at",(item['id'],platform,now()))
            conn.execute('INSERT INTO upload_attempts VALUES (?,?,?,?)',(item['id'],'unemployer-content',item['title'],now()));conn.commit()
        except Exception:conn.rollback();raise
        from ..upload import upload_video
        try:
            id=upload_video(PostRecord(item['id'],item['script'],video_path=item['video_path']),script,pipeline.settings,service)
            complete(pipeline,item['id'],platform,id)
            return {'handled':True,'state':'published','content_id':item['id'],'external_id':id}
        except Exception as exc:
            from googleapiclient.errors import HttpError
            state='uncertain';retry=None
            if isinstance(exc,HttpError) and 400<=exc.resp.status<500 and exc.resp.status!=408:
                state='pending';retry=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
                if b'quotaExceeded' in exc.content or b'uploadLimitExceeded' in exc.content:
                    conn.execute('INSERT OR REPLACE INTO youtube_backoff VALUES (?,?,?)',(pipeline.settings['upload'].get('expected_channel_id',''),retry,'YouTube limit'))
            conn.execute('UPDATE content_deliveries SET status=?,retry_after=?,error=? WHERE content_id=? AND platform=?',(state,retry,type(exc).__name__,item['id'],platform));conn.commit()
            return {'handled':True,'state':state,'content_id':item['id']}
    return {'handled':False}
