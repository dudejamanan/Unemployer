"""Private revenue evidence and outreach preparation; never sends messages."""
import json,math
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit
from .store import now,identifier

KINDS={'researched','prepared','contacted','reply','meeting','offer','declined','follow_up'}


def activity(conn,contact,kind,provenance,offer=None,value=None,currency='INR'):
 if kind not in KINDS or not conn.execute('SELECT 1 FROM outreach_contacts WHERE id=?',(contact,)).fetchone():raise ValueError('Known contact and activity kind required')
 if not provenance.strip():raise ValueError('Actual activity needs a private provenance reference')
 if value is not None and (not math.isfinite(value) or value<0):raise ValueError('Invalid proposed amount')
 id=identifier(contact+'|'+kind+'|'+provenance)
 conn.execute('INSERT OR IGNORE INTO outreach_activity VALUES (?,?,?,?,?,?,?,?)',(id,contact,kind,now(),offer,value,currency,provenance))
 if kind=='contacted':conn.execute("UPDATE outreach_contacts SET outreach_date=?,message_status='contacted',follow_up_date=? WHERE id=?",(now()[:10],(datetime.now(timezone.utc)+timedelta(days=7)).date().isoformat(),contact))
 elif kind in ('reply','meeting','declined'):conn.execute('UPDATE outreach_contacts SET message_status=? WHERE id=?',(kind,contact))
 conn.commit();return id


def revenue(conn,contact,amount,currency,paid_at,evidence):
 if not conn.execute('SELECT 1 FROM outreach_contacts WHERE id=?',(contact,)).fetchone():raise ValueError('Known contact required')
 if not math.isfinite(amount) or amount<=0 or currency not in ('INR','USD','EUR','GBP'):raise ValueError('Positive confirmed revenue and supported currency required')
 paid=datetime.fromisoformat(paid_at)
 if paid.tzinfo is None or paid>datetime.now(timezone.utc) or not evidence.strip():raise ValueError('Actual payment date and evidence reference required')
 id=identifier(contact+'|'+evidence)
 conn.execute('INSERT OR IGNORE INTO revenue_records VALUES (?,?,?,?,?,?)',(id,contact,amount,currency,paid_at,evidence));conn.commit();return id


def prepare(conn,limit=15):
 # Registered employers are prospects, not invented interested buyers.
 for row in conn.execute("SELECT company,apply_url FROM opportunities WHERE is_open=1 AND source IN ('greenhouse','lever','ashby') GROUP BY company ORDER BY company LIMIT ?",(max(0,min(50,int(limit))),)):
  u=urlsplit(row['apply_url'])
  if u.scheme!='https' or not u.hostname:continue
  id=identifier(row['company']+'|employer')
  conn.execute('INSERT OR IGNORE INTO outreach_contacts(id,organization,category,public_source_url) VALUES (?,?,?,?)',(id,row['company'],'employer',row['apply_url']))
 conn.commit();return {'prospects':conn.execute('SELECT COUNT(*) FROM outreach_contacts').fetchone()[0],'sent':0,'limit':'preparation only; no outreach API is connected'}


def summary(conn):
 totals={r['currency']:r['total'] for r in conn.execute('SELECT currency,SUM(amount) AS total FROM revenue_records GROUP BY currency')}
 due=[dict(r) for r in conn.execute("SELECT id,organization,follow_up_date FROM outreach_contacts WHERE follow_up_date<=? AND message_status!='declined'",(now()[:10],))]
 sponsored=[]
 from ..trust import is_promoted
 for row in conn.execute("SELECT o.*,p.youtube_id,p.posted_at FROM opportunities o JOIN posts p ON p.opportunity_id=o.id WHERE p.status='posted'"):
  if not is_promoted(dict(row)):continue
  metric=conn.execute('SELECT views,captured_at FROM video_metrics WHERE youtube_id=?',(row['youtube_id'],)).fetchone() if conn.execute("SELECT 1 FROM sqlite_master WHERE name='video_metrics'").fetchone() else None
  sponsored.append({'company':row['company'],'video_id':row['youtube_id'],'published_at':row['posted_at'],'public_lifetime_views':metric['views'] if metric else None,'measured_at':metric['captured_at'] if metric else None,'applications_confirmed':None})
 return {'sponsored_distribution':sponsored,'confirmed_revenue_by_currency':totals,'revenue_records':conn.execute('SELECT COUNT(*) FROM revenue_records').fetchone()[0],'prospects':conn.execute('SELECT COUNT(*) FROM outreach_contacts').fetchone()[0],'followups_due':due,'sent_outreach_automatically':0,'notes':'No inferred revenue; empty totals mean no recorded payment evidence, not audited zero business revenue.'}


def main():
 import argparse
 from ..pipeline import Pipeline
 parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
 sub.add_parser('status');sub.add_parser('prepare')
 a=sub.add_parser('activity');a.add_argument('contact');a.add_argument('--kind',choices=sorted(KINDS),required=True);a.add_argument('--provenance',required=True);a.add_argument('--offer');a.add_argument('--value',type=float);a.add_argument('--currency',default='INR')
 a=sub.add_parser('revenue');a.add_argument('contact');a.add_argument('--amount',type=float,required=True);a.add_argument('--currency',default='INR');a.add_argument('--paid-at',required=True);a.add_argument('--evidence',required=True)
 args=parser.parse_args();p=Pipeline();conn=p.posts.conn
 try:
  if args.command=='status':result=summary(conn)
  elif args.command=='prepare':result=prepare(conn)
  elif args.command=='activity':result={'activity':activity(conn,args.contact,args.kind,args.provenance,args.offer,args.value,args.currency)}
  else:result={'revenue_record':revenue(conn,args.contact,args.amount,args.currency,args.paid_at,args.evidence)}
  print(json.dumps(result,indent=2))
 finally:p.close()
if __name__=='__main__':main()
