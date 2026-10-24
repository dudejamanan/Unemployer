"""Cached, bounded discovery signals; discussion text never becomes guide evidence."""
import html,json,re
from datetime import datetime,timedelta,timezone
from urllib.parse import urlsplit
import requests
from .store import now,identifier,discover
from .research import retrieve

CATEGORIES={
 'applications':('resume','cover letter','application'),
 'interviews':('interview','interview preparation'),
 'outreach':('network','outreach','cold email'),
 'research':('research','laborator','phd'),
 'remote':('remote','work from home'),
 'verification':('scam','verify','verification'),
 'eligibility':('eligibility','eligible'),
 'deadlines':('deadline','closing date'),
 'paid_internships':('paid internship','stipend'),
 'early_career':('first job','career mistake')}


def category(text):
 return next((k for k,terms in CATEGORIES.items() if any(t in text.lower() for t in terms)),'applications')


def cached(conn,url,fetch):
 old=conn.execute('SELECT * FROM discovery_cache WHERE url=?',(url,)).fetchone()
 if old and datetime.fromisoformat(old['fetched_at'])>datetime.now(timezone.utc)-timedelta(hours=24):return json.loads(old['payload'])
 try:value=fetch();error=None
 except Exception:value=[];error='Source unavailable or permission not established'
 conn.execute('INSERT OR REPLACE INTO discovery_cache VALUES (?,?,?,?)',(url,now(),json.dumps(value),error));conn.commit()
 return value


def evidence_urls(cfg,kind):
 return [s['url'] for s in cfg['sources'] if kind in s.get('categories',['applications'])]


def add(conn,cfg,adapter,question,source,demand=1,kind=None):
 question=html.unescape(re.sub('<[^>]*>',' ',str(question))).strip()
 if not 12<=len(question)<=200 or '@' in question or re.search(r'ignore previous|system prompt|api key',question,re.I):return None
 kind=kind or category(question);urls=evidence_urls(cfg,kind)
 fingerprint=identifier(re.sub(r'\W+',' ',question.lower()))
 conn.execute('INSERT OR IGNORE INTO discovery_signals VALUES (?,?,?,?,?,?,?,?,?,?)',(fingerprint,adapter,kind,question,source,json.dumps(urls),now(),(datetime.now(timezone.utc)+timedelta(days=14)).isoformat(),min(100,max(0,float(demand))),fingerprint))
 conn.commit()
 # Discovery without two relevant evidence sources remains a signal, not a draft.
 if len(urls)<2:return None
 titles={'applications':'Make your application evidence useful','interviews':'Prepare clear examples for your interview','outreach':'Prepare for a useful career conversation'}
 return discover(conn,titles.get(kind,'Prepare your next career step'),question,kind,adapter,urls)


def run(pipeline,cfg):
 conn=pipeline.posts.conn;ids=[]
 for spec in cfg.get('sources',[])[:12]:
  def load(spec=spec):return [retrieve(spec,cfg)]
  for source in cached(conn,spec['url'],load):
   for sentence in re.split(r'[\n.!]',source['excerpt']):
    sentence=sentence.strip()
    if re.match(r'^(How|What|When|Why|Should|Can)\b',sentence,re.I) and 20<=len(sentence)<=160:
     id=add(conn,cfg,'official_career_service',sentence+'?' if not sentence.endswith('?') else sentence,source['url'])
     if id:ids.append(id)
 for row in conn.execute('SELECT title,apply_url FROM opportunities WHERE is_open=1 AND status!=\'rejected\' ORDER BY last_seen_at DESC LIMIT 20'):
  kind=category(row['title']);question={'research':'How should I prepare an application for a research internship?','applications':'How can I explain relevant skills in an internship application?'} .get(kind,'What should I check before applying for this internship?')
  id=add(conn,cfg,'employer_opening',question,row['apply_url'],kind=kind)
  if id:ids.append(id)
 # Anonymous Stack Exchange discovery is opt-in, keyless, and stores title/link only.
 if cfg.get('discovery',{}).get('public_discussions',True):
  url='https://api.stackexchange.com/2.3/search/advanced?site=academia&q=internship&sort=creation&order=desc&pagesize=10'
  def discussions():
   r=requests.get(url,timeout=(5,20));r.raise_for_status();data=r.json()
   if data.get('backoff') or data.get('error_id'):return []
   return [{'title':i['title'],'link':i['link'],'score':i.get('score',0)} for i in data.get('items',[]) if urlsplit(i.get('link','')).hostname=='academia.stackexchange.com']
  for item in cached(conn,url,discussions):
   id=add(conn,cfg,'stackexchange_question',item['title'],item['link'],1+max(0,item['score']))
   if id:ids.append(id)
 # Public Trends RSS is demand discovery only, never factual evidence.
 if cfg.get('discovery',{}).get('public_trends',True):
  url='https://trends.google.com/trending/rss?geo=IN'
  def trends():
   from urllib.robotparser import RobotFileParser
   from xml.etree import ElementTree
   robot=requests.get('https://trends.google.com/robots.txt',timeout=(5,15))
   if robot.status_code!=200:return []
   parser=RobotFileParser();parser.parse(robot.text.splitlines())
   if not parser.can_fetch('UnemployerResearch',url):return []
   response=requests.get(url,timeout=(5,20),headers={'User-Agent':'UnemployerResearch/1.0'});response.raise_for_status()
   if len(response.content)>500000:return []
   root=ElementTree.fromstring(response.content)
   return [item.findtext('title','') for item in root.findall('./channel/item') if re.search(r'internship|fresher|placement|research position',item.findtext('title',''),re.I)][:10]
  for title in cached(conn,url,trends):
   id=add(conn,cfg,'public_trends_rss','What should I check about '+title+' before applying?',url)
   if id:ids.append(id)
 # FAQs are transparent configured questions; demand is not fabricated popularity.
 for item in cfg.get('discovery',{}).get('faqs',[]):
  id=add(conn,cfg,'configured_faq',item['question'],None,0,item['category'])
  if id:ids.append(id)
 # Existing view counts signal which content has been seen, not why it succeeded.
 for row in conn.execute("SELECT c.title,c.category,p.external_id FROM content_publications p JOIN content_items c ON c.id=p.content_id WHERE p.platform='youtube' LIMIT 10"):
  add(conn,cfg,'published_content_followup','What should I practise after learning about '+row['title'].rstrip('.')+'?','https://www.youtube.com/watch?v='+row['external_id'],kind=row['category'])
 return {'topics':len(set(ids)),'signals':conn.execute('SELECT COUNT(*) FROM discovery_signals').fetchone()[0],'unavailable':['Search suggestions: no documented provider configured','Website questions: no verified submission endpoint; anonymous input is not treated as verified']}


def priority(conn,topic):
 signals=conn.execute('SELECT demand FROM discovery_signals WHERE fingerprint=? AND expires_at>?',(identifier(re.sub(r'\W+',' ',topic['question'].lower())),now())).fetchall()
 demand=max((r[0] for r in signals),default=0)
 count=conn.execute('SELECT COUNT(*) FROM content_publications WHERE category=?',(topic['category'],)).fetchone()[0]
 # Compare only lifetime public observations at a comparable measured video age.
 values=[r[0] for r in conn.execute("SELECT json_extract(m.metrics,'$.views') FROM metric_observations m JOIN content_publications p ON p.external_id=m.object_id WHERE m.provenance='youtube_data_api' AND p.category=? AND (julianday(m.captured_at)-julianday(p.published_at))*24 BETWEEN 24 AND 72 GROUP BY m.object_id",(topic['category'],)) if r[0] is not None]
 import statistics
 score=statistics.median(values) if len(values)>=5 else 0
 return (0 if topic['status']=='drafted' else 1 if topic['status']=='researched' else 2,count,-score,-demand,topic['discovered_at'])
