#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Pull on-site behaviour data from Yandex.Metrika (Reporting API, stat/v1/data)
for the whole site — complements gsc_report.py (Google) and
yandex_webmaster_report.py (Yandex search) with the third layer: what visitors
actually do *after* landing, not just how they're found in search.

Credentials come from .env or the process environment (YANDEX_OAUTH_TOKEN) —
same pattern as GSC_*/WP_*. Same token as yandex_webmaster_report.py works
here too (app scope includes metrika:read) — no separate OAuth flow needed.
See integrations/yandex-metrika.md for the counter/token and the one hard
limitation this script works around.

IMPORTANT — known API restriction (found 2026-08-08, see
integrations/yandex-metrika.md and decisions/yandex-metrika-lead-enrichment-2026-08-08.md):
`ym:s:lastSearchPhrase` cannot be combined with `ym:s:clientID` in one request
(silently returns 0 rows). That only matters for per-visitor lookups (the lead
enrichment module). Site-wide aggregate reports here don't touch clientID at
all, so lastSearchPhrase works fine as its own dimension — just don't add
clientID to a request that also has lastSearchPhrase.

NOISE FILTERS (found 2026-08-08, see geo/2026-08-08-yandex-metrika-pervy-zamer.md):
Egor checks the live site often himself (VPN — shows up as a "New York" city
row alongside his real "Mogilev" — plus long idle tabs, internal navigation).
One clientID (1777990502174519885) alone accounted for ~29% of all visits in
the first 28-day pull. Default behaviour (no flag needed) excludes both that
clientID AND the whole "New York" city (the VPN exit node — in case he shows
up under a different clientID from the same node later). --include-self turns
both off. --search-only additionally keeps only ym:s:trafficSource=='organic'
(arrived via a search engine result) — drops direct/internal/bookmark visits.
Neither is a substitute for the durable fix: Egor should install Yandex's
official opt-out cookie/extension (https://yandex.ru/support/metrica/general/opt-out.html)
on his own browser(s) — that excludes his visits at the source (works across
VPN exit nodes, also cleans Webvisor and the live Metrika dashboard itself,
not just this script's reports).

Usage:
    python3 scripts/yandex_metrika_report.py --dimensions startURL --days 28
    python3 scripts/yandex_metrika_report.py --dimensions startURL --days 28 --search-only
    python3 scripts/yandex_metrika_report.py --dimensions regionCity --days 28
    python3 scripts/yandex_metrika_report.py --dimensions lastSearchEngineRoot --days 28
    python3 scripts/yandex_metrika_report.py --dimensions lastSearchPhrase --days 28 --limit 30
    python3 scripts/yandex_metrika_report.py --dimensions startURL --days 28 --json
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

API_URL = "https://api-metrika.yandex.net/stat/v1/data"
COUNTER_ID = "105197777"  # fastup.by, header.php / integrations/yandex-metrika.md

DEFAULT_METRICS = "ym:s:visits,ym:s:pageviews,ym:s:avgVisitDurationSeconds,ym:s:bounceRate"

# Egor's own browser/VPN, identified 2026-08-08 (см. NOISE FILTERS выше) — ~29% всех
# визитов в первом замере, прыгает между Mogilev (реальный город) и New York (VPN-нода).
# Не единственное устройство, с которого он заходит — просто самое частое; если найдёте
# ещё, дописать через запятую и обновить фильтр ниже.
EGOR_OWN_CLIENT_ID = "1777990502174519885"

# Тот же VPN-выход целиком (не только его clientID) — исключаем город, а не только один
# идентификатор, на случай если он зайдёт с этой же VPN-ноды с другого устройства/браузера
# (очищенные куки, другой профиль) и получит новый clientID под тем же городом.
EGOR_VPN_CITY = "New York"


def load_env():
    """Load YANDEX_OAUTH_TOKEN from .env (repo root) if present, else process env."""
    from env_load import env_file_path  # из worktree — .env основной копии
    env_path = env_file_path()
    value = None
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        marker = "YANDEX_OAUTH_TOKEN="
        idx = content.find(marker)
        if idx != -1:
            value = content[idx + len(marker):].splitlines()[0].strip()

    token = os.environ.get("YANDEX_OAUTH_TOKEN") or value
    if not token:
        sys.exit(
            "YANDEX_OAUTH_TOKEN не найден ни в процессе, ни в .env.\n"
            "См. integrations/yandex-webmaster.md — тот же токен, права metrika:read уже есть."
        )
    return token


def query(token, dimensions, metrics, days, limit, sort, filters=None, date1=None, date2=None):
    import requests

    # Явное окно (--date1/--date2) нужно, чтобы пересчитать прошлый замер тем же срезом:
    # без него любое сравнение с базовой линией упирается в «окно всегда кончается сегодня».
    if date2:
        end_date = date.fromisoformat(date2)
    else:
        end_date = date.today()
    if date1:
        start_date = date.fromisoformat(date1)
    else:
        start_date = end_date - timedelta(days=days - 1)

    params = {
        "ids": COUNTER_ID,
        "dimensions": ",".join(f"ym:s:{d}" for d in dimensions),
        "metrics": metrics,
        "date1": start_date.isoformat(),
        "date2": end_date.isoformat(),
        "limit": limit,
        "sort": sort,
    }
    if filters:
        params["filters"] = filters
    resp = requests.get(
        API_URL,
        headers={"Authorization": f"OAuth {token}", "Accept": "application/json"},
        params=params,
        timeout=15,
    )
    if resp.status_code != 200:
        sys.exit(f"Yandex.Metrika API error {resp.status_code}: {resp.text}")
    return resp.json(), start_date, end_date


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dimensions", default="startURL", help="comma-separated: startURL,regionCity,lastSearchEngineRoot,lastSearchPhrase")
    ap.add_argument("--metrics", default=DEFAULT_METRICS, help="comma-separated ym:s:* metric names")
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--date1", help="начало окна YYYY-MM-DD (вместо --days, для пересчёта прошлых замеров)")
    ap.add_argument("--date2", help="конец окна YYYY-MM-DD (по умолчанию сегодня)")
    ap.add_argument("--limit", type=int, default=50, help="max rows per request (API max ~10000)")
    ap.add_argument("--sort", default="-ym:s:visits")
    ap.add_argument("--search-only", action="store_true", help="только визиты из поисковых систем (ym:s:trafficSource=='organic') — убирает прямые заходы/закладки/внутреннюю навигацию")
    ap.add_argument("--include-self", action="store_true", help="не исключать EGOR_OWN_CLIENT_ID и город EGOR_VPN_CITY (по умолчанию оба исключены из отчёта)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    token = load_env()
    dims = [d.strip() for d in args.dimensions.split(",") if d.strip()]
    if "clientID" in dims and any("SearchPhrase" in d for d in dims):
        sys.exit(
            "clientID нельзя комбинировать с lastSearchPhrase в одном запросе — API молча\n"
            "вернёт 0 строк (см. integrations/yandex-metrika.md). Запрашивай их отдельными вызовами."
        )

    # Та же несовместимость, что и для dimensions выше, действует и на фильтры, причём шире:
    # запрос с searchPhrase молча возвращает 0 строк, если в filters упомянут clientID ИЛИ
    # regionCityName. Проверено прямыми вызовами 2026-08-16: без обоих — 37 строк, с любым
    # из них — ноль; фильтр по trafficSource при этом работает нормально. Похоже на
    # приватность API: поисковую фразу нельзя резать по признакам, сужающим до человека.
    # Из-за этого шумовые фильтры делали любой отчёт по фразам пустым, и это выглядело как
    # «Метрика не отдаёт поисковые фразы» — хотя отдаёт.
    wants_phrases = any("searchphrase" in d.lower() for d in dims)

    filter_parts = []
    if args.search_only:
        filter_parts.append("ym:s:trafficSource=='organic'")
    if not args.include_self:
        if wants_phrases:
            print(
                "# внимание: шумовые фильтры (clientID, город) сняты — они несовместимы с "
                "searchPhrase, иначе API молча вернёт 0 строк. Свои визиты в отчёте остаются.",
                file=sys.stderr,
            )
        else:
            filter_parts.append(f"ym:s:clientID!='{EGOR_OWN_CLIENT_ID}'")
            filter_parts.append(f"ym:s:regionCityName!='{EGOR_VPN_CITY}'")
    filters = " AND ".join(filter_parts) if filter_parts else None

    data, start_date, end_date = query(token, dims, args.metrics, args.days, args.limit, args.sort, filters, args.date1, args.date2)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    rows = data.get("data", [])
    total_rows = data.get("total_rows", len(rows))
    metric_names = [m.split(":")[-1] for m in args.metrics.split(",")]

    filter_note = f" [фильтры: {filters}]" if filters else ""
    print(f"# fastup.by (counter {COUNTER_ID}) — {start_date.isoformat()} .. {end_date.isoformat()} ({total_rows} строк всего, показано {len(rows)}){filter_note}")
    print("\t".join(dims + metric_names))

    for row in rows:
        dim_values = []
        for d in row.get("dimensions", []):
            # regionCity has {"name": "Minsk", "id": ..., "iso_name": ...}, most
            # dims have just {"name": ...}; lastSearchEngineRoot can be null (direct traffic).
            dim_values.append(d.get("name") or "(прямой заход/н-д)")
        met_values = []
        for i, v in enumerate(row.get("metrics", [])):
            if metric_names[i] == "avgVisitDurationSeconds":
                met_values.append(f"{v:.0f}с")
            elif metric_names[i] == "bounceRate":
                met_values.append(f"{v:.1f}%")
            else:
                met_values.append(f"{v:.0f}")
        print("\t".join([*dim_values, *met_values]))

    totals = data.get("totals", [])
    if totals:
        totals_fmt = []
        for i, v in enumerate(totals):
            if metric_names[i] == "avgVisitDurationSeconds":
                totals_fmt.append(f"{v:.0f}с")
            elif metric_names[i] == "bounceRate":
                totals_fmt.append(f"{v:.1f}%")
            else:
                totals_fmt.append(f"{v:.0f}")
        print(f"# итого по сайту: {', '.join(f'{n}={v}' for n, v in zip(metric_names, totals_fmt))}")


if __name__ == "__main__":
    main()
