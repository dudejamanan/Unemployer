"""Public-only validated guide snapshots; no subscriber or operational data."""
import json
from .content import validate_ready
from .research import config


def public_guides(conn):
    result=[]
    for item in conn.execute("SELECT * FROM content_items WHERE format='career_guide' AND status IN ('ready','published')"):
        try:validate_ready(conn,item,config())
        except (ValueError,TypeError,KeyError):continue
        topic=conn.execute('SELECT * FROM career_topics WHERE id=?',(item['topic_id'],)).fetchone()
        metadata=json.loads(topic['validation_metadata']);claims=[];sources={}
        for id in metadata['claim_ids']:
            claim=conn.execute('SELECT * FROM career_claims WHERE id=?',(id,)).fetchone()
            source=conn.execute('SELECT * FROM career_sources WHERE id=?',(claim['source_id'],)).fetchone()
            claims.append(claim['quote']);sources[source['id']]={'title':source['title'],'url':source['url'],'retrieved_at':source['retrieved_at']}
        publication=conn.execute('SELECT MIN(published_at) FROM content_publications WHERE content_id=?',(item['id'],)).fetchone()[0]
        if not publication:continue
        result.append({'id':item['id'],'title':item['title'],'question':topic['question'],'category':topic['category'],'takeaways':claims,
            'sources':list(sources.values()),'caveats':json.loads(topic['caveats']),'published_at':publication,'updated_at':item['validated_at']})
    return result
