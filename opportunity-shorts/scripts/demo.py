"""Build a clearly fictional example in an isolated database. Never uploads."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['OPP_DB_PATH'] = str(ROOT / 'out' / 'demo' / 'opportunities.db')

from collector.pipeline import import_manual
from shorts.pipeline import Pipeline


def main():
    pipeline = Pipeline()
    try:
        import_manual(ROOT / 'config' / 'manual_example.yaml', pipeline.collector_settings, pipeline.db)
        row = pipeline.db.list(limit=1)[0]
        post = pipeline.build(row['id'], force=True)
        print(post.video_path)
    finally:
        pipeline.close()


if __name__ == '__main__':
    main()
