#!/usr/bin/env python3
"""Start only the API. Run the React frontend separately."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    try:
        raise SystemExit(subprocess.call([sys.executable, '-m', 'backend.server', *sys.argv[1:]], cwd=root))
    except KeyboardInterrupt:
        pass
