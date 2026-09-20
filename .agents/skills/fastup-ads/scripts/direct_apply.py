#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Применяет изменения к кампании Директа из JSON-файла.

    python scripts/direct_apply.py <файл>.json           # только показать, что будет сделано
    python scripts/direct_apply.py <файл>.json --apply   # применить в боевой кампании

Формат файла:
    {"campaign_id": 714220844,
     "negative_keywords": [...],           # заменяет минус-слова кампании целиком
     "add_keywords": {"Имя группы": [{"phrase": "...", "bid_byn": 3.0}, ...]},
     "ads": [{"id": 1920709953520143427,                      # комбинаторное объявление:
              "titles": ["..."], "texts": ["..."]}],          # списки заменяются целиком
     "suspend_ads": [1920709953520143428],                    # останавливает объявления
     "delete_bid_modifiers": [242119280236]}                  # удаляет корректировки по Id

Токен — из переменной окружения YANDEX_DIRECT_TOKEN. Показы не запускает. Удаляет только
корректировки, перечисленные явно в delete_bid_modifiers.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path as _P
import sys as _sys
_sys.path.insert(0, str(_P(__file__).resolve().parent))
from env_load import require
from pathlib import Path

V5 = "https://api.direct.yandex.com/json/v5/"
V501 = "https://api.direct.yandex.com/json/v501/"
MICRO = 1_000_000


def call(service, method, params, token, base=V5):
    req = urllib.request.Request(
        base + service,
        data=json.dumps({"method": method, "params": params}, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ru",
                 "Content-Type": "application/json; charset=utf-8"},
    )
    data = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    if "error" in data:
        e = data["error"]
        raise SystemExit(f"[{service}.{method}] {e['error_code']}: {e['error_string']} — {e.get('error_detail','')}")
    return data["result"]


def report_results(res, label):
    for r in res:
        for e in r.get("Errors", []) + r.get("Warnings", []):
            print(f"  ! {r.get('Id', '')} {e['Code']} {e['Message']} {e.get('Details', '')}")
    ok = sum(1 for r in res if r.get("Id") and not r.get("Errors"))
    print(f"{label}: {ok} из {len(res)}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    # по умолчанию ничего не применяется: изменения в боевой кампании требуют явного флага
    dry = "--apply" not in sys.argv
    if not args:
        raise SystemExit(__doc__)
    spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    token = None if dry else require("YANDEX_DIRECT_TOKEN")

    cid = spec["campaign_id"]
    add = spec.get("add_keywords", {})
    negs = spec.get("negative_keywords")
    ads = spec.get("ads", [])
    del_mods = spec.get("delete_bid_modifiers", [])
    suspend = spec.get("suspend_ads", [])

    # объявления кампании комбинаторные (RESPONSIVE_AD): старое поле TextAd.Title2 API
    # принимает с предупреждением 10252 и молча не записывает
    for a in ads:
        if not 1 <= len(a["titles"]) <= 7 or not 1 <= len(a["texts"]) <= 3:
            raise SystemExit(f"объявление {a['id']}: нужно 1–7 заголовков и 1–3 текста")

    print(f"кампания {cid}" + ("  [проверка, ничего не применяется]" if dry else "  [ПРИМЕНЯЮ]"))
    if negs:
        print(f"  минус-слов: {len(negs)}")
    for g, kws in add.items():
        print(f"  +{len(kws):>3} фраз в группу «{g}»")
    for a in ads:
        print(f"  объявление {a['id']}: заголовков {len(a['titles'])}, текстов {len(a['texts'])}")
        for s in a["titles"] + a["texts"]:
            print(f"      {len(s):>3}  {s}")
    if suspend:
        print(f"  остановить объявления: {suspend}")
    if del_mods:
        print(f"  удалить корректировки: {del_mods}")
    if dry:
        print()
        print("это был разбор без записи. Применить — тот же вызов с флагом --apply")
        return

    if negs:
        call("campaigns", "update", {"Campaigns": [{"Id": cid, "NegativeKeywords": {"Items": negs}}]},
             token, V501)
        print("минус-слова обновлены")

    if ads:
        res = call("ads", "update", {"Ads": [{"Id": a["id"], "ResponsiveAd": {
            "Titles": a["titles"], "Texts": a["texts"]}} for a in ads]}, token, V501)["UpdateResults"]
        report_results(res, "обновлено объявлений")

    if suspend:
        res = call("ads", "suspend", {"SelectionCriteria": {"Ids": suspend}}, token)["SuspendResults"]
        report_results(res, "остановлено объявлений")

    if del_mods:
        res = call("bidmodifiers", "delete", {"SelectionCriteria": {"Ids": del_mods}}, token)["DeleteResults"]
        report_results(res, "удалено корректировок")

    if add:
        groups = call("adgroups", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
                                          "FieldNames": ["Id", "Name"]}, token)["AdGroups"]
        by_name = {g["Name"]: g["Id"] for g in groups}
        existing = call("keywords", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
                                            "FieldNames": ["Keyword", "AdGroupId"]}, token).get("Keywords", [])
        have = {(k["AdGroupId"], k["Keyword"].lower()) for k in existing}

        payload = []
        for gname, kws in add.items():
            gid = by_name.get(gname)
            if not gid:
                print(f"  ! группы «{gname}» нет в кампании, пропущена")
                continue
            for k in kws:
                if (gid, k["phrase"].lower()) in have:
                    continue
                payload.append({"Keyword": k["phrase"], "AdGroupId": gid,
                                "Bid": int(k.get("bid_byn", 3) * MICRO)})
        if not payload:
            print("новых фраз нет")
            return
        res = call("keywords", "add", {"Keywords": payload}, token)["AddResults"]
        ok = sum(1 for r in res if r.get("Id"))
        for r in res:
            for e in r.get("Errors", []):
                print(f"  ! {e['Code']} {e['Message']} {e.get('Details','')}")
        print(f"добавлено фраз: {ok} из {len(payload)}")


if __name__ == "__main__":
    main()
