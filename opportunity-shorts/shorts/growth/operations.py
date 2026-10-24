"""Routine growth jobs isolated from both platform publishers."""
import json,logging
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .store import now
from ..production import atomic_json
log=logging.getLogger(__name__)


def run_job(p,name,hours,fn):
 conn=p.posts.conn;conn.execute('BEGIN IMMEDIATE')
 old=conn.execute('SELECT * FROM growth_jobs WHERE name=?',(name,)).fetchone()
 if old and old['next_at'] and old['next_at']>now():
  conn.rollback();return {'state':'spacing'}
 failures=old['failures'] if old else 0
 # Lease survives restart; abandoned work retries, not runs concurrently every minute.
 conn.execute('INSERT OR REPLACE INTO growth_jobs VALUES (?,?,?,?,?,?)',(name,(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(),'working',failures,now(),None));conn.commit()
 try:
  result=fn();next_at=(datetime.now(timezone.utc)+timedelta(hours=hours)).isoformat()
  conn.execute('UPDATE growth_jobs SET status=\'ok\',next_at=?,failures=0,error=NULL WHERE name=?',(next_at,name));conn.commit();return result
 except Exception as exc:
  message=str(exc)[:250] if isinstance(exc,ValueError) else type(exc).__name__
  conn.execute('UPDATE growth_jobs SET status=\'retry\',next_at=?,failures=?,error=? WHERE name=?',((datetime.now(timezone.utc)+timedelta(minutes=min(360,5*2**min(failures,6)))).isoformat(),failures+1,message,name));conn.commit()
  return {'state':'retry','reason':message}


def funnel(p):
 import requests
 from ..media_host import settings
 base,headers=settings();response=requests.get(base+'/api/funnel',headers=headers,timeout=(10,30),allow_redirects=False);response.raise_for_status()
 rows=response.json()['rows']
 for r in rows:
  if r['event'] not in ('page_view','category_search','guide_view','application_click','checklist_download'):continue
  if r['campaign'] not in ('youtube','linkedin','direct') or r['category'] not in ('all','internship','job','research'):continue
  count=r['count']
  if isinstance(count,int) and 0<=count<10**9:p.posts.conn.execute('INSERT OR REPLACE INTO funnel_daily VALUES (?,?,?,?,?)',(r['day'],r['campaign'],r['event'],r['category'],count))
 p.posts.conn.commit();return {'aggregates':len(rows)}


def reports(p):
 from .reporting import report
 from .revenue import summary
 conn=p.posts.conn;performance=report(conn)
 jobs=[dict(r) for r in conn.execute('SELECT * FROM growth_jobs')]
 funnel_rows=[dict(r) for r in conn.execute('SELECT * FROM funnel_daily ORDER BY day DESC LIMIT 2000')]
 channel=conn.execute('SELECT * FROM channel_observations ORDER BY captured_at DESC LIMIT 1').fetchone()
 channel_data={'metrics':json.loads(channel['metrics']),'captured_at':channel['captured_at'],'provenance':channel['provenance']} if channel else None
 result={'generated_at':now(),'performance':performance,'breakdowns':[dict(r) for r in conn.execute('SELECT object_id,captured_at,kind,period_start,period_end,data FROM analytics_breakdowns ORDER BY captured_at DESC LIMIT 20')],'jobs':jobs,'experiments':[dict(r) for r in conn.execute('SELECT e.*,d.target_audience,d.format FROM growth_experiments e JOIN experiment_details d ON d.experiment_id=e.id')],'funnel':{'observed_aggregate_actions':funnel_rows,'returning_visitors':None,'confirmed_applications':None,'per_content_web_attribution':None,'unique_visitors':None,'channel_metrics':channel_data,'notes':['Views in public snapshots are lifetime; owner Analytics/CSV periods are separate.','Consented campaign action counts are not unique people or confirmed applications.','Organic versus sponsored attribution is unavailable unless a publication is explicitly labelled.']},'revenue':summary(conn),'alerts':[{'job':j['name'],'reason':j['error'],'next_retry':j['next_at']} for j in jobs if j['status']=='retry']}
 folder=Path(p.settings['paths']['output_dir'])/'growth'
 for kind,period in [('daily',now()[:10]),('weekly',datetime.now(timezone.utc).strftime('%G-W%V'))]:
  conn.execute('INSERT OR REPLACE INTO growth_reports VALUES (?,?,?,?)',(kind,period,json.dumps(result),now()));atomic_json(folder/(kind+'-report.json'),result)
 conn.commit();return {'daily_and_weekly_reports':True,'alerts':len(result['alerts'])}


def tick(p):
 from ..analytics import collect,breakdowns
 from .discovery import run
 from .research import config
 from .sync import sync
 from .experiments import plan,evaluate
 jobs=[('analytics',6,lambda:collect(p)),('analytics_breakdowns',6,lambda:breakdowns(p)),('discovery',24,lambda:run(p,config())),('guide_sync',0.1,lambda:sync(p)),('funnel',6,lambda:funnel(p)),('experiments',24,lambda:(plan(p.posts.conn),evaluate(p.posts.conn))),('revenue_preparation',24,lambda:revenue_prepare(p)),('reports',1,lambda:reports(p))]
 return {name:run_job(p,name,interval,fn) for name,interval,fn in jobs}


def revenue_prepare(p):
 from .revenue import prepare
 return prepare(p.posts.conn,p.settings.get('growth',{}).get('prospect_preparation_limit',15))


def background(config_dir=None):
 import time
 from ..pipeline import Pipeline
 while True:
  p=None
  try:
   p=Pipeline(config_dir);result=tick(p)
   from collector.config import load_settings
   states=[dict(r) for r in p.posts.conn.execute('SELECT * FROM growth_jobs')]
   atomic_json(Path(load_settings(config_dir)['db_path']).parent/'growth-health.json',{'checked_at':now(),'jobs':result,'persistent_jobs':states,'alerts':[r for r in states if r['status']=='retry']})
  except Exception:log.warning('Growth background cycle unavailable; platform publishing continues')
  finally:
   if p:p.close()
  time.sleep(60)


def main():
 from ..pipeline import Pipeline
 p=Pipeline()
 try:print(json.dumps(tick(p),indent=2))
 finally:p.close()
if __name__=='__main__':main()
