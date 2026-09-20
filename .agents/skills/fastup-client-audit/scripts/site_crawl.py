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
scripts/site_crawl.py

Технический сбор данных с произвольного сайта — единственный вход для субагентов
`technical-seo-auditor` и `geo-auditor`. Краулит один раз, отдаёт один JSON:
и SEO-поля (title/description/H1/канониклы/редиректы), и GEO-сигналы (JSON-LD,
структура «вопрос → ответ», llms.txt, доступность ИИ-краулеров).

Скрипт только СОБИРАЕТ факты. Оценку, приоритеты и рекомендации даёт агент —
здесь нет ни одного «хорошо/плохо».

Использование:
    python scripts/site_crawl.py https://example.by --out G:/fastup-clients/example/crawl.json
    python scripts/site_crawl.py https://example.by --max-pages 40

Зависимости: requests, beautifulsoup4 (уже стоят в окружении).
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = "Mozilla/5.0 (compatible; FastUpAudit/1.0; +https://fastup.by/)"
TIMEOUT = 20

# ИИ-краулеры, доступность которых проверяем в robots.txt (playbook/site-works-checklist.md, фаза 1)
AI_CRAWLERS = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-Web",
    "anthropic-ai", "PerplexityBot", "Google-Extended", "YandexBot",
    "Applebot-Extended", "CCBot", "Bytespider",
]

# Длины, по которым агент судит об обрезке в выдаче (сами пороги — в промпте агента)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})


def fetch(url, allow_redirects=True):
    """Один запрос. Возвращает (response | None, error_str | None)."""
    try:
        t0 = time.time()
        r = SESSION.get(url, timeout=TIMEOUT, allow_redirects=allow_redirects)
        r.elapsed_s = round(time.time() - t0, 3)
        return r, None
    except requests.RequestException as e:
        return None, f"{type(e).__name__}: {e}"


def check_robots(base):
    """robots.txt: наличие, объявленные sitemap, доступность ИИ-краулеров."""
    url = urljoin(base, "/robots.txt")
    r, err = fetch(url)
    out = {"url": url, "exists": False, "error": err, "sitemaps": [], "ai_crawlers": {}, "raw": ""}
    if not r or r.status_code != 200 or "html" in r.headers.get("Content-Type", ""):
        return out

    out["exists"] = True
    text = r.text
    out["raw"] = text[:4000]
    out["sitemaps"] = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", text)

    # Разбор по группам User-agent
    groups, current = {}, []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if re.match(r"(?i)^user-agent:", line):
            agent = line.split(":", 1)[1].strip()
            current = groups.setdefault(agent.lower(), [])
        elif re.match(r"(?i)^disallow:", line) and current is not None:
            current.append(line.split(":", 1)[1].strip())

    for bot in AI_CRAWLERS:
        rules = groups.get(bot.lower())
        if rules is None:
            status = "not_mentioned"          # действует правило для *
        elif "/" in rules:
            status = "blocked_fully"
        elif rules:
            status = "partially_blocked"
        else:
            status = "allowed"
        out["ai_crawlers"][bot] = status
    out["wildcard_disallow"] = groups.get("*", [])
    return out


def check_llms_txt(base):
    """llms.txt — файл-манифест для ИИ-систем."""
    url = urljoin(base, "/llms.txt")
    r, err = fetch(url)
    exists = bool(r and r.status_code == 200 and "html" not in r.headers.get("Content-Type", ""))
    return {"url": url, "exists": exists, "error": err,
            "preview": (r.text[:1000] if exists else "")}


def collect_sitemap_urls(base, robots, limit=500):
    """Карта сайта: из robots.txt + типовые пути. Разворачивает sitemap-индексы."""
    candidates = list(robots.get("sitemaps") or [])
    for path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap-index.xml"):
        u = urljoin(base, path)
        if u not in candidates:
            candidates.append(u)

    found, urls, checked = [], [], set()
    by_segment = {}   # какая карта -> какие URL (нужно для равномерной выборки)
    queue = list(candidates)
    while queue and len(urls) < limit:
        sm = queue.pop(0)
        if sm in checked:
            continue
        checked.add(sm)
        r, _ = fetch(sm)
        if not r or r.status_code != 200:
            continue

        # fetch() по умолчанию идёт по редиректам сама, и без этой проверки кандидат вида
        # /wp-sitemap.xml, который просто 301 на /sitemap_index.xml, выглядит как вторая
        # независимая карта сайта ("обе отдают 200") — реальный баг, найденный 2026-08-21
        # на живом клиентском аудите: находка "две карты сайта" оказалась ложной, вторая
        # была лишь алиасом на первую. final_url — то, что реально отдалось.
        final_url = r.url
        redirected = bool(r.history)
        if final_url in checked and final_url != sm:
            found.append({"url": sm, "status": r.status_code, "redirects_to": final_url,
                          "note": "алиас — контент идентичен уже учтённой карте, не отдельная"})
            continue
        checked.add(final_url)

        try:
            root = ElementTree.fromstring(r.content)
        except ElementTree.ParseError:
            continue
        entry = {"url": sm, "status": r.status_code}
        if redirected:
            entry["redirects_to"] = final_url
        found.append(entry)
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        if root.tag.endswith("sitemapindex"):
            for loc in root.iter(f"{ns}loc"):
                if loc.text:
                    queue.append(loc.text.strip())
        else:
            seg = sm.rsplit("/", 1)[-1].replace(".xml", "")
            bucket = by_segment.setdefault(seg, [])
            for loc in root.iter(f"{ns}loc"):
                if loc.text and len(urls) < limit:
                    u = loc.text.strip()
                    urls.append(u)
                    bucket.append(u)
    return {"found": found, "url_count": len(urls), "urls": urls, "by_segment": by_segment}


def extract_jsonld(soup):
    """Все JSON-LD блоки: типы + сами объекты (агент читает содержимое)."""
    blocks, types = [], []
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            blocks.append({"parse_error": True, "raw_head": raw[:300]})
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict):
                if "@graph" in item and isinstance(item["@graph"], list):
                    items.extend([g for g in item["@graph"] if isinstance(g, dict)])
                    continue
                t = item.get("@type")
                if t:
                    types.extend(t if isinstance(t, list) else [t])
                blocks.append(item)
    return {"types": sorted(set(types)), "blocks": blocks[:20]}


def extract_answer_structure(soup):
    """
    Структура «вопрос → прямой ответ» — ключевой GEO-сигнал (playbook/geo-method.md).
    Для каждого H2/H3: текст заголовка + первые ~60 слов текста под ним.
    Агент сам судит, вопросная ли форма и есть ли прямой ответ с цифрой.
    """
    out = []
    headings = soup.find_all(["h1", "h2", "h3"])
    for h in headings:
        head = " ".join(h.get_text(" ", strip=True).split())
        if not head:
            continue
        # Обход в порядке документа, а не по соседям: на реальных темах заголовок обычно
        # завёрнут в контейнер, и find_next_sibling() не видит текст, лежащий в соседнем
        # блоке-обёртке. Собираем текстовые узлы после заголовка до следующего заголовка.
        words = []
        for node in h.find_all_next(string=True):
            ancestors = list(node.parents)
            if h in ancestors:            # это текст самого заголовка, не ответ под ним
                continue
            names = {a.name for a in ancestors}
            if names & {"script", "style", "noscript"}:
                continue
            if names & {"h1", "h2", "h3"}:  # дошли до следующего заголовка — стоп
                break
            chunk = node.strip()
            if chunk:
                words.extend(chunk.split())
            if len(words) >= 60:
                break
        out.append({"tag": h.name, "heading": head, "first_words": " ".join(words[:60])})
    return out[:40]


def parse_page(url):
    """Один URL → все поля, нужные обоим агентам."""
    r, err = fetch(url)
    if not r:
        return {"url": url, "error": err}

    chain = [{"url": h.url, "status": h.status_code} for h in r.history]
    page = {
        "url": url,
        "final_url": r.url,
        "status": r.status_code,
        "redirect_chain": chain,
        "response_time_s": getattr(r, "elapsed_s", None),
        "html_size_kb": round(len(r.content) / 1024, 1),
        "content_type": r.headers.get("Content-Type", ""),
        "x_robots_tag": r.headers.get("X-Robots-Tag"),
    }
    if r.status_code != 200 or "html" not in page["content_type"]:
        return page

    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else None
    desc_tag = soup.find("meta", attrs={"name": re.compile(r"(?i)^description$")})
    desc = desc_tag.get("content", "").strip() if desc_tag else None
    robots_tag = soup.find("meta", attrs={"name": re.compile(r"(?i)^robots$")})
    canonical = soup.find("link", rel=lambda v: v and "canonical" in v)

    h1s = [" ".join(h.get_text(" ", strip=True).split()) for h in soup.find_all("h1")]
    h2s = [" ".join(h.get_text(" ", strip=True).split()) for h in soup.find_all("h2")]

    images = soup.find_all("img")
    no_alt = [i.get("src", "")[:160] for i in images if not (i.get("alt") or "").strip()]

    body_text = soup.get_text(" ", strip=True)

    page.update({
        "title": title,
        "title_len": len(title) if title else 0,
        "description": desc,
        "description_len": len(desc) if desc else 0,
        "meta_robots": robots_tag.get("content") if robots_tag else None,
        "canonical": canonical.get("href") if canonical else None,
        "canonical_matches_url": (canonical.get("href", "").rstrip("/") == r.url.rstrip("/")) if canonical else None,
        "h1": h1s,
        "h1_count": len(h1s),
        "h2": h2s,
        "h2_count": len(h2s),
        "word_count": len(body_text.split()),
        "images_total": len(images),
        "images_without_alt": len(no_alt),
        "images_without_alt_samples": no_alt[:10],
        "has_viewport": bool(soup.find("meta", attrs={"name": "viewport"})),
        "lang": (soup.html.get("lang") if soup.html else None),
        "og_title": (soup.find("meta", property="og:title") or {}).get("content") if soup.find("meta", property="og:title") else None,
        "jsonld": extract_jsonld(soup),
        "answer_structure": extract_answer_structure(soup),
    })
    return page


def pick_pages(base, sitemap, max_pages):
    """
    Выбор страниц для обхода. Цель — покрыть **все шаблоны сайта**, а не топ по алфавиту:
    дефекты живут в шаблонах (лид статьи, карточка каталога, архив рубрики), и по одним
    посадочным их не видно.

    Поэтому берём по кругу из каждой карты сайта (статьи, карточки, рубрики, страницы),
    а не по длине пути. Первый реальный аудит (2026-08-19) с сортировкой по длине пути
    отдал 6 слотов из 30 юридическим документам и ещё 6 — одинаковым битым редиректам,
    а статей и карточек каталога взял по две при полутора сотнях на сайте.
    """
    host = urlparse(base).netloc
    picked, seen = [], set()

    def add(u):
        u = u.split("#")[0].rstrip("/") or u
        if u in seen or urlparse(u).netloc != host:
            return False
        seen.add(u)
        picked.append(u)
        return True

    add(base.rstrip("/"))

    # Юридическое и служебное — не предмет SEO-аудита: берём максимум одну штуку как образец
    LOW_VALUE = re.compile(
        r"(?i)(politik|polzovatel|ofert|soglashenie|pravila|avtorski|cookie|privacy|terms|"
        r"settings|password|login|register|signup|cart|checkout|account|/add-|wp-admin)"
    )

    segments = sitemap.get("by_segment") or {}
    if not segments and sitemap.get("urls"):
        segments = {"all": sitemap["urls"]}

    # Внутри сегмента — сначала верхнеуровневое, служебное в хвост
    def rank(u):
        path = urlparse(u).path.strip("/")
        return (1 if LOW_VALUE.search(u) else 0, path.count("/"), len(path))

    queues = {name: sorted(urls, key=rank) for name, urls in segments.items() if urls}
    low_value_taken = 0

    # Круговой обход сегментов: каждый шаблон получает свою долю лимита
    while queues and len(picked) < max_pages:
        for name in list(queues):
            if len(picked) >= max_pages:
                break
            bucket = queues[name]
            while bucket:
                u = bucket.pop(0)
                if LOW_VALUE.search(u):
                    if low_value_taken >= 1:
                        continue          # образец уже есть, остальное не тратим
                    if add(u):
                        low_value_taken += 1
                    break
                if add(u):
                    break
            if not bucket:
                queues.pop(name, None)

    # Карты нет вообще — добираем ссылками с главной
    if len(picked) < max_pages:
        r, _ = fetch(base)
        if r and r.status_code == 200 and "html" in r.headers.get("Content-Type", ""):
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                if len(picked) >= max_pages:
                    break
                href = urljoin(base, a["href"])
                if href.startswith("http") and not re.search(
                    r"\.(jpg|jpeg|png|webp|svg|pdf|zip|docx?|xlsx?)$", href, re.I
                ):
                    add(href)
    return picked[:max_pages]


def main():
    ap = argparse.ArgumentParser(description="Технический сбор данных с сайта для аудита FastUp")
    ap.add_argument("url", help="Базовый URL сайта, например https://example.by")
    ap.add_argument("--max-pages", type=int, default=25, help="Сколько страниц обойти (по умолчанию 25)")
    ap.add_argument("--out", help="Куда положить JSON (по умолчанию — печать в stdout)")
    ap.add_argument("--delay", type=float, default=0.4, help="Пауза между запросами, сек")
    args = ap.parse_args()

    base = args.url if args.url.startswith("http") else "https://" + args.url
    base = base.rstrip("/")

    print(f"[1/4] robots.txt и llms.txt: {base}", file=sys.stderr)
    robots = check_robots(base)
    llms = check_llms_txt(base)

    print("[2/4] карта сайта", file=sys.stderr)
    sitemap = collect_sitemap_urls(base, robots)

    print(f"[3/4] выбор страниц (лимит {args.max_pages})", file=sys.stderr)
    # Маленький сайт сэмплировать незачем — полный обход дешевле и точнее выборки.
    # Без этой подсказки легко потерять целый тип страниц: у сайта с одной плоской
    # картой балансировать по сегментам не по чему, и решает сортировка по глубине —
    # так при обходе fastup.by (52 URL, лимит 30) выпали все подстраницы второго уровня.
    total = sitemap.get("url_count") or 0
    if 0 < args.max_pages < total <= 120:
        print(f"    ! в карте сайта {total} URL, обходим {args.max_pages}. "
              f"Для полного покрытия: --max-pages {total + 5}", file=sys.stderr)
    # Берём запас: часть кандидатов окажется редиректами на уже обойдённый адрес
    targets = pick_pages(base, sitemap, args.max_pages * 3)

    print(f"[4/4] обход, цель {args.max_pages} уникальных страниц", file=sys.stderr)
    pages, finals, collapsed = [], set(), []
    for u in targets:
        if len(pages) >= args.max_pages:
            break
        print(f"    {len(pages)+1}/{args.max_pages} {u}", file=sys.stderr)
        page = parse_page(u)
        time.sleep(args.delay)

        # Несколько URL, ведущих на одну и ту же страницу, не должны съедать лимит: это
        # типовой дефект (рубрики без шаблона архива редиректят на главную), и он важен
        # сам по себе — но одной записи о нём достаточно, дальше нужен реальный контент.
        final = (page.get("final_url") or u).rstrip("/")
        if final in finals:
            collapsed.append({"url": u, "final_url": page.get("final_url"),
                              "status": page.get("status"),
                              "redirect_chain": page.get("redirect_chain")})
            continue
        finals.add(final)
        pages.append(page)

    # Дубли title/description считаем здесь — это факт, а не оценка
    def dupes(field):
        seen = {}
        for p in pages:
            v = (p.get(field) or "").strip()
            if v:
                seen.setdefault(v, []).append(p["url"])
        return {v: urls for v, urls in seen.items() if len(urls) > 1}

    result = {
        "meta": {
            "site": base,
            "crawled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pages_crawled": len(pages),
            "tool": "scripts/site_crawl.py",
        },
        "robots": robots,
        "llms_txt": llms,
        "sitemap": {
            "found": sitemap["found"],
            "url_count": sitemap["url_count"],
            # by_segment целиком раздувает отчёт — агенту нужен состав, а не все URL
            "segments": {k: len(v) for k, v in (sitemap.get("by_segment") or {}).items()},
            "sample_urls": sitemap["urls"][:50],
        },
        "duplicates": {"title": dupes("title"), "description": dupes("description")},
        # URL из карты сайта, ведущие на уже обойдённую страницу (обычно — редирект
        # рубрики на главную). Полный разбор — по одному представителю в `pages`.
        "collapsed_duplicate_urls": collapsed,
        "pages": pages,
    }

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        from pathlib import Path
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(f"OK: {out} ({len(payload)//1024} KB, {len(pages)} страниц)", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
