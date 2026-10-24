"""Evidence-constrained guide drafts, build validation and no human publishing gate."""
import asyncio
import hashlib
import json
from pathlib import Path
from datetime import datetime,timedelta,timezone
from .store import now,identifier,update_topic,ensure_mutable
from .research import safe_source
from ..models import ScriptDoc,OnScreenText,VoiceoverLine

ADVICE={'application_exercise':'Try this: choose a relevant project and write what you contributed and why it fits the role.'}
CAVEAT='General guidance; follow the actual employer instructions.'
CTA='Save this guide for your next application.'


def validate_plan(plan,claims):
    if set(plan)!={'claim_ids','advice_id'}:raise ValueError('Unknown script fields are not allowed')
    ids=plan['claim_ids']
    if not isinstance(ids,list) or not 2<=len(ids)<=3 or len(ids)!=len(set(ids)):
        raise ValueError('Guide needs two or three distinct takeaways')
    registry={c['id']:c for c in claims}
    if not set(ids)<=set(registry) or plan['advice_id'] not in ADVICE:
        raise ValueError('Script contains unsupported claims/advice')
    if len({registry[id]['source_id'] for id in ids})<2:raise ValueError('Guide must preserve independent source evidence')
    return ids


def draft(conn,topic_id,settings,cfg,model):
    topic=conn.execute('SELECT * FROM career_topics WHERE id=?',(topic_id,)).fetchone()
    if not topic or topic['status']!='researched':raise ValueError('Research must pass before drafting')
    ensure_mutable(conn,topic['content_id'])
    current_ids={c['claim_id'] for c in json.loads(topic['brief'])['claims']}
    claims=[dict(c) for c in conn.execute('SELECT * FROM career_claims WHERE topic_id=?',(topic_id,)) if c['id'] in current_ids]
    aliases={'C'+str(i+1):c for i,c in enumerate(claims)}
    aliased_claims=[{**c,'id':alias} for alias,c in aliases.items()]
    payload=dict(question=topic['question'],claims=aliased_claims)
    for attempt in range(2):
        plan=model('script_generation',payload,settings)
        try:
            ids=validate_plan(plan,aliased_claims)
            break
        except (ValueError,TypeError) as exc:
            if attempt==1:raise
            payload['validation_error']=str(exc)
            payload['allowed_claim_ids']=list(aliases)
            payload['allowed_advice_ids']=list(ADVICE)
    validation=model('script_validation',dict(plan=plan,claims=aliased_claims,claim_ids=ids),settings)
    if validation.get('valid') is not True or validation.get('claim_ids')!=ids:
        raise ValueError('Model evidence cross-check failed; defer rather than publish')
    ids=[aliases[id]['id'] for id in ids]
    registry={c['id']:c for c in claims}
    sources={s['id']:dict(s) for s in conn.execute('SELECT * FROM career_sources')}
    from .experiments import hook as select_hook
    hook=select_hook(conn,topic,'guide-'+topic_id)
    spoken=[hook]+[registry[id]['quote'] for id in ids]+[ADVICE[plan['advice_id']],CAVEAT,CTA]
    if not 40<=len(' '.join(spoken).split())<=105:raise ValueError('Guide narration length is unsuitable; revise source selection')
    description=topic['question']+'\n\nSources and attribution:\n'+'\n'.join(dict.fromkeys(sources[registry[id]['source_id']]['url'] for id in ids))+'\n\n'+CAVEAT+'\nMore opportunities: '+settings.get('business',{}).get('hub_url','https://unemployer.syrupytide17.chatgpt.site')+'\n#CareerAdvice #Internships #Shorts #Unemployer'
    signal=conn.execute("SELECT adapter,source_url FROM discovery_signals WHERE question=? AND source_url IS NOT NULL LIMIT 1",(topic['question'],)).fetchone()
    if signal and signal['adapter']=='stackexchange_question':
        # Attribute public question discovery without reusing it as factual evidence.
        description+='\nQuestion discovery: '+signal['source_url']+' (Stack Exchange; CC BY-SA). Answer evidence is listed above.'
    script=ScriptDoc(hook,[VoiceoverLine(x) for x in spoken],OnScreenText(topic['title'],'Unemployer','','','','',CTA),topic['title'][:100],description,['#CareerAdvice','#Internships','#Shorts','#Unemployer'])
    scenes=[{'heading':topic['title'],'body':'Practical guidance for your next application.','label':'CAREER GUIDE'}]
    for id in ids:
        source=sources[registry[id]['source_id']]
        scenes.append({'heading':'A useful takeaway','body':registry[id]['quote'],'label':'SOURCE RECOMMENDATION',
                       'source_title':source['title'],'source_domain':source['domain'],'source_date':source['retrieved_at'][:10]})
    scenes.append({'heading':'Put it into practice','body':ADVICE[plan['advice_id']],'label':'OUR GENERAL EXERCISE'})
    scenes.append({'heading':'Save this guide','body':CAVEAT,'label':'YOUR NEXT STEP'})
    content_id='guide-'+topic_id
    conn.execute('INSERT INTO content_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET script=excluded.script,status=excluded.status,evidence_hash=excluded.evidence_hash',
        (content_id,'career_guide',topic['category'],topic['title'],topic_id,'[]','drafted',json.dumps(script.to_dict()),None,now(),None,
         hashlib.sha256(json.dumps(claims,sort_keys=True).encode()).hexdigest(),None))
    conn.commit()
    update_topic(conn,topic_id,'drafted',script=script.to_dict(),scene_plan=scenes,content_id=content_id,
                 validation_metadata={'mode':'autonomous','validator':'evidence-plan-v1','claim_ids':ids,'advice_id':plan['advice_id'],'hook':hook})
    return content_id


def validate_ready(conn,item,cfg):
    if item['format']=='career_guide':
        topic=conn.execute('SELECT * FROM career_topics WHERE id=?',(item['topic_id'],)).fetchone()
        if not topic or topic['status'] not in ('drafted','approved','published'):
            raise ValueError('Topic is not in an automatically validated publication state')
        claims=[dict(r) for r in conn.execute('SELECT * FROM career_claims WHERE topic_id=?',(item['topic_id'],))]
        registry={r['id']:r for r in claims}
        metadata=json.loads(topic['validation_metadata'])
        selected=metadata.get('claim_ids',[])
        if len(selected)<2 or not set(selected)<=set(registry):raise ValueError('Validated claim registry is incomplete')
        if len({registry[id]['source_id'] for id in selected})<2:raise ValueError('Independent sources are required')
        for id in selected:
            claim=registry[id];source=conn.execute('SELECT * FROM career_sources WHERE id=?',(claim['source_id'],)).fetchone()
            if not source or not source['available'] or claim['quote'] not in source['excerpt']:raise ValueError('Evidence changed or became unavailable')
            safe_source(source['url'],cfg)
            if datetime.fromisoformat(source['retrieved_at'])<datetime.now(timezone.utc)-timedelta(days=cfg.get('source_max_age_days',14)):
                raise ValueError('Career evidence is stale; refresh research')
        script=ScriptDoc.from_dict(json.loads(item['script']))
        expected=[metadata.get('hook',topic['title']+'.')]+[registry[id]['quote'] for id in selected]+[ADVICE[metadata['advice_id']],CAVEAT,CTA]
        if [l.text for l in script.voiceover_lines]!=expected:raise ValueError('Guide script contains unsupported or edited claims')
        permitted={conn.execute('SELECT url FROM career_sources WHERE id=?',(registry[id]['source_id'],)).fetchone()[0] for id in selected}
        discovery=conn.execute("SELECT source_url FROM discovery_signals WHERE question=? AND adapter='stackexchange_question'",(topic['question'],)).fetchone()
        if discovery and discovery[0]:permitted.add(discovery[0])
        import re
        urls=set(re.findall(r'https?://[^\s]+',script.description))
        if not permitted<=urls or urls-permitted-{'https://unemployer.syrupytide17.chatgpt.site'}:raise ValueError('Guide source links changed')
    elif item['format']=='weekly_roundup':
        from ..pipeline import fact_digest
        from collector.db import row_to_card
        evidence=json.loads(item['evidence_hash']);hashes=evidence.get('facts',{})
        if evidence.get('script_hash')!=hashlib.sha256(json.dumps(json.loads(item['script']),sort_keys=True).encode()).hexdigest():raise ValueError('Roundup script changed after evidence validation')
        for id in json.loads(item['opportunity_ids']):
            row=conn.execute('SELECT * FROM opportunities WHERE id=?',(id,)).fetchone()
            if not row or not row['is_open'] or row['status']=='rejected' or (row['deadline'] and row['deadline']<datetime.now(timezone.utc).date().isoformat()):raise ValueError('Roundup contains an unavailable opportunity')
            from urllib.parse import urlsplit
            url=urlsplit(row['apply_url'])
            if url.scheme!='https' or not url.hostname or url.username or url.password:raise ValueError('Roundup application URL is unsafe')
            if not row['last_seen_at'] or datetime.fromisoformat(row['last_seen_at'].replace('Z','+00:00'))<datetime.now(timezone.utc)-timedelta(hours=24):raise ValueError('Roundup source is stale')
            if hashes.get(id)!=fact_digest(row_to_card(row)):raise ValueError('Roundup source facts changed')
    return True


def build(conn,content_id,settings,cfg):
    from ..tts import generate_tts
    from ..render.render_scenes import render_scene,_get_theme
    from ..assemble import assemble_with_captions
    item=conn.execute('SELECT * FROM content_items WHERE id=?',(content_id,)).fetchone()
    if not item or item['status'] not in ('drafted','ready'):raise ValueError('A validated draft is required')
    ensure_mutable(conn,content_id)
    validate_ready(conn,item,cfg)
    script=ScriptDoc.from_dict(json.loads(item['script']))
    folder=Path(settings['paths']['output_dir'])/'growth'/content_id;folder.mkdir(parents=True,exist_ok=True)
    topic=conn.execute('SELECT scene_plan FROM career_topics WHERE id=?',(item['topic_id'],)).fetchone() if item['topic_id'] else None
    plan=json.loads(topic['scene_plan']) if topic else json.loads(item['opportunity_ids'])
    if item['format']=='weekly_roundup':plan=roundup_scenes(conn,item)
    audio=asyncio.run(generate_tts(' '.join(l.text for l in script.voiceover_lines),settings['voices']['male'],settings))
    render_settings={**settings,'assembly':{**settings['assembly'],'max_duration':settings.get('growth',{}).get('guide_max_duration_seconds',60)}}
    scenes=[]
    for i,scene in enumerate(plan):
        path=folder/f'scene-{i:02d}.png'
        render_scene('guide',script,_get_theme(settings,0),path,settings={**render_settings,'enrichment':scene})
        scenes.append(path)
    import shutil
    shutil.copy2(scenes[0],folder/'thumbnail.png')
    video=assemble_with_captions(scenes,Path(audio.audio_path),folder/'video.mp4',audio.word_timestamps,settings=render_settings)
    conn.execute("UPDATE content_items SET status='ready',video_path=?,validated_at=?,error=NULL WHERE id=?",(str(video),now(),content_id));conn.commit()
    if item['topic_id']:update_topic(conn,item['topic_id'],'approved',validation_metadata={**json.loads(conn.execute('SELECT validation_metadata FROM career_topics WHERE id=?',(item['topic_id'],)).fetchone()[0]),'approval_actor':'automated-validator','validated_at':now()})
    return str(video)


def roundup_scenes(conn,item):
    scenes=[{'heading':'This week’s opportunity shortlist','body':'Compare the fit, then apply through the original source.','label':'WEEKLY ROUNDUP'}]
    for id in json.loads(item['opportunity_ids']):
        r=conn.execute('SELECT * FROM opportunities WHERE id=?',(id,)).fetchone()
        scenes.append({'heading':r['title'],'body':r['company']+' · '+r['location']+' · '+(r['stipend_text'] or 'Compensation not disclosed'),'label':'SOURCE-LINKED OPENING'})
    scenes.append({'heading':'Check eligibility before applying','body':'Source links are in the description. No selection guarantees.','label':'YOUR NEXT STEP'})
    return scenes
