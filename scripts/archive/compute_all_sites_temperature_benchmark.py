#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/compute_all_sites_temperature_benchmark.py

Замер ПОКРЫТИЯ КОММЕРЧЕСКИХ ИНТЕНТОВ по 5 разделам сайта: FastUp (живой и черновики)
против веб-студий Беларуси, чьи страницы лежат в content/research/competitors/multi_service/.

ЧТО ЭТОТ ЗАМЕР МЕРИТ:
    Насколько текст страницы семантически покрывает вопрос, который задаёт клиент.
    Это РЕДАКТОРСКИЙ инструмент: он показывает, ответили ли мы на странице на конкретный
    коммерческий вопрос, или тема осталась незакрытой.

ЧТО ОН НЕ МЕРИТ (и заявлять этого нельзя):
    Видимость в ChatGPT, Яндекс.Нейро и Google AI. Эти системы используют свои эмбеддинги,
    свой индекс, реранкер, авторитет домена и сторонние упоминания. Локальный косинус
    их выбор не предсказывает. Для видимости в ИИ есть NVI/CBK/PKS через реальные
    прогоны запросов — см. geo/metric-spec-v1.md.

ИЗМЕНЕНИЯ ОТ 2026-08-15 (после аудита первой версии):
    1. Интент-запросы переписаны на язык клиента: убраны собственные цены, бренд FastUp,
       имя ИП, GitHub и Wikidata ID. В прежней версии запрос содержал наши же данные,
       поэтому конкурент не мог показать высокий балл в принципе — замер был предвзят
       по построению.
    2. Оценка страницы — среднее топ-3 чанков вместо максимума одного абзаца.
    3. Снята обрезка на 12 чанков: раньше читались только первые ~700 слов, что резало
       длинные страницы конкурентов и льстило нашим компактным черновикам.
    4. Отсутствующая страница показывается прочерком и исключается из среднего,
       а не приравнивается к 0.000. Отдельно выводится колонка покрытия N/5.
    5. Все выводы под таблицей считаются из данных. В прежней версии текст выводов был
       захардкожен и уже разошёлся с таблицей.
    6. Имя конкурента берётся из фронтматтера файла, а не из имени папки: часть папок
       создалась с потерянной кириллицей.

Запуск:
    python scripts/compute_all_sites_temperature_benchmark.py
Требует запущенной LM Studio с моделью text-embedding-qwen3-embedding-8b.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geo_embed import (  # noqa: E402
    MODEL_NAME,
    REPO_ROOT,
    LMStudioUnavailable,
    get_embedding,
    page_frontmatter,
    require_lm_studio,
    score_page,
    setup_console,
)

MULTI_DIR = REPO_ROOT / "content" / "research" / "competitors" / "multi_service"
LIVE_DIR = REPO_ROOT / "content" / "live-pages"
DRAFTS_DIR = REPO_ROOT / "content" / "drafts"
OUT_MD = REPO_ROOT / "geo" / "2026-08-15-INTENT-COVERAGE-BENCHMARK.md"

# Запросы сформулированы так, как их печатает клиент: без названия FastUp,
# без наших цен, без реквизитов и без наших внутренних терминов.
# Правило: если из запроса понятно, чья это страница, — запрос негоден.
PAGE_INTENTS: dict[str, dict[str, str]] = {
    "web_dev": {
        "title": "Разработка сайтов",
        "file": "web_dev.md",
        "query": (
            "сколько стоит разработка сайта в минске цена лендинга корпоративного сайта "
            "интернет магазина сроки изготовления на какой платформе делать что входит "
            "в работу договор и гарантия после сдачи"
        ),
    },
    "seo": {
        "title": "SEO-продвижение",
        "file": "seo.md",
        "query": (
            "seo продвижение сайта в минске сколько стоит в месяц через какое время будут "
            "результаты что входит в работы какая отчётность даёте ли гарантии позиций "
            "как проверить что работа идёт"
        ),
    },
    "ads": {
        "title": "Контекстная реклама",
        "file": "ads.md",
        "query": (
            "настройка и ведение контекстной рекламы яндекс директ google ads стоимость "
            "услуг агентства на кого оформляется рекламный кабинет берут ли процент от "
            "бюджета как считается стоимость заявки"
        ),
    },
    "geo_ai": {
        "title": "GEO и продвижение в ИИ",
        "file": "geo_ai.md",
        "query": (
            "как попасть в ответы нейросетей chatgpt яндекс нейро google ai оптимизация "
            "сайта под генеративный поиск как проверить упоминает ли искусственный "
            "интеллект мою компанию можно ли на это влиять"
        ),
    },
    "home": {
        "title": "Главная страница",
        "file": "home.md",
        "query": (
            "агентство интернет маркетинга полного цикла в минске какие услуги оказывает "
            "разработка сайтов продвижение и реклама цены на услуги кто в команде "
            "работа по договору с юридическим лицом"
        ),
    },
}

FASTUP_LIVE_FILES = {
    "web_dev": "razrabotka-saitov.md",
    "seo": "seo-prodvizhenie.md",
    "ads": "kontekstnaya-reklama.md",
    "geo_ai": "geo-ne-pro-blokirovki-botov-chto-realno-reshaet-uvidit-li-neyroset-vash-biznes.md",
    "home": "front-page.md",
}

FASTUP_DRAFT_FILES = {
    "web_dev": "razrabotka-saitov-modernized-content.md",
    "seo": "seo-prodvizhenie-modernized-content.md",
    "ads": "kontekstnaya-reklama-modernized-content.md",
    "geo_ai": "geo-audit-system-modernized-content.md",
    "home": "front-page-modernized-content.md",
}

STATUS_MARK = {"missing": "—", "thin": "н/д"}


def competitor_name(agency_dir: Path) -> str:
    """Человеческое имя студии из фронтматтера любой её страницы."""
    for candidate in ("home.md", "web_dev.md", "seo.md", "ads.md", "geo_ai.md"):
        page = agency_dir / candidate
        if page.exists():
            meta = page_frontmatter(page)
            name = meta.get("competitor", "").strip()
            url = meta.get("url", "").strip()
            if name:
                domain = url.replace("https://", "").replace("http://", "").strip("/")
                return f"{name} (`{domain}`)" if domain else name
    return agency_dir.name


def measure(page_paths: dict[str, Path], intent_embs: dict[str, list[float]]) -> dict:
    """Прогнать один сайт по всем пяти разделам."""
    scores: dict[str, float | None] = {}
    statuses: dict[str, str] = {}
    for key, path in page_paths.items():
        score, status = score_page(path, intent_embs[key])
        scores[key] = score
        statuses[key] = status
    present = [s for s in scores.values() if s is not None]
    return {
        "scores": scores,
        "statuses": statuses,
        "coverage": len(present),
        # Среднее считается ТОЛЬКО по имеющимся страницам. Отсутствующая страница —
        # это пробел покрытия (колонка «Покрытие»), а не нулевая релевантность.
        "avg": sum(present) / len(present) if present else None,
    }


def fmt(value: float | None, status: str) -> str:
    if value is None:
        return STATUS_MARK.get(status, "—")
    return f"`{value:.3f}`"


def main() -> int:
    setup_console()
    try:
        require_lm_studio()
    except LMStudioUnavailable as exc:
        print(f"[STOP] {exc}")
        return 1

    print("=== [1/3] Векторизация 5 клиентских интентов ===")
    intent_embs = {k: get_embedding(v["query"]) for k, v in PAGE_INTENTS.items()}

    print("=== [2/3] Замер сайтов ===")
    rows: list[dict] = []

    for agency_dir in sorted(p for p in MULTI_DIR.iterdir() if p.is_dir()):
        name = competitor_name(agency_dir)
        print(f"  -> {name}")
        result = measure(
            {k: agency_dir / v["file"] for k, v in PAGE_INTENTS.items()}, intent_embs
        )
        rows.append({"name": name, "kind": "competitor", **result})

    print("  -> FastUp.by (живой сайт)")
    rows.append(
        {
            "name": "FastUp.by (живой сайт сейчас)",
            "kind": "fastup_live",
            **measure({k: LIVE_DIR / v for k, v in FASTUP_LIVE_FILES.items()}, intent_embs),
        }
    )

    print("  -> FastUp.by (черновики модернизации)")
    rows.append(
        {
            "name": "FastUp.by (черновики модернизации, ещё не на сайте)",
            "kind": "fastup_draft",
            **measure({k: DRAFTS_DIR / v for k, v in FASTUP_DRAFT_FILES.items()}, intent_embs),
        }
    )

    ranked = sorted(rows, key=lambda r: (r["avg"] is not None, r["avg"] or 0), reverse=True)

    print("=== [3/3] Отчёт ===")
    keys = list(PAGE_INTENTS)
    head = " | ".join(PAGE_INTENTS[k]["title"] for k in keys)

    md = [
        "# Покрытие коммерческих интентов: 5 разделов, FastUp против студий Беларуси",
        "",
        f"> **Дата замера:** 2026-08-15. Модель: `{MODEL_NAME}` (локально, LM Studio).",
        "> Отчёт сгенерирован скриптом `scripts/compute_all_sites_temperature_benchmark.py`.",
        "> Все числа получены прогоном; вручную в этот файл ничего не вписывается.",
        "",
        "## Что этот замер показывает и чего не показывает",
        "",
        "**Показывает:** насколько текст страницы семантически покрывает вопрос, который",
        "задаёт клиент. Это редакторский инструмент — видно, ответили ли мы на странице на",
        "конкретный коммерческий вопрос или тема осталась незакрытой.",
        "",
        "**Не показывает:** видимость в ChatGPT, Яндекс.Нейро и Google AI. Эти системы",
        "используют собственные эмбеддинги, индекс, реранкер, авторитет домена и сторонние",
        "упоминания — локальный косинус их выбор не предсказывает. Для видимости в ИИ",
        "применяются метрики NVI/CBK/PKS через реальные прогоны запросов",
        "(`geo/metric-spec-v1.md`). **Это не рейтинг качества студий и не прогноз позиций.**",
        "",
        "Шкала косинуса ни к чему не калибрована: сравнивать значения между строками",
        "таблицы можно, объявлять пороги («0.85 = лидер рынка») — нельзя.",
        "",
        "## Как считалось",
        "",
        "- Оценка страницы — среднее трёх наиболее релевантных фрагментов (чанк 70 слов,",
        "  перекрытие 15). Не максимум одного абзаца: максимум награждает keyword-stuffing.",
        "- Страница читается целиком, без обрезки по числу фрагментов.",
        "- Запросы сформулированы на языке клиента: без брендов, наших цен и реквизитов.",
        "  Запрос, по которому понятно, чья это страница, к замеру не допускается.",
        "- Отсутствующая страница — прочерк (`—`) и минус к покрытию, а не 0.000.",
        "  `н/д` — файл есть, но текста меньше 100 слов (неудавшийся краулинг).",
        "- Средняя считается только по имеющимся страницам, поэтому сайт с покрытием 2/5",
        "  сравнивать со сайтом 5/5 по одной средней некорректно — смотри обе колонки.",
        "",
        f"| # | Сайт | {head} | Средняя | Покрытие |",
        "|:---:|---|" + ":---:|" * (len(keys) + 2),
    ]

    for rank, row in enumerate(ranked, 1):
        cells = " | ".join(fmt(row["scores"][k], row["statuses"][k]) for k in keys)
        avg = f"**`{row['avg']:.3f}`**" if row["avg"] is not None else "—"
        name = f"**{row['name']}**" if row["kind"].startswith("fastup") else row["name"]
        md.append(f"| {rank} | {name} | {cells} | {avg} | {row['coverage']}/5 |")

    live = next(r for r in ranked if r["kind"] == "fastup_live")
    draft = next(r for r in ranked if r["kind"] == "fastup_draft")
    competitors = [r for r in ranked if r["kind"] == "competitor" and r["avg"] is not None]
    full_cov = [r for r in competitors if r["coverage"] == len(keys)]

    md += ["", "## Выводы (посчитаны из таблицы выше)", ""]

    if competitors:
        best = competitors[0]
        comp_avg = sum(r["avg"] for r in competitors) / len(competitors)
        md += [
            f"- Замерено конкурентов: **{len(competitors)}**, из них с полным покрытием "
            f"5/5 разделов — **{len(full_cov)}**.",
            f"- Средняя по конкурентам: **`{comp_avg:.3f}`**. "
            f"Лучший результат — {best['name']}: **`{best['avg']:.3f}`** "
            f"(покрытие {best['coverage']}/5).",
        ]
        for label, row in (("живой сайт", live), ("черновики", draft)):
            if row["avg"] is None:
                continue
            place = sorted(
                [r for r in ranked if r["avg"] is not None],
                key=lambda r: r["avg"],
                reverse=True,
            ).index(row) + 1
            delta = row["avg"] - comp_avg
            md.append(
                f"- FastUp ({label}): **`{row['avg']:.3f}`**, место {place} из "
                f"{len([r for r in ranked if r['avg'] is not None])}, "
                f"отклонение от средней по конкурентам {delta:+.3f}."
            )

    if live["avg"] is not None and draft["avg"] is not None:
        gain = draft["avg"] - live["avg"]
        pct = gain / live["avg"] * 100
        md += [
            "",
            f"- **Эффект модернизации (черновики против живого сайта): "
            f"{gain:+.3f} ({pct:+.1f}%).**",
            "",
            "Постранично:",
            "",
            "| Раздел | Живой сайт | Черновик | Изменение |",
            "|---|:---:|:---:|:---:|",
        ]
        for k in keys:
            before, after = live["scores"][k], draft["scores"][k]
            change = (
                f"**{after - before:+.3f}**" if before is not None and after is not None else "—"
            )
            md.append(
                f"| {PAGE_INTENTS[k]['title']} | {fmt(before, live['statuses'][k])} "
                f"| {fmt(after, draft['statuses'][k])} | {change} |"
            )
        md += [
            "",
            "Изменение считается между нашим живым текстом и нашим черновиком — это",
            "единственное честное сравнение «до/после» в таблице. Черновики короче и плотнее",
            "живых страниц, а страницы конкурентов спарсены целиком, с меню и футером, поэтому",
            "прямое сравнение черновика с конкурентом завышает нас — учитывай это при чтении.",
        ]

    md += [
        "",
        "---",
        "",
        "Заменяет `2026-08-15-ALL-SITES-TEMPERATURE-LEADERBOARD.md`: тот файл содержал",
        "оценки, которых прогон выдать не мог (студии без нужных страниц получали баллы),",
        "и выводы, захардкоженные в скрипте. Прежний файл удалён, история — в git.",
    ]

    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"[OK] Отчёт сохранён: {OUT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
