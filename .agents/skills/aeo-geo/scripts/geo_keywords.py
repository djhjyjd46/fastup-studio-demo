#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Wordstat keyword pull + frequency filter + lemma-dedup — outline research.

Credentials come from .env (YANDEX_CLOUD_API_KEY, YANDEX_CLOUD_FOLDER_ID) if present,
otherwise from the process environment. Never hardcode them here. See
integrations/geo-keywords.md for setup and the API contract (Yandex Cloud Search API
v2 /wordstat/topRequests, not the old Direct API — no ad account required).

What this does (and only this):
    1. Pulls raw phrase+frequency pairs from Wordstat for a seed phrase.
    2. Drops noise below --min-count.
    3. Groups near-duplicate phrasings by lemma (pymorphy3) — "создание сайта" /
       "создание сайтов" / "создать сайт" collapse into one bucket, counts summed.
    4. Prints/saves a compact list — small enough to hand an LLM for the *next* step
       (grouping buckets into 5-15 semantic intents -> article H2/H3). That grouping
       step is NOT done here — it needs meaning, not morphology; this script only
       removes the morphological noise so that step is cheap.

Usage:
    python3 scripts/geo_keywords.py "создание сайта" --min-count 5 --num 500 \
        --out content/research/create-site-keywords.json

Output JSON: list of {label, count, variants: [...]}, sorted by count desc.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import pymorphy3
except ImportError:
    print("Нужен pymorphy3: pip install pymorphy3 pymorphy3-dicts-ru", file=sys.stderr)
    sys.exit(1)

API_URL = "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests"

STOPWORDS = {
    "в", "на", "и", "с", "для", "от", "до", "по", "не", "к", "из", "у",
    "как", "что", "это", "или", "а", "но", "же", "ли",
}


def get_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(
            f"Не найдена переменная окружения {name}. "
            f"Задай в .env или в переменных окружения сессии (см. integrations/geo-keywords.md).",
            file=sys.stderr,
        )
        sys.exit(1)
    return val


def fetch_wordstat(phrase: str, api_key: str, folder_id: str, num_phrases: int, regions: list[str]) -> dict:
    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Api-Key {api_key}", "Content-Type": "application/json; charset=utf-8"},
        json={"phrase": phrase, "numPhrases": num_phrases, "regions": regions, "folderId": folder_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


_morph = None


def lemma_key(phrase: str) -> frozenset:
    global _morph
    if _morph is None:
        _morph = pymorphy3.MorphAnalyzer()
    words = re.findall(r"[а-яёa-z0-9]+", phrase.lower())
    lemmas = {
        _morph.parse(w)[0].normal_form
        for w in words
        if w not in STOPWORDS and len(w) > 1
    }
    return frozenset(lemmas)


def dedupe(raw: list[dict], min_count: int) -> list[dict]:
    """Group phrases by lemma set, sum counts, keep the most frequent phrasing as label."""
    buckets: dict[frozenset, list[dict]] = defaultdict(list)
    for item in raw:
        count = int(item.get("count", 0))
        if count < min_count:
            continue
        phrase = item["phrase"]
        key = lemma_key(phrase)
        if not key:
            continue
        buckets[key].append({"phrase": phrase, "count": count})

    out = []
    for key, items in buckets.items():
        items.sort(key=lambda x: -x["count"])
        out.append({
            "label": items[0]["phrase"],
            "count": sum(i["count"] for i in items),
            "variants": [i["phrase"] for i in items],
        })
    out.sort(key=lambda x: -x["count"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phrase", help="Seed-фраза для Wordstat")
    ap.add_argument("--min-count", type=int, default=5, help="Отсекать фразы с частотой ниже этого (default: 5)")
    ap.add_argument("--num", type=int, default=500, help="Сколько фраз запросить у Wordstat (default: 500, max по API)")
    # Коды проверены эмпирически 2026-08-12 (сверка totalCount по одной seed-фразе):
    # 149 = Беларусь (3847), 157 = Минск (1206, подмножество 149), 225 = Россия (14699).
    # До этой правки дефолтом стоял 157 с подписью «Беларусь» — все замеры до 2026-08-12
    # сняты по одному городу и занижены примерно втрое.
    ap.add_argument("--regions", default="149",
                    help="Regions ID через запятую (149 = Беларусь, default; 157 = Минск, 225 = Россия)")
    ap.add_argument("--out", help="Путь для сохранения JSON (по умолчанию — печать в stdout)")
    args = ap.parse_args()

    api_key = get_env("YANDEX_CLOUD_API_KEY")
    folder_id = get_env("YANDEX_CLOUD_FOLDER_ID")
    regions = [r.strip() for r in args.regions.split(",")]

    data = fetch_wordstat(args.phrase, api_key, folder_id, args.num, regions)
    raw = data.get("results", []) + data.get("associations", [])
    grouped = dedupe(raw, args.min_count)

    result = {
        "seed_phrase": args.phrase,
        "total_count_raw": int(data.get("totalCount", 0)),
        "raw_phrases": len(raw),
        "grouped_buckets": len(grouped),
        "buckets": grouped,
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Сохранено: {args.out} ({len(grouped)} групп из {len(raw)} сырых фраз)", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
