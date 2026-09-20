#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Строит HTML-страницу с графиками помесячной динамики спроса.

    python scripts/market_chart.py --months 24 --out ads/reports/market-demand.html

Тянет помесячные данные Wordstat по фразам из конфига, рисует inline-SVG (без внешних
библиотек, файл самодостаточный — можно отправить кому угодно) и считает две базы
сравнения: год назад и два года назад.

Зачем два года: замер на 12 месяцах обманывает, если год назад был пик. Для «разработка
сайта» база августа 2025 оказалась пиком двухлетнего всплеска, и годовое падение −77%
превращалось в −37% при взгляде на 24 месяца.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_load import load_env, require

API = "https://searchapi.api.cloud.yandex.net/v2/wordstat/dynamics"
COLORS = ["#C1443B", "#D98324", "#3E7CB1", "#2E7D5B", "#7A5AA8", "#8A8F98"]


CACHE = Path(__file__).resolve().parent.parent / "ads" / "campaigns" / "wordstat-monthly.json"


def cached(phrase, regions, key, folder, months):
    """Кэш на диске: Wordstat отдаёт 429 при частых запросах, а данные помесячные."""
    store = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    if phrase in store and len(store[phrase]) >= months - 1:
        return [(m, c) for m, c in store[phrase]]
    for attempt in range(4):
        try:
            data = dynamics(phrase, regions, key, folder, months)
            store[phrase] = data
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
            time.sleep(2)
            return data
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            wait = 10 * (attempt + 1)
            print("    429, жду {} с".format(wait), flush=True)
            time.sleep(wait)
    return []


def dynamics(phrase, regions, key, folder, months):
    first = date.today().replace(day=1)
    start = (first - timedelta(days=31 * months)).replace(day=1)
    end = first - timedelta(days=1)
    body = json.dumps({"phrase": phrase, "regions": regions, "folderId": folder,
                       "period": "PERIOD_MONTHLY",
                       "fromDate": start.isoformat() + "T00:00:00Z",
                       "toDate": end.isoformat() + "T00:00:00Z"}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": "Api-Key " + key, "Content-Type": "application/json; charset=utf-8"})
    data = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    return [(r["date"][:7], int(r["count"])) for r in data.get("results", [])]


def chart(series, title, subtitle):
    """Линейный график в индексах: первая точка каждой линии = 100."""
    w, h = 860, 340
    pad_l, pad_r, pad_t, pad_b = 46, 168, 26, 40
    months = [m for m, _ in series[0][1]]
    n = len(months)
    values = [[v for _, v in s] for _, s in series]
    idx = [[(v / s[0] * 100 if s[0] else 0) for v in s] for s in values]
    top = max(max(line) for line in idx)
    top = 120 if top <= 120 else (200 if top <= 200 else (round(top / 100) + 1) * 100)

    def x(i):
        return pad_l + i * (w - pad_l - pad_r) / (n - 1)

    def y(v):
        return pad_t + (1 - v / top) * (h - pad_t - pad_b)

    parts = ['<svg viewBox="0 0 {} {}" width="100%" role="img" aria-label="{}">'.format(w, h, title)]
    for gv in [0, 50, 100] + ([200] if top >= 200 else []) + ([top] if top > 200 else []):
        if gv > top:
            continue
        parts.append('<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="var(--grid)" stroke-width="1"/>'
                     .format(pad_l, y(gv), w - pad_r, y(gv)))
        parts.append('<text x="{}" y="{:.1f}" fill="var(--dim)" font-size="11" text-anchor="end">{}</text>'
                     .format(pad_l - 7, y(gv) + 4, gv))
    step = max(1, n // 8)
    for i in range(0, n, step):
        parts.append('<text x="{:.1f}" y="{}" fill="var(--dim)" font-size="10.5" text-anchor="middle">{}</text>'
                     .format(x(i), h - pad_b + 17, months[i][2:].replace("-", ".")))
    labels = []
    for k, (name, s) in enumerate(series):
        line = idx[k]
        color = COLORS[k % len(COLORS)]
        d = " ".join(("M" if i == 0 else "L") + "{:.1f} {:.1f}".format(x(i), y(v)) for i, v in enumerate(line))
        parts.append('<path d="{}" fill="none" stroke="{}" stroke-width="2.2" stroke-linejoin="round"/>'
                     .format(d, color))
        parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="3.4" fill="{}"/>'
                     .format(x(n - 1), y(line[-1]), color))
        labels.append([y(line[-1]), name, color, line[-1]])

    # разводим подписи по вертикали, если линии сошлись в одной точке
    labels.sort(key=lambda a: a[0])
    for i in range(1, len(labels)):
        if labels[i][0] - labels[i - 1][0] < 34:
            labels[i][0] = labels[i - 1][0] + 34
    shift = labels[-1][0] - (h - pad_b) if labels and labels[-1][0] > h - pad_b else 0
    for ly, name, color, val in labels:
        ly -= shift
        parts.append('<text x="{}" y="{:.1f}" fill="{}" font-size="12.5" font-weight="600">{}</text>'
                     .format(w - pad_r + 12, ly + 4, color, name))
        parts.append('<text x="{}" y="{:.1f}" fill="var(--dim)" font-size="11">индекс {:.0f}</text>'
                     .format(w - pad_r + 12, ly + 19, val))
    parts.append("</svg>")
    return ('<figure><figcaption><b>{}</b><span>{}</span></figcaption>{}</figure>'
            .format(title, subtitle, "".join(parts)))


PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Спрос в IT-нишах Беларуси, {period}</title>
<style>
 :root{{--bg:#FBFAF8;--panel:#fff;--ink:#1A1A18;--dim:#6E6F6A;--line:#E5E4DF;--grid:#EDECE7}}
 @media (prefers-color-scheme:dark){{:root{{--bg:#131412;--panel:#1B1C19;--ink:#EDEDE8;--dim:#9A9B94;--line:#2A2B27;--grid:#24251F}}}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
   font:16px/1.6 "Inter","Segoe UI",system-ui,sans-serif}}
 .wrap{{max-width:900px;margin:0 auto;padding:40px 20px 70px;display:flex;flex-direction:column;gap:34px}}
 h1{{font-size:31px;line-height:1.15;margin:0;letter-spacing:-.02em}}
 h2{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim);margin:0}}
 p{{margin:0;max-width:66ch}} .dim{{color:var(--dim)}}
 section{{display:flex;flex-direction:column;gap:14px}}
 figure{{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:5px;padding:16px 18px 10px}}
 figcaption{{display:flex;flex-direction:column;gap:3px;margin-bottom:8px}}
 figcaption b{{font-size:16px}} figcaption span{{font-size:13.5px;color:var(--dim)}}
 table{{border-collapse:collapse;width:100%;font-size:14.5px}}
 th{{text-align:right;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);
    font-weight:600;padding:0 12px 7px;border-bottom:1px solid var(--line)}}
 th:first-child{{text-align:left}}
 td{{padding:7px 12px;border-bottom:1px solid var(--line);text-align:right;
    font-variant-numeric:tabular-nums;white-space:nowrap}}
 td:first-child{{text-align:left}}
 .up{{color:#1B7A4B;font-weight:600}} .down{{color:#B3392C;font-weight:600}}
 .box{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--ink);
   border-radius:5px;padding:16px 18px;display:flex;flex-direction:column;gap:9px}}
 footer{{border-top:1px solid var(--line);padding-top:14px;color:var(--dim);font-size:13px}}
 @media print{{body{{background:#fff}} figure,.box{{break-inside:avoid}}}}
</style></head><body><div class="wrap">
{body}
</div></body></html>"""


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="ads/campaigns/market-chart-phrases.json")
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--out", required=True)
    ap.add_argument("--regions", default="149")
    args = ap.parse_args()

    key, folder = require("YANDEX_CLOUD_API_KEY"), require("YANDEX_CLOUD_FOLDER_ID")
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    regions = args.regions.split(",")

    data = {}
    for group in cfg["charts"]:
        for phrase in group["phrases"]:
            if phrase not in data:
                print("  " + phrase, flush=True)
                data[phrase] = cached(phrase, regions, key, folder, args.months)

    blocks = [cfg["intro"].format(months=args.months)]
    for group in cfg["charts"]:
        series = [(p, data[p]) for p in group["phrases"] if data.get(p)]
        if not series:
            continue
        blocks.append("<section><h2>{}</h2>{}</section>".format(
            group["section"], chart(series, group["title"], group["subtitle"])))

    rows = []
    for phrase, s in data.items():
        by = dict(s)
        last = s[-1]
        y1 = by.get(s[-13][0]) if len(s) >= 13 else None
        y2 = s[0][1]
        def pct(a, b):
            return "—" if not a else '<span class="{}">{:+.0f}%</span>'.format(
                "up" if b >= a else "down", (b - a) / a * 100)
        rows.append("<tr><td>{}</td><td>{:,}</td><td>{}</td><td>{}</td></tr>".format(
            phrase, last[1], pct(y1, last[1]), pct(y2, last[1])).replace(",", " "))
    blocks.append("""<section><h2>Итог</h2><table>
      <thead><tr><th>Запрос</th><th>В месяц сейчас</th><th>За год</th><th>За два года</th></tr></thead>
      <tbody>{}</tbody></table></section>""".format("".join(rows)))
    blocks.append(cfg["outro"])

    period = "{} — {}".format(list(data.values())[0][0][0], list(data.values())[0][-1][0])
    Path(args.out).write_text(PAGE.format(period=period, body="\n".join(blocks)), encoding="utf-8")
    print("\nстраница: " + args.out)


if __name__ == "__main__":
    main()
