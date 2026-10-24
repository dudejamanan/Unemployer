"""Validated published-only guide sync using the existing private hosting credential."""
import hashlib,json
from datetime import datetime,timedelta,timezone
import requests
from .store import now
from .export import public_guides
from ..media_host import settings


def sync(pipeline,http=requests):
 conn=pipeline.posts.conn;base,headers=settings();success=0;failed=0
 for guide in public_guides(conn):
  if not guide.get('published_at'):continue
  payload=json.dumps(guide,sort_keys=True);digest=hashlib.sha256(payload.encode()).hexdigest()
  old=conn.execute('SELECT * FROM guide_sync WHERE content_id=?',(guide['id'],)).fetchone()
  if old and old['payload_hash']==digest and old['status']=='synced':continue
  if old and old['next_at'] and old['next_at']>now():continue
  attempts=(old['attempts'] if old else 0)+1
  conn.execute('INSERT INTO guide_sync VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(content_id) DO UPDATE SET payload_hash=excluded.payload_hash,version=excluded.version,status=excluded.status,attempts=excluded.attempts', (guide['id'],digest,guide['updated_at'],'syncing',attempts,None,None,None));conn.commit()
  try:
   response=http.put(base+'/api/guides/'+guide['id'],headers={**headers,'Content-Type':'application/json'},data=payload.encode(),timeout=(10,30),allow_redirects=False)
   if response.status_code not in (200,201):raise ValueError('Guide synchronization rejected')
   result=response.json()
   if result.get('id')!=guide['id'] or result.get('version')!=guide['updated_at']:raise ValueError('Guide synchronization readback mismatch')
   conn.execute("UPDATE guide_sync SET status='synced',synced_at=?,next_at=NULL,error=NULL WHERE content_id=?",(now(),guide['id']));success+=1
  except Exception:
   conn.execute("UPDATE guide_sync SET status='retry',next_at=?,error='Sync unavailable; prior public guide preserved' WHERE content_id=?",((datetime.now(timezone.utc)+timedelta(minutes=min(360,2**min(attempts,8)))).isoformat(),guide['id']));failed+=1
  conn.commit()
 return {'synced':success,'retrying':failed,'deployment':'runtime R2 upserts; no source deployment needed'}
