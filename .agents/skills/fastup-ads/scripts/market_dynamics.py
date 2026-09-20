#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Динамика спроса по нишам: объём, изменение за год и за три месяца.

    python scripts/market_dynamics.py --config ads/campaigns/market-phrases.json \
        --out ads/campaigns/market-dynamics.json

Считает по каждой фразе:
    volume        — запросов за последний полный месяц
    year_share    — изменение ДОЛИ рынка за 12 месяцев, %
    quarter_share — изменение ДОЛИ за последние 3 месяца, %
    year_abs      — изменение абсолюта за 12 месяцев, % (для сравнения)

Доля важнее абсолюта: она очищена от общего оттока аудитории Яндекса. Если абсолют
падает на 60%, а доля на 55% — 5 процентных пунктов это отток, остальное реальная
потеря интереса к теме. Контрольная группа («погода», «купить») показывает, сколько
именно составляет отток в текущем периоде.

Источник — Wordstat через Yandex Cloud Search API (ключи YANDEX_CLOUD_API_KEY,
YANDEX_CLOUD_FOLDER_ID в .env). Данные измеряемые и воспроизводимые: тот же запуск
через полгода даст сопоставимые цифры.
"""
import argparse
import json
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_load import load_env, require

API = "https://searchapi.api.cloud.yandex.net/v2/wordstat/dynamics"


def dynamics(phrase, regions, key, folder):
    first = date.today().replace(day=1)
    start = (first - timedelta(days=370)).replace(day=1)
    end = first - timedelta(days=1)
    body = json.dumps({"phrase": phrase, "regions": regions, "folderId": folder,
                       "period": "PERIOD_MONTHLY",
                       "fromDate": start.isoformat() + "T00:00:00Z",
                       "toDate": end.isoformat() + "T00:00:00Z"}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": "Api-Key " + key, "Content-Type": "application/json; charset=utf-8"})
    try:
        data = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    except Exception as e:
        return {"error": "{}: {}".format(type(e).__name__, str(e)[:120])}
    points = [{"month": r["date"][:7], "count": int(r["count"]), "share": r.get("share") or 0}
              for r in data.get("results", [])]
    if len(points) < 4:
        return {"error": "мало точек"}

    def change(a, b, field):
        return round((b[field] - a[field]) / a[field] * 100) if a[field] else None

    return {"volume": points[-1]["count"],
            "year_share": change(points[0], points[-1], "share"),
            "year_abs": change(points[0], points[-1], "count"),
            "quarter_share": change(points[-4], points[-1], "share"),
            "quarter_abs": change(points[-4], points[-1], "count"),
            "months": points}


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--regions", default="149")
    args = ap.parse_args()

    key = require("YANDEX_CLOUD_API_KEY")
    folder = require("YANDEX_CLOUD_FOLDER_ID")
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    regions = args.regions.split(",")

    out = {"measured_at": date.today().isoformat(), "regions": regions, "groups": {}}
    for group, phrases in cfg["groups"].items():
        print("\n" + group)
        print("  {:<34}{:>9}{:>9}{:>9}".format("запрос", "объём", "год", "3 мес"))
        out["groups"][group] = {}
        for phrase in phrases:
            d = dynamics(phrase, regions, key, folder)
            out["groups"][group][phrase] = d
            if "error" in d:
                print("  {:<34}{:>27}".format(phrase, d["error"]))
                continue
            print("  {:<34}{:>9}{:>+8}%{:>+8}%".format(
                phrase, d["volume"], d["year_share"], d["quarter_share"]))

    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nзаписано: " + args.out)


if __name__ == "__main__":
    main()
