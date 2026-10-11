"""Report configured sources and current matching opportunities without network access."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.config import load_boards, load_settings, load_sources_cfg
from collector.db import Database
from collector.pipeline import build_targets
from shorts.pipeline import IST


def main():
    settings = load_settings()
    db = Database(settings['db_path'])
    try:
        cards = db.list(status=None, limit=100000, only_open=True, today=datetime.now(IST).date())
        sources = build_targets(load_boards(), load_sources_cfg())
        report = {
            'enabled_sources': len(sources),
            'filters': settings['filters'],
            'open_unexpired_opportunities': len(cards),
            'by_type': dict(Counter(row['opp_type'] for row in cards)),
            'by_status': dict(Counter(row['status'] for row in cards)),
            'sources': [
                {
                    'source': source.key(config),
                    'company': config.get('company') or config.get('name'),
                    'matching_opportunities': sum(row['board'] == source.key(config) for row in cards),
                }
                for source, config in sources
            ],
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        db.close()


if __name__ == '__main__':
    main()
