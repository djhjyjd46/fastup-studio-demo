#!/usr/bin/env python3
"""
Universal FastUp Studio domain tool dispatcher.

Usage:
    python scripts/run.py <script_name> [args...]
    python scripts/run.py --list

Examples:
    python scripts/run.py geo_check --engine all
    python scripts/run.py direct_status
    python scripts/run.py tools
    python scripts/run.py gsc_report
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Search candidates in order of preference
SKILL_ROOTS = [
    REPO_ROOT / ".claude" / "skills",
    REPO_ROOT / ".agents" / "skills",
]


def discover_tools() -> dict[str, tuple[str, Path]]:
    """
    Discover all domain tools located inside skills/scripts.
    Returns: {tool_name: (skill_name, absolute_script_path)}
    """
    tools: dict[str, tuple[str, Path]] = {}
    for skill_root in SKILL_ROOTS:
        if not skill_root.exists():
            continue
        for skill_dir in sorted(skill_root.iterdir()):
            if not skill_dir.is_dir():
                continue
            scripts_dir = skill_dir / "scripts"
            if not scripts_dir.exists():
                continue
            for script_file in sorted(scripts_dir.glob("*.py")):
                tool_name = script_file.stem
                if tool_name not in tools:
                    tools[tool_name] = (skill_dir.name, script_file)
    return tools


def print_tool_list(tools: dict[str, tuple[str, Path]]) -> None:
    """Print a clean formatted list of all available domain tools."""
    print("\nAvailable FastUp Studio Domain Tools:\n" + "=" * 60)
    by_skill: dict[str, list[str]] = {}
    for tool_name, (skill_name, _) in tools.items():
        by_skill.setdefault(skill_name, []).append(tool_name)

    for skill_name, tool_names in sorted(by_skill.items()):
        print(f"\nSkill [{skill_name}]:")
        for tool in sorted(tool_names):
            print(f"  python scripts/run.py {tool}")
    print("\n" + "=" * 60)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print(__doc__.strip())
        print("\nTip: Run 'python scripts/run.py --list' to see all available tools.")
        sys.exit(0)

    tools = discover_tools()

    if sys.argv[1] in ("--list", "list", "-l"):
        print_tool_list(tools)
        sys.exit(0)

    target_name = sys.argv[1]
    if target_name.endswith(".py"):
        target_name = target_name[:-3]

    if target_name not in tools:
        print(f"Error: Unknown tool '{sys.argv[1]}'.", file=sys.stderr)
        # Offer fuzzy suggestions if close
        similar = [t for t in tools if target_name in t or t in target_name]
        if similar:
            print(f"Did you mean: {', '.join(similar)}?", file=sys.stderr)
        else:
            print("Run 'python scripts/run.py --list' to see all available tools.", file=sys.stderr)
        sys.exit(1)

    skill_name, target_path = tools[target_name]

    # Ensure repository root and target script directory are in sys.path
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if str(target_path.parent) not in sys.path:
        sys.path.insert(0, str(target_path.parent))

    # Reconstruct sys.argv for the target script (stripping run.py)
    sys.argv = [str(target_path)] + sys.argv[2:]

    # Execute target script in place
    runpy.run_path(str(target_path), run_name="__main__")


if __name__ == "__main__":
    main()
