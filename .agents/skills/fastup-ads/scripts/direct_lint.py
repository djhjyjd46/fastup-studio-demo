#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Проверка кампании Директа перед запуском.

    python scripts/direct_lint.py 714220844

Прогоняет проверки, которых нет в документации API, но которые стоят денег:
ставки против дневного лимита, война групп за один запрос, минус-слова против
собственной семантики, дубли фраз, пустые расширения, автотаргетинг дороже фраз.

Ничего не меняет. Код возврата 1, если найдены ОШИБКИ.
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path as _P
import sys as _sys
_sys.path.insert(0, str(_P(__file__).resolve().parent))
from env_load import require
from collections import defaultdict

V5 = "https://api.direct.yandex.com/json/v5/"
V501 = "https://api.direct.yandex.com/json/v501/"

try:
    import pymorphy3
    _morph = pymorphy3.MorphAnalyzer()

    def lemma(word):
        return _morph.parse(word)[0].normal_form
except ImportError:                                  # без морфологии проверки грубее
    def lemma(word):
        return word.rstrip("аяуюыиеойь")

TITLE_MAX, TEXT_MAX, WORDS_MAX = 56, 81, 7
BID_SHARE_OF_DAILY = 0.25        # одна ставка не должна съедать больше четверти дня


def call(service, method, params, token, base=V5):
    req = urllib.request.Request(
        base + service,
        data=json.dumps({"method": method, "params": params}, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + token, "Accept-Language": "ru",
                 "Content-Type": "application/json; charset=utf-8"})
    data = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    if "error" in data:
        e = data["error"]
        raise SystemExit("[{}.{}] {}: {}".format(service, method, e["error_string"], e.get("error_detail", "")))
    return data["result"]


def positive_lemmas(phrase):
    """Леммы положительной части фразы — до первого минус-слова."""
    head = phrase.split(" -")[0]
    return frozenset(lemma(w) for w in re.findall(r"[а-яёa-z]+", head.lower()))


def lint(cid, token):
    errors, warns, notes = [], [], []

    camp = call("campaigns", "get", {"SelectionCriteria": {"Ids": [cid]},
        "FieldNames": ["Id", "Name", "State", "Status", "DailyBudget", "NegativeKeywords"],
        "UnifiedCampaignFieldNames": ["BiddingStrategy", "CounterIds"]}, token, V501)["Campaigns"][0]
    groups = call("adgroups", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["Id", "Name", "RegionIds", "Status"]}, token)["AdGroups"]
    keywords = call("keywords", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["Id", "AdGroupId", "Keyword", "Bid", "State", "Status"]}, token).get("Keywords", [])
    ads = call("ads", "get", {"SelectionCriteria": {"CampaignIds": [cid]},
        "FieldNames": ["Id", "AdGroupId", "State", "Status"],
        "TextAdFieldNames": ["Title", "Title2", "Text", "Href", "SitelinkSetId",
                             "DisplayUrlPath", "AdExtensions"]}, token).get("Ads", [])

    gname = {g["Id"]: g["Name"] for g in groups}
    phrases = [k for k in keywords if not k["Keyword"].startswith("---")]
    autotargets = [k for k in keywords if k["Keyword"].startswith("---")]

    print("кампания {} «{}» — {}/{}".format(cid, camp["Name"], camp["State"], camp["Status"]))
    print("групп {}, фраз {}, автотаргетингов {}, объявлений {}\n".format(
        len(groups), len(phrases), len(autotargets), len(ads)))

    # бюджет и ставки
    strategy_type = ((camp.get("UnifiedCampaign") or {}).get("BiddingStrategy") or {})         .get("Search", {}).get("BiddingStrategyType", "")
    manual = strategy_type == "HIGHEST_POSITION"
    daily = (camp.get("DailyBudget") or {}).get("Amount", 0) / 1e6
    strat_body = next((v for k, v in ((camp.get("UnifiedCampaign") or {}).get("BiddingStrategy") or {})
                       .get("Search", {}).items()
                       if isinstance(v, dict) and ("WeeklySpendLimit" in v or "AverageCpc" in v)), {})
    weekly = strat_body.get("WeeklySpendLimit", 0) / 1e6
    if not daily and not weekly:
        errors.append("не задан лимит расхода: кампания может открутить весь баланс за день")
    elif not manual:
        notes.append("стратегия {} — ставки фраз не действуют, цену держит стратегия "
                     "(средняя цена клика {:.2f}, недельный лимит {:.0f})".format(
                         strategy_type, strat_body.get("AverageCpc", 0) / 1e6, weekly))
    elif daily:
        cap = daily * BID_SHARE_OF_DAILY
        for k in phrases:
            bid = k.get("Bid", 0) / 1e6
            if bid > cap:
                errors.append("ставка {:.2f} BYN у «{}» — больше {:.0%} дневного лимита ({:.2f}): "
                              "один клик съедает день".format(bid, k["Keyword"], BID_SHARE_OF_DAILY, daily))

    # автотаргетинг не должен торговаться дороже собственной семантики
    max_bid = defaultdict(float)
    for k in phrases:
        max_bid[k["AdGroupId"]] = max(max_bid[k["AdGroupId"]], k.get("Bid", 0) / 1e6)
    for a in autotargets:
        bid, own = a.get("Bid", 0) / 1e6, max_bid.get(a["AdGroupId"], 0)
        if own and bid > own:
            warns.append("автотаргетинг в «{}» стоит {:.2f} BYN против {:.2f} у собственных фраз — "
                         "конкурирует с вами за ваш бюджет".format(gname.get(a["AdGroupId"]), bid, own))

    # минус-слова против собственной семантики
    negs = {lemma(n.lower().lstrip("!")) for n in camp["NegativeKeywords"]["Items"] if " " not in n}
    for k in phrases:
        for w in re.findall(r"[а-яёa-z]+", k["Keyword"].split(" -")[0].lower()):
            if lemma(w) in negs:
                errors.append("минус-слово «{}» блокирует собственную фразу «{}»".format(w, k["Keyword"]))

    # дубли
    seen = defaultdict(list)
    for k in phrases:
        seen[k["Keyword"].lower()].append(gname.get(k["AdGroupId"]))
    for phrase, gs in seen.items():
        if len(gs) > 1:
            errors.append("фраза «{}» заведена в нескольких группах: {}".format(phrase, ", ".join(gs)))

    # межгрупповые пересечения
    items = [(gname.get(k["AdGroupId"]), k["Keyword"], positive_lemmas(k["Keyword"])) for k in phrases]
    for g1, p1, l1 in items:
        minus1 = set(re.findall(r"-([а-яёa-z]+)", p1.lower()))
        for g2, p2, l2 in items:
            if p1 == p2 or g1 == g2 or not l1 < l2:
                continue
            words2 = {lemma(w) for w in re.findall(r"[а-яёa-z]+", p2.lower())}
            if {lemma(m) for m in minus1} & words2:
                continue                                  # минус-слово уже разводит фразы
            warns.append("«{}» [{}] перехватит «{}» [{}] — нужна кросс-минусовка".format(p1, g1, p2, g2))

    # длина фраз
    for k in phrases:
        words = len(re.findall(r"[а-яёa-z]+", k["Keyword"]))
        if words > WORDS_MAX:
            errors.append("во фразе «{}» {} слов, лимит {}".format(k["Keyword"], words, WORDS_MAX))

    # группы
    for g in groups:
        if not g.get("RegionIds"):
            errors.append("в группе «{}» не задано гео".format(g["Name"]))
        if not any(k["AdGroupId"] == g["Id"] for k in phrases):
            errors.append("в группе «{}» нет ни одной фразы".format(g["Name"]))
        n_ads = sum(1 for a in ads if a["AdGroupId"] == g["Id"])
        if n_ads == 0:
            errors.append("в группе «{}» нет объявлений".format(g["Name"]))
        elif n_ads == 1:
            notes.append("в группе «{}» одно объявление — сравнивать не с чем".format(g["Name"]))

    # объявления
    for a in ads:
        t = a.get("TextAd", {})
        title = (t.get("Title") or "") + ((" " + t["Title2"]) if t.get("Title2") else "")
        if len(title) > TITLE_MAX:
            errors.append("заголовок длиннее {}: «{}…»".format(TITLE_MAX, title[:60]))
        if len(t.get("Text") or "") > TEXT_MAX:
            errors.append("текст длиннее {} у объявления {}".format(TEXT_MAX, a["Id"]))
        if not t.get("SitelinkSetId"):
            warns.append("у объявления {} нет быстрых ссылок — теряется место в выдаче".format(a["Id"]))
        if not t.get("AdExtensions"):
            warns.append("у объявления {} нет уточнений".format(a["Id"]))
        if not t.get("DisplayUrlPath"):
            notes.append("у объявления {} нет отображаемой ссылки".format(a["Id"]))
        href = t.get("Href") or ""
        if href and "utm_" not in href:
            errors.append("в ссылке объявления {} нет UTM — трафик не разложить по источникам".format(a["Id"]))

    # аналитика и сеть
    uni = camp.get("UnifiedCampaign", {})
    if not (uni.get("CounterIds") or {}).get("Items"):
        errors.append("к кампании не привязан счётчик Метрики — конверсии считать нечем")
    net = (uni.get("BiddingStrategy") or {}).get("Network", {}).get("BiddingStrategyType")
    if net and net != "SERVING_OFF":
        notes.append("сеть включена ({}) — на тестовом бюджете её обычно отключают".format(net))

    return errors, warns, notes


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    token = require("YANDEX_DIRECT_TOKEN")
    errors, warns, notes = lint(int(sys.argv[1]), token)

    for title, items in (("ОШИБКИ", errors), ("ПРЕДУПРЕЖДЕНИЯ", warns), ("ЗАМЕТКИ", notes)):
        uniq = list(dict.fromkeys(items))
        if uniq:
            print("{} ({})".format(title, len(uniq)))
            for i in uniq:
                print("  · " + i)
            print()
    if not (errors or warns or notes):
        print("замечаний нет")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
