#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Семантика для кампании Директа из данных Wordstat.

Берёт базисы, тянет по каждому Wordstat через scripts/geo_keywords.py
(Yandex Cloud Search API, ключи YANDEX_CLOUD_API_KEY / YANDEX_CLOUD_FOLDER_ID),
объединяет, чистит и раскладывает фразы на три корзины:

    commercial — есть коммерческий маркер (заказать, цена, под ключ, студия…)
    info       — информационный интент (как, что такое, самому, бесплатно…)
    junk       — не про нашу услугу вообще

`info` и `junk` не выбрасываются: из них собирается список кандидатов
в минус-слова — это половина ценности сбора.

    python scripts/direct_semantics.py --config ads/campaigns/razrabotka-seeds.json \
        --out ads/campaigns/razrabotka-wordstat.json

Конфиг: {"seeds": [...], "must_have": [...], "commercial": [...], "info": [...],
         "junk": [...], "regions": "149", "min_count": 3}
"""
import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pull(seed: str, regions: str, min_count: int, num: int, cache_dir: Path) -> list[dict]:
    """Один базис Wordstat через geo_keywords.py. Кэшируется на диске."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / (re.sub(r"[^\w]+", "-", seed).strip("-") + ".json")
    if not out.exists():
        cmd = [sys.executable, str(ROOT / "scripts" / "geo_keywords.py"), seed,
               "--min-count", str(min_count), "--num", str(num),
               "--regions", regions, "--out", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ! {seed}: {r.stderr.strip()[:160]}")
            return []
    data = json.loads(out.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else (data.get("buckets") or data.get("results") or [])
    return [i for i in items if i.get("label")]


def classify(phrase: str, cfg: dict) -> str:
    words = set(re.findall(r"\w+", phrase.lower()))
    if not any(re.search(m, phrase.lower()) for m in cfg["must_have"]):
        return "junk"
    if words & set(cfg["info"]):
        return "info"
    if words & set(cfg["junk_words"]):
        return "junk"
    if any(re.search(c, phrase.lower()) for c in cfg["commercial"]):
        return "commercial"
    return "info"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--num", type=int, default=500)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cfg.setdefault("regions", "149")
    cfg.setdefault("min_count", 3)
    cfg.setdefault("junk_words", [])
    cache = Path(args.out).parent / "wordstat"

    merged: dict[str, int] = {}
    for seed in cfg["seeds"]:
        items = pull(seed, cfg["regions"], cfg["min_count"], args.num, cache)
        print(f"{seed:34} {len(items):>4} бакетов")
        for i in items:
            merged[i["label"]] = max(merged.get(i["label"], 0), i.get("count", 0))

    buckets = defaultdict(list)
    for phrase, count in merged.items():
        buckets[classify(phrase, cfg)].append({"phrase": phrase, "count": count})
    for k in buckets:
        buckets[k].sort(key=lambda x: -x["count"])

    # кандидаты в минус-слова: слова, которые встречаются только в info/junk
    comm_words = {w for r in buckets["commercial"] for w in re.findall(r"\w+", r["phrase"].lower())}
    bad_words: dict[str, int] = defaultdict(int)
    for key in ("info", "junk"):
        for r in buckets[key]:
            for w in re.findall(r"[а-яёa-z]{3,}", r["phrase"].lower()):
                if w not in comm_words:
                    bad_words[w] += r["count"]

    result = {
        "seeds": cfg["seeds"],
        "regions": cfg["regions"],
        "total_phrases": len(merged),
        "commercial": buckets["commercial"],
        "info": buckets["info"][:200],
        "negative_candidates": [w for w, _ in sorted(bad_words.items(), key=lambda x: -x[1])[:120]],
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nвсего фраз {len(merged)} → коммерческих {len(buckets['commercial'])}, "
          f"информационных {len(buckets['info'])}, мусор {len(buckets['junk'])}")
    print(f"кандидатов в минус-слова: {len(result['negative_candidates'])}")
    print(f"записано: {args.out}")


if __name__ == "__main__":
    main()
