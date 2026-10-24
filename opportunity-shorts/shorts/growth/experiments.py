"""Single-variable experiments and bounded, descriptive performance feedback."""
import json
from datetime import datetime,timedelta,timezone
from .store import now,identifier
from .reporting import report,experiment


def plan(conn):
 existing=conn.execute("SELECT id FROM growth_experiments WHERE status IN ('planned','running') AND ends_at>? LIMIT 1",(now(),)).fetchone()
 if existing:return existing[0]
 start=now();end=(datetime.now(timezone.utc)+timedelta(days=21)).isoformat()
 id=experiment(conn,'A question hook changes engagement for source-backed application guides','hook',['direct','question'],start,end)
 conn.execute("UPDATE growth_experiments SET status='running' WHERE id=?",(id,))
 conn.execute('INSERT OR IGNORE INTO experiment_details VALUES (?,?,?,NULL)',(id,'Indian early-career applicants','career_guide'));conn.commit();return id


def hook(conn,topic,content_id):
 row=conn.execute("SELECT e.* FROM growth_experiments e JOIN experiment_details d ON d.experiment_id=e.id WHERE e.variable='hook' AND e.status='running' AND d.format='career_guide' AND e.starts_at<=? AND e.ends_at>? ORDER BY e.starts_at LIMIT 1",(now(),now())).fetchone()
 base=topic['title']+'.'
 if not row:return base
 saved=conn.execute('SELECT * FROM experiment_assignments WHERE content_id=?',(content_id,)).fetchone()
 variants=json.loads(row['variants']);variant=saved['variant'] if saved else variants[int(identifier(content_id),16)%2]
 if not saved and row['results']:
  recommendations=json.loads(row['results']).get('bounded_exploration',[])
  preferred=next((r['variant'] for r in recommendations if r['category']==topic['category']),None)
  if preferred in variants:
   # 60/40 exploration is a bounded allocation change, not a declared winner.
   variant=preferred if int(identifier(content_id),16)%10<6 else next(v for v in variants if v!=preferred)
 conn.execute('INSERT OR IGNORE INTO experiment_assignments VALUES (?,?,?,?)',(content_id,row['id'],variant,now()));conn.commit()
 question={'applications':'What can make your application evidence more useful?','interviews':'How can you prepare useful interview examples?','outreach':'How can you prepare a useful career conversation?'}
 return question.get(topic['category'],'What should you check for your next career step?') if variant=='question' else base


def evaluate(conn):
 data=report(conn)
 for exp in conn.execute("SELECT e.*,d.format FROM growth_experiments e JOIN experiment_details d ON d.experiment_id=e.id WHERE e.status IN ('running','planned')"):
  assignments={r['content_id']:r['variant'] for r in conn.execute('SELECT * FROM experiment_assignments WHERE experiment_id=?',(exp['id'],))}
  cells={}
  for video in data['videos']:
   pub=conn.execute("SELECT content_id FROM content_publications WHERE external_id=? AND platform='youtube'",(video['video_id'],)).fetchone()
   if not pub or pub[0] not in assignments or video['format']!=exp['format']:continue
   key=assignments[pub[0]]+'|'+str(video['category'])+'|'+video['comparison_band']
   value=video['metrics']['views']
   if value is not None:cells.setdefault(key,[]).append(value)
  import statistics
  summary=[{'cohort':k,'sample_size':len(v),'median_views':statistics.median(v)} for k,v in cells.items()]
  recommendations=[]
  variants=json.loads(exp['variants'])
  for cell in summary:
   parts=cell['cohort'].split('|');other=next((r for r in summary if r['cohort']==next(v for v in variants if v!=parts[0])+'|'+parts[1]+'|'+parts[2]),None)
   if other and parts[2] in ('24-72h','3-7d') and min(cell['sample_size'],other['sample_size'])>=5 and cell['median_views']>max(1,other['median_views'])*1.2:
    recommendations.append({'category':parts[1],'age_band':parts[2],'variant':parts[0],'allocation':'60/40 exploratory only','causal_claim':False})
  result={'bounded_exploration':recommendations,'cohorts':summary,'decision':'insufficient evidence; no automatic winner','minimum_per_variant_same_cohort':5,'causal_claim':False}
  conn.execute('UPDATE experiment_details SET results=? WHERE experiment_id=?',(json.dumps(result),exp['id']))
  conn.execute('UPDATE growth_experiments SET results=?,conclusion=? WHERE id=?',(json.dumps(result),'Descriptive comparison; no significance or causal claim',exp['id']))
  if exp['ends_at']<now():conn.execute("UPDATE growth_experiments SET status='evaluated' WHERE id=?",(exp['id'],))
 conn.commit();return {'experiments_evaluated':True,'selection_feedback':'underrepresented published categories and bounded observed demand; publishing caps unchanged'}
