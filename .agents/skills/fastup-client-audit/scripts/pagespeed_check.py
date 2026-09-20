#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""
scripts/pagespeed_check.py

Прогон Google PageSpeed Insights API (бесплатный, ключ уже в .env) по списку URL —
дополнение к scripts/site_crawl.py: тот собирает мету/разметку, этот — Core Web Vitals
и реальные диагностики Lighthouse (включая layout shift).

Использование:
    python scripts/pagespeed_check.py https://example.by/ https://example.by/page/ --out report.json
"""

import argparse
import json
import time
from pathlib import Path

import requests

API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def load_api_key(repo_root: Path) -> str:
    from env_load import env_file_path  # из worktree — .env основной копии
    env_path = env_file_path()
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("PAGESPEED_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("PAGESPEED_API_KEY не найден в .env")


# Пороги Google: значение "хорошо" (needs-improvement начинается отсюда).
CLS_GOOD_THRESHOLD = 0.1


def run_psi(url: str, api_key: str, strategy: str) -> dict:
    params = {
        "url": url,
        "key": api_key,
        "strategy": strategy,
        "category": ["PERFORMANCE", "ACCESSIBILITY", "SEO"],
    }
    r = requests.get(API_URL, params=params, timeout=60)
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}: {r.text[:300]}"}
    data = r.json()

    lh = data.get("lighthouseResult", {})
    audits = lh.get("audits", {})
    categories = lh.get("categories", {})
    field = data.get("loadingExperience", {}).get("metrics", {})

    def metric(key):
        a = audits.get(key, {})
        return {"value": a.get("numericValue"), "display": a.get("displayValue")}

    return {
        "performance_score": round((categories.get("performance", {}).get("score") or 0) * 100),
        "accessibility_score": round((categories.get("accessibility", {}).get("score") or 0) * 100),
        "seo_score": round((categories.get("seo", {}).get("score") or 0) * 100),
        "lab_metrics": {
            "LCP": metric("largest-contentful-paint"),
            "CLS": metric("cumulative-layout-shift"),
            "TBT": metric("total-blocking-time"),
            "FCP": metric("first-contentful-paint"),
            "Speed Index": metric("speed-index"),
        },
        "field_data_available": bool(field),
        "field_metrics": {
            k: v.get("percentile") for k, v in field.items()
        } if field else None,
        "top_opportunities": [
            {"title": a.get("title"), "savings_ms": a.get("details", {}).get("overallSavingsMs")}
            for key, a in audits.items()
            if a.get("details", {}).get("overallSavingsMs", 0) and a["details"]["overallSavingsMs"] > 100
        ][:8],
        "layout_shift_culprits": [
            item
            for item in (audits.get("layout-shift-elements", {}).get("details", {}) or {}).get("items", [])
        ][:5],
    }


def run_psi_verified(url: str, api_key: str, strategy: str) -> dict:
    """
    run_psi() плюс автоматическая перепроверка выбросов — раньше это держалось на памяти
    агента ("перепрогони вторым разом, если цифра выбивается"), а не в коде, и один раз
    это уже потерялось: CLS 0.389 ("плохо") на brandplatform.by/mobile ушёл в отчёт как
    находка, второй ручной прогон дал 0.003 ("хорошо") — первое было разовым выбросом
    (2026-08-21, playbook/geo-method.md, раздел 5). Теперь перепроверка не полагается на
    то, что кто-то вспомнит её сделать.

    Правило: если CLS первого прогона хуже порога "хорошо" — прогоняем второй раз. Если
    второй раз тоже плохой — подтверждено, находка настоящая. Если второй раз хороший —
    первый был выбросом, отчёт получает подтверждённое (второе) значение и явную пометку,
    что расхождение было.
    """
    first = run_psi(url, api_key, strategy)
    if first.get("error"):
        return first

    cls = (first.get("lab_metrics", {}).get("CLS", {}) or {}).get("value")
    if cls is None or cls < CLS_GOOD_THRESHOLD:
        return first

    time.sleep(2.0)
    second = run_psi(url, api_key, strategy)
    if second.get("error"):
        # Второй прогон не удался технически — не подтверждаем и не опровергаем,
        # оставляем первый результат с явной пометкой, что перепроверка не прошла.
        first["cls_recheck"] = {"attempted": True, "error": second["error"]}
        return first

    cls2 = (second.get("lab_metrics", {}).get("CLS", {}) or {}).get("value")
    confirmed = cls2 is not None and cls2 >= CLS_GOOD_THRESHOLD
    second["cls_recheck"] = {
        "attempted": True,
        "first_run_cls": cls,
        "second_run_cls": cls2,
        "confirmed": confirmed,
    }
    return second


def main():
    ap = argparse.ArgumentParser(description="Google PageSpeed Insights по списку URL")
    ap.add_argument("urls", nargs="+", help="Один или несколько URL")
    ap.add_argument("--out", type=Path, help="Куда сохранить JSON (по умолчанию — печать)")
    ap.add_argument("--strategy", choices=["mobile", "desktop", "both"], default="both")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    api_key = load_api_key(repo_root)

    strategies = ["mobile", "desktop"] if args.strategy == "both" else [args.strategy]

    result = {}
    for url in args.urls:
        result[url] = {}
        for strategy in strategies:
            print(f"[PSI] {strategy}: {url}", flush=True)
            res = run_psi_verified(url, api_key, strategy)
            if res.get("cls_recheck", {}).get("attempted"):
                rc = res["cls_recheck"]
                if "error" in rc:
                    print(f"    ! CLS выбивался (>= {CLS_GOOD_THRESHOLD}), перепроверка не удалась: {rc['error']}", flush=True)
                elif rc["confirmed"]:
                    print(f"    ✓ CLS {rc['first_run_cls']:.3f} подтверждён повторным прогоном ({rc['second_run_cls']:.3f})", flush=True)
                else:
                    print(f"    ⚠ CLS {rc['first_run_cls']:.3f} НЕ подтвердился — второй прогон дал {rc['second_run_cls']:.3f}, взято второе значение", flush=True)
            result[url][strategy] = res
            time.sleep(1.0)

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        print(f"OK: {args.out}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
