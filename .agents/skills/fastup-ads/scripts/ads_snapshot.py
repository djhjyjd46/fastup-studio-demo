#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Снимок всех рекламных данных за день в один JSON — сырьё для разбора.

    python scripts/ads_snapshot.py                 # снимок за 7 дней в ads/snapshots/
    python scripts/ads_snapshot.py --days 30 --print

Собирает в одном файле то, что иначе пришлось бы тянуть из четырёх мест:

    Директ    — кампания, стратегия, лимиты, баланс, фразы, данные торгов,
                открутка по фразам и по дням, реальные поисковые запросы
    Метрика   — визиты, источники, цели, поведение рекламного трафика
    Вебмастер — запросы, по которым сайт показывается в органике, позиции
    Wordstat  — сезонность спроса по базисам (кэш 30 дней, дёргается редко)

Скрипт только собирает и считает. Выводы делает `ads-analyst` по этому файлу.
Ключи — из `.env` (см. scripts/env_load.py).
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_load import load_env, require

ROOT = Path(__file__).resolve().parent.parent
V5 = "https://api.direct.yandex.com/json/v5/"
V501 = "https://api.direct.yandex.com/json/v501/"
V4 = "https://api.direct.yandex.ru/live/v4/json/"
METRIKA = "https://api-metrika.yandex.net"
WEBMASTER = "https://api.webmaster.yandex.net/v4"
WORDSTAT = "https://searchapi.api.cloud.yandex.net/v2/wordstat"
SEASON_CACHE_DAYS = 30


def _json(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        return json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": "HTTP {}: {}".format(e.code, e.read().decode("utf-8")[:200])}
    except Exception as e:  # сеть, таймаут — снимок не должен падать целиком
        return {"_error": "{}: {}".format(type(e).__name__, str(e)[:150])}


# ---------- Директ ----------

def direct(service, method, params, token, base=V5):
    body = json.dumps({"method": method, "params": params}, ensure_ascii=False).encode("utf-8")
    d = _json(base + service, body, {"Authorization": "Bearer " + token, "Accept-Language": "ru",
                                     "Content-Type": "application/json; charset=utf-8"})
    if "_error" in d:
        return d
    return d.get("result", {"_error": d.get("error")})


def direct_report(cid, token, days, fields, rtype):
    to = date.today()
    frm = to - timedelta(days=days)
    body = json.dumps({"params": {
        "SelectionCriteria": {"Filter": [{"Field": "CampaignId", "Operator": "IN", "Values": [str(cid)]}],
                              "DateFrom": frm.isoformat(), "DateTo": to.isoformat()},
        "FieldNames": fields, "ReportName": "snap-{}".format(int(time.time() * 1000)),
        "ReportType": rtype, "DateRangeType": "CUSTOM_DATE", "Format": "TSV",
        "IncludeVAT": "NO", "IncludeDiscount": "NO"}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(V5 + "reports", data=body, headers={
        "Authorization": "Bearer " + token, "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8", "processingMode": "auto",
        "returnMoneyInMicros": "false", "skipReportHeader": "true", "skipReportSummary": "true"})
    for _ in range(20):
        try:
            resp = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            return {"_error": "{}: {}".format(e.code, e.read().decode("utf-8")[:200])}
        if resp.status == 200:
            rows = [r.split("\t") for r in resp.read().decode("utf-8").strip().split("\n") if r.strip()]
            if len(rows) < 2:
                return []
            head = rows[0]
            return [dict(zip(head, r)) for r in rows[1:]]
        time.sleep(int(resp.headers.get("retryIn", 5)))
    return {"_error": "отчёт не подготовился"}


def collect_direct(cid, token, login, days):
    camp = direct("campaigns", "get", {"SelectionCriteria": {"Ids": [cid]},
        "FieldNames": ["Id", "Name", "State", "Status", "StatusClarification", "DailyBudget", "NegativeKeywords"],
        "UnifiedCampaignFieldNames": ["BiddingStrategy", "CounterIds"]}, token, V501)
    camp = (camp.get("Campaigns") or [{}])[0] if isinstance(camp, dict) else {}
    groups = direct("adgroups", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["Id", "Name", "RegionIds"]}, token).get("AdGroups", [])
    kws = direct("keywords", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["Id", "AdGroupId", "Keyword", "Bid", "State", "Status"]}, token).get("Keywords", [])
    ads = direct("ads", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["Id", "AdGroupId", "State", "Status"],
        "TextAdFieldNames": ["Title", "Text", "Href"]}, token).get("Ads", [])

    bids = direct("keywordbids", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["KeywordId"], "SearchFieldNames": ["Bid", "AuctionBids"]}, token).get("KeywordBids", [])
    names = {k["Id"]: k["Keyword"] for k in kws}
    market = []
    for row in bids:
        items = ((row.get("Search") or {}).get("AuctionBids") or {}).get("AuctionBidItems") or []
        phrase = names.get(row["KeywordId"], "")
        if not items or phrase.startswith("---"):
            continue
        by = {i["TrafficVolume"]: i["Price"] / 1e6 for i in items}

        def near(t):
            close = [v for v in by if abs(v - t) <= 4]
            return round(by[min(close, key=lambda v: abs(v - t))], 2) if close else None
        market.append({"phrase": phrase, "price_15": near(15), "price_62": near(62),
                       "price_85": near(85), "price_100": near(100)})

    acc = _json(V4, json.dumps({"method": "AccountManagement", "token": token, "locale": "ru",
        "param": {"Action": "Get", "SelectionCriteria": {"Logins": [login]}}},
        ensure_ascii=False).encode("utf-8"), {"Content-Type": "application/json; charset=utf-8"})
    amount = (acc.get("data", {}).get("Accounts") or [{}])[0].get("Amount")

    strat = (camp.get("UnifiedCampaign") or {}).get("BiddingStrategy", {})
    search = strat.get("Search", {})
    body = next((v for v in search.values() if isinstance(v, dict) and
                 ("WeeklySpendLimit" in v or "AverageCpc" in v)), {})

    return {
        "campaign": {"id": cid, "name": camp.get("Name"), "state": camp.get("State"),
                     "status": camp.get("Status"), "clarification": camp.get("StatusClarification"),
                     "strategy_search": search.get("BiddingStrategyType"),
                     "strategy_network": strat.get("Network", {}).get("BiddingStrategyType"),
                     "average_cpc": body.get("AverageCpc", 0) / 1e6 or None,
                     "weekly_limit": body.get("WeeklySpendLimit", 0) / 1e6 or None,
                     "daily_budget": (camp.get("DailyBudget") or {}).get("Amount", 0) / 1e6 or None,
                     "counters": (camp.get("UnifiedCampaign") or {}).get("CounterIds", {}).get("Items"),
                     "balance": amount},
        "negative_keywords": (camp.get("NegativeKeywords") or {}).get("Items", []),
        "groups": [{"id": g["Id"], "name": g["Name"], "regions": g.get("RegionIds")} for g in groups],
        "keywords": [{"id": k["Id"], "group": k["AdGroupId"], "phrase": k["Keyword"],
                      "bid": k.get("Bid", 0) / 1e6, "status": k.get("Status")} for k in kws],
        "ads": [{"id": a["Id"], "group": a["AdGroupId"], "state": a["State"], "status": a["Status"],
                 "title": (a.get("TextAd") or {}).get("Title")} for a in ads],
        "market_prices": sorted(market, key=lambda m: -(m["price_100"] or 0)),
        "performance": direct_report(cid, token, days,
            ["Date", "Criteria", "CriteriaType", "Impressions", "Clicks", "Cost", "AvgCpc",
             "Slot", "Device", "Conversions"], "CUSTOM_REPORT"),
        "search_queries": direct_report(cid, token, days,
            ["Query", "Criteria", "Impressions", "Clicks", "Cost"], "SEARCH_QUERY_PERFORMANCE_REPORT"),
    }


# ---------- Метрика ----------

def collect_metrika(counter, token, days):
    to = date.today()
    frm = to - timedelta(days=days)
    hdr = {"Authorization": "OAuth " + token}

    def stat(params):
        params.update({"ids": counter, "date1": frm.isoformat(), "date2": to.isoformat()})
        return _json(METRIKA + "/stat/v1/data?" + urllib.parse.urlencode(params, doseq=True), headers=hdr)

    goals = _json(METRIKA + "/management/v1/counter/{}/goals".format(counter), headers=hdr).get("goals", [])
    goal_metrics = ["ym:s:goal{}reaches".format(g["id"]) for g in goals[:10]]

    sources = stat({"metrics": "ym:s:visits,ym:s:bounceRate,ym:s:avgVisitDurationSeconds,ym:s:pageDepth",
                    "dimensions": "ym:s:lastSignTrafficSource", "limit": 20})
    ad_pages = stat({"metrics": "ym:s:visits,ym:s:bounceRate,ym:s:avgVisitDurationSeconds",
                     "dimensions": "ym:s:startURL",
                     "filters": "ym:s:lastSignTrafficSource=='ad'", "limit": 20})
    conv = stat({"metrics": ",".join(["ym:s:visits"] + goal_metrics)}) if goal_metrics else {}
    ad_conv = stat({"metrics": ",".join(["ym:s:visits"] + goal_metrics),
                    "filters": "ym:s:lastSignTrafficSource=='ad'"}) if goal_metrics else {}

    def rows(d, names):
        return [{"name": r["dimensions"][0]["name"], **dict(zip(names, r["metrics"]))}
                for r in d.get("data", [])] if "data" in d else d

    return {
        "goals": [{"id": g["id"], "name": g["name"], "type": g.get("type")} for g in goals],
        "by_source": rows(sources, ["visits", "bounce_rate", "avg_seconds", "page_depth"]),
        "ad_landing_pages": rows(ad_pages, ["visits", "bounce_rate", "avg_seconds"]),
        "totals_all": dict(zip(["visits"] + [g["name"] for g in goals[:10]], conv.get("totals", []))),
        "totals_ad": dict(zip(["visits"] + [g["name"] for g in goals[:10]], ad_conv.get("totals", []))),
    }


# ---------- Вебмастер ----------

def collect_webmaster(user_id, host_id, token):
    base = "{}/user/{}/hosts/{}".format(WEBMASTER, user_id, urllib.parse.quote(host_id, safe=""))
    hdr = {"Authorization": "OAuth " + token}
    summary = _json(base + "/summary", headers=hdr)
    q = _json(base + "/search-queries/popular?order_by=TOTAL_SHOWS"
                     "&query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS"
                     "&query_indicator=AVG_SHOW_POSITION&limit=100", headers=hdr)
    queries = [{"query": x["query_text"],
                "shows": x.get("indicators", {}).get("TOTAL_SHOWS"),
                "clicks": x.get("indicators", {}).get("TOTAL_CLICKS"),
                "position": round(x.get("indicators", {}).get("AVG_SHOW_POSITION") or 0, 1)}
               for x in q.get("queries", [])] if "queries" in q else q
    return {"summary": summary, "organic_queries": queries}


# ---------- Wordstat: сезонность ----------

def collect_seasonality(seeds, regions, key, folder):
    cache = ROOT / "ads" / "campaigns" / "seasonality.json"
    if cache.exists():
        age = (time.time() - cache.stat().st_mtime) / 86400
        if age < SEASON_CACHE_DAYS:
            return json.loads(cache.read_text(encoding="utf-8"))

    today = date.today().replace(day=1)
    start = (today - timedelta(days=370)).replace(day=1)
    end = today - timedelta(days=1)
    out = {}
    for seed in seeds:
        d = _json(WORDSTAT + "/dynamics", json.dumps({
            "phrase": seed, "regions": regions, "folderId": folder, "period": "PERIOD_MONTHLY",
            "fromDate": start.isoformat() + "T00:00:00Z", "toDate": end.isoformat() + "T00:00:00Z"},
            ensure_ascii=False).encode("utf-8"),
            {"Authorization": "Api-Key " + key, "Content-Type": "application/json; charset=utf-8"})
        if "_error" in d:
            out[seed] = d
            continue
        out[seed] = [{"month": r["date"][:7], "count": int(r["count"])} for r in d.get("results", [])]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out")
    ap.add_argument("--print", action="store_true", dest="show")
    args = ap.parse_args()

    token = require("YANDEX_DIRECT_TOKEN")
    cid = int(require("DIRECT_CAMPAIGN_ID"))
    login = require("YANDEX_DIRECT_LOGIN")

    snap = {"taken_at": datetime.now().isoformat(timespec="seconds"), "period_days": args.days}
    print("Директ…", flush=True)
    snap["direct"] = collect_direct(cid, token, login, args.days)

    counters = snap["direct"]["campaign"].get("counters") or []
    if counters:
        print("Метрика…", flush=True)
        snap["metrika"] = collect_metrika(counters[0], token, args.days)

    if os.environ.get("YANDEX_OAUTH_TOKEN") and os.environ.get("YANDEX_USER_ID"):
        print("Вебмастер…", flush=True)
        snap["webmaster"] = collect_webmaster(os.environ["YANDEX_USER_ID"],
                                              os.environ["YANDEX_HOST_ID"], os.environ["YANDEX_OAUTH_TOKEN"])

    if os.environ.get("YANDEX_CLOUD_API_KEY"):
        print("Wordstat (сезонность)…", flush=True)
        seeds_file = ROOT / "ads" / "campaigns" / "razrabotka-seeds.json"
        seeds = json.loads(seeds_file.read_text(encoding="utf-8"))["seeds"][:6] if seeds_file.exists() else []
        if seeds:
            snap["seasonality"] = collect_seasonality(
                seeds, ["149"], os.environ["YANDEX_CLOUD_API_KEY"], os.environ["YANDEX_CLOUD_FOLDER_ID"])

    out = Path(args.out) if args.out else ROOT / "ads" / "snapshots" / "{}.json".format(date.today().isoformat())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    d = snap["direct"]
    perf = d["performance"] if isinstance(d["performance"], list) else []
    clicks = sum(int(r["Clicks"]) for r in perf)
    cost = sum(float(r["Cost"]) for r in perf)
    print("\nснимок: {}".format(out))
    print("  фраз {} · объявлений {} · минус-слов {} · баланс {}".format(
        len(d["keywords"]), len(d["ads"]), len(d["negative_keywords"]), d["campaign"]["balance"]))
    print("  за {} дн.: кликов {} · расход {:.2f}{}".format(
        args.days, clicks, cost, " · поисковых запросов {}".format(len(d["search_queries"]))
        if isinstance(d["search_queries"], list) else ""))
    for block in ("metrika", "webmaster", "seasonality"):
        if block in snap:
            print("  {}: собрано".format(block))
    if args.show:
        print(json.dumps(snap, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
