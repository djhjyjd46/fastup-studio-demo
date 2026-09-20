#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Сборка страницы отрасли «Индекса видимости в ИИ-поиске» из данных замера.

Верстает по живой дизайн-системе fastup-v2: используются ТОЛЬКО классы, реально
присутствующие в собранном CSS темы (сняты с живых страниц 2026-08-22). Новых
Tailwind-классов не вводить — они не отрендерятся без пересборки CSS.

Стоп-правило (geo/index/PROMPT-stranitsa.md): числа берутся только из завершённого
замера. Файл проверяется до генерации; пробный прогон отбрасывается.

Запуск:
  python scripts/index_build_page.py --industry zagorodnoe-stroitelstvo --publish
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = ROOT / "geo" / "index"

SECTION = "max-w-6xl mx-auto px-3 sm:px-6 py-8 md:py-20"
SECTION_ALT = "bg-slate-100/50 border-y border-slate-200/60 py-8 md:py-20"
CARD = ("bg-white border border-slate-200/60 rounded-[24px] sm:rounded-[32px] "
        "p-4 sm:p-6 shadow-sm hover:shadow-md hover:border-sky-400 transition-all duration-700 ease-out")
CARD_SOFT = "bg-sky-50/50 border border-sky-200/70 rounded-[24px] sm:rounded-[32px] p-6 sm:p-8"
BADGE = ("inline-flex items-center gap-2 bg-sky-100/70 border border-sky-200 text-sky-800 "
         "font-bold px-3.5 sm:px-4 py-1.5 rounded-full text-xs uppercase tracking-wider mb-4 md:mb-6")
BTN = ("inline-flex items-center gap-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold "
       "px-5 py-2.5 rounded-xl transition shadow-sm hover:shadow-md")


def validate(data: dict, expected_queries: int) -> list:
    """Стоп-правило: возвращает список причин, по которым файл нельзя использовать."""
    bad = []
    if len(data.get("queries", [])) < expected_queries:
        bad.append(f"запросов в файле {len(data.get('queries', []))}, ожидалось {expected_queries}")
    if not data.get("engines"):
        bad.append("не указаны движки")
    if not data.get("hits"):
        bad.append("поле hits пустое — компании не найдены ни разу")
    if not data.get("answers"):
        bad.append("нет собранных ответов")
    return bad


def top_brands(data: dict, limit: int = 5) -> list:
    """Топ строится по тому, кого ИИ реально называет, а не по пересечению с выборкой."""
    merged = {}
    for name, per in data.get("hits", {}).items():
        merged[name] = dict(per)
    ranked = sorted(merged.items(), key=lambda kv: -sum(kv[1].values()))
    return ranked[:limit]


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def build_html(data: dict, industry_title: str, region: str, month_label: str) -> str:
    queries = data["queries"]
    nq = len(queries)
    total = data.get("companies_total", 0)
    top = top_brands(data, 10)
    named = len(data.get("hits", {}))
    engines_ru = {"google": "Google AI Overview", "yandex": "Обзор от Алисы",
                  "chatgpt": "ChatGPT (веб-поиск)"}
    engines = ", ".join(engines_ru.get(e, e) for e in data.get("engines", []))

    rows = []
    per_engine_total = {e: 0 for e in data.get("engines", [])}
    for a in data.get("answers", []):
        if a.get("engine") in per_engine_total:
            per_engine_total[a["engine"]] += 1
    answers_total = sum(per_engine_total.values()) or 1
    for i, (name, per) in enumerate(top, 1):
        cnt = sum(per.values())
        share = round(100 * cnt / answers_total)
        cells = ""
        for e in data.get("engines", []):
            v = per.get(e, 0)
            cells += (f'<td class="py-4 px-5 align-top text-center '
                      f'{"font-semibold text-slate-800" if v else "text-slate-400"}">'
                      f'{v if v else "—"}</td>')
        rows.append(f"""
                    <tr class="hover:bg-slate-50/60 transition-all duration-700 ease-out">
                        <th scope="row" class="py-4 px-5 text-left font-semibold text-slate-700 bg-slate-50/40 align-top">{i}. {esc(name)}</th>
                        {cells}
                        <td class="py-4 px-5 align-top text-center font-medium text-slate-700 bg-sky-50/30 border-l border-sky-200/70">{cnt}</td>
                        <td class="py-4 px-5 align-top text-center font-bold text-sky-700 bg-sky-50/30">{share}%</td>
                    </tr>""")

    reg = json.loads((INDEX_DIR / "industries.json").read_text(encoding="utf-8"))["industries"]
    cards = []
    for it in reg:
        if it.get("status") == "ready":
            meta = f'Замер от {it.get("measured_at","")}, обновление {it.get("next_at","")}'
            tag = ('<span class="inline-flex items-center bg-sky-100/70 border border-sky-200 text-sky-800 '
                   'font-bold px-3 py-1 rounded-full text-xs uppercase tracking-wider mb-3">Готово</span>')
            link = (f'<a href="/indeks-vidimosti/{it["slug"]}/" class="inline-flex items-center gap-2 '
                    f'text-sky-600 font-bold text-sm hover:text-sky-700 transition duration-700 ease-out mt-3">'
                    f'Смотреть замер</a>')
        else:
            meta = f'Срез готовится, выход {it.get("planned_at","")}'
            tag = ('<span class="inline-flex items-center bg-slate-100 border border-slate-200 text-slate-600 '
                   'font-bold px-3 py-1 rounded-full text-xs uppercase tracking-wider mb-3">В работе</span>')
            link = ""
        cards.append(
            f'<div class="{CARD}">{tag}'
            f'<h3 class="text-lg font-bold text-slate-800 mb-2">{esc(it["title"])}</h3>'
            f'<p class="text-xs sm:text-sm text-slate-600 leading-relaxed">{esc(it["region"])}</p>'
            f'<p class="text-xs text-slate-600 mt-2">{esc(meta)}</p>{link}</div>')
    ind_cards = "".join(cards)

    q_items = "".join(
        f'<li class="py-2 border-b border-slate-200/60 last:border-0">{esc(q)}</li>' for q in queries)

    return f"""
<section class="{SECTION}">
  <div class="{BADGE}">Первый в Беларуси индекс видимости в нейросетях</div>
  <h1 class="h1-hero">Кого нейросети советуют клиентам в Беларуси</h1>
  <p class="p-section-sub">Каждый месяц замеряем, какие белорусские компании называют ChatGPT, Google и Яндекс,
  когда у них спрашивают, кому доверить работу. Первый срез — {esc(industry_title)}, {esc(region)}:
  из {total} компаний отрасли нейросети называют {named}.</p>
</section>

<section class="{SECTION_ALT}">
  <div class="max-w-6xl mx-auto px-3 sm:px-6">
    <h2 class="h2-section">{esc(industry_title.capitalize())} — {esc(region)}, {esc(month_label)}</h2>
    <div class="overflow-x-auto rounded-[24px] sm:rounded-[32px] border border-slate-200/70 shadow-sm bg-white mb-8 mt-6">
      <table class="w-full text-left text-sm text-slate-700 border-collapse">
        <thead class="bg-slate-50/60 text-slate-700 font-semibold border-b border-slate-200/70">
          <tr>
            <th scope="col" class="py-4 px-5">Компания</th>
            <th scope="col" class="py-4 px-5 text-center">Google</th>
            <th scope="col" class="py-4 px-5 text-center">Яндекс</th>
            <th scope="col" class="py-4 px-5 text-center">ChatGPT</th>
            <th scope="col" class="py-4 px-5 text-center bg-sky-50/70 text-sky-900 font-bold border-l border-sky-200/70">Всего</th>
            <th scope="col" class="py-4 px-5 text-center bg-sky-50/70 text-sky-900 font-bold">Доля ответов</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200/60">{"".join(rows)}
        </tbody>
      </table>
    </div>

    <p class="text-xs sm:text-sm text-slate-600 mb-8">Доля ответов — сколько из {answers_total} полученных
    ответов содержали упоминание компании. Считается делением, без весов и скрытых коэффициентов.</p>

    <div class="{CARD_SOFT}">
      <h3 class="text-lg sm:text-xl font-bold text-slate-900 mb-4">Вашей компании нет в списке?</h3>
      <p class="text-sm sm:text-lg text-slate-600 leading-relaxed mb-6">Клиент спрашивает нейросеть, кому доверить
      работу, и получает пять названий. Работать он будет с этими пятью. Покажем ваше место в замере и то,
      по каким запросам вас не называют.</p>
      <a href="/kontakty/" class="{BTN}">Узнать своё место в замере</a>
    </div>
  </div>
</section>

<section class="{SECTION}">
  <h2 class="h2-section">Отрасли в индексе</h2>
  <p class="p-section-sub">Каждый месяц добавляем новые срезы. Ниже — что уже замерено и что выходит следующим.</p>
  <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 mt-6">{ind_cards}</div>
</section>

<section class="{SECTION_ALT}">
  <div class="max-w-6xl mx-auto px-3 sm:px-6">
  <h2 class="h2-section">Что спрашивают у нейросетей в этой отрасли</h2>
  <p class="p-section-sub">{nq} запросов, на которых строится замер. По ним клиент и выбирает подрядчика.</p>
  <div class="{CARD} mt-6">
    <ol class="text-sm sm:text-base text-slate-700 leading-relaxed list-decimal pl-5">{q_items}</ol>
  </div>
  <p class="text-xs sm:text-sm text-slate-600 mt-6">Системы: {esc(engines)}.
  <a href="/indeks-vidimosti/metodika/" class="text-sky-600 font-bold hover:text-sky-700 transition">Методика</a></p>
  </div>
</section>
""".strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--industry", required=True)
    ap.add_argument("--title", default="загородное строительство")
    ap.add_argument("--region", default="Минск и область")
    ap.add_argument("--month", default="август 2026")
    ap.add_argument("--data")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    d = INDEX_DIR / args.industry
    data_path = Path(args.data) if args.data else sorted(d.glob("*-data.json"))[-1]
    if "probe" in data_path.name:
        sys.exit(f"ОТКАЗ: {data_path.name} — пробный прогон. Нужен полный замер.")
    data = json.loads(data_path.read_text(encoding="utf-8"))

    expected = len([l for l in (d / "queries.md").read_text(encoding="utf-8").splitlines()
                    if re.match(r"^\s*\d+\.\s+", l)])
    problems = validate(data, expected)
    if problems:
        print(f"ОТКАЗ по стоп-правилу ({data_path.name}):")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    html = build_html(data, args.title, args.region, args.month)
    out = Path(args.out) if args.out else d / "page.html"
    out.write_text(html, encoding="utf-8")
    print(f"страница собрана: {out} ({len(html)} символов)")
    print(f"источник данных: {data_path.name}, запросов {len(data['queries'])}, "
          f"движков {len(data['engines'])}, компаний в hits {len(data['hits'])}")


if __name__ == "__main__":
    main()
