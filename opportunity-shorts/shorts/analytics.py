"""Owner Analytics uses a separate token and never changes upload authorization."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,math,os

SCOPES=['https://www.googleapis.com/auth/yt-analytics.readonly','https://www.googleapis.com/auth/youtube.readonly']
METRICS={'views':'views','engagedViews':'engaged_views','averageViewDuration':'average_view_duration_seconds','averageViewPercentage':'average_percentage_viewed','likes':'likes','comments':'comments','shares':'shares','subscribersGained':'subscribers_gained'}


def services(settings,interactive=False):
 from google.oauth2.credentials import Credentials
 from google.auth.transport.requests import Request
 from google.auth.exceptions import RefreshError
 from google_auth_oauthlib.flow import InstalledAppFlow
 from googleapiclient.discovery import build
 from google_auth_httplib2 import AuthorizedHttp
 import httplib2
 from collector.config import ROOT
 path=Path(os.getenv('YOUTUBE_ANALYTICS_TOKEN_FILE',str(ROOT/'secrets/youtube_analytics_token.json')))
 credentials=Credentials.from_authorized_user_file(str(path)) if path.exists() else None
 if credentials and not credentials.has_scopes(SCOPES):credentials=None
 if credentials and credentials.expired and credentials.refresh_token:
  try:credentials.refresh(Request())
  except RefreshError:raise ValueError('Analytics authorization revoked; run python -m shorts.analytics auth') from None
 if not credentials or not credentials.valid:
  if not interactive:raise ValueError('Analytics consent required: python -m shorts.analytics auth; upload authorization is unchanged')
  credentials=InstalledAppFlow.from_client_secrets_file(settings['youtube_client_secrets_file'],SCOPES).run_local_server(port=0,timeout_seconds=300,prompt='consent',authorization_prompt_message='')
 http=AuthorizedHttp(credentials,http=httplib2.Http(timeout=30))
 data=build('youtube','v3',http=http,cache_discovery=False)
 channels=data.channels().list(part='id',mine=True).execute().get('items',[])
 expected=settings['upload'].get('expected_channel_id')
 if not expected or not any(c['id']==expected for c in channels):raise ValueError('Analytics account is not the configured Unemployer channel')
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(credentials.to_json(),encoding='utf-8')
 return build('youtubeAnalytics','v2',http=http,cache_discovery=False)


def collect(pipeline,service=None):
 from .growth.store import now
 live=service is None
 service=service or services(pipeline.settings)
 conn=pipeline.posts.conn
 end=(datetime.now(timezone.utc).date()-timedelta(days=3)).isoformat()
 start=(datetime.now(timezone.utc).date()-timedelta(days=30)).isoformat()
 known={r[0] for r in conn.execute('SELECT youtube_id FROM posts WHERE youtube_id IS NOT NULL')}
 known.update(r[0] for r in conn.execute("SELECT external_id FROM content_deliveries WHERE platform='youtube' AND external_id IS NOT NULL"))
 pending=[];unavailable=[];captured=now()
 # Separate metric requests prevent one unavailable metric from losing the others.
 for remote,local in METRICS.items():
  batch_size=1 if remote=='averageViewPercentage' else 200
  for batch_offset in range(0,len(known),batch_size):
   batch=sorted(known)[batch_offset:batch_offset+batch_size]
   offset=1
   try:
    for page in range(20):
     data=service.reports().query(ids='channel==MINE',startDate=start,endDate=end,dimensions='video',metrics=remote,maxResults=200,startIndex=offset,filters='video=='+','.join(batch)).execute()
     headers=[c['name'] for c in data.get('columnHeaders',[])]
     if 'video' not in headers or remote not in headers:break
     rows=data.get('rows',[])
     for values in rows:
      id=values[headers.index('video')];value=values[headers.index(remote)]
      if id not in known or value is None:continue
      number=float(value)
      if not math.isfinite(number) or number<0:continue
      pending.append((id,captured,'youtube_analytics:'+remote,json.dumps({local:number}),start,end))
     if len(rows)<200:break
     offset+=200
    else:unavailable.append(remote+':pagination_limit')
   except Exception as exc:
    status=getattr(getattr(exc,'resp',None),'status',None)
    if status in (401,403):
     try:reasons=[r.get('reason') for r in json.loads(exc.content).get('error',{}).get('errors',[])]
     except Exception:reasons=[]
     if 'accessNotConfigured' in reasons:raise ValueError('Enable the YouTube Analytics API in Google Cloud; consent is already separate from uploads') from None
     raise ValueError('Owner Analytics permission unavailable or revoked; uploads remain independent') from None
    unavailable.append(remote+':unavailable')
 conn.executemany('INSERT OR IGNORE INTO metric_observations VALUES (?,?,?,?,?,?)',pending);conn.commit()
 try:
  if not live:raise ValueError('Mocked Analytics collection skips live channel lookup')
  from .upload import youtube_service
  channel_id=pipeline.settings['upload']['expected_channel_id']
  channels=youtube_service(pipeline.settings).channels().list(part='statistics',id=channel_id).execute().get('items',[])
  if channels:
   stats=channels[0].get('statistics',{});counts={key:int(stats[field]) if field in stats else None for key,field in [('views','viewCount'),('subscribers','subscriberCount'),('video_count','videoCount')]}
   conn.execute('INSERT OR IGNORE INTO channel_observations VALUES (?,?,?,?)',(captured,channel_id,json.dumps(counts),'youtube_data_api'));conn.commit()
 except Exception:pass
 return {'state':'collected' if pending else 'no_available_rows','observations':len(pending),'retrieved_metrics':sorted({next(iter(json.loads(r[3]))) for r in pending}),'unavailable':unavailable,'period_start':start,'period_end_requested':end,'reporting_delay_days':3,'scope':'per-video watch-page subscriber attribution; not total channel subscribers'}


def breakdowns(pipeline,service=None):
 service=service or services(pipeline.settings);conn=pipeline.posts.conn
 start=(datetime.now(timezone.utc).date()-timedelta(days=30)).isoformat();end=(datetime.now(timezone.utc).date()-timedelta(days=3)).isoformat()
 ids=[r[0] for r in conn.execute("SELECT youtube_id FROM posts WHERE status='posted' AND youtube_id IS NOT NULL AND julianday(posted_at)<=julianday(?) ORDER BY posted_at DESC LIMIT 5",(end+'T23:59:59Z',))]
 from .growth.store import now
 observed=[];unavailable=[]
 for id in ids:
  for kind,dimension,metric in [('traffic_sources','insightTrafficSourceType','views'),('retention','elapsedVideoTimeRatio','audienceWatchRatio')]:
   try:
    value=service.reports().query(ids='channel==MINE',startDate=start,endDate=end,dimensions=dimension,metrics=metric,filters='video=='+id,maxResults=200).execute()
    if value.get('rows'):
     conn.execute('INSERT OR IGNORE INTO analytics_breakdowns VALUES (?,?,?,?,?,?)',(id,now(),kind,start,end,json.dumps({'columns':value.get('columnHeaders',[]),'rows':value['rows']})));observed.append(kind)
    else:unavailable.append(kind)
   except Exception:unavailable.append(kind)
 conn.commit();return {'observed_breakdowns':sorted(set(observed)),'unavailable_or_empty':sorted(set(unavailable)),'video_sample_limit':5}


def main():
 import argparse
 from .pipeline import Pipeline
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['auth','sync']);args=parser.parse_args();p=Pipeline()
 try:
  if args.command=='auth':services(p.settings,True);print('Owner Analytics authorized; upload token unchanged')
  else:print(json.dumps(collect(p),indent=2))
 except Exception as exc:print(str(exc) if isinstance(exc,ValueError) else 'Analytics unavailable; publishing is unaffected');return 1
 finally:p.close()
 return 0

if __name__=='__main__':raise SystemExit(main())
