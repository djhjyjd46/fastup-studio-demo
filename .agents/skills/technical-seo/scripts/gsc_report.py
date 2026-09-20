#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Pull query/page performance data from Google Search Console via the API.

Credentials come from .env or the process environment (GSC_SITE_URL,
GSC_SERVICE_ACCOUNT_JSON) — never hardcode here. See integrations/wordpress.md
for the same pattern used with WP_* vars; this follows it.

GSC_SITE_URL must match the property exactly as registered in Search Console:
  - URL-prefix property: "https://fastup.by/" (trailing slash)
  - Domain property:     "sc-domain:fastup.by"

GSC_SERVICE_ACCOUNT_JSON is the full service-account key JSON as one string.
The service account's client_email must be added as a user (read access is
enough) in Search Console → Settings → Users and permissions, on the exact
property above.

Usage:
    python3 scripts/gsc_report.py --dimensions query --days 28
    python3 scripts/gsc_report.py --dimensions page --days 28
    python3 scripts/gsc_report.py --dimensions query,page --days 28 --row-limit 50
    python3 scripts/gsc_report.py --dimensions date --days 28
    python3 scripts/gsc_report.py --dimensions query --page-filter /seo-prodvizhenie/
"""

import argparse
import io
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Windows-консоль по умолчанию не в UTF-8 — переключаем stdout, иначе кириллица
# в выводе превращается в "?"/"".
if sys.platform == "win32" and hasattr(sys.stdout, "buffer") and not getattr(sys.stdout, "_is_utf8_wrapped", False):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stdout._is_utf8_wrapped = True
    except Exception:
        pass

SEARCH_ANALYTICS_URL = "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def load_env():
    """Load GSC_* from .env (repo root) if present, else process env."""
    from env_load import env_file_path  # из worktree — .env основной копии
    env_path = env_file_path()
    values = {}
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        # GSC_SITE_URL is a single line; GSC_SERVICE_ACCOUNT_JSON spans until
        # its balanced closing brace (may contain literal newlines).
        for key in ("GSC_SITE_URL", "GSC_SERVICE_ACCOUNT_JSON"):
            marker = f"{key}="
            idx = content.find(marker)
            if idx == -1:
                continue
            rest = content[idx + len(marker):]
            if key == "GSC_SERVICE_ACCOUNT_JSON":
                start = rest.index("{")
                depth = 0
                end = None
                for i, ch in enumerate(rest[start:], start):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                values[key] = rest[start:end]
            else:
                values[key] = rest.splitlines()[0].strip()

    # Prefer values from .env if available, since setx truncates environment variables >1024 chars
    sa_json = values.get("GSC_SERVICE_ACCOUNT_JSON") or os.environ.get("GSC_SERVICE_ACCOUNT_JSON")
    site_url = values.get("GSC_SITE_URL") or os.environ.get("GSC_SITE_URL")

    if not site_url or not sa_json:
        sys.exit(
            "GSC_SITE_URL / GSC_SERVICE_ACCOUNT_JSON не найдены ни в процессе, ни в .env.\n"
            "См. integrations/wordpress.md для того же паттерна с WP_*."
        )
    return site_url, sa_json


def get_credentials(sa_json_str):
    from google.oauth2 import service_account

    info = json.loads(sa_json_str)
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def query(site_url, credentials, dimensions, days, row_limit, page_filter, query_filter, start_row):
    from google.auth.transport.requests import AuthorizedSession

    session = AuthorizedSession(credentials)
    end_date = date.today() - timedelta(days=3)  # GSC data has ~2-3 day lag
    start_date = end_date - timedelta(days=days - 1)

    body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "startRow": start_row,
    }

    filters = []
    if page_filter:
        filters.append({"dimension": "page", "operator": "contains", "expression": page_filter})
    if query_filter:
        filters.append({"dimension": "query", "operator": "contains", "expression": query_filter})
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]

    from urllib.parse import quote
    url = SEARCH_ANALYTICS_URL.format(site=quote(site_url, safe=""))
    resp = session.post(url, json=body)
    if resp.status_code != 200:
        sys.exit(f"GSC API error {resp.status_code}: {resp.text}")
    return resp.json(), start_date, end_date


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dimensions", default="query", help="comma-separated: query,page,date,device,country")
    ap.add_argument("--days", type=int, default=28, help="window size ending ~3 days ago (GSC lag)")
    ap.add_argument("--row-limit", type=int, default=25000, help="max rows per request (API max 25000)")
    ap.add_argument("--start-row", type=int, default=0)
    ap.add_argument("--page-filter", default=None, help="substring filter on page URL")
    ap.add_argument("--query-filter", default=None, help="substring filter on query text")
    ap.add_argument("--json", action="store_true", help="print raw JSON instead of a table")
    args = ap.parse_args()

    site_url, sa_json = load_env()
    credentials = get_credentials(sa_json)
    dims = [d.strip() for d in args.dimensions.split(",") if d.strip()]

    data, start_date, end_date = query(
        site_url, credentials, dims, args.days, args.row_limit,
        args.page_filter, args.query_filter, args.start_row,
    )

    rows = data.get("rows", [])
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    print(f"# {site_url} — {start_date.isoformat()} .. {end_date.isoformat()} ({len(rows)} строк)")
    header = dims + ["clicks", "impressions", "ctr", "position"]
    print("\t".join(header))
    for row in rows:
        keys = row.get("keys", [])
        ctr = f"{row['ctr'] * 100:.2f}%"
        position = f"{row['position']:.2f}"
        print("\t".join([*keys, str(row["clicks"]), str(row["impressions"]), ctr, position]))


if __name__ == "__main__":
    main()
