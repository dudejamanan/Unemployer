"""Package public fields only; never export database files or OAuth credentials."""
import base64
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collector.config import load_boards, ROOT
from shorts.pipeline import Pipeline, IST
from datetime import datetime

p = Pipeline()
try:
    rows = p.db.list(status=None, limit=10000, today=datetime.now(IST).date())
    snapshot = [dict(id=r['id'], title=r['title'], company=r['company'], location=r['location'],
                     remote=bool(r['is_remote']), type=r['opp_type'], stipend=r['stipend_text'],
                     deadline=r['deadline'], apply_url=r['apply_url'], source=r['board'],
                     checked_at=r['last_seen_at'], skill_text=r['title']+' '+(r['description'] or '')) for r in rows if r['status'] != 'rejected']
    import re
    patterns={'Python':r'\bpython\b','JavaScript':r'\bjavascript\b','TypeScript':r'\btypescript\b','Java':r'\bjava\b','React':r'\breact(?:\.js)?\b','SQL':r'\bsql\b','Excel':r'\bexcel\b','C++':r'(?:^|\W)c\+\+(?:$|\W)','Machine learning':r'\bmachine learning\b','Figma':r'\bfigma\b','Digital marketing':r'\bdigital marketing\b','Node.js':r'\bnode\.?js\b'}
    for job in snapshot:
        text=job.pop('skill_text')
        job['skills']=[name for name,pattern in patterns.items() if re.search(pattern,text,re.I)]
    from shorts.growth.export import public_guides
    guides=public_guides(p.posts.conn)
finally:
    p.close()
folder = ROOT / 'sites' / 'unemployer' / 'worker'
search = (folder / 'search.js').read_text(encoding='utf-8')
page = (folder / 'page.html').read_text(encoding='utf-8').replace('/*SEARCH_HELPERS*/',search)
logo = base64.b64encode((ROOT / 'assets/branding/unemployer-logo.png').read_bytes()).decode()
source = (folder / 'distribution.js').read_text(encoding='utf-8')+'\n'+search+'\n'+(folder / 'media.js').read_text(encoding='utf-8')+'\n'+(folder / 'runtime.js').read_text(encoding='utf-8')
source = 'const GUIDES='+json.dumps(guides)+';\n'+'const PAGE=' + json.dumps(page) + ';\nconst LOGO="' + logo + '";\nconst BOARDS=' + json.dumps(load_boards()) + ';\nconst SNAPSHOT=' + json.dumps(snapshot) + ';\n' + source
(folder / 'index.js').write_text(source, encoding='utf-8')
print('Hub packaged:',len(snapshot),'public listings; no private credentials')
