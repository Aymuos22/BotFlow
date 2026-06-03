#!/usr/bin/env python3
"""
Ingest repo ``data/`` (markdown/JSON catalog) into Weaviate for SK Group.

Skips ``data/scripts/`` (operational Python and stray files).

Requires ``WEAVIATE_URL`` (and ``WEAVIATE_API_KEY`` on cloud). Optional:
``DATABASE_URL`` is not required if collection is derived from the company UUID.

Usage (from repository root):

    python data/scripts/ingest_sk_group.py

Same as:

    python scripts/ingest_local_data.py --data-dir ./data \\
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
        str(_ROOT / "data"),
        "--company-id",
        str(SK_GROUP_COMPANY_ID),
        "--collection",
        collection,
    ]
    raise SystemExit(subprocess.call(cmd, cwd=str(_ROOT)))


if __name__ == "__main__":
    main()
