"""Bounded official-source research, exact evidence mapping, fail-closed validation."""
import hashlib
import json
import re
from datetime import datetime,timedelta,timezone
from urllib.parse import urlsplit,urljoin
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from collector.config import ROOT,load_yaml
from .store import identifier,now,discover,update_topic,ensure_mutable


def config(config_dir=None):
    return load_yaml((__import__('pathlib').Path(config_dir) if config_dir else ROOT/'config')/'career.yaml',{})


def safe_source(url,cfg):
    u=urlsplit(url)
    if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or u.hostname not in cfg.get('allowed_hosts',[]):
        raise ValueError('Research URL is outside the configured authoritative source allowlist')
    return url


def retrieve(source,cfg,session=requests):
    url=safe_source(source['url'],cfg)
    headers={'User-Agent':'UnemployerResearch/1.0 (+https://unemployer.syrupytide17.chatgpt.site)'}
    robots_url=urljoin(url,'/robots.txt')
    r=session.get(robots_url,headers=headers,timeout=(5,15),allow_redirects=False)
    if r.status_code==200:
        parser=RobotFileParser();parser.parse(r.text[:100000].splitlines())
        if not parser.can_fetch(headers['User-Agent'],url):raise ValueError('Source robots policy disallows retrieval')
    elif r.status_code!=404:raise ValueError('Cannot establish source robots permission')
    for attempt in range(4):
        response=session.get(url,headers=headers,timeout=(5,20),allow_redirects=False,stream=True)
        if response.status_code in (301,302,303,307,308):
            destination=safe_source(urljoin(url,response.headers.get('Location','')),cfg)
            if urlsplit(destination).hostname!=urlsplit(url).hostname:
                response.close();raise ValueError('Register the canonical source URL before cross-host retrieval')
            url=destination;response.close();continue
        response.raise_for_status()
        if 'html' not in response.headers.get('content-type',''):
            response.close();raise ValueError('Only public HTML research sources are supported')
        chunks=[];size=0
        try:
            for chunk in response.iter_content(16384):
                size+=len(chunk)
                if size>500000:raise ValueError('Research source exceeds retrieval size limit')
                chunks.append(chunk)
        finally:response.close()
        soup=BeautifulSoup(b''.join(chunks),'html.parser')
        for e in soup.select('script,style,nav,footer,header,form,aside'):e.decompose()
        main=soup.select_one('main article') or soup.select_one('main') or soup.select_one('article') or soup
        lines=[' '.join(x.split()) for x in main.get_text('\n',strip=True).splitlines()]
        lines=[x for x in lines if len(x)>40 and '@' not in x and not re.search(r'\b\d{3}[- .]\d{3}[- .]\d{4}\b',x)]
        excerpt='\n'.join(lines)[:8000]
        if len(excerpt)<150:raise ValueError('Source contains insufficient usable career guidance')
        digest=hashlib.sha256(excerpt.encode()).hexdigest()
        return dict(id=identifier(url+'|'+digest),url=url,title=source['title'],domain=urlsplit(url).hostname,
                    retrieved_at=now(),content_hash=digest,excerpt=excerpt,authority=source['authority'])
    raise ValueError('Research source redirects exceeded limit')


def seed(conn,cfg):
    ids=[]
    for topic in cfg.get('topics',[]):
        urls=[cfg['sources'][i]['url'] for i in topic['sources']]
        ids.append(discover(conn,topic['title'],topic['question'],topic['category'],'configured_student_questions',urls))
    return ids


def validate_claims(claims,sources,cfg):
    if not isinstance(claims,list) or not 2<=len(claims)<=4:raise ValueError('Research needs two to four evidence claims')
    registry={s['id']:s for s in sources};counts={};seen=set()
    verified=[]
    for claim in claims:
        if set(claim)!={'source_id','quote'}:raise ValueError('Claim schema must contain only source_id and quote')
        source=registry.get(claim['source_id']);quote=claim['quote']
        if not source or not isinstance(quote,str) or len(quote.split())<5:raise ValueError('Claim refers to unknown evidence')
        if quote not in source['excerpt']:raise ValueError('Claim is not an exact excerpt from the retrieved source')
        if any(x in quote.lower() for x in ('ignore previous','system prompt','api key','guarantee','guaranteed')) or re.search(r'\balways\b|\ball employers\b|\bevery employer\b',quote,re.I):raise ValueError('Unsafe or universal evidence claim')
        if quote in seen:raise ValueError('Duplicate evidence claim')
        seen.add(quote);counts[source['id']]=counts.get(source['id'],0)+len(quote.split())
        if counts[source['id']]>cfg.get('max_quote_words_per_source',25):raise ValueError('Source quotation limit exceeded')
        verified.append(dict(claim_id=identifier(source['id']+quote),source_id=source['id'],quote=quote))
    if len(counts)<cfg.get('minimum_sources',2):raise ValueError('Independent authoritative sources are insufficient')
    return verified


def candidates(sources,category='applications'):
    result=[]
    for source in sources:
        source_count=0
        for quote in re.split(r'(?<=[.!?])\s+|\n',source['excerpt']):
            quote=quote.strip()
            if not 6<=len(quote.split())<=25 or not re.search(r'[.!?]$',quote):continue
            if not re.search(r'tailor|show|explain|check|use|include|avoid|writ|connect|match|identify|highlight|articulate|prepare|practi|ask|listen|follow|review|learn',quote,re.I):continue
            if not re.search(r'cover letter|résumé|resume|application|skills|experience|qualifications|interview|network|contact|career|research',quote,re.I):continue
            if re.search(r'\balways\b|\bguarantee|ignore previous|system prompt|api key',quote,re.I):continue
            if source_count>=12:break
            source_count+=1
            result.append({'candidate_id':'C'+str(len(result)+1),'source_id':source['id'],'quote':quote})
    return result[:50]


def research_topic(conn,id,settings,cfg,model):
    row=conn.execute('SELECT * FROM career_topics WHERE id=?',(id,)).fetchone()
    if not row:raise ValueError('Unknown topic')
    if row['status']=='published':raise ValueError('Published research is immutable; discover a follow-up topic')
    ensure_mutable(conn,row['content_id'])
    if row['content_id']:
        conn.execute("UPDATE content_items SET status='deferred' WHERE id=?",(row['content_id'],));conn.commit()
    # Consequential advice is automatically deferred, never sent to a human approval queue.
    if re.search(r'law|legal|visa|scam|salary rights|pay.*fee|financial|contract',row['question'],re.I):
        update_topic(conn,id,'deferred',error='Consequential topic outside autonomous source policy');return
    update_topic(conn,id,'researching',error=None)
    sources=[]
    for url in json.loads(row['source_urls']):
        spec=next((s for s in cfg.get('sources',[]) if s['url']==url),None)
        if not spec:raise ValueError('Topic source is not registered')
        try:source=retrieve(spec,cfg)
        except (requests.RequestException,ValueError):
            conn.execute('UPDATE career_sources SET available=0 WHERE url=?',(url,));conn.commit();continue
        conn.execute('INSERT OR REPLACE INTO career_sources VALUES (?,?,?,?,?,?,?,?,1)',tuple(source[k] for k in ('id','url','title','domain','retrieved_at','content_hash','excerpt','authority')))
        sources.append(source)
    conn.commit()
    if len(sources)<cfg.get('minimum_sources',2):raise ValueError('Too few accessible authoritative research sources')
    registry=candidates(sources)
    pairs=[]
    for first in registry:
        for second in registry:
            if first['source_id']!=second['source_id'] and first['candidate_id']<second['candidate_id']:
                pairs.append({'pair_id':'P'+str(len(pairs)+1),'candidate_ids':[first['candidate_id'],second['candidate_id']],'quotes':[first['quote'],second['quote']]})
                if len(pairs)>=30:break
        if len(pairs)>=30:break
    if not pairs:raise ValueError('No actionable evidence pair from two sources')
    payload=dict(question=row['question'],candidate_registry=registry,pair_registry=pairs,maximum_claims=2)
    for attempt in range(2):
        raw=model('evidence_extraction',payload,settings)
        try:
            chosen=next((p for p in pairs if p['pair_id']==raw.get('pair_id')),None)
            ids=chosen['candidate_ids'] if chosen else raw.get('candidate_ids')
            if not isinstance(ids,list) or len(ids)!=2 or len(set(ids))!=2:raise ValueError('Choose exactly two distinct registered candidate IDs')
            selected=[c for id in ids for c in registry if c['candidate_id']==id]
            if len(selected)!=2:raise ValueError('Unknown evidence candidate ID')
            claims=validate_claims([{'source_id':c['source_id'],'quote':c['quote']} for c in selected],sources,cfg)
            break
        except ValueError as exc:
            payload['validation_error']=str(exc)
            payload['revision_instruction']='Return one pair_id from pair_registry. Do not return quotes or extra fields.'
            if attempt==1:raise
    if any(not re.search(r'cover letter|résumé|resume|application|skills|experience|interview|network|contact|career|research',c['quote'],re.I) for c in claims):
        raise ValueError('Research excerpts do not address the configured application question')
    if any(not re.search(r'tailor|show|explain|check|use|include|avoid|writ|connect|match|identify|highlight|articulate|prepare|practi|ask|listen|follow|review|learn',c['quote'],re.I) for c in claims):
        raise ValueError('Research excerpts lack actionable guidance')
    # A shared source quote may support multiple topics without moving their records.
    for claim in claims:claim['claim_id']=identifier(id+'|'+claim['claim_id'])
    # Brief fields reference validated claims; no new free-form factual claims accepted.
    brief=model('brief_synthesis',dict(question=row['question'],claim_ids=[c['claim_id'] for c in claims]),settings)
    if set(brief)!={'claim_ids','caveats'} or not isinstance(brief['caveats'],list) or set(brief['claim_ids'])!={c['claim_id'] for c in claims}:
        raise ValueError('Brief must preserve the exact verified claim registry')
    caveats=['General university guidance; individual employer instructions take precedence.']
    for c in claims:
        conn.execute('INSERT OR REPLACE INTO career_claims VALUES (?,?,?,?,?,?)',(c['claim_id'],id,c['source_id'],c['quote'],'source_recommendation',now()))
    conn.commit()
    update_topic(conn,id,'researched',brief={'claims':claims,'angle':row['question']},caveats=caveats,
                 validation_metadata={'mode':'autonomous','validator':'exact-evidence-v1','sources':len(sources)})
