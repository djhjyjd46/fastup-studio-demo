#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Comprehensive Yandex.Direct campaign status snapshot in a single call.

Usage:
    python scripts/direct_status.py            # campaign from DIRECT_CAMPAIGN_ID in .env
    python scripts/direct_status.py 714220844 --days 3

Outputs: campaign status and strategy, account balance, groups, keywords, bids,
autotargeting, ad states, spending/impressions over period, and bid overspend checks. Read-only.
"""
import argparse
import json
import statistics
import sys
import time
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_load import load_env, require

V5 = "https://api.direct.yandex.com/json/v5/"
V501 = "https://api.direct.yandex.com/json/v501/"
V4 = "https://api.direct.yandex.ru/live/v4/json/"


def call(service, method, params, token, base=V5):
    req = urllib.request.Request(
        base + service,
        data=json.dumps({"method": method, "params": params}, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + token, "Accept-Language": "en",
                 "Content-Type": "application/json; charset=utf-8"})
    data = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    if "error" in data:
        e = data["error"]
        raise SystemExit("[{}.{}] {}: {}".format(service, method, e["error_string"], e.get("error_detail", "")))
    return data["result"]


def balance(login, token):
    req = urllib.request.Request(V4, data=json.dumps(
        {"method": "AccountManagement", "token": token, "locale": "en",
         "param": {"Action": "Get", "SelectionCriteria": {"Logins": [login]}}},
        ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"})
    data = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    acc = data.get("data", {}).get("Accounts", [{}])[0]
    return acc.get("Amount"), acc.get("Currency")


def report(cid, token, days, fields, rtype):
    date_to = date.today()
    date_from = date_to - timedelta(days=days)
    body = json.dumps({"params": {
        "SelectionCriteria": {"Filter": [{"Field": "CampaignId", "Operator": "IN", "Values": [str(cid)]}],
                              "DateFrom": date_from.isoformat(), "DateTo": date_to.isoformat()},
        "FieldNames": fields, "ReportName": "status-{}".format(int(time.time() * 1000)),
        "ReportType": rtype, "DateRangeType": "CUSTOM_DATE", "Format": "TSV",
        "IncludeVAT": "NO", "IncludeDiscount": "NO"}}, ensure_ascii=False)
    req = urllib.request.Request("https://api.direct.yandex.com/json/v5/reports", data=body.encode("utf-8"),
        headers={"Authorization": "Bearer " + token, "Accept-Language": "en",
                 "Content-Type": "application/json; charset=utf-8", "processingMode": "auto",
                 "returnMoneyInMicros": "false", "skipReportHeader": "true", "skipReportSummary": "true"})
    for _ in range(20):
        resp = urllib.request.urlopen(req)
        if resp.status == 200:
            rows = [r.split("\t") for r in resp.read().decode("utf-8").strip().split("\n") if r.strip()]
            return (rows[0], rows[1:]) if len(rows) > 1 else ([], [])
        time.sleep(int(resp.headers.get("retryIn", 5)))
    return [], []


def auction(cid, token, names):
    """Fetch market CPC by traffic volume tiers from Yandex bidding data."""
    data = call("keywordbids", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["KeywordId"], "SearchFieldNames": ["Bid", "AuctionBids"]}, token)
    out = []
    for row in data.get("KeywordBids", []):
        search = row.get("Search") or {}
        items = (search.get("AuctionBids") or {}).get("AuctionBidItems") or []
        phrase = names.get(row["KeywordId"], "")
        if not items or phrase.startswith("---"):
            continue
        by_volume = {i["TrafficVolume"]: i["Price"] / 1e6 for i in items}

        def near(target):
            close = [v for v in by_volume if abs(v - target) <= 4]
            return by_volume[min(close, key=lambda v: abs(v - target))] if close else None

        full = near(100)
        if full:
            out.append((phrase, near(62), near(85), full))
    return sorted(out, key=lambda x: -(x[3] or 0))


def main():
    load_env()
    ap = argparse.ArgumentParser(description="Inspect Yandex.Direct campaign performance and bids.")
    ap.add_argument("campaign_id", nargs="?", help="Campaign ID (defaults to DIRECT_CAMPAIGN_ID)")
    ap.add_argument("--days", type=int, default=3, help="Historical report days (default: 3)")
    args = ap.parse_args()

    token = require("YANDEX_DIRECT_TOKEN")
    cid = int(args.campaign_id or require("DIRECT_CAMPAIGN_ID", "default campaign ID"))
    login = require("YANDEX_DIRECT_LOGIN")

    camp = call("campaigns", "get", {"SelectionCriteria": {"Ids": [cid]},
        "FieldNames": ["Id", "Name", "State", "Status", "StatusClarification", "DailyBudget", "NegativeKeywords"],
        "UnifiedCampaignFieldNames": ["BiddingStrategy", "CounterIds"]}, token, V501)["Campaigns"][0]
    groups = call("adgroups", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["Id", "Name"]}, token)["AdGroups"]
    keywords = call("keywords", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["Id", "AdGroupId", "Keyword", "Bid", "State", "Status"]}, token).get("Keywords", [])
    ads = call("ads", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["Id", "AdGroupId", "State", "Status"]}, token).get("Ads", [])

    gname = {g["Id"]: g["Name"] for g in groups}
    phrases = [k for k in keywords if not k["Keyword"].startswith("---")]
    autos = [k for k in keywords if k["Keyword"].startswith("---")]
    bids = [k.get("Bid", 0) / 1e6 for k in phrases]
    strat = camp.get("UnifiedCampaign", {}).get("BiddingStrategy", {})
    search = strat.get("Search", {})
    strat_body = next((v for k, v in search.items()
                       if isinstance(v, dict) and ("WeeklySpendLimit" in v or "AverageCpc" in v)), {})
    weekly = strat_body.get("WeeklySpendLimit", 0) / 1e6
    avg_cpc = strat_body.get("AverageCpc", 0) / 1e6
    daily = (camp.get("DailyBudget") or {}).get("Amount", 0) / 1e6
    amount, currency = balance(login, token)

    print("CAMPAIGN {} '{}'".format(cid, camp["Name"]))
    print("  state         {}/{} — {}".format(camp["State"], camp["Status"], camp.get("StatusClarification") or ""))
    print("  strategy      search {} · network {}".format(
        search.get("BiddingStrategyType"), strat.get("Network", {}).get("BiddingStrategyType")))
    print("  limits        weekly {:.0f} · daily {}{}".format(
        weekly, "{:.2f}".format(daily) if daily else "auto",
        " · avg cpc {:.2f}".format(avg_cpc) if avg_cpc else ""))
    print("  balance       {} {}".format(amount, currency))
    print("  counter       {}".format((camp.get("UnifiedCampaign", {}).get("CounterIds") or {}).get("Items")))
    print("  negatives     {}".format(len(camp["NegativeKeywords"]["Items"])))

    print("\nCOMPOSITION")
    per_group = Counter(gname.get(k["AdGroupId"]) for k in phrases)
    for g, n in per_group.items():
        print("  {:<20} {:>2} keywords".format(g, n))
    if bids:
        print("  bids          {:.2f}–{:.2f}, median {:.2f}".format(min(bids), max(bids), statistics.median(bids)))
    print("  autotarget    {} items, bids {}".format(
        len(autos), sorted({round(a.get("Bid", 0) / 1e6, 2) for a in autos})))
    print("  ads           {}".format(dict(Counter("{}/{}".format(a["State"], a["Status"]) for a in ads))))

    market = auction(cid, token, {k["Id"]: k["Keyword"] for k in keywords})
    if market:
        print()
        print("MARKET CPC BENCHMARK (Yandex auction)")
        print("  {:<30}{:>7}{:>7}{:>7}".format("keyword", "62%", "85%", "100%"))
        for phrase, v62, v85, v100 in market[:6]:
            print("  {:<30}".format(phrase[:30]) + "".join(
                "{:>7.2f}".format(v) if v else "      —" for v in (v62, v85, v100)))
        top = market[0][3]
        if avg_cpc and top and avg_cpc > top * 1.3:
            print("  ! Current avg CPC {:.2f} exceeds 100% traffic of most expensive keyword ({:.2f}) — overpaying".format(
                avg_cpc, top))
        elif avg_cpc:
            cover = sum(1 for m in market if m[3] and m[3] <= avg_cpc)
            print("  Avg CPC {:.2f} covers 100% volume for {} of {} keywords".format(
                avg_cpc, cover, len(market)))

    _header, rows = report(cid, token, args.days,
                          ["Criteria", "CriteriaType", "Impressions", "Clicks", "Cost", "AvgCpc"], "CUSTOM_REPORT")
    print("\nSPEND & CLICKS (last {} days)".format(args.days))
    if not rows:
        print("  no data")
        return
    imp = sum(int(r[2]) for r in rows)
    clicks = sum(int(r[3]) for r in rows)
    cost = sum(float(r[4]) for r in rows)
    print("  impressions {} · clicks {} · cost {:.2f} · avg CPC {}".format(
        imp, clicks, cost, "{:.2f}".format(cost / clicks) if clicks else "—"))

    bid_by_phrase = {k["Keyword"].lower(): k.get("Bid", 0) / 1e6 for k in keywords}
    alarm = []
    for r in rows:
        if int(r[3]) and r[5] not in ("--", ""):
            cpc, bid = float(r[5]), bid_by_phrase.get(r[0].lower())
            if bid and cpc > bid + 0.01:
                alarm.append("  ! '{}' — click {:.2f} vs bid {:.2f}".format(r[0], cpc, bid))
    for r in sorted(rows, key=lambda x: -int(x[3]))[:8]:
        if int(r[3]) or int(r[2]) > 2:
            print("    {:<34} imp {:>3}  clicks {:>2}  cost {:>6}".format(r[0][:34], r[2], r[3], r[4]))
    if alarm:
        print("\nWARNING: cost per click exceeds bid")
        print("\n".join(alarm))


if __name__ == "__main__":
    main()
