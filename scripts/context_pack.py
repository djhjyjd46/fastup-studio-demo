#!/usr/bin/env python3
"""context_pack — structured multi-folder context assembly in a single call.

Solves the problem of high token overhead and one-sided context by querying SQLite FTS
with folder-level quotas rather than global relevance (which tends to crowd out from a single folder).

Usage:
    python scripts/context_pack.py "warranties in proposal" --task text

Profiles define mandatory folder coverage. Folders with zero matches output a 'ПУСТО' token,
serving as an explicit negative fact rather than an invitation to hallucinate.
"""
import argparse
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "scripts" / "memory_index.db"

# Profile: folder -> minimum chunk quota. Order defines output sequence.
PROFILES = {
    "text": {
        "expert/": 3,        # Author voice and stance
        "cases/": 3,         # Live case studies and verified metrics
        "positioning/": 3,   # Offer, facts, objection handling
        "content/": 2,       # Brand voice, pipeline, published copy
        "geo/": 1,
    },
    "decision": {
        "decisions/": 4,     # Previously rejected options to prevent loops
        "business/": 3,      # Economics, margins, team structure
        "notes/raw/founder.md": 1,  # Founder profile
        "promotion/": 2,
        "positioning/": 2,
        "cases/": 2,        # Evidence base
        "TODO.md": 1,
    },
    "geo": {
        "geo/": 4,
        "playbook/": 3,
        "content/": 2,
        "positioning/": 2,
        "cases/": 2,
    },
    "site": {
        "integrations/": 3,
        "design/": 3,
        "playbook/": 3,
        "decisions/": 2,
    },
    "all": {
        "positioning/": 2, "cases/": 2, "expert/": 2, "decisions/": 2,
        "business/": 2, "geo/": 2, "content/": 2, "promotion/": 1,
        "playbook/": 1, "notes/": 1,
    },
}

CHUNK_CHARS = 1400   # Max characters per printed chunk
RAW_PREFIX = "notes/raw"  # Raw transcripts — excluded by default
# notes/raw lives in private repository fastup-private, available only on founder's machine
RAW_ALLOWED = {"notes/raw/founder.md"}


def fts_query(terms):
    """OR query across words: strict AND on long queries usually yields empty results."""
    words = [w for w in re.findall(r"\w+", terms) if len(w) > 2]
    if not words:
        return None
    return " OR ".join(words)


def pull(cur, match, folder, limit):
    like = folder.replace("/", os.sep) + ("" if folder.endswith(".md") else "%")
    sql = """
        SELECT c.file_path, c.header, c.start_line, c.end_line, c.content
        FROM memory_fts f JOIN memory_chunks c ON f.rowid = c.id
        WHERE memory_fts MATCH ? AND c.file_path LIKE ?
        ORDER BY rank LIMIT ?
    """
    try:
        cur.execute(sql, (match, like, limit * 3))
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        return []
    out = []
    seen_files = set()
    # At most 2 chunks per file to ensure folder diversity
    for r in rows:
        fp = r[0]
        if fp.replace(os.sep, "/").startswith(RAW_PREFIX) and folder not in RAW_ALLOWED:
            continue
        if list(seen_files).count(fp) >= 2 or sum(1 for x in out if x[0] == fp) >= 2:
            continue
        out.append(r)
        seen_files.add(fp)
        if len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description="Assemble multi-folder context pack for agent tasks.")
    ap.add_argument("query", help="search query")
    ap.add_argument("--task", default="all", choices=sorted(PROFILES), help="target task profile")
    ap.add_argument("--chars", type=int, default=CHUNK_CHARS, help="max chars per chunk")
    args = ap.parse_args()

    if not DB.exists():
        print("Memory index missing: run `python scripts/search_memory.py --reindex`", file=sys.stderr)
        return 1

    match = fts_query(args.query)
    if not match:
        print("Query too short.", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    profile = PROFILES[args.task]

    print(f"# Context Pack: '{args.query}' (profile: {args.task})\n")
    empty, total = [], 0

    for folder, quota in profile.items():
        rows = pull(cur, match, folder, quota)
        if not rows:
            empty.append(folder)
            continue
        print(f"\n{'=' * 70}\n## {folder}  ({len(rows)} of {quota})\n{'=' * 70}")
        for fp, header, s, e, content in rows:
            total += 1
            body = content.strip()
            cut = " …[truncated, read source file]" if len(body) > args.chars else ""
            print(f"\n### {fp}:{s}-{e} — {header}\n")
            print(body[: args.chars] + cut)

    print(f"\n{'=' * 70}")
    print(f"Total chunks: {total} across {len(profile)} profile folders.")
    if empty:
        print("ПУСТО (no records found in database for this query): " + ", ".join(empty))
    print("Pack is a starting ground. Always read key matched source files completely.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
