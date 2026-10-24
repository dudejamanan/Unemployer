"""One bounded research/build step per refresh, isolated from opportunity state."""
import json
from datetime import datetime,timedelta,timezone
from .store import migrate,now,update_topic,identifier
from .research import config,seed,research_topic
from .content import draft,build,validate_ready
from .model import ask


def maintenance(pipeline,config_dir=None):
    if not pipeline.settings.get('growth',{}).get('enabled'):return {'state':'disabled'}
    conn=pipeline.posts.conn;cfg=config(config_dir);seed(conn,cfg)
    interval=int(pipeline.settings['growth'].get('research_interval_minutes',60))
    last=conn.execute('SELECT MAX(started_at) FROM research_runs').fetchone()[0]
    if last and datetime.now(timezone.utc)-datetime.fromisoformat(last)<timedelta(minutes=interval):return {'state':'spacing'}
    from ..pipeline import IST
    if datetime.now(IST).weekday()==int(pipeline.settings['growth'].get('roundup_weekday',4)):
        roundup=create_roundup(pipeline)
        if roundup:
            item=conn.execute('SELECT * FROM content_items WHERE id=?',(roundup,)).fetchone()
            if item['status']=='drafted':
                run=conn.execute('INSERT INTO research_runs(topic_id,stage,status,started_at) VALUES (?,?,?,?)',(None,'roundup_build','working',now())).lastrowid;conn.commit()
                try:
                    build(conn,roundup,pipeline.settings,cfg)
                    conn.execute("UPDATE research_runs SET status='completed',completed_at=? WHERE id=?",(now(),run));conn.commit()
                    return {'state':'completed','content_id':roundup,'stage':'roundup_build'}
                except Exception as exc:
                    conn.execute("UPDATE content_items SET status='deferred',error=? WHERE id=?",(type(exc).__name__,roundup))
                    conn.execute("UPDATE research_runs SET status='deferred',completed_at=?,error=? WHERE id=?",(now(),type(exc).__name__,run));conn.commit()
                    return {'state':'deferred','content_id':roundup,'stage':'roundup_build'}
    rows=conn.execute("SELECT * FROM career_topics WHERE status IN ('discovered','researching','researched','drafted','deferred') AND (retry_after IS NULL OR retry_after<=?) ORDER BY CASE status WHEN 'drafted' THEN 0 WHEN 'researched' THEN 1 ELSE 2 END,discovered_at",(now(),)).fetchall()
    from .discovery import priority
    row=min(rows,key=lambda r:priority(conn,r)) if rows else None
    if not row:return {'state':'idle'}
    stage='research' if row['status'] in ('discovered','researching','deferred') else 'draft' if row['status']=='researched' else 'build'
    run=conn.execute('INSERT INTO research_runs(topic_id,stage,status,started_at) VALUES (?,?,?,?)',(row['id'],stage,'working',now())).lastrowid;conn.commit()
    try:
        if stage=='research':research_topic(conn,row['id'],pipeline.settings,cfg,ask)
        elif stage=='draft':draft(conn,row['id'],pipeline.settings,cfg,ask)
        else:build(conn,row['content_id'],pipeline.settings,cfg)
        conn.execute("UPDATE research_runs SET status='completed',completed_at=? WHERE id=?",(now(),run));conn.commit()
        return {'state':'completed','topic_id':row['id'],'stage':stage}
    except Exception as exc:
        message=str(exc)[:350] if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__
        update_topic(conn,row['id'],'deferred',error=message,retry_after=(datetime.now(timezone.utc)+timedelta(hours=6)).isoformat())
        conn.execute("UPDATE research_runs SET status='deferred',completed_at=?,error=? WHERE id=?",(now(),message,run));conn.commit()
        return {'state':'deferred','topic_id':row['id'],'stage':stage,'reason':message}


def create_roundup(pipeline):
    from ..pipeline import IST,fact_digest
    from ..priority import priority_key,compensation
    from collector.db import row_to_card
    from ..models import ScriptDoc,OnScreenText,VoiceoverLine
    conn=pipeline.posts.conn;today=datetime.now(IST).date()
    id='roundup-'+today.strftime('%G-W%V')
    existing=conn.execute('SELECT id FROM content_items WHERE id=?',(id,)).fetchone()
    if existing:return existing[0]
    candidates=sorted(pipeline.db.list(status=None,limit=10000,today=today),key=lambda r:priority_key(r,today))
    selected=[];companies=set()
    for row in candidates:
        if row['status']=='rejected' or not row['last_seen_at'] or datetime.fromisoformat(row['last_seen_at'].replace('Z','+00:00'))<datetime.now(timezone.utc)-timedelta(hours=24):continue
        if compensation(row['stipend_text'])[0]!=2 or row['company'].casefold() in companies:continue
        if not row['verified'] and row['source'] not in ('greenhouse','lever','ashby'):continue
        selected.append(row);companies.add(row['company'].casefold())
        if len(selected)==3:break
    if len(selected)<3:return None
    lines=['Compare these paid early-career openings before you apply.']
    for r in selected:lines.append(r['title']+' at '+r['company']+'. Listed compensation: '+r['stipend_text']+'.')
    lines+=['Check eligibility, location and the deadline on each source page.','Copy the application links from the description.']
    if len(' '.join(lines).split())>100:return None
    description='A source-linked weekly shortlist; no selection guarantees.\n'+'\n'.join(r['apply_url'] for r in selected)+'\n#Internships #FresherJobs #Shorts #Unemployer'
    script=ScriptDoc(lines[0],[VoiceoverLine(l) for l in lines],OnScreenText('Weekly opportunity shortlist','Unemployer','','','','','Check the source links'),'This week’s paid opportunity shortlist',description,['#Internships','#FresherJobs','#Shorts','#Unemployer'])
    hashes={r['id']:fact_digest(row_to_card(r)) for r in selected}
    import hashlib
    evidence={'facts':hashes,'script_hash':hashlib.sha256(json.dumps(script.to_dict(),sort_keys=True).encode()).hexdigest()}
    conn.execute('INSERT INTO content_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(id,'weekly_roundup','opportunities',script.title,None,json.dumps(list(hashes)),'drafted',json.dumps(script.to_dict()),None,now(),None,json.dumps(evidence),None));conn.commit()
    return id
