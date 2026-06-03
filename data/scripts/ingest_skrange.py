#!/usr/bin/env python3
"""
Ingest ``data/skrange/`` into Weaviate for SK Group (Skin Range knowledge).

Requires ``WEAVIATE_URL`` and ``WEAVIATE_API_KEY`` (on cloud). Optional: embedding
settings if you want hybrid vector search.

Usage (from repository root):

    python data/scripts/ingest_skrange.py

Equivalent to:

    python scripts/ingest_local_data.py --data-dir ./data/skrange \\
        --company-id 33eaf707-06f1-4e30-93d8-d8da71afaa92 \\
        --collection Co33EAF70706F14E3093D8D8DA71AFAA92
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import UUID

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.utils.naming import generate_weaviate_collection_name  # noqa: E402

SK_GROUP_COMPANY_ID = UUID("33eaf707-06f1-4e30-93d8-d8da71afaa92")


def main() -> None:
    collection = generate_weaviate_collection_name(SK_GROUP_COMPANY_ID)
    ingest = _ROOT / "scripts" / "ingest_local_data.py"
    cmd = [
        sys.executable,
        str(ingest),
        "--data-dir",
        str(_ROOT / "data" / "skrange"),
        "--company-id",
        str(SK_GROUP_COMPANY_ID),
        "--collection",
        collection,
    ]
    raise SystemExit(subprocess.call(cmd, cwd=str(_ROOT)))


if __name__ == "__main__":
    main()
