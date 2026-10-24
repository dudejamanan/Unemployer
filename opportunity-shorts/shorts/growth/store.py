"""Additive, versioned SQLite migrations; existing publisher tables are untouched."""
import hashlib
import json
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS growth_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS career_topics(
 id TEXT PRIMARY KEY,title TEXT NOT NULL,question TEXT NOT NULL,category TEXT NOT NULL,
 discovery_source TEXT NOT NULL,discovered_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'discovered',
 source_urls TEXT NOT NULL DEFAULT '[]',brief TEXT,script TEXT,scene_plan TEXT,
 caveats TEXT NOT NULL DEFAULT '[]',error TEXT,retry_after TEXT,updated_at TEXT NOT NULL,
 validation_metadata TEXT,content_id TEXT
);
CREATE TABLE IF NOT EXISTS career_sources(
 id TEXT PRIMARY KEY,url TEXT NOT NULL,title TEXT NOT NULL,domain TEXT NOT NULL,
 retrieved_at TEXT NOT NULL,content_hash TEXT NOT NULL,excerpt TEXT NOT NULL,
 authority TEXT NOT NULL,available INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS career_claims(
 id TEXT PRIMARY KEY,topic_id TEXT NOT NULL,source_id TEXT NOT NULL,
 quote TEXT NOT NULL,kind TEXT NOT NULL,verified_at TEXT NOT NULL,
 FOREIGN KEY(topic_id) REFERENCES career_topics(id), FOREIGN KEY(source_id) REFERENCES career_sources(id)
);
CREATE TABLE IF NOT EXISTS content_items(
 id TEXT PRIMARY KEY,format TEXT NOT NULL,category TEXT NOT NULL,title TEXT NOT NULL,
 topic_id TEXT,opportunity_ids TEXT NOT NULL DEFAULT '[]',status TEXT NOT NULL,
 script TEXT NOT NULL,video_path TEXT,created_at TEXT NOT NULL,validated_at TEXT,
 evidence_hash TEXT,error TEXT
);
CREATE TABLE IF NOT EXISTS content_deliveries(
 content_id TEXT NOT NULL,platform TEXT NOT NULL,status TEXT NOT NULL,
 external_id TEXT,published_at TEXT,attempted_at TEXT,retry_after TEXT,error TEXT,
 PRIMARY KEY(content_id,platform)
);
CREATE TABLE IF NOT EXISTS content_publications(
 content_id TEXT NOT NULL,platform TEXT NOT NULL,format TEXT NOT NULL,category TEXT,
 company TEXT,role TEXT,hook TEXT,published_at TEXT NOT NULL,external_id TEXT,
 PRIMARY KEY(content_id,platform)
);
CREATE TABLE IF NOT EXISTS metric_observations(
 object_id TEXT NOT NULL,captured_at TEXT NOT NULL,provenance TEXT NOT NULL,
 metrics TEXT NOT NULL,period_start TEXT,period_end TEXT,
 PRIMARY KEY(object_id,captured_at,provenance)
);
CREATE TABLE IF NOT EXISTS growth_experiments(
 id TEXT PRIMARY KEY,hypothesis TEXT NOT NULL,variable TEXT NOT NULL,variants TEXT NOT NULL,
 starts_at TEXT NOT NULL,ends_at TEXT NOT NULL,status TEXT NOT NULL,
 results TEXT,conclusion TEXT NOT NULL DEFAULT 'Preliminary; no causal or significance claim'
);
CREATE TABLE IF NOT EXISTS outreach_contacts(
 id TEXT PRIMARY KEY,organization TEXT NOT NULL,category TEXT NOT NULL,
 professional_contact TEXT,public_source_url TEXT,outreach_date TEXT,message_status TEXT NOT NULL DEFAULT 'not_sent',
 follow_up_date TEXT,response TEXT,outcome TEXT,partnership_status TEXT NOT NULL DEFAULT 'prospect'
);
CREATE TABLE IF NOT EXISTS research_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,topic_id TEXT,stage TEXT NOT NULL,status TEXT NOT NULL,
 started_at TEXT NOT NULL,completed_at TEXT,error TEXT
);
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    return hashlib.sha256(value.strip().casefold().encode()).hexdigest()[:16]


def migrate(conn):
    from .operations_store import SCHEMA as OPERATIONS_SCHEMA
    conn.executescript(SCHEMA+OPERATIONS_SCHEMA)
    conn.execute('INSERT OR IGNORE INTO growth_migrations VALUES (2,?)',(now(),))
    conn.execute('INSERT OR IGNORE INTO growth_migrations VALUES (3,?)',(now(),));conn.commit()
    if conn.execute('SELECT 1 FROM growth_migrations WHERE version=1').fetchone():
        return
    conn.execute('INSERT OR IGNORE INTO growth_migrations VALUES (1,?)',(now(),))
    # Seed the history from existing latest observations without deleting/replacing them.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='video_metrics'").fetchone():
        for row in conn.execute('SELECT * FROM video_metrics').fetchall():
            row=dict(row)
            conn.execute('INSERT OR IGNORE INTO metric_observations VALUES (?,?,?,?,?,?)',
                (row['youtube_id'],row['captured_at'],'youtube_data_api',json.dumps({k:row.get(k) for k in ('views','likes','comments')}),None,None))
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='posts'").fetchone():
        for row in conn.execute("SELECT p.*,o.company,o.title FROM posts p JOIN opportunities o ON o.id=p.opportunity_id WHERE p.status='posted' AND p.posted_at IS NOT NULL").fetchall():
            try:hook=json.loads(row['script_json']).get('hook','')
            except (ValueError,TypeError):hook=''
            conn.execute('INSERT OR IGNORE INTO content_publications VALUES (?,?,?,?,?,?,?,?,?)',
                (row['opportunity_id'],'youtube','opportunity_alert','opportunities',row['company'],row['title'],hook,row['posted_at'],row['youtube_id']))
    conn.commit()


def discover(conn,title,question,category,source,urls):
    if not title.strip() or not question.strip():
        raise ValueError('A title and student question are required')
    import re
    normalized=re.sub(r'\W+',' ',question.casefold()).strip()
    for previous in conn.execute('SELECT id,question FROM career_topics'):
        if re.sub(r'\W+',' ',previous['question'].casefold()).strip()==normalized:return previous['id']
    id=identifier(normalized)
    timestamp=now()
    conn.execute("INSERT OR IGNORE INTO career_topics(id,title,question,category,discovery_source,discovered_at,source_urls,updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (id,title.strip(),question.strip(),category,source,timestamp,json.dumps(urls),timestamp))
    conn.commit()
    return id


def update_topic(conn,id,status,**fields):
    allowed={'brief','script','scene_plan','caveats','error','retry_after','validation_metadata','content_id'}
    if set(fields)-allowed:raise ValueError('Unknown topic field')
    assignments=['status=?','updated_at=?']+[k+'=?' for k in fields]
    conn.execute('UPDATE career_topics SET '+','.join(assignments)+' WHERE id=?',
        [status,now()]+[json.dumps(v) if isinstance(v,(dict,list)) else v for v in fields.values()]+[id])
    conn.commit()


def ensure_mutable(conn,content_id):
    if content_id and conn.execute("SELECT 1 FROM content_deliveries WHERE content_id=? AND status IN ('published','publishing','uncertain') LIMIT 1",(content_id,)).fetchone():
        raise ValueError('Published or uncertain deliveries are immutable; create a follow-up topic')
