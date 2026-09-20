#!/usr/bin/env python3
"""Incident escalation utility for FastUp Studio.

Standardizes incident packaging when automation failure thresholds are reached.
Generates actionable escalation cards and optionally dispatches them to
FastUp Telegram topics (default: topic 626 'service', or topic 581 'tasks').

Usage:
    python scripts/escalate.py --task "SEO Audit" --error "Timeout connecting to client host" \
        --hypothesis "Client hosting blocks bot User-Agent" --action "Whitelisting required" \
        --topic service --notify

    # Dry-run preview without dispatching Telegram message
    python scripts/escalate.py --task "Yandex Direct" --error "Auth 401" --dry-run
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from tool_envelope import envelope_error, envelope_success
except ImportError:
    envelope_error = None
    envelope_success = None


def format_escalation_card(
    task: str,
    error: str,
    hypothesis: Optional[str] = None,
    action: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
) -> str:
    """Format a human-actionable incident report card in Markdown/HTML."""
    now_str = timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"🚨 <b>FASTUP ESCALATION INCIDENT</b>",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"📌 <b>Task / Workflow:</b> {task}",
        f"⏰ <b>Time:</b> {now_str}",
        f"❌ <b>Error:</b> <code>{error}</code>",
    ]
    if hypothesis:
        lines.append(f"💡 <b>Hypothesis:</b> {hypothesis}")
    if action:
        lines.append(f"👉 <b>Action Required:</b> {action}")
    if context:
        ctx_str = json.dumps(context, ensure_ascii=False, indent=2)
        lines.append(f"📦 <b>Context:</b> <pre>{ctx_str}</pre>")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Automation budget exhausted. Handed off to human operator.</i>")
    return "\n".join(lines)


def notify_telegram(message: str, topic: str = "service") -> bool:
    """Send an escalation message via tg_agent.py."""
    tg_script = SCRIPTS_DIR / "tg_agent.py"
    if not tg_script.exists():
        print(f"Warning: tg_agent.py not found at {tg_script}", file=sys.stderr)
        return False

    cmd = [sys.executable, str(tg_script), "send", message, "--topic", topic]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"Failed to dispatch Telegram escalation: {exc.stderr}", file=sys.stderr)
        return False


def escalate(
    task: str,
    error: str,
    hypothesis: Optional[str] = None,
    action: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    topic: str = "service",
    notify: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Core escalation engine function."""
    card = format_escalation_card(
        task=task,
        error=error,
        hypothesis=hypothesis,
        action=action,
        context=context,
    )

    dispatched = False
    if notify and not dry_run:
        dispatched = notify_telegram(card, topic=topic)

    return {
        "task": task,
        "error": error,
        "hypothesis": hypothesis,
        "action": action,
        "topic": topic,
        "card": card,
        "dispatched": dispatched,
        "dry_run": dry_run,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="FastUp Incident Escalation Utility")
    parser.add_argument("--task", required=True, help="Name of the failed task or workflow")
    parser.add_argument("--error", required=True, help="Error message or exception details")
    parser.add_argument("--hypothesis", default=None, help="Assumed root cause of the failure")
    parser.add_argument("--action", default=None, help="Required action from human operator")
    parser.add_argument("--topic", default="service", help="Target Telegram topic alias (default: service/626)")
    parser.add_argument("--context-json", default=None, help="Additional context data as JSON string")
    parser.add_argument("--notify", action="store_true", help="Send alert to Telegram topic")
    parser.add_argument("--dry-run", action="store_true", help="Preview escalation card without sending")
    parser.add_argument("--json", action="store_true", help="Output result as JSON envelope")

    args = parser.parse_args()

    context = None
    if args.context_json:
        try:
            context = json.loads(args.context_json)
        except json.JSONDecodeError as exc:
            print(f"Invalid --context-json: {exc}", file=sys.stderr)
            sys.exit(1)

    result = escalate(
        task=args.task,
        error=args.error,
        hypothesis=args.hypothesis,
        action=args.action,
        context=context,
        topic=args.topic,
        notify=args.notify,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n" + result["card"] + "\n")
        if result["dry_run"]:
            print("[DRY-RUN] Alert was not sent to Telegram.")
        elif result["dispatched"]:
            print(f"✅ Escalation successfully dispatched to Telegram topic '{args.topic}'.")
        elif args.notify:
            print(f"⚠️ Failed to dispatch escalation to Telegram topic '{args.topic}'.")


if __name__ == "__main__":
    main()
