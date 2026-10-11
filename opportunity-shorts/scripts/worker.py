"""Hidden Windows entry point with visible diagnostics on disk."""
from pathlib import Path
import os
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
(ROOT / 'data').mkdir(exist_ok=True)
with (ROOT / 'data' / 'worker-console.log').open('a', encoding='utf-8', buffering=1) as output:
    sys.stdout = sys.stderr = output
    try:
        from shorts.scheduler import run_daemon
        run_daemon()
    except Exception:
        traceback.print_exc()
        raise
