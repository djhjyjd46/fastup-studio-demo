#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Прогонщик отраслевого замера для «Индекса видимости в ИИ-поиске».

Меряет один наблюдаемый факт: названа компания в ответе ИИ или нет.
Спецификация — geo/index/SPEC.md.

ВАЖНО про поверхность замера. Меряются именно ИИ-ответы, а не поисковая выдача.
Это не мелочь: `scripts/geo_check.py` (GAS v1.4.2) для «Яндекса» и «Google» собирал
список url/title из обычного SERP, из-за чего замеры до 2026-08-22 мерили не то, что
заявлено. Здесь для Google и Яндекса берётся блок <ai> XMLRiver, для ChatGPT —
Responses API с инструментом web_search.

Движки:
  google   — «Обзор от ИИ» Google через XMLRiver (country=by), XMLRIVER_*
  yandex   — «Обзор от Алисы» через XMLRiver, требует включённой платной опции
             в кабинете XMLRiver (25 руб/1000 + 10 руб наценки)
  chatgpt  — OpenAI web search через ProxyAPI, PROXYAPI_KEY

Запуск:
  python scripts/index_measure.py --industry zagorodnoe-stroitelstvo \
      --engines google,yandex,chatgpt --runs 3
"""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = ROOT / "geo" / "index"

XMLRIVER_ENDPOINTS = {
    "google": "http://xmlriver.com/search/xml",
    "yandex": "http://xmlriver.com/search_yandex/xml",
}

# Названия, совпадающие с обычными словами: матчить по ним нельзя — дадут
# ложные срабатывания в любом тексте про стройку.
STOPNAMES = {
    "стройматериалы", "строительство", "дома", "домострой", "стройка",
    "проект", "проекты", "ремонт", "коттедж", "коттеджи", "сруб", "срубы",
}

# Слова, из которых состоит обычная речь отрасли. Название, целиком собранное из них
# («Деревянные дома», «Строим Дом», «Дом под ключ»), в тексте про стройку встретится
# всегда — такие засчитываются ТОЛЬКО по совпадению домена.
# Проверено 2026-08-22: «Деревянные дома» ловилось на описании ArchiLine, «Строим Дом» —
# на глаголе «мы строим», «Барнхаус» — на другой компании «БарнХаусБел».
GENERIC_WORDS = {
    "дом", "дома", "домов", "домик", "под", "ключ", "строй", "строим", "строит",
    "строительство", "строительная", "компания", "деревянные", "деревянный",
    "каркас", "каркасные", "каркасный", "брус", "бруса", "блок", "блоки",
    "коттедж", "коттеджи", "загородный", "проект", "проекты", "бани", "баня",
    "беседки", "фахверк", "сруб", "и", "в", "на", "из", "по", "бел",
}


def load_env() -> dict:
    env = dict(os.environ)
    from env_load import env_file_path  # из worktree — .env основной копии
    f = env_file_path()
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def norm(text: str) -> str:
    """Нормализация для сравнения: регистр, кавычки, ё, орг-формы."""
    t = text.lower().replace("ё", "е")
    t = re.sub(r"[«»\"'`]", " ", t)
    t = re.sub(r"\b(ооо|чуп|одо|ип|зао|оао|тчуп|учп)\b", " ", t)
    t = re.sub(r"[^0-9a-zа-я\.\-]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def clean_site(raw: str) -> str:
    """Один URL из поля сайта источника (Excel/Карты иногда кладут туда несколько
    ссылок через запятую — «сайт, /проекты, /каталог» — что ломает href целиком).
    Найдено 2026-08-22 на 22 из 328 записей загородного строительства."""
    if not raw:
        return ""
    first = re.split(r"[,\s]+", raw.strip())[0].strip()
    if not first:
        return ""
    if not re.match(r"^https?://", first, re.I):
        first = "https://" + first.lstrip("/")
    return first


def domain_of(url: str) -> str:
    if not url:
        return ""
    u = re.sub(r"^https?://", "", url.strip().lower()).split("/")[0]
    return u[4:] if u.startswith("www.") else u


def canon(name: str) -> str:
    """Каноничная форма названия — чтобы «Зодчий» и «Зодчие» не считались дважды."""
    n = norm(name)
    n = re.sub(r"(bel|by|\.by)", "", n).strip()
    return re.sub(r"(ий|ие|ый|ые|ая|ой|а|ы|и|е)$", "", n) if len(n) > 6 else n


def brand_stem(name: str) -> str:
    """Основа названия без окончания — грубый учёт склонений («хата»→«хат»)."""
    n = norm(name)
    return n[:-1] if len(n) > 5 and n[-1] in "аяуюыиеоьй" else n


def mentioned(company: dict, answer: str) -> bool:
    a = norm(answer)
    dom = domain_of(clean_site(company.get("site", "")))
    if dom and dom in answer.lower():
        return True
    name_n = norm(company["name"])
    if not name_n or name_n in STOPNAMES or len(name_n) < 4:
        return False
    # Название целиком из общеотраслевых слов — только по домену, иначе ловит обычную речь.
    if all(w in GENERIC_WORDS for w in name_n.split()):
        return False
    # Границы слова: «Барнхаус» не должен срабатывать внутри «БарнХаусБел».
    if re.search(r"(?<![0-9a-zа-я])" + re.escape(name_n) + r"(?![0-9a-zа-я])", a):
        return True
    stem = brand_stem(company["name"])
    if not stem or len(stem) < 6:
        return False
    # Правая граница обязательна, но с допуском на окончание (склонение): «хат» + «ы» — да,
    # «барнхаус» + «бел» — нет. Без этого чужое название ловится по своему префиксу.
    return bool(re.search(r"(?<![0-9a-zа-я])" + re.escape(stem) + r"[а-я]{0,2}(?![0-9a-zа-я])", a))


def strip_html(fragment: str) -> str:
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return html.unescape(re.sub(r"\s+", " ", txt)).strip()


# ---------- движки ----------
# Каждый возвращает {"text": str, "sources": [{"title","url"}]}.
# sources — это список источников, из которых ИИ собрал ответ: он отвечает на вопрос
# «откуда модель взяла лидеров», ради которого и делается разбор «что общего у топ-5».

def ask_xmlriver_ai(query: str, env: dict, engine: str) -> dict:
    params = urllib.parse.urlencode({
        "user": env["XMLRIVER_USER"], "key": env["XMLRIVER_KEY"],
        "query": query, "country": "by", "ai": "1", "groupby": "10",
    })
    url = XMLRIVER_ENDPOINTS[engine] + "?" + params
    # Код 500 у XMLRiver — сетевая ошибка, до 20% ответов с ней норма (их документация),
    # нужен повтор без остановки сбора. Плюс код 115 — блокировка за частые запросы.
    last = ""
    for attempt in range(4):
        try:
            raw = urllib.request.urlopen(url, timeout=90).read().decode("utf-8", "replace")
        except Exception as exc:                                   # noqa: BLE001
            last = str(exc)
            time.sleep(2)
            continue
        block = re.search(r"<ai>(.*?)</ai>", raw, re.S)
        if not block:
            err = re.search(r"<error[^>]*>(.*?)</error>", raw, re.S)
            last = f"нет блока <ai>" + (f"; {strip_html(err.group(1))}" if err else "")
            # Блок может отсутствовать законно: ИИ-обзор показывается не на каждый запрос.
            if err:
                time.sleep(2)
                continue
            return {"text": "", "sources": [], "note": "ИИ-обзор не показан для этого запроса"}
        inner = block.group(1)
        if "<present>" in inner and "<answer>" not in inner:
            return {"text": "", "sources": [],
                    "note": "включён только базовый режим: XMLRiver отдаёт факт наличия "
                            "блока, но не его текст — включите платную опцию AI в кабинете"}
        # Формат различается: Google -> <answer>base64</answer> + <item><title><url>,
        # Яндекс -> <item><content>base64</content><position><type></item>.
        # Проверено 2026-08-22; парсить только гугловский вариант нельзя.
        payload = re.search(r"<answer>(.*?)</answer>", inner, re.S) or                   re.search(r"<content>(.*?)</content>", inner, re.S)
        text, page_html = "", ""
        if payload and payload.group(1).strip():
            try:
                page_html = base64.b64decode(payload.group(1)).decode("utf-8", "replace")
            except Exception:                                      # noqa: BLE001
                page_html = payload.group(1)
            text = strip_html(page_html)
        sources = []
        for item in re.findall(r"<item>(.*?)</item>", inner, re.S):
            t = re.search(r"<title>(.*?)</title>", item, re.S)
            u = re.search(r"<url>(.*?)</url>", item, re.S)
            if u:
                sources.append({"title": strip_html(t.group(1)) if t else "",
                                "url": u.group(1).strip()})
        if not sources and page_html:
            # У Яндекса ссылки на источники лежат внутри HTML самого блока.
            for href in re.findall(r'href="(https?://[^"]+)"', page_html):
                if "yandex." in href or "/search" in href:
                    continue
                sources.append({"title": "", "url": html.unescape(href)})
        return {"text": text, "sources": sources}
    return {"text": "", "sources": [], "error": last}


def ask_google(query: str, env: dict) -> dict:
    return ask_xmlriver_ai(query, env, "google")


def ask_yandex(query: str, env: dict) -> dict:
    return ask_xmlriver_ai(query, env, "yandex")


def ask_chatgpt(query: str, env: dict) -> dict:
    body = {"model": "gpt-4o-mini", "tools": [{"type": "web_search"}], "input": query}
    req = urllib.request.Request(
        "https://api.proxyapi.ru/openai/v1/responses",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + env["PROXYAPI_KEY"],
                 "Content-Type": "application/json; charset=utf-8"})
    data = json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8"))
    text, sources = [], []
    for o in data.get("output", []):
        if o.get("type") != "message":
            continue
        for c in o.get("content", []):
            text.append(c.get("text", ""))
            for ann in c.get("annotations", []) or []:
                if ann.get("url"):
                    sources.append({"title": ann.get("title", ""), "url": ann["url"]})
    return {"text": "\n".join(text), "sources": sources}


ENGINES = {"google": ask_google, "yandex": ask_yandex, "chatgpt": ask_chatgpt}


def extract_brands(answer: str) -> list:
    """Имена компаний, которые ИИ назвал сам.

    Круг, из которого модель берёт ответ, шире любой нашей выборки (проверено
    2026-08-22: в ответах регулярно всплывают компании, отсутствующие в категории
    Яндекс.Карт). Поэтому топ строится по тому, кого реально называют, а выборка
    служит для обратной задачи — кого не называют ни разу.
    """
    names = []
    for m in re.finditer(r"\*\*\[?([^\]\*\n]{3,80}?)\]?\*\*", answer):
        n = m.group(1).strip(" .:—-")
        if not n or n.lower().startswith(("закрыто", "открыто")):
            continue
        if "|" in n:
            n = n.split("|")[-1].strip()
        n = re.sub(r"^[«\"']|[»\"']$", "", n).strip()
        if len(n) >= 3 and not re.match(r"^\d", n):
            names.append(n)
    seen, out = set(), []
    for n in names:
        k = norm(n)
        if k and k not in seen:
            seen.add(k)
            out.append(n)
    return out


def parse_queries(path: Path) -> list:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*(\d+)\.\s+(.+?)\s*$", line)
        if m:
            # Служебные HTML-комментарии (частотность кластера) не должны уезжать в ИИ
            # вместе с запросом — найдено 2026-08-22, испортило целый прогон.
            q = re.sub(r"<!--.*?-->", "", m.group(2)).strip()
            if q:
                out.append(q)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--industry", required=True)
    ap.add_argument("--engines", default="google,yandex,chatgpt")
    ap.add_argument("--runs", type=int, default=None,
                     help="одно число прогонов на все движки; если не задано, берутся "
                          "дефолты RUNS_PER_ENGINE (дешёвые движки гоняются чаще)")
    ap.add_argument("--limit-queries", type=int, default=0)
    ap.add_argument("--out-suffix", default="")
    args = ap.parse_args()

    env = load_env()
    d = INDEX_DIR / args.industry
    companies = json.loads((d / "companies.json").read_text(encoding="utf-8"))
    queries = parse_queries(d / "queries.md")
    if args.limit_queries:
        queries = queries[: args.limit_queries]

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]

    # XMLRiver (google/yandex) стоит ~3,5 копейки за запрос с ai=1 — прогоняем чаще для
    # устойчивости среднего. ProxyAPI/ChatGPT дороже (~2-3 руб/запрос).
    # Проверено 2026-08-22: при chatgpt=1 часть реальных конкурентов (пример: «Хоромы»,
    # державшиеся только на ChatGPT) выпадает из топа просто из-за меньшей выборки — это
    # не вариативность, а потеря реального сигнала. Решение Егора 2026-08-22: chatgpt=2
    # (компромисс цена/полнота), не 1.
    RUNS_PER_ENGINE = {"google": 5, "yandex": 5, "chatgpt": 2}
    runs_map = {e: (args.runs if args.runs is not None else RUNS_PER_ENGINE.get(e, 3))
                for e in engines}

    print(f"выборка: {len(companies)} компаний | запросов: {len(queries)} | "
          f"движки: {engines} | прогонов по движкам: {runs_map}")

    res = {"industry": args.industry, "date": str(date.today()),
           "engines": engines, "runs_per_engine": runs_map, "queries": queries,
           "companies_total": len(companies),
           "answers": [], "hits": {}, "brands_named": {}, "sources": {}}

    # XMLRiver: стандартный аккаунт держит 10 параллельных потоков (их документация,
    # раздел «Способы сбора»). Код 115 — это превышение лимита, а не сам факт параллели.
    # Берём 8 с запасом. ProxyAPI гоняем осторожнее — их лимиты не документированы.
    WORKERS = {"google": 8, "yandex": 8, "chatgpt": 3}

    def one(engine, q, run):
        try:
            return engine, q, run, ENGINES[engine](q, env)
        except Exception as exc:                                   # noqa: BLE001
            return engine, q, run, {"text": "", "sources": [], "error": str(exc)}

    for engine in engines:
        n_runs = runs_map[engine]
        jobs = [(engine, q, run) for q in queries for run in range(1, n_runs + 1)]
        done = 0
        with ThreadPoolExecutor(max_workers=WORKERS.get(engine, 4)) as pool:
            futures = [pool.submit(one, *j) for j in jobs]
            for fut in as_completed(futures):
                eng, q, run, r = fut.result()
                done += 1
                text = r.get("text", "")
                note = r.get("note") or r.get("error")
                res["answers"].append({"engine": eng, "query": q, "run": run,
                                       "text": text, "sources": r.get("sources", []),
                                       "note": note})
                found, seen_canon = [], set()
                for c in companies:
                    if not mentioned(c, text):
                        continue
                    k = canon(c["name"])
                    if k in seen_canon:
                        continue
                    seen_canon.add(k)
                    found.append(c["name"])
                for name in found:
                    res["hits"].setdefault(name, {}).setdefault(eng, 0)
                    res["hits"][name][eng] += 1
                for br in extract_brands(text):
                    res["brands_named"].setdefault(br, {}).setdefault(eng, 0)
                    res["brands_named"][br][eng] += 1
                for sc in r.get("sources", []):
                    dom = domain_of(sc.get("url", ""))
                    if dom:
                        res["sources"].setdefault(dom, {}).setdefault(eng, 0)
                        res["sources"][dom][eng] += 1
                (d / f"{date.today():%Y-%m}{args.out_suffix}-data.json").write_text(
                    json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"  [{eng}] {done}/{len(jobs)}: {len(text)} симв., "
                      f"источников {len(r.get('sources', []))}, компаний {len(found)}"
                      + (f" -> {', '.join(found[:4])}" if found else "")
                      + (f"  [{note[:60]}]" if note else ""), flush=True)

    # company_sites — универсально, считается каждый прогон заново из companies.json
    # (не зависит от отрасли). Нужно для кликабельных ссылок на компании в вёрстке.
    res["company_sites"] = {c["name"]: clean_site(c.get("site", ""))
                             for c in companies if clean_site(c.get("site", ""))}

    # intent_map — НЕ пересчитывается тут: кластеризация запросов в интенты у каждой
    # отрасли своя (регулярки под конкретную лексику), это отдельный ручной шаг при
    # сборе карты интентов, не при каждом замере. Persistent-файл на отрасль, чтобы
    # интенты не терялись при перезамере (найдено 2026-08-22: полный перезамер
    # перезаписывал data.json целиком и стирал ранее посчитанные интенты).
    intent_map_file = d / "intent_map.json"
    if intent_map_file.exists():
        res["intent_map"] = json.loads(intent_map_file.read_text(encoding="utf-8"))
    elif "intent_map" in res:
        # На случай будущего вызова, где intent_map передали иначе — сохраняем как
        # persistent-файл, чтобы следующий прогон его подхватил сам.
        intent_map_file.write_text(json.dumps(res["intent_map"], ensure_ascii=False, indent=1),
                                    encoding="utf-8")

    out = d / f"{date.today():%Y-%m}{args.out_suffix}-data.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nсохранено: {out}")

    def table(title, dct, limit=20):
        print(f"\n{title}")
        for k, per in sorted(dct.items(), key=lambda kv: -sum(kv[1].values()))[:limit]:
            print(f"  {k:<44} {sum(per.values()):>3}  {per}")

    table("КОГО ИИ НАЗЫВАЕТ САМ (из ответов):", res["brands_named"])
    table("ИСТОЧНИКИ, ИЗ КОТОРЫХ СОБРАН ОТВЕТ (домены):", res["sources"])
    print(f"\nиз нашей выборки ({len(companies)}) упомянуто: {len(res['hits'])}")
    table("упоминания компаний выборки:", res["hits"])


if __name__ == "__main__":
    main()
