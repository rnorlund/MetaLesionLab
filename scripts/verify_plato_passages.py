"""Check every passage in public_data/plato_passages.json word for word against its source.

Kept so the old command still works: the check now covers Aristotle too, and lives in
scripts/verify_passages.py.

    python scripts/verify_plato_passages.py [--cache DIR]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_passages import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
