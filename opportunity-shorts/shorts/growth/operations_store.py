SCHEMA='''
CREATE TABLE IF NOT EXISTS growth_jobs(name TEXT PRIMARY KEY,next_at TEXT,status TEXT,failures INTEGER DEFAULT 0,last_at TEXT,error TEXT);
CREATE TABLE IF NOT EXISTS discovery_signals(id TEXT PRIMARY KEY,adapter TEXT,category TEXT,question TEXT,source_url TEXT,evidence_urls TEXT,observed_at TEXT,expires_at TEXT,demand REAL,fingerprint TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS discovery_cache(url TEXT PRIMARY KEY,fetched_at TEXT,payload TEXT,error TEXT);
CREATE TABLE IF NOT EXISTS guide_sync(content_id TEXT PRIMARY KEY,payload_hash TEXT,version TEXT,status TEXT,attempts INTEGER DEFAULT 0,next_at TEXT,synced_at TEXT,error TEXT);
CREATE TABLE IF NOT EXISTS growth_reports(kind TEXT,period TEXT,data TEXT,created_at TEXT,PRIMARY KEY(kind,period));
CREATE TABLE IF NOT EXISTS experiment_details(experiment_id TEXT PRIMARY KEY,target_audience TEXT,format TEXT,results TEXT);
CREATE TABLE IF NOT EXISTS experiment_assignments(content_id TEXT PRIMARY KEY,experiment_id TEXT,variant TEXT,assigned_at TEXT);
CREATE TABLE IF NOT EXISTS outreach_activity(id TEXT PRIMARY KEY,contact_id TEXT,kind TEXT,happened_at TEXT,offer TEXT,value REAL,currency TEXT,provenance TEXT);
CREATE TABLE IF NOT EXISTS revenue_records(id TEXT PRIMARY KEY,contact_id TEXT,amount REAL,currency TEXT,paid_at TEXT,evidence_ref TEXT);
CREATE TABLE IF NOT EXISTS analytics_breakdowns(object_id TEXT,captured_at TEXT,kind TEXT,period_start TEXT,period_end TEXT,data TEXT,PRIMARY KEY(object_id,captured_at,kind));
CREATE TABLE IF NOT EXISTS channel_observations(captured_at TEXT PRIMARY KEY,channel_id TEXT,metrics TEXT,provenance TEXT);
CREATE TABLE IF NOT EXISTS funnel_daily(day TEXT,campaign TEXT,event TEXT,category TEXT,count INTEGER,PRIMARY KEY(day,campaign,event,category));
'''
