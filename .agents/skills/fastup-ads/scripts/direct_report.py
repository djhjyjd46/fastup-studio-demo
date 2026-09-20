#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Отчёты Директа: статистика по фразам и реальные поисковые запросы.

    python scripts/direct_report.py 714220844 --days 7            # сводка по фразам
    python scripts/direct_report.py 714220844 --queries --days 7  # поисковые запросы
    python scripts/direct_report.py 714220844 --queries --out ads/reports/queries.tsv

Поисковые запросы — главный источник экономии: по ним отбираются минус-слова.
Отчёт может ставиться в очередь (202) — скрипт ждёт и забирает готовый.
"""
import argparse
import os
import time
import urllib.error
import urllib.request
from pathlib import Path as _P
import sys as _sys
_sys.path.insert(0, str(_P(__file__).resolve().parent))
from env_load import require
from datetime import date, timedelta

REPORTS_URL = "https://api.direct.yandex.com/json/v5/reports"

SUMMARY_FIELDS = ["CampaignName", "AdGroupName", "Criteria", "Impressions", "Clicks",
                  "Ctr", "Cost", "AvgCpc", "Conversions", "CostPerConversion"]
QUERY_FIELDS = ["Query", "AdGroupName", "Criteria", "Impressions", "Clicks", "Ctr", "Cost"]


def fetch(body, token):
    req = urllib.request.Request(
        REPORTS_URL,
        data=body.encode("utf-8"),
        headers={"Authorization": "Bearer " + token,
                 "Accept-Language": "ru",
                 "Content-Type": "application/json; charset=utf-8",
                 "processingMode": "auto",
                 "returnMoneyInMicros": "false",
                 "skipReportHeader": "true",
                 "skipReportSummary": "true"})
    for attempt in range(30):
        try:
            resp = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            raise SystemExit("{}: {}".format(e.code, e.read().decode("utf-8")[:400]))
        if resp.status == 200:
            return resp.read().decode("utf-8")
        wait = int(resp.headers.get("retryIn", 5))
        print("отчёт готовится, ждём {} с (попытка {})".format(wait, attempt + 1))
        time.sleep(wait)
    raise SystemExit("отчёт так и не подготовился")


def build(cid, fields, report_type, date_from, date_to, name):
    fnames = "".join('"{}",'.format(f) for f in fields).rstrip(",")
    return ('{"params":{"SelectionCriteria":{"Filter":[{"Field":"CampaignId","Operator":"IN",'
            '"Values":["%s"]}],"DateFrom":"%s","DateTo":"%s"},"FieldNames":[%s],'
            '"ReportName":"%s","ReportType":"%s","DateRangeType":"CUSTOM_DATE",'
            '"Format":"TSV","IncludeVAT":"NO","IncludeDiscount":"NO"}}'
            % (cid, date_from, date_to, fnames, name, report_type))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign_id")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--queries", action="store_true", help="отчёт по поисковым запросам")
    ap.add_argument("--out", help="сохранить TSV в файл")
    args = ap.parse_args()

    token = require("YANDEX_DIRECT_TOKEN")

    date_to = date.today()
    date_from = date_to - timedelta(days=args.days)
    if args.queries:
        fields, rtype = QUERY_FIELDS, "SEARCH_QUERY_PERFORMANCE_REPORT"
    else:
        fields, rtype = SUMMARY_FIELDS, "CUSTOM_REPORT"
    name = "{}-{}-{}".format(rtype[:12], args.campaign_id, int(time.time()))

    tsv = fetch(build(args.campaign_id, fields, rtype,
                      date_from.isoformat(), date_to.isoformat(), name), token)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(tsv)
        print("записано: " + args.out)

    rows = [r.split("\t") for r in tsv.strip().split("\n") if r.strip()]
    if len(rows) < 2:
        print("данных за период {} — {} нет (кампания ещё не откручивалась?)".format(date_from, date_to))
        return
    header, data = rows[0], rows[1:]
    widths = [max(len(str(r[i])) for r in [header] + data[:40]) for i in range(len(header))]
    print("\nпериод {} — {}, строк {}\n".format(date_from, date_to, len(data)))
    print("  ".join(h.ljust(w) for h, w in zip(header, widths)))
    for r in data[:40]:
        print("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))
    if len(data) > 40:
        print("… ещё {} строк, полный отчёт в --out".format(len(data) - 40))


if __name__ == "__main__":
    main()
