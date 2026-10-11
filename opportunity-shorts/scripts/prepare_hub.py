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
                     checked_at=r['last_seen_at']) for r in rows if r['status'] != 'rejected']
finally:
    p.close()
folder = ROOT / 'sites' / 'unemployer' / 'worker'
page = (folder / 'page.html').read_text(encoding='utf-8')
logo = base64.b64encode((ROOT / 'assets/branding/unemployer-logo.png').read_bytes()).decode()
source = (folder / 'runtime.js').read_text(encoding='utf-8')
source = 'const PAGE=' + json.dumps(page) + ';\nconst LOGO="' + logo + '";\nconst BOARDS=' + json.dumps(load_boards()) + ';\nconst SNAPSHOT=' + json.dumps(snapshot) + ';\n' + source
(folder / 'index.js').write_text(source, encoding='utf-8')
print('Hub packaged:',len(snapshot),'public listings; no private credentials')
