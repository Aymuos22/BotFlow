#!/usr/bin/env python3
"""Normalize API .env: LF only, single SUPABASE_JWT_SECRET line."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
lines = text.splitlines()
jwt = None
out: list[str] = []
for line in lines:
    if line.startswith("SUPABASE_JWT_SECRET="):
        v = line.split("=", 1)[1].strip()
        if jwt is None:
            jwt = v
        continue
    out.append(line)
if jwt:
    out.append(f"SUPABASE_JWT_SECRET={jwt}")
p.write_text("\n".join(out) + "\n", encoding="utf-8")
