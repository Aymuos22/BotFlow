#!/usr/bin/env python3
"""Update WEAVIATE_URL and WEAVIATE_API_KEY in a .env file. Usage: script.py <path> <url> <api_key>"""
import sys
from pathlib import Path


def main() -> None:
    _, path_s, new_url, new_key = sys.argv
    p = Path(path_s)
    text = p.read_text()
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        if line.startswith("WEAVIATE_URL="):
            out.append(f"WEAVIATE_URL={new_url}")
        elif line.startswith("WEAVIATE_API_KEY="):
            out.append(f"WEAVIATE_API_KEY={new_key}")
        else:
            out.append(line)
    ending = "\n" if text.endswith("\n") else ""
    p.write_text("\n".join(out) + ending)
    print("patched", p)


if __name__ == "__main__":
    main()
