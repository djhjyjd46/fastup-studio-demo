#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Pull search query performance data from Yandex.Webmaster via the API.

Credentials come from .env or the process environment (YANDEX_OAUTH_TOKEN,
YANDEX_USER_ID, YANDEX_HOST_ID) — never hardcode here. Same pattern as
GSC_* in scripts/gsc_report.py and WP_* in integrations/wordpress.md.

Setup (one-time, must be done by a human in a browser — see
integrations/yandex-webmaster.md for the full walkthrough):
  1. Register an app at https://oauth.yandex.ru/client/new
     (platform: веб-сервисы, redirect URI: https://oauth.yandex.ru/verification_code,
     scopes: webmaster:hostinfo + webmaster:verify)
  2. Open https://oauth.yandex.ru/authorize?response_type=token&client_id=<ClientID>,
     log in, copy the token from the result page. Token is valid ~180 days.
  3. Run this script once with --discover to find YANDEX_USER_ID and
     YANDEX_HOST_ID automatically from the token, then save all three to .env.

Important differences from the Google Search Console script:
  - Yandex's API has no per-page breakdown like GSC's "page" dimension —
    it returns query-level stats for the whole host only. Don't expect
    --page-filter here; it doesn't exist on this API.
  - "Position" here means AVG_SHOW_POSITION (average position among all
    impressions), roughly comparable to GSC's "position" but not identical
    in methodology — don't treat the two numbers as directly interchangeable.

Usage:
    python3 scripts/yandex_webmaster_report.py --discover
    python3 scripts/yandex_webmaster_report.py --days 28
    python3 scripts/yandex_webmaster_report.py --days 28 --limit 50 --order-by TOTAL_SHOWS
    python3 scripts/yandex_webmaster_report.py --days 28 --all > geo/2026-08-08-yandex-webmaster-zamer.md
"""

import argparse
import io
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "buffer") and not getattr(sys.stdout, "_is_utf8_wrapped", False):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stdout._is_utf8_wrapped = True
    except Exception:
        pass

API_BASE = "https://api.webmaster.yandex.net/v4"


def load_env():
    """Load YANDEX_* from .env (repo root) if present, else process env."""
    from env_load import env_file_path  # из worktree — .env основной копии
    env_path = env_file_path()
    values = {}
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        for key in ("YANDEX_OAUTH_TOKEN", "YANDEX_USER_ID", "YANDEX_HOST_ID"):
            marker = f"{key}="
            idx = content.find(marker)
            if idx == -1:
                continue
            rest = content[idx + len(marker):]
            values[key] = rest.splitlines()[0].strip()

    token = os.environ.get("YANDEX_OAUTH_TOKEN") or values.get("YANDEX_OAUTH_TOKEN")
    user_id = os.environ.get("YANDEX_USER_ID") or values.get("YANDEX_USER_ID")
    host_id = os.environ.get("YANDEX_HOST_ID") or values.get("YANDEX_HOST_ID")

    if not token:
        sys.exit(
            "YANDEX_OAUTH_TOKEN не найден ни в процессе, ни в .env.\n"
            "См. integrations/yandex-webmaster.md — токен получает человек в браузере,\n"
            "агент не может пройти OAuth-логин сам."
        )
    return token, user_id, host_id


def api_get(token, path):
    import requests

    resp = requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"OAuth {token}"},
    )
    if resp.status_code != 200:
        sys.exit(f"Yandex.Webmaster API error {resp.status_code}: {resp.text}")
    return resp.json()


def discover(token):
    """Print user-id and available hosts so they can be saved to .env."""
    user = api_get(token, "/user")
    user_id = user["user_id"]
    print(f"YANDEX_USER_ID={user_id}")

    hosts = api_get(token, f"/user/{user_id}/hosts")
    for h in hosts.get("hosts", []):
        print(f"# {h.get('unicode_host_url', '?')} verified={h.get('verified')}")
        print(f"YANDEX_HOST_ID={h.get('host_id')}")


def recrawl(token, user_id, host_id, url):
    """Queue a single URL for Yandex to re-crawl. Doesn't force an instant
    re-index — just moves the page up the crawl queue. Recalculating the
    snippet after the crawl can still take hours to a couple of days.
    Daily quota is per-account, shared across all verified hosts."""
    import requests

    resp = requests.post(
        f"{API_BASE}/user/{user_id}/hosts/{host_id}/recrawl/queue",
        headers={"Authorization": f"OAuth {token}", "Content-Type": "application/json"},
        json={"url": url},
    )
    if resp.status_code != 202:
        sys.exit(f"Recrawl request failed {resp.status_code}: {resp.text}")
    data = resp.json()
    print(f"OK task_id={data.get('task_id')} quota_remainder={data.get('quota_remainder')}")


def query(token, user_id, host_id, days, limit, order_by, offset=0):
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    path = (
        f"/user/{user_id}/hosts/{host_id}/search-queries/popular"
        f"?order_by={order_by}"
        f"&query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS"
        f"&query_indicator=AVG_SHOW_POSITION&query_indicator=AVG_CLICK_POSITION"
        f"&date_from={start_date.isoformat()}&date_to={end_date.isoformat()}"
        f"&limit={limit}&offset={offset}"
    )
    data = api_get(token, path)
    return data, start_date, end_date


def query_all(token, user_id, host_id, days, order_by, page_size=500):
    """Page through /search-queries/popular until every row (per data['count']) is fetched."""
    all_queries = []
    offset = 0
    total = None
    start_date = end_date = None
    while total is None or offset < total:
        data, start_date, end_date = query(token, user_id, host_id, days, page_size, order_by, offset)
        rows = data.get("queries", [])
        if not rows:
            break
        all_queries.extend(rows)
        total = data.get("count", len(all_queries))
        offset += len(rows)
    return {"queries": all_queries, "count": total or len(all_queries)}, start_date, end_date


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--discover", action="store_true", help="print YANDEX_USER_ID/YANDEX_HOST_ID for .env, then exit")
    ap.add_argument("--recrawl", metavar="URL", help="queue a single page URL for re-crawl, then exit")
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--limit", type=int, default=100, help="max rows per request (API max 500), ignored with --all")
    ap.add_argument("--all", action="store_true", help="page through every query the host has (API count), not just one page")
    ap.add_argument("--order-by", default="TOTAL_SHOWS", choices=["TOTAL_SHOWS", "TOTAL_CLICKS"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    token, user_id, host_id = load_env()

    if args.discover:
        discover(token)
        return

    if args.recrawl:
        if not user_id or not host_id:
            sys.exit(
                "YANDEX_USER_ID / YANDEX_HOST_ID не заданы. Запусти сперва:\n"
                "  python3 scripts/yandex_webmaster_report.py --discover\n"
                "и сохрани обе строки в .env."
            )
        recrawl(token, user_id, host_id, args.recrawl)
        return

    if not user_id or not host_id:
        sys.exit(
            "YANDEX_USER_ID / YANDEX_HOST_ID не заданы. Запусти сперва:\n"
            "  python3 scripts/yandex_webmaster_report.py --discover\n"
            "и сохрани обе строки в .env."
        )

    if args.all:
        data, start_date, end_date = query_all(token, user_id, host_id, args.days, args.order_by)
    else:
        data, start_date, end_date = query(token, user_id, host_id, args.days, args.limit, args.order_by)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    queries = data.get("queries", [])
    print(f"# host_id={host_id} — {start_date.isoformat()} .. {end_date.isoformat()} ({data.get('count', len(queries))} запросов всего, показано {len(queries)})")
    print("query\tshows\tclicks\tavg_show_pos\tavg_click_pos")
    def fmt_pos(value):
        # AVG_CLICK_POSITION may be present as a key but null when a query
        # had impressions with no clicks — can't average a position over zero clicks.
        return f"{value:.2f}" if isinstance(value, (int, float)) else ""

    for q in queries:
        ind = q.get("indicators", {})
        print("\t".join([
            q.get("query_text", ""),
            str(ind.get("TOTAL_SHOWS", "")),
            str(ind.get("TOTAL_CLICKS", "")),
            fmt_pos(ind.get("AVG_SHOW_POSITION")),
            fmt_pos(ind.get("AVG_CLICK_POSITION")),
        ]))


if __name__ == "__main__":
    main()
