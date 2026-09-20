#!/usr/bin/env python3
"""Prints session card — the block between markers in positioning/facts.md.

Invoked by SessionStart hooks to inject critical grounding facts into session context.
Ensures core truths (identity, pricing format, claims we never make) are physically present in context.
Single source of truth is positioning/facts.md.
"""
import re
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FACTS = ROOT / "positioning" / "facts.md"
TODO = ROOT / "TODO.md"
START, END = "<!-- SESSION-CARD:START -->", "<!-- SESSION-CARD:END -->"
STALE_DAYS = 7          # Threshold age (days) after which an open item is considered stale


def stale_blocks():
    """TODO blocks with open tasks and header dates older than STALE_DAYS.

    Surfaced at session start to prevent stale items from being drowned under fresh entries.
    """
    if not TODO.exists():
        return []
    today = date.today()
    out = []
    blocks = re.split(r"^## ", TODO.read_text(encoding="utf-8"), flags=re.M)[1:]
    for b in blocks:
        title = b.split(chr(10), 1)[0].strip()
        body = b[len(title):]
        open_tasks = body.count("- [ ]")
        if not open_tasks:
            continue
        dates = re.findall(r"20\d\d-\d\d-\d\d", title)
        if not dates:
            continue
        try:
            age = (today - date.fromisoformat(sorted(dates)[-1])).days
        except ValueError:
            continue
        if age >= STALE_DAYS:
            out.append((age, open_tasks, title))
    return sorted(out, reverse=True)


def main() -> int:
    if not FACTS.exists():
        return 0
    text = FACTS.read_text(encoding="utf-8")
    try:
        body = text.split(START, 1)[1].split(END, 1)[0]
    except IndexError:
        print(f"[session_card] markers not found in {FACTS.name} — card omitted",
              file=sys.stderr)
        return 0
    print(body.strip())

    stale = stale_blocks()
    if stale:
        print(chr(10) + "**Stale items in TODO (>7 days) — resolve or archive before taking new tasks:**")
        for age, tasks, title in stale[:6]:
            print("- {}d old · {} open · {}".format(age, tasks, title[:80]))
        print("If an item is obsolete, declare it and archive rather than silently postponing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
