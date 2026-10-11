"""Check all current cards against template-script fact validation, without API calls."""
from datetime import datetime
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collector.config import load_settings
from collector.db import Database, row_to_card
from shorts.pipeline import IST
from shorts.script_gen import _template_fallback
from shorts.settings import load_shorts_settings
from shorts.validate_script import validate_script


def main():
    db = Database(load_settings()['db_path'])
    settings = load_shorts_settings()
    failures = []
    try:
        rows = db.list(status=None, limit=100000, today=datetime.now(IST).date())
        for row in rows:
            card = row_to_card(row)
            try:
                script = _template_fallback(card, settings)
                valid, errors = validate_script(script, card)
            except Exception as exc:
                valid, errors = False, [str(exc)]
            if not valid:
                failures.append({'id': card['id'], 'source': card['source'], 'errors': errors})
        report = {'checked': len(rows), 'valid': len(rows)-len(failures), 'failures': failures}
        print(json.dumps(report, indent=2))
        path = ROOT / 'data/source_probes/script_validation.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        return bool(failures)
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
