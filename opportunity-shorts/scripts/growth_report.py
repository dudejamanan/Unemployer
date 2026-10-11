"""Summarize previously fetched public metadata, without more network requests."""
from collections import Counter
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / 'data' / 'source_probes'
for name in ('talkpro', 'apna', 'babbar', 'internshala', 'saumya'):
    report = json.loads((folder / (name + '.json')).read_text(encoding='utf-8'))
    videos = report['videos']
    print(json.dumps({'channel': report['channel'], 'sample': len(videos),
        'descriptions': sum(v.get('description_available', False) for v in videos),
        'hashtags': Counter(t.lower() for v in videos for t in v.get('hashtags', [])).most_common(12)}, ensure_ascii=True))
html = (folder / 'channel.html').read_text(encoding='utf-8')
match = re.search(r'(?:var\s+)?ytInitialData\s*=\s*', html)
if match:
    data = json.JSONDecoder().raw_decode(html[match.end():])[0]
    print(json.dumps({'own_channel_metadata': data.get('metadata', {}),
                     'header': data.get('header', {})}, ensure_ascii=True)[:4000])
