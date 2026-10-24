"""Append-only observations, explicit provenance, and cautious cohort summaries."""
import csv
import json
import re
from datetime import datetime,timezone
from pathlib import Path
from .store import now,identifier

METRICS={'engaged_views','views','likes','comments','shares','subscribers_gained','average_view_duration_seconds',
         'average_percentage_viewed','feed_exposure','stayed_to_watch_percentage','website_visits','application_clicks'}
CSV_HEADERS={'Content':'video_id','Video ID':'video_id','video_id':'video_id','Views':'views','Likes':'likes',
 'Engaged views':'engaged_views','Comments':'comments','Shares':'shares','Subscribers gained':'subscribers_gained',
 'Average view duration':'average_view_duration_seconds','Average percentage viewed (%)':'average_percentage_viewed',
 'Shown in feed':'feed_exposure','Stayed to watch (%)':'stayed_to_watch_percentage'}


def number(value,metric):
    if value is None or str(value).strip() in ('','--','N/A'):return None
    value=str(value).strip().replace(',','').removesuffix('%')
    if metric=='average_view_duration_seconds' and ':' in value:
        parts=value.split(':')
        if not 2<=len(parts)<=3:raise ValueError('Invalid view duration')
        total=0
        for part in parts:total=total*60+float(part)
        if not __import__('math').isfinite(total) or total<0:raise ValueError('Duration must be finite and nonnegative')
        return total
    result=float(value)
    if not __import__('math').isfinite(result) or result<0:raise ValueError('Metrics must be finite and nonnegative')
    return int(result) if metric in ('views','likes','comments','shares','subscribers_gained','feed_exposure','website_visits','application_clicks') else result


def import_csv(conn,path,captured_at,period_start=None,period_end=None):
    timestamp=datetime.fromisoformat(captured_at.replace('Z','+00:00'))
    if timestamp.tzinfo is None:raise ValueError('Measurement capture time needs an explicit timezone')
    if bool(period_start)!=bool(period_end):raise ValueError('CSV reporting periods need both start and end')
    if period_start:
        from datetime import date
        if date.fromisoformat(period_start)>date.fromisoformat(period_end):raise ValueError('Invalid CSV reporting window')
    known={r[0] for r in conn.execute('SELECT youtube_id FROM posts WHERE youtube_id IS NOT NULL')}
    known.update(r[0] for r in conn.execute("SELECT external_id FROM content_deliveries WHERE platform='youtube' AND external_id IS NOT NULL"))
    pending=[]
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not any(CSV_HEADERS.get(h)=='video_id' for h in reader.fieldnames):raise ValueError('CSV needs Content, Video ID, or video_id column')
        for raw in reader:
            row={CSV_HEADERS[k]:v for k,v in raw.items() if k in CSV_HEADERS}
            id=row.pop('video_id','')
            if id in ('','Total'):continue
            if id not in known:raise ValueError('CSV references an unknown published video')
            values={k:number(v,k) for k,v in row.items() if k in METRICS}
            pending.append((id,timestamp.isoformat(),'youtube_studio_csv',json.dumps(values),period_start,period_end))
    conn.executemany('INSERT OR IGNORE INTO metric_observations VALUES (?,?,?,?,?,?)',pending);conn.commit()
    return len(pending)


def report(conn):
    observations=[dict(r) for r in conn.execute('SELECT * FROM metric_observations ORDER BY captured_at')]
    latest={}
    period_observations=[{**r,'metrics':json.loads(r['metrics'])} for r in observations if r['period_start'] or r['period_end']]
    for row in observations:
        if row['period_start'] or row['period_end']:continue
        item=latest.setdefault(row['object_id'],{'video_id':row['object_id'],'metrics':{k:None for k in METRICS},'provenance':{},'measurement_timestamps':{}})
        for key,value in json.loads(row['metrics']).items():
            if key in METRICS and value is not None:
                item['metrics'][key]=value;item['provenance'][key]=row['provenance'];item['measurement_timestamps'][key]=row['captured_at']
    for item in latest.values():
        publication=conn.execute("SELECT * FROM content_publications WHERE external_id=? AND platform='youtube'",(item['video_id'],)).fetchone()
        item['format']=publication['format'] if publication else 'unknown'
        item['category']=publication['category'] if publication else None
        if publication:
            measured=item['measurement_timestamps'].get('views') or max(item['measurement_timestamps'].values(),default=now())
            age=max(0,(datetime.fromisoformat(measured.replace('Z','+00:00'))-datetime.fromisoformat(publication['published_at'].replace('Z','+00:00'))).total_seconds()/3600)
            item['age_hours_at_measurement']=round(age,1)
            item['comparison_band']='0-24h' if age<24 else '24-72h' if age<72 else '3-7d' if age<168 else '7d+'
        else:item['age_hours_at_measurement']=None;item['comparison_band']='unknown'
    import statistics
    groups={}
    for item in latest.values():
        # Public lifetime counters only: do not mix CSV reporting windows into cohorts.
        if item['provenance'].get('views')!='youtube_data_api' or item['comparison_band']=='unknown':continue
        key=(item['format'],item['category'],item['comparison_band'])
        groups.setdefault(key,[]).append(item['metrics']['views'])
    cohorts=[{'format':key[0],'category':key[1],'age_band':key[2],'sample_size':len(values),'median_public_views':statistics.median(values),'interpretation':'descriptive; not a causal test'} for key,values in groups.items()]
    return {'generated_at':now(),'videos':list(latest.values()),'observations':len(observations),'cohorts':cohorts,'period_observations':period_observations,
      'limits':['Missing metrics are null, not zero.','Public observations do not expose retention, feed exposure, shares or subscriber attribution.',
                'CSV metrics retain their supplied measurement date and import provenance.','Compare the same format, category and age band; these are descriptive cohorts, not controlled causal tests.',
                'No statistical significance or growth guarantee is inferred.']}


def experiment(conn,hypothesis,variable,variants,starts_at,ends_at):
    if not hypothesis.strip() or not variable.strip() or len(set(variants))!=2:raise ValueError('Choose one variable and two distinct variants')
    start,end=datetime.fromisoformat(starts_at),datetime.fromisoformat(ends_at)
    if start.tzinfo is None or end.tzinfo is None:raise ValueError('Experiment times require explicit timezones')
    if end<=start:raise ValueError('Experiment observation window must end after it starts')
    id=identifier(hypothesis+'|'+starts_at)
    conn.execute('INSERT OR IGNORE INTO growth_experiments(id,hypothesis,variable,variants,starts_at,ends_at,status) VALUES (?,?,?,?,?,?,?)',
        (id,hypothesis,variable,json.dumps(variants),starts_at,ends_at,'planned'));conn.commit()
    return id
