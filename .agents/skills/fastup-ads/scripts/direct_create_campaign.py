#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Создаёт кампанию в Яндекс.Директе из JSON-описания.

Кампания создаётся приостановленной: показы не начнутся, пока её не запустят
вручную в интерфейсе. Токен берётся из переменной окружения YANDEX_DIRECT_TOKEN.

    python scripts/direct_create_campaign.py promotion/direct-campaign-razrabotka.json [--dry-run]

Единая перфоманс-кампания живёт на отдельном адресе /v501/, обычные сервисы —
на /json/v5/ (см. integrations/yandex-direct.md).
"""
import json
import os
import sys
import urllib.request
from pathlib import Path as _P
import sys as _sys
_sys.path.insert(0, str(_P(__file__).resolve().parent))
from env_load import require

API_V5 = "https://api.direct.yandex.com/json/v5/"
API_V501 = "https://api.direct.yandex.com/json/v501/"
MICRO = 1_000_000


def call(service, method, params, token, base=API_V5):
    body = json.dumps({"method": method, "params": params}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base + service,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept-Language": "ru",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "error" in data:
        e = data["error"]
        raise SystemExit(f"[{service}.{method}] {e['error_code']}: {e['error_string']} — {e.get('error_detail','')}")
    result = data["result"]
    for warning in result.get("AddResults", []):
        for w in warning.get("Warnings", []):
            print(f"  ! предупреждение: {w['Message']} {w.get('Details','')}")
    return result


def ids_or_die(result, key="AddResults"):
    out = []
    for item in result[key]:
        if "Id" not in item:
            errs = "; ".join(f"{e['Code']} {e['Message']} {e.get('Details','')}" for e in item.get("Errors", []))
            raise SystemExit(f"не создано: {errs}")
        out.append(item["Id"])
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if not args:
        raise SystemExit(__doc__)
    spec = json.load(open(args[0], encoding="utf-8"))
    token = None if dry else require("YANDEX_DIRECT_TOKEN")

    c = spec["campaign"]
    href = c["landing"] + ("&" if "?" in c["landing"] else "?") + c["utm"]

    campaign = {
        "Name": c["name"],
        "StartDate": c.get("start_date") or __import__("datetime").date.today().isoformat(),
        "NegativeKeywords": {"Items": c["negative_keywords"]},
        "UnifiedCampaign": {
            "BiddingStrategy": {
                "Search": {
                    "BiddingStrategyType": "HIGHEST_POSITION",
                    "HighestPosition": {"WeeklySpendLimit": int(c["weekly_spend_limit_byn"] * MICRO)},
                    "PlacementTypes": {
                        "SearchResults": "YES",
                        "ProductGallery": "NO",
                        "DynamicPlaces": "NO",
                        "Maps": "NO",
                        "SearchOrganizationList": "NO",
                    },
                },
                "Network": {"BiddingStrategyType": "SERVING_OFF"},
            },
            "CounterIds": {"Items": [c["counter_id"]]},
        },
    }

    print(f"кампания: {c['name']}")
    print(f"  недельный лимит {c['weekly_spend_limit_byn']} BYN, только поиск, ручные ставки")
    print(f"  посадочная: {href}")
    print(f"  минус-слов: {len(c['negative_keywords'])}, групп: {len(spec['groups'])}")
    if dry:
        print(json.dumps(campaign, ensure_ascii=False, indent=1))
        return

    cid = ids_or_die(call("campaigns", "add", {"Campaigns": [campaign]}, token, API_V501))[0]
    print(f"создана кампания {cid}")

    for g in spec["groups"]:
        gid = ids_or_die(call("adgroups", "add", {"AdGroups": [{
            "Name": g["name"],
            "CampaignId": cid,
            "RegionIds": c["region_ids"],
            "UnifiedAdGroup": {"OfferRetargeting": "NO"},
        }]}, token, API_V501))[0]

        kws = [{"Keyword": k["phrase"], "AdGroupId": gid, "Bid": int(k["bid_byn"] * MICRO)} for k in g["keywords"]]
        ids_or_die(call("keywords", "add", {"Keywords": kws}, token))

        ads = [{"AdGroupId": gid, "TextAd": {
            "Title": a["title"], "Title2": a["title2"], "Text": a["text"],
            "Href": href, "Mobile": "NO",
        }} for a in g["ads"]]
        ids_or_die(call("ads", "add", {"Ads": ads}, token))
        print(f"  группа {gid} «{g['name']}»: {len(kws)} фраз, {len(ads)} объявления")

    call("campaigns", "suspend", {"SelectionCriteria": {"Ids": [cid]}}, token)
    print(f"кампания {cid} остановлена — показы не идут, запуск вручную из интерфейса")


if __name__ == "__main__":
    main()
