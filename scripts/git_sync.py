#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Automated git synchronization hook for AI agents — hands-off git workflow.

Keeps repository synchronized between Egor and Evgeniy on branch 'main':
  start — SessionStart / PreInvocation: fetch, and if origin/main is ahead: pull --rebase --autostash.
  stop  — Turn stop: if new uncommitted changes exist, remind agent to commit;
          if commits are ahead of GitHub: pull --rebase and push.

Clients:
  --client claude       .claude/settings.json: SessionStart / Stop
  --client antigravity  .agents/hooks.json: PreInvocation / Stop

Non-blocking: network failures, conflicts, or foreign branches emit warnings with exit code 0.
Internal sync state is tracked in .git/fastup-sync/ (outside working tree, not committed).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".git" / "fastup-sync"
BRANCH = "main"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def git(*args, timeout=25, raw=False):
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        out = r.stdout or ""
        # Porcelain output starts with whitespace (' M path') — strip would truncate the status column
        return r.returncode, (out if raw else out.strip()), (r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as e:
        return 127, "", str(e)


def read_input():
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        return json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        return {}


def session_key(data):
    key = data.get("session_id") or data.get("conversationId") or "manual"
    return "".join(c for c in str(key) if c.isalnum() or c in "-_")[:80] or "manual"


def dirty_snapshot():
    """Return {path: mtime} of uncommitted files (gitignores are omitted)."""
    code, out, _ = git("status", "--porcelain=v1", "-z", "--untracked-files=all", raw=True)
    if code != 0:
        return {}
    snap = {}
    parts = out.split("\0")
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            i += 1  # Rename entries are followed by the old path
        try:
            snap[path] = (ROOT / path).stat().st_mtime
        except OSError:
            snap[path] = -1.0
    return snap


def load_snapshot(key):
    try:
        return json.loads((STATE / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_snapshot(key, snap):
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        (STATE / f"{key}.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def current_branch():
    return git("rev-parse", "--abbrev-ref", "HEAD")[1]


def pull():
    """Pull origin/main if remote is ahead. Returns message for agent or ''."""
    code, _, err = git("fetch", "origin", BRANCH, "--quiet")
    if code != 0:
        return f"git_sync: fetch failed ({err[:120]}) — continuing on local copy, pull later."
    behind = git("rev-list", "--count", f"HEAD..origin/{BRANCH}")[1]
    if not behind or behind == "0":
        return ""
    code, _, err = git("pull", "--rebase", "--autostash", "origin", BRANCH, timeout=60)
    if code != 0:
        git("rebase", "--abort")
        return (f"git_sync: pull failed (conflict or local modifications: {err[:160]}). "
                "Resolve conflicts before modifying shared files.")
    return f"git_sync: pulled {behind} commit(s) from GitHub."


def push():
    ahead = git("rev-list", "--count", f"origin/{BRANCH}..HEAD")[1]
    if not ahead or ahead == "0":
        return ""
    code, _, err = git("pull", "--rebase", "--autostash", "origin", BRANCH, timeout=60)
    if code != 0:
        git("rebase", "--abort")
        return f"git_sync: push postponed — pre-push pull failed ({err[:160]}). Resolve conflict."
    code, _, err = git("push", "origin", BRANCH, timeout=60)
    if code != 0:
        return f"git_sync: push failed ({err[:160]})."
    return f"git_sync: pushed {ahead} commit(s) to GitHub."


def emit(client, event, text="", block_reason=""):
    if client == "antigravity":
        if block_reason:
            print(json.dumps({"decision": "continue", "reason": block_reason}, ensure_ascii=False))
        elif text and event == "start":
            print(json.dumps({"injectSteps": [{"ephemeralMessage": text}]}, ensure_ascii=False))
        else:
            print("{}")
        return 0
    if block_reason:
        print(block_reason, file=sys.stderr)
        return 2
    if text:
        print(text)
    return 0


def run_start(client, data):
    key = session_key(data)
    if client == "antigravity":
        marker = STATE / f"{key}.started"
        if marker.exists():
            return emit(client, "start")
        try:
            STATE.mkdir(parents=True, exist_ok=True)
            marker.write_text("1", encoding="utf-8")
        except OSError:
            pass
    branch = current_branch()
    if branch != BRANCH:
        return emit(client, "start", f"git_sync: session on branch '{branch}', but working on '{BRANCH}' — please switch.")
    text = pull()
    save_snapshot(key, dirty_snapshot())
    return emit(client, "start", text)


def run_stop(client, data):
    if client == "antigravity" and data.get("fullyIdle") is False:
        return emit(client, "stop")
    if current_branch() != BRANCH:
        return emit(client, "stop")
    key = session_key(data)
    before = load_snapshot(key)
    now = dirty_snapshot()
    save_snapshot(key, now)  # Next stop only checks fresh edits to prevent infinite loops
    fresh = sorted(p for p, m in now.items() if before.get(p) != m)
    if fresh and not data.get("stop_hook_active"):
        shown = ", ".join(fresh[:10]) + (f" and {len(fresh) - 10} more" if len(fresh) > 10 else "")
        return emit(client, "stop", block_reason=(
            f"git_sync: uncommitted edits detected this turn: {shown}. "
            "Please commit edits made by this session with a meaningful message and push."
        ))
    return emit(client, "stop", push())


def main():
    ap = argparse.ArgumentParser(description="Git synchronization hook for AI agent sessions.")
    ap.add_argument("mode", choices=["start", "stop"])
    ap.add_argument("--client", choices=["claude", "antigravity"], default="claude")
    args = ap.parse_args()
    data = read_input()
    try:
        code = run_start(args.client, data) if args.mode == "start" else run_stop(args.client, data)
    except Exception as e:  # Hook must never crash agent session
        print(f"git_sync: skipped ({e})", file=sys.stderr)
        if args.client == "antigravity":
            print("{}")
        code = 0
    sys.exit(code)


if __name__ == "__main__":
    main()
