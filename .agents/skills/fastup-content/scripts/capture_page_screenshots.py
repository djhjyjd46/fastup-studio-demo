#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Снять скриншоты страниц сайта (десктоп + мобильный) в папку — для фиксации
состояния «до» и «после» переработки.

Скриншот «до» невозможно снять задним числом, поэтому он делается до правок и
кладётся в отдельную датированную папку, которая дальше не перезаписывается.

Пример:
  python scripts/capture_page_screenshots.py --out design/previews/before-2026-08-16
  python scripts/capture_page_screenshots.py --out design/previews/after-2026-09-13
"""
import argparse
import pathlib
import re
import sys

DEFAULT_URLS = [
    "https://fastup.by/",
    "https://fastup.by/razrabotka-saitov/",
    "https://fastup.by/seo-prodvizhenie/",
    "https://fastup.by/kontekstnaya-reklama/",
    "https://fastup.by/geo-audit-system/",
]

VIEWPORTS = {"desktop": (1440, 900), "mobile": (375, 812)}


def slug(url):
    s = re.sub(r"^https?://", "", url).rstrip("/")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-")
    return s or "index"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="каталог для скриншотов")
    ap.add_argument("--urls", nargs="*", default=DEFAULT_URLS)
    ap.add_argument("--full-page", action="store_true", default=True)
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright не установлен: pip install playwright && playwright install chromium")

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for url in args.urls:
            for name, (w, h) in VIEWPORTS.items():
                page = browser.new_page(viewport={"width": w, "height": h})
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                except Exception as exc:  # noqa: BLE001 — сетевая ошибка не должна ронять весь прогон
                    print(f"  ПРОПУЩЕНО {url} [{name}]: {exc}")
                    page.close()
                    continue
                page.wait_for_timeout(1200)  # доигрывают ленивые изображения и переходы
                path = out / f"{slug(url)}--{name}.png"
                page.screenshot(path=str(path), full_page=args.full_page)
                print(f"  {path} ({w}x{h})")
                page.close()
        browser.close()
    print(f"Готово: {out}")


if __name__ == "__main__":
    main()
