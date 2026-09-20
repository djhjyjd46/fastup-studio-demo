#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""FastUp tools runner on hosting (tools.fastup.by): CRM and knowledge base via CLI.

Works identically across Claude Code and Antigravity: requires no MCP client configuration,
only a personal token in `.env` (FASTUP_TOOLS_TOKEN). Tool permissions depend on the token:
Egor has full access; Evgeniy has read access plus deal payment and feed notes.

Usage:
    python scripts/tools.py list                          # list available tools
    python scripts/tools.py schema crm_list_tasks         # show tool parameter schema
    python scripts/tools.py crm_search_leads q=Acme       # call tool: key=value
    python scripts/tools.py crm_get_lead id=911
    python scripts/tools.py crm_sql_query --json args.json # complex parameters via JSON file
    echo '{"q": "Acme"}' | python scripts/tools.py crm_search_leads --json -

Values in `key=value`: numbers, true/false, and JSON arrays/objects are auto-parsed;
everything else is treated as string. Tool output is printed to stdout as returned (usually JSON).
Exit code 1: tool returned an error; Exit code 2: missing token or network error.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_load import load_env  # noqa: E402

DEFAULT_URL = "https://tools.fastup.by/mcp"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def die(message, code=2):
    print(message, file=sys.stderr)
    sys.exit(code)


def rpc(method, params):
    load_env()
    token = os.environ.get("FASTUP_TOOLS_TOKEN", "").strip()
    if not token:
        die("Missing FASTUP_TOOLS_TOKEN in .env — personal token is provisioned by Egor")
    url = os.environ.get("FASTUP_TOOLS_URL", "").strip() or DEFAULT_URL
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        # Hosting nginx drops requests without a browser-like User-Agent
        "User-Agent": "Mozilla/5.0 (compatible; FastUp-Tools/1.0)",
    })
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        if error.code == 401:
            die("Tools server rejected token (401) — verify FASTUP_TOOLS_TOKEN in .env")
        die(f"Tools server responded with HTTP {error.code}")
    except (urllib.error.URLError, TimeoutError) as error:
        die(f"Tools server unreachable: {error}")
    # Streamable HTTP may return SSE: extract 'data:' line if present
    data = next((line[5:].strip() for line in body.splitlines() if line.startswith("data:")), body)
    message = json.loads(data)
    if "error" in message:
        die(f"Protocol error: {message['error'].get('message')}", 1)
    return message["result"]


def list_tools():
    return rpc("tools/list", {})["tools"]


def parse_value(raw):
    # If explicitly quoted (e.g. parent_number='33' or parent_number="33"), preserve as string
    if len(raw) >= 2 and ((raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'"))):
        return raw[1:-1]
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def parse_args(items):
    args, json_source = {}, None
    it = iter(items)
    for item in it:
        if item == "--json":
            json_source = next(it, None)
            if json_source is None:
                die("Path to file or '-' required after --json", 2)
        elif "=" in item:
            key, _, value = item.partition("=")
            args[key] = parse_value(value)
        else:
            die(f"Invalid argument '{item}' — expected key=value or --json file", 2)
    if json_source is not None:
        if json_source == "-":
            text = sys.stdin.buffer.read().decode("utf-8", "replace") if hasattr(sys.stdin, "buffer") else sys.stdin.read()
        else:
            text = Path(json_source).read_text(encoding="utf-8-sig")
        args = {**json.loads(text), **args}
    return args


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    command = argv[0]

    if command == "list":
        for tool in list_tools():
            first_line = (tool.get("description") or "").strip().split("\n")[0]
            print(f"{tool['name']:34} {first_line[:110]}")
        return

    if command == "schema":
        if len(argv) < 2:
            die("Specify tool name: tools.py schema <name>", 2)
        tool = next((t for t in list_tools() if t["name"] == argv[1]), None)
        if not tool:
            die(f"Tool '{argv[1]}' not found or unavailable for this token", 1)
        print(tool.get("description", ""))
        print(json.dumps(tool.get("inputSchema", {}), ensure_ascii=False, indent=2))
        return

    result = rpc("tools/call", {"name": command, "arguments": parse_args(argv[1:])})
    text = "\n".join(part.get("text", "") for part in result.get("content", []) if part.get("type") == "text")
    print(text)
    if result.get("isError"):
        sys.exit(1)


if __name__ == "__main__":
    main()
