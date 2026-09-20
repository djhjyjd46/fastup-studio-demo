#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/build_grand_intent_matrix_fast.py

Быстрый и точный векторный Gap-аудит (29 ключевых страниц FastUp: 6 услуг, 8 кейсов, 15 статей)
против Громадного Ядра Интентов (РБ + РФ спрос).
"""

import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[1]
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/embeddings"
MODEL_NAME = "text-embedding-qwen3-embedding-8b"

INTENT_UNIVERSE = {
    "GEO_AI_SEARCH": [
        "что такое geo продвижение сайтов в нейросетях простыми словами",
        "как вывести компанию в рекомендации chatgpt search и яндекс нейро",
        "почему нейросети путают бренд с конкурентами и выдают галлюцинации",
        "как настроить цифровой паспорт компании и schema org json ld для ии",
        "как измерить видимость сайта в генеративном поиске метрики nvi cbk pks",
        "в чем разница между seo aeo и geo оптимизацией",
        "почему сайт на первом месте в поиске не попадает в ответы нейросетей",
        "нужно ли блокировать краулеры нейросетей gptbot claudebot в robots txt",
        "как самостоятельно бесплатно проверить видит ли нейросеть сайт",
        "стоимость geo аудита и ежемесячного ведения в нейросетях",
        "открытый стандарт аудита видимости бизнеса fastup gas на pypi github",
        "как связать компанию с объектом wikidata и профилями sameas для llm",
        "почему цитирование статей блога не дает заявок на коммерческие услуги в ии",
        "как подготовить сайт к поиску будущего generative engine optimization",
        "чек лист подготовки сайта к цитированию в поиске с искусственным интеллектом"
    ],
    "WEB_DEV_SPEED": [
        "разработка сайта на чистом wordpress без elementor и конструкторов",
        "сколько стоит создание сайта в беларуси в 2026 году цены под ключ",
        "как разогнать wordpress до 100 баллов в google pagespeed без плагинов",
        "сравнение wordpress или tilda что лучше выбрать для бизнеса",
        "как перенести сайт с конструктора тильда на wordpress без потери позиций",
        "разработка мультилендинга на одной теме wordpress под несколько услуг",
        "экспресс разработка сайта за 2 3 дня под ключ для малого бизнеса",
        "создание сайта для автосервиса сто с онлайн прайсом и записью",
        "разработка интерактивного квиз калькулятора стоимости на чистом js",
        "создание вариативного каталога товаров на wordpress без woocommerce",
        "почему сайты на elementor тормозят на мобильных устройствах",
        "время отклика сервера ttfb меньше 150 мс на wordpress хостинге",
        "разработка легковесных микросервисов microapps на чистом php без бд",
        "какой сайт выбрать для бизнеса лендинг каталог или интернет магазин",
        "юридический договор на разработку сайта защита прав на код и гарантии"
    ],
    "SEO_SEMANTICS": [
        "сколько стоит seo продвижение сайта в месяц в беларуси минске",
        "как вывести сайт в топ 1 яндекса и google в беларуси",
        "встроенное seo на этапе верстки сайта из коробки без переплат",
        "микроразметка schema org organization service breadcrumblist faqpage",
        "правильная структура каталога товаров и услуг для поисковых систем",
        "региональное seo продвижение в беларуси поддомены или папки городов",
        "почему сайт не индексируется в яндексе и google аудит технических ошибок",
        "как провести seo аудит сайта самостоятельно по чек листу",
        "коммерческие факторы ранжирования сайтов услуг в яндексе",
        "entity first seo связывание сущностей и семантическое ядро нового поколения",
        "как не потерять позиции и трафик при редизайне и смене cms сайта",
        "оптимизация изображений для сайта webp без потери качества и плагинов",
        "как составить карту интентов пользователей и семантический кластер",
        "отличие разового seo аудита от ежемесячного поискового продвижения",
        "гарантии в seo почему никто не может гарантировать 1 место в поиске"
    ],
    "CRO_ANALYTICS": [
        "как настроить яндекс метрику и цели на кнопки и формы сайта",
        "сквозная аналитика и отслеживание источников заявок по utm меткам",
        "как увеличить конверсию сайта из контекстной рекламы яндекс директ",
        "анализ поведения пользователей по вебвизору яндекс метрики точки слива",
        "почему сайт получает переходы но нет звонков и заявок аудит конверсии",
        "настройка контекстной рекламы яндекс директ и google ads в минске цены",
        "интеграция кнопок прямой связи whatsapp telegram viber на сайт",
        "как сделать удобный мобильный слайдер фото и видео на swiper js",
        "сравнение tco совокупной стоимости владения сайтом за 3 года",
        "как проверить подрядчика по веб разработке 7 критериев и red flags",
        "как сделать прайс лист на сайте понятным для клиента и поисковика",
        "почему нельзя латать старый legacy код когда проще собрать с нуля",
        "как получить реальные отзывы клиентов на яндекс картах для бизнеса",
        "настройка отслеживания кликов по номеру телефона и кнопкам мессенджеров",
        "как снизить стоимость заявки cpl в контекстной рекламе для b2b"
    ]
}


def get_embeddings_batch(texts: list) -> list:
    """Пакетное получение эмбеддингов."""
    if not texts:
        return []
    data = json.dumps({"input": texts, "model": MODEL_NAME}).encode("utf-8")
    req = urllib.request.Request(LM_STUDIO_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        items = sorted(res["data"], key=lambda x: x.get("index", 0))
        return [x["embedding"] for x in items]


def cosine_similarity(v1, v2) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def chunk_text(text: str, chunk_size: int = 70, overlap: int = 15, min_words: int = 15) -> list:
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    words = clean.split()
    chunks = []
    
    if len(words) < min_words:
        return []
    if len(words) <= chunk_size:
        return [" ".join(words)]
        
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        chunk = words[i:i + chunk_size]
        if len(chunk) >= min_words:
            chunks.append(" ".join(chunk))
        if i + chunk_size >= len(words):
            break
    return chunks


def load_targeted_site_content():
    """Сбор только ключевых 29 опубликованных страниц/черновиков FastUp."""
    docs = []
    
    # 6 коммерческих страниц
    commercial_files = [
        "content/drafts/main-page-modernized.html",
        "content/drafts/razrabotka-saitov-modernized.html",
        "content/drafts/seo-prodvizhenie-modernized.html",
        "content/drafts/kontekstnaya-reklama-modernized.html",
        "content/drafts/geo-prodvizhenie-modernized.html",
        "content/drafts/geo-audit-system-modernized.html"
    ]
    for rel in commercial_files:
        p = REPO_ROOT / rel
        if p.exists():
            docs.append({"source": p.name, "text": p.read_text(encoding="utf-8")})
            
    # 8 кейсов
    cases_dir = REPO_ROOT / "cases"
    if cases_dir.exists():
        for p in cases_dir.glob("*.md"):
            docs.append({"source": f"cases/{p.name}", "text": p.read_text(encoding="utf-8")})

    # Статьи блога из live-pages
    live_dir = REPO_ROOT / "content" / "live-pages"
    if live_dir.exists():
        for p in live_dir.glob("*.md"):
            if not p.name.startswith("cases_"):
                docs.append({"source": f"blog/{p.name}", "text": p.read_text(encoding="utf-8")})
                
    return docs


def main():
    print(f"=== Быстрый Gap-Аудит Ядра Интентов FastUp (РБ + РФ) ===", flush=True)
    docs = load_targeted_site_content()
    print(f"Загружено целевых страниц/кейсов: {len(docs)}", flush=True)
    
    all_chunks = []
    for doc in docs:
        chunks = chunk_text(doc["text"], chunk_size=70, overlap=15, min_words=15)
        for c in chunks:
            all_chunks.append({"source": doc["source"], "text": c})
            
    print(f"Всего RAG-чанков базы: {len(all_chunks)}", flush=True)
    print("Батч-векторизация чанков...", flush=True)
    
    chunk_embeddings = []
    BATCH_SIZE = 64
    for i in range(0, len(all_chunks), BATCH_SIZE):
        batch = [x["text"] for x in all_chunks[i:i + BATCH_SIZE]]
        batch_embs = get_embeddings_batch(batch)
        chunk_embeddings.extend(batch_embs)
        print(f"  Векторизовано {min(i + BATCH_SIZE, len(all_chunks))}/{len(all_chunks)} чанков...", flush=True)
        
    print("\nВекторизация 60 целевых интентов...", flush=True)
    all_intent_keys = []
    all_intent_texts = []
    for cluster_name, intents in INTENT_UNIVERSE.items():
        for q in intents:
            all_intent_keys.append((cluster_name, q))
            all_intent_texts.append(q)
            
    intent_embeddings = get_embeddings_batch(all_intent_texts)
    
    audit_results = {k: [] for k in INTENT_UNIVERSE.keys()}
    
    for idx, (cluster_name, q) in enumerate(all_intent_keys):
        q_emb = intent_embeddings[idx]
        sims = []
        for c_idx, c_emb in enumerate(chunk_embeddings):
            sim = cosine_similarity(q_emb, c_emb)
            sims.append((sim, all_chunks[c_idx]))
            
        sims.sort(key=lambda x: x[0], reverse=True)
        top3 = sims[:3]
        max_sim = top3[0][0] if top3 else 0.0
        avg_top3 = sum(x[0] for x in top3) / len(top3) if top3 else 0.0
        best_chunk = top3[0][1] if top3 else None
        
        if avg_top3 >= 0.67 or max_sim >= 0.72:
            status = "STRONG"
        elif avg_top3 >= 0.60 or max_sim >= 0.65:
            status = "MODERATE"
        else:
            status = "GAP"
            
        audit_results[cluster_name].append({
            "intent": q,
            "max_sim": round(max_sim, 4),
            "avg_top3": round(avg_top3, 4),
            "status": status,
            "best_source": best_chunk["source"] if best_chunk else "none",
            "best_text": best_chunk["text"][:120] if best_chunk else ""
        })

    # Сохраняем итоговые файлы
    output_json = REPO_ROOT / "geo" / "2026-08-16-grand-intent-matrix-audit.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, ensure_ascii=False, indent=2)
        
    report_md = REPO_ROOT / "geo" / "2026-08-16-grand-intent-matrix-gap-analysis.md"
    with open(report_md, "w", encoding="utf-8") as f:
        f.write("# Громадное ядро интентов FastUp (РБ + РФ): Gap-анализ и контент-план\n\n")
        f.write(f"**Дата аудита:** 16 августа 2026  \n")
        f.write(f"**Модель эмбеддингов:** `{MODEL_NAME}` (LM Studio)  \n")
        f.write(f"**Объем базы:** {len(docs)} страниц/кейсов/статей, {len(all_chunks)} RAG-чанков  \n")
        f.write(f"**Всего исследовано интентов:** {len(all_intent_keys)}  \n\n")
        f.write("---\n\n")
        f.write("## 1. Сводка покрытия по кластерам\n\n")
        f.write("| Кластер спроса | Всего | 🟢 STRONG (>=0.67) | 🟡 MODERATE (0.60–0.66) | 🔴 GAP (<0.60) | Средний Max | Средний Avg3 |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        
        for c_name, items in audit_results.items():
            cnt = len(items)
            strong_cnt = sum(1 for x in items if x["status"] == "STRONG")
            mod_cnt = sum(1 for x in items if x["status"] == "MODERATE")
            gap_cnt = sum(1 for x in items if x["status"] == "GAP")
            mean_max = sum(x["max_sim"] for x in items) / cnt
            mean_avg3 = sum(x["avg_top3"] for x in items) / cnt
            f.write(f"| **{c_name}** | {cnt} | {strong_cnt} | {mod_cnt} | **{gap_cnt}** | {mean_max:.4f} | {mean_avg3:.4f} |\n")
            
        f.write("\n---\n\n")
        for c_name, items in audit_results.items():
            f.write(f"## 2. Кластер: {c_name}\n\n")
            f.write("| Интент клиента (РБ + РФ) | Max | Avg3 | Статус | Лучший источник | Фрагмент покрытия |\n")
            f.write("| :--- | :---: | :---: | :---: | :--- | :--- |\n")
            for x in items:
                status_icon = "🟢" if x["status"] == "STRONG" else ("🟡" if x["status"] == "MODERATE" else "🔴")
                f.write(f"| {x['intent']} | {x['max_sim']} | {x['avg_top3']} | {status_icon} **{x['status']}** | `{x['best_source']}` | {x['best_text']}... |\n")
            f.write("\n")
            
    print(f"Готово! Отчет сохранен в: {report_md}", flush=True)


if __name__ == "__main__":
    main()
