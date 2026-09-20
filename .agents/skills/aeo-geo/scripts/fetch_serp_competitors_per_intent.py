#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""
scripts/fetch_serp_competitors_per_intent.py

Competitive intelligence pipeline against live search engine results (Yandex Cloud Search API v2 + Google XMLRiver BY).
Gathers TOP SERP results for a target intent, parses competitor page structures (title, H2/H3, words, tables, FAQs, pricing, metrics),
classifies source types (studio, media, reference, aggregator), vectorizes H2 headings in LM Studio (text-embedding-qwen3-embedding-8b),
and generates factual analytical reports in geo/<date>-serp-competitors-<slug>.md.

Strictly adheres to content/TZ-CONTENT-CAMPAIGN-2026.md (§3 and §4):
- 4 URLs from Yandex (Yandex Cloud Search API v2, region=149 Belarus) + 4 URLs from Google (XMLRiver BY, country=by)
- At most 2 URLs per domain
- Excludes search engine SERP pages and internal fastup.by domain, preserving reference subdomains (support.google.com, etc.)
- Downloads complete pages without truncation; retries with backoff on 502/503/504
- Unreachable pages marked as 'failed' and excluded from zero calculations
- LM Studio vectorization calculating semantic coverage across top-3 average cosine similarity (when our_url is provided)
- Zero hallucinated or hardcoded conclusions; reports contain computed factual metrics only
- Concurrency ceiling of 10 worker threads
"""

import argparse
import base64
import hashlib
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

# Configure UTF-8 for Windows console
if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent

# LM Studio configuration
LM_STUDIO_BASE = os.environ.get("LM_STUDIO_BASE", "http://127.0.0.1:1234/v1")
EMBED_URL = f"{LM_STUDIO_BASE}/embeddings"
MODELS_URL = f"{LM_STUDIO_BASE}/models"
MODEL_NAME = os.environ.get("GEO_EMBED_MODEL", "text-embedding-qwen3-embedding-8b")
CACHE_DIR = REPO_ROOT / "scripts" / ".embed_cache"


def load_env(repo_root: Path) -> dict[str, str]:
    """Load environment variables from .env and os.environ."""
    env = {}
    from env_load import env_file_path  # From worktree — .env of main workspace
    env_file = env_file_path()
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    for k in [
        "YANDEX_CLOUD_API_KEY", "YANDEX_CLOUD_FOLDER_ID",
        "XMLRIVER_USER", "XMLRIVER_KEY",
        "ROUTERAI_API_KEY", "OPENROUTER_API_KEY", "LM_STUDIO_BASE"
    ]:
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


# ---------------------------------------------------------------------------
# LM Studio Embeddings & Cosine Similarity
# ---------------------------------------------------------------------------

_MEM_CACHE: dict[str, list[float]] = {}


def check_lm_studio() -> bool:
    """Verify availability of LM Studio local endpoint."""
    try:
        req = urllib.request.Request(MODELS_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            available = [m.get("id") for m in data.get("data", [])]
            return MODEL_NAME in available
    except Exception:
        return False


def _get_cache_path(text: str) -> Path:
    key = hashlib.sha256(f"{MODEL_NAME}\x00{text}".encode("utf-8")).hexdigest()
    return CACHE_DIR / key[:2] / f"{key}.json"


def get_embedding(text: str) -> list[float]:
    """Retrieve string embedding from LM Studio with disk-based caching."""
    payload_text = text.strip()
    if not payload_text:
        return [0.0] * 4096

    if payload_text in _MEM_CACHE:
        return _MEM_CACHE[payload_text]

    cache_file = _get_cache_path(payload_text)
    if cache_file.exists():
        try:
            emb = json.loads(cache_file.read_text(encoding="utf-8"))
            _MEM_CACHE[payload_text] = emb
            return emb
        except Exception:
            cache_file.unlink(missing_ok=True)

    body = json.dumps({"model": MODEL_NAME, "input": payload_text}).encode("utf-8")
    req = urllib.request.Request(
        EMBED_URL, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            emb = json.loads(resp.read().decode("utf-8"))["data"][0]["embedding"]
    except Exception as exc:
        raise RuntimeError(f"LM Studio embedding error for '{payload_text[:40]}...': {exc}") from exc

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(emb), encoding="utf-8")
    _MEM_CACHE[payload_text] = emb
    return emb


def cosine_sim(v1: list[float], v2: list[float]) -> float:
    """Calculate cosine similarity between two vector embeddings."""
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = sum(a * a for a in v1) ** 0.5
    n2 = sum(b * b for b in v2) ** 0.5
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


# ---------------------------------------------------------------------------
# Search queries against SERP (Yandex Cloud Search API v2 & Google XMLRiver BY)
# ---------------------------------------------------------------------------

def is_domain_excluded(url: str) -> bool:
    """
    Check whether URL should be excluded from analysis.
    Excludes:
    - fastup.by and internal subdomains
    - Search engine SERP pages (search, url, webhp)
    - Non-text documents (.pdf, .doc, .xlsx, etc.)
    Preserves:
    - Reference and documentation subdomains (support.google.com, docs.google.com, etc.)
    """
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
        if not netloc:
            return True

        # Exclude internal studio domain
        if netloc == "fastup.by" or netloc.endswith(".fastup.by"):
            return True

        # Exclude non-text files and document binaries
        if any(path.endswith(ext) for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".ppt", ".pptx"]):
            return True

        # Google validation: strip SERP interfaces, permit reference/documentation subdomains
        if "google." in netloc:
            if any(netloc.startswith(prefix) for prefix in ["support.", "developers.", "cloud.", "docs.", "policies.", "workspace."]):
                return False
            if netloc in ["google.com", "google.by", "google.ru", "google.kz", "www.google.com", "www.google.by", "www.google.ru"] or path.startswith(("/search", "/url", "/webhp", "/preferences")):
                return True

        # Yandex validation: strip SERP interfaces, permit reference/service subdomains
        if netloc in ["ya.ru", "www.ya.ru"] or netloc.startswith("yandex.") or netloc.endswith(".yandex.ru") or netloc.endswith(".yandex.by") or netloc.endswith(".yandex.com") or netloc.endswith(".yandex.kz"):
            if any(netloc.startswith(prefix) for prefix in ["metrika.", "help.", "support.", "docs.", "cloud.", "practicum."]) or path.startswith(("/support", "/dev", "/docs")):
                return False
            if path.startswith(("/search", "/clck", "/images", "/video", "/all")) or netloc in ["ya.ru", "yandex.ru", "yandex.by", "yandex.com", "yandex.kz", "www.yandex.ru", "www.yandex.by"]:
                return True

        return False
    except Exception:
        return True


def query_yandex_cloud(yc_key: str, folder_id: str, query_text: str, region: str = "149", max_results: int = 15) -> list[dict[str, Any]]:
    """Execute query via Yandex Cloud Search API v2 with explicit Belarus region (149)."""
    url = "https://searchapi.api.cloud.yandex.net/v2/web/search"
    headers = {
        "Authorization": f"Api-Key {yc_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "folderId": folder_id,
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText": query_text,
            "region": str(region)
        },
        "responseFormat": "FORMAT_XML"
    }

    results = []
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                res_data = resp.json()
                raw_xml = base64.b64decode(res_data.get("rawData", "")).decode("utf-8", errors="ignore")
                root = ET.fromstring(raw_xml)
                
                for doc in root.findall(".//doc"):
                    u = doc.findtext("url")
                    if not u:
                        continue
                    
                    t_el = doc.find("title")
                    title = "".join(t_el.itertext()).strip() if t_el is not None else ""
                    
                    passages = []
                    for p in doc.findall(".//passage"):
                        p_text = "".join(p.itertext()).strip()
                        if p_text:
                            passages.append(p_text)
                    snippet = " ".join(passages)

                    results.append({
                        "engine": "Yandex",
                        "url": u,
                        "title": title,
                        "snippet": snippet
                    })
                break
            else:
                time.sleep(1.5)
        except Exception as e:
            if attempt == 2:
                print(f"  [!] Yandex Cloud Search error: {e}", flush=True)
            time.sleep(1.5)

    return results


def query_google_xmlriver(xml_user: str, xml_key: str, query_text: str, country: str = "by", max_results: int = 15) -> list[dict[str, Any]]:
    """Execute query via Google XMLRiver API targeted to Belarus (country=by)."""
    url = "https://xmlriver.com/search_google/xml"
    params = {
        "user": xml_user,
        "key": xml_key,
        "query": query_text,
        "country": country,
        "num": str(max_results)
    }

    results = []
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=25)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for doc in root.findall(".//doc"):
                    u = doc.findtext("url")
                    if not u:
                        continue
                    
                    t_el = doc.find("title")
                    title = "".join(t_el.itertext()).strip() if t_el is not None else ""
                    
                    passages = []
                    for p in doc.findall(".//passage"):
                        p_text = "".join(p.itertext()).strip()
                        if p_text:
                            passages.append(p_text)
                    snippet = " ".join(passages) if passages else (doc.findtext("snippet") or "")

                    results.append({
                        "engine": "Google",
                        "url": u,
                        "title": title,
                        "snippet": snippet
                    })
                break
            else:
                time.sleep(1.5)
        except Exception as e:
            if attempt == 2:
                print(f"  [!] Google XMLRiver error: {e}", flush=True)
            time.sleep(1.5)

    return results


def get_top_serp_competitors(
    query_text: str,
    yc_key: str,
    folder_id: str,
    xml_user: str,
    xml_key: str,
    per_engine: int = 4,
    max_per_domain: int = 2
) -> list[dict[str, Any]]:
    """
    Fetch per_engine (4) URLs from Yandex (region=149) and Google (country=by),
    capping at max_per_domain (2) URLs per domain.
    """
    print(f"[*] Gathering SERP results: '{query_text}' (Yandex region=149, Google country=by)...", flush=True)
    
    ya_raw = query_yandex_cloud(yc_key, folder_id, query_text, region="149", max_results=20)
    goog_raw = query_google_xmlriver(xml_user, xml_key, query_text, country="by", max_results=20)

    selected_urls: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    domain_counts: dict[str, int] = {}

    def get_domain(u: str) -> str:
        try:
            return urllib.parse.urlparse(u).netloc.lower()
        except Exception:
            return ""

    # Select from Yandex (4 URLs, <= 2 per domain)
    ya_count = 0
    for item in ya_raw:
        u = item["url"].strip()
        domain = get_domain(u)
        if not is_domain_excluded(u) and u not in seen_urls:
            if domain_counts.get(domain, 0) < max_per_domain:
                seen_urls.add(u)
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                selected_urls.append(item)
                ya_count += 1
                if ya_count >= per_engine:
                    break

    # Select from Google (4 URLs, <= 2 per domain)
    goog_count = 0
    for item in goog_raw:
        u = item["url"].strip()
        domain = get_domain(u)
        if not is_domain_excluded(u) and u not in seen_urls:
            if domain_counts.get(domain, 0) < max_per_domain:
                seen_urls.add(u)
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                selected_urls.append(item)
                goog_count += 1
                if goog_count >= per_engine:
                    break

    by_domains_count = sum(1 for item in selected_urls if get_domain(item["url"]).endswith(".by"))
    print(f"    [+] Selected target competitors: {len(selected_urls)} (Yandex: {ya_count}, Google: {goog_count} | .by domains: {by_domains_count})", flush=True)
    return selected_urls


# ---------------------------------------------------------------------------
# Page parsing, sanitization, and source classification
# ---------------------------------------------------------------------------

KNOWN_MEDIA_DOMAINS = {
    "habr.com", "vc.ru", "dzen.ru", "journal.tinkoff.ru", "klerk.ru", "rb.ru",
    "spark.ru", "cossa.ru", "ppc.world", "searchengines.guru", "marketing.by",
    "dev.by", "probusiness.io", "cyberleninka.ru", "new-retail.ru", "e-pepper.ru",
    "rusability.ru", "texterra.ru", "skillbox.ru", "netology.ru", "blog.calltouch.ru",
    "blog.albato.ru", "blog.unisender.com", "getcompass.ru", "metrium.kz", "sostav.ru",
    "ixbt.com", "forbes.ru", "rbc.ru", "trends.rbc.ru", "lpmotor.ru"
}

KNOWN_REFERENCE_DOMAINS = {
    "support.google.com", "developers.google.com", "docs.google.com", "cloud.google.com",
    "yandex.ru/support", "support.yandex.ru", "help.yandex.ru", "metrika.yandex.ru/docs",
    "helpdesk.bitrix24.ru", "helpdesk.bitrix24.by", "help.bitrix24.ru", "help.bitrix24.by",
    "support.bitrix24.ru", "docs.yandex.ru", "roistat.com/help", "help.roistat.com",
    "wikipedia.org", "github.com", "developer.mozilla.org", "w3schools.com", "schema.org"
}

KNOWN_AGGREGATOR_DOMAINS = {
    "zoon.ru", "deal.by", "otzyvy.by", "allbiz", "avito.ru", "tiu.ru",
    "ratingbynet", "cmsmagazine.ru", "tagline.ru", "workspace.ru",
    "tam.by", "kachestvo.by", "kupala.by", "uslugi.yandex.ru", "uslugi.yandex.by"
}

KNOWN_STUDIO_DOMAINS = {
    "redline.by", "gusarov.by", "gusarov-group.by", "qmedia.by", "seologic.by",
    "makit.by", "zmitroc.by", "imedia.by", "itpanda.by", "vtop3.by", "bk-media.by",
    "artcly.by", "aliva.by", "webhouse.by", "webslon.by", "seolime.by", "avanta.by",
    "media-line.by", "artox.by", "amdg.by", "atevi.by", "webcom-group.by", "redline.by",
    "d-element.ru", "delomatika.ru", "t-f-a.agency", "zenlink.ru", "rookee.ru", "hozyindachi.ru"
}


def classify_source(url: str, text: str = "") -> str:
    """
    Classify source type:
    - studio: digital agency, web studio, commercial contractor
    - media: tech media, editorial portal, industry blog
    - reference: official vendor documentation, knowledge base
    - aggregator: directory, ranking index, marketplace, listings board
    """
    parsed = urllib.parse.urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.lower()
    full_host = netloc

    # 1. Check Reference
    for ref_d in KNOWN_REFERENCE_DOMAINS:
        if ref_d in full_host or ref_d in f"{full_host}{path}":
            return "reference"
    if any(k in full_host for k in ["helpdesk.", "support.", "docs.", "developer.", "help."]):
        return "reference"
    if any(k in path for k in ["/support/", "/help/", "/manual/", "/docs/", "/glossary/", "/spravka/", "/guide/"]):
        if not any(k in path for k in ["/blog/"]):
            return "reference"

    # 2. Check Aggregator
    for agg_d in KNOWN_AGGREGATOR_DOMAINS:
        if agg_d in full_host:
            return "aggregator"
    if any(k in full_host for k in ["catalog", "katalog", "rating", "reiting", "otzyvy"]):
        return "aggregator"

    # 3. Check Studio
    for std_d in KNOWN_STUDIO_DOMAINS:
        if std_d in full_host:
            return "studio"
    if full_host.endswith(".agency") or any(k in full_host for k in ["studio", "agency", "digital", "seo", "dev", "marketing", "webcom", "amdg", "artox"]):
        return "studio"

    # 4. Check Media
    for med_d in KNOWN_MEDIA_DOMAINS:
        if med_d in full_host:
            return "media"
    if any(k in full_host for k in ["media.", "journal.", "mag.", "blog."]) or any(k in path for k in ["/articles/", "/stati/", "/news/"]):
        return "media"

    # Page text analysis
    text_lower = text.lower()
    if any(phrase in text_lower for phrase in ["наши услуги", "заказать", "стоимость услуг", "оставить заявку", "маркетинговое агентство", "веб-студия"]):
        return "studio"

    if "/blog/" in path or "/post/" in path or "/stati/" in path or "/news/" in path:
        return "media"

    return "studio"


def fetch_and_parse_page(url: str, session: requests.Session) -> dict[str, Any]:
    """
    Download full page HTML and extract structural markup elements:
    - title
    - sequential H2 and H3 headings
    - word count volume
    - table elements
    - FAQ sections
    - commercial pricing
    - concrete numbers and metrics
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    raw_html = ""
    status_code = 0
    error_msg = None

    for attempt in range(3):
        try:
            resp = session.get(url, headers=headers, timeout=20)
            status_code = resp.status_code
            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding or "utf-8"
                raw_html = resp.text
                # Handle cp1251 bytes masquerading under utf-8 header to prevent corrupting LM Studio tokenizer
                if raw_html.count("�") > 5 or raw_html.count("Ð") > 20:
                    try:
                        alt = resp.content.decode("cp1251")
                        if alt.count("�") < raw_html.count("�"):
                            raw_html = alt
                    except Exception:
                        pass
                break
            elif resp.status_code in [502, 503, 504]:
                time.sleep(2.0 * (attempt + 1))
            else:
                error_msg = f"HTTP {resp.status_code}"
                break
        except Exception as e:
            if attempt == 2:
                error_msg = str(e)
            time.sleep(1.5 * (attempt + 1))

    if not raw_html or status_code != 200:
        return {
            "url": url,
            "status": "не получена",
            "status_code": status_code,
            "error": error_msg or "Failed to load",
            "source_type": classify_source(url),
            "title": "",
            "word_count": 0,
            "h2_list": [],
            "h3_list": [],
            "all_headings": [],
            "has_table": False,
            "has_faq": False,
            "has_price": False,
            "has_metrics": False,
            "text": ""
        }

    soup = BeautifulSoup(raw_html, "html.parser")

    # Detect FAQPage in JSON-LD
    has_faq_jsonld = False
    for s_tag in soup.find_all("script", type="application/ld+json"):
        try:
            if s_tag.string and ("FAQPage" in s_tag.string or "Question" in s_tag.string):
                has_faq_jsonld = True
                break
        except Exception:
            pass

    # Extract title tag
    title = ""
    t_tag = soup.find("title")
    if t_tag:
        title = re.sub(r"\s+", " ", t_tag.get_text(strip=True))
    if not title:
        og_t = soup.find("meta", property="og:title")
        if og_t and og_t.get("content"):
            title = re.sub(r"\s+", " ", og_t["content"].strip())

    # Detect table elements prior to decomposing structural tags
    tables = soup.find_all("table")
    has_table = any(len(t.find_all(["tr", "td", "th"])) > 2 for t in tables)

    # Detect FAQ markup in HTML body
    has_faq_html = bool(
        soup.find_all(attrs={"class": re.compile(r"faq|accordion|spoiler|questions", re.I)}) or
        soup.find_all(["details"]) or
        has_faq_jsonld
    )

    # Remove non-content tags
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe", "aside"]):
        tag.decompose()

    # Collect sequential H2 and H3 headings
    all_headings: list[dict[str, str]] = []
    h2_list: list[str] = []
    h3_list: list[str] = []

    for h in soup.find_all(["h2", "h3"]):
        clean_text = re.sub(r"\s+", " ", h.get_text(strip=True))
        # Filter empty and boilerplate navigational headings
        if not clean_text or len(clean_text) < 4:
            continue
        if clean_text.lower() in [
            "навигация", "меню", "контакты", "форма заявки", "оставить заявку",
            "поделиться", "похожие статьи", "комментарии", "читайте также"
        ]:
            continue

        tag_name = h.name.lower()
        if tag_name == "h2":
            h2_list.append(clean_text)
            all_headings.append({"tag": "H2", "text": clean_text})
        elif tag_name == "h3":
            h3_list.append(clean_text)
            all_headings.append({"tag": "H3", "text": clean_text})

    # Page text and word count
    body_text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))
    words = [w for w in body_text.split() if len(w) > 0]
    word_count = len(words)

    # Search for commercial pricing
    price_patterns = re.findall(
        r"\b(?:\d{1,3}(?:[\s,.]\d{3})+|\d+)\s*(?:BYN|byn|руб\.?|р\.|USD|\$|EUR|€|тыс\.?\s*руб)\b",
        body_text,
        re.I
    )
    has_price = len(price_patterns) > 0 or any(k in body_text.lower() for k in ["тариф", "прайс", "стоимость услуг", "цена от"])

    # Search for concrete numbers and metrics
    metric_patterns = re.findall(
        r"\b\d+(?:[.,]\d+)?\s*%\b|\b\d+\s*(?:мс|ms|сек|мин|дней|дня|часов|час|x|X)\b|\b(?:CPA|CPO|ROI|ROMI|LTV|CTR|CR|TTFB|LCP|FID|CLS|NVI|CBK|PKS|PCL|SCG)\b",
        body_text,
        re.I
    )
    has_metrics = len(metric_patterns) >= 2

    # Classify source type
    source_type = classify_source(url, body_text)

    return {
        "url": url,
        "status": "ok",
        "status_code": status_code,
        "error": None,
        "source_type": source_type,
        "title": title,
        "word_count": word_count,
        "h2_list": h2_list,
        "h3_list": h3_list,
        "all_headings": all_headings,
        "has_table": has_table,
        "has_faq": has_faq_html,
        "has_price": has_price,
        "has_metrics": has_metrics,
        "text": body_text[:4000]
    }


# ---------------------------------------------------------------------------
# Vectorization & H2 Semantic Coverage (Top-3 Average)
# ---------------------------------------------------------------------------

def analyze_h2_coverage(
    competitor_pages: list[dict[str, Any]],
    query_text: str,
    our_url: str | None = None
) -> dict[str, Any]:
    """
    Vectorize all competitor H2s in LM Studio and calculate semantic coverage.
    If our_url is set, downloads our page and computes coverage across top-3 average cosine similarity.
    If our_url is null, ranks unique competitor sub-queries by semantic proximity to query.
    """
    lm_available = check_lm_studio()
    if not lm_available:
        print("[!] Warning: LM Studio or model unavailable. Vector analysis will be skipped.", flush=True)

    # Collect unique competitor H2 headings
    unique_h2s: list[dict[str, Any]] = []
    seen_texts: set[str] = set()

    for page in competitor_pages:
        if page.get("status") != "ok":
            continue
        for h2_text in page.get("h2_list", []):
            norm_text = h2_text.strip().lower()
            if norm_text not in seen_texts and len(norm_text) > 5:
                seen_texts.add(norm_text)
                unique_h2s.append({
                    "text": h2_text,
                    "url": page["url"],
                    "source_type": page["source_type"]
                })

    if not unique_h2s:
        return {"unique_h2_count": 0, "h2_analysis": [], "our_coverage": None}

    # Vectorize search query and H2 headings
    query_emb = get_embedding(query_text) if lm_available else []

    h2_data = []
    for item in unique_h2s:
        h2_text = item["text"]
        emb = get_embedding(h2_text) if lm_available else []
        sim_to_query = round(cosine_sim(query_emb, emb), 4) if (lm_available and query_emb) else 0.0
        h2_data.append({
            **item,
            "sim_to_query": sim_to_query,
            "emb": emb
        })

    # Sort H2 headings by relevance to search query
    h2_data.sort(key=lambda x: x["sim_to_query"], reverse=True)

    # If our_url is provided, calculate semantic coverage against our page
    our_coverage_results = None
    if our_url and lm_available:
        print(f"[*] Analyzing our page for H2 comparison: {our_url}...", flush=True)
        session = requests.Session()
        our_page = fetch_and_parse_page(our_url, session)
        if our_page.get("status") == "ok":
            our_h2_list = [h for h in our_page.get("h2_list", []) if len(h.strip()) > 3]
            our_h2_embs = [get_embedding(h) for h in our_h2_list]
            
            # For each competitor H2, calculate top-3 average cosine similarity
            coverage_list = []
            for h in h2_data:
                if our_h2_embs:
                    sims = sorted([cosine_sim(h["emb"], our_emb) for our_emb in our_h2_embs], reverse=True)
                    top3 = sims[:min(3, len(sims))]
                    avg_top3 = round(sum(top3) / len(top3), 4) if top3 else 0.0
                else:
                    avg_top3 = 0.0
                
                is_missing = avg_top3 < 0.65
                coverage_list.append({
                    "text": h["text"],
                    "url": h["url"],
                    "sim_to_query": h["sim_to_query"],
                    "avg_top3_score": avg_top3,
                    "is_missing": is_missing
                })
            our_coverage_results = {
                "our_url": our_url,
                "our_h2_count": len(our_h2_list),
                "items": coverage_list,
                "missing_count": sum(1 for c in coverage_list if c["is_missing"]),
                "covered_count": sum(1 for c in coverage_list if not c["is_missing"])
            }

    # Clean vector arrays from dicts before returning
    for h in h2_data:
        h.pop("emb", None)

    return {
        "unique_h2_count": len(h2_data),
        "h2_analysis": h2_data,
        "our_coverage": our_coverage_results
    }


# ---------------------------------------------------------------------------
# Factual Markdown Report Generator
# ---------------------------------------------------------------------------

def generate_markdown_report(
    slug: str,
    query_text: str,
    our_url: str | None,
    competitors: list[dict[str, Any]],
    h2_analysis_res: dict[str, Any],
    output_dir: Path,
    report_date: str
) -> Path:
    """Generate detailed factual Markdown report from SERP intelligence data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_filename = f"{report_date}-serp-competitors-{slug}.md"
    report_path = output_dir / report_filename

    ok_pages = [c for c in competitors if c.get("status") == "ok"]
    failed_pages = [c for c in competitors if c.get("status") != "ok"]

    # 1. Source type distribution
    type_counts: dict[str, int] = {}
    for c in ok_pages:
        st = c.get("source_type", "unknown")
        type_counts[st] = type_counts.get(st, 0) + 1

    # 2. Domain distribution
    domain_counts: dict[str, int] = {}
    for c in ok_pages:
        u = c.get("url", "")
        p = urllib.parse.urlparse(u)
        d = p.netloc.lower()
        if d:
            domain_counts[d] = domain_counts.get(d, 0) + 1

    repeated_domains = {d: count for d, count in domain_counts.items() if count > 1}
    by_domains_count = sum(1 for d in domain_counts if d.endswith(".by"))

    # 3. Word count distribution
    word_counts = [c.get("word_count", 0) for c in ok_pages if c.get("word_count", 0) > 0]
    min_words = min(word_counts) if word_counts else 0
    max_words = max(word_counts) if word_counts else 0
    median_words = int(statistics.median(word_counts)) if word_counts else 0
    avg_words = int(statistics.mean(word_counts)) if word_counts else 0

    # 4. Structural trust elements
    total_ok = len(ok_pages)
    table_count = sum(1 for c in ok_pages if c.get("has_table"))
    faq_count = sum(1 for c in ok_pages if c.get("has_faq"))
    price_count = sum(1 for c in ok_pages if c.get("has_price"))
    metrics_count = sum(1 for c in ok_pages if c.get("has_metrics"))

    lines = [
        "---",
        f"date: {report_date}",
        f"tags: [geo, serp, competitors, intent, {slug}]",
        f"slug: {slug}",
        f'query: "{query_text}"',
        f'our_url: {json.dumps(our_url)}',
        "status: confirmed",
        "---",
        "",
        f"# Конкурентный SERP-анализ: {query_text}",
        "",
        f"**Целевой интент (запрос):** `{query_text}`  ",
        f"**Слаг материала:** `{slug}`  ",
        f"**Наш URL для сопоставления:** `{our_url or 'null (Новый материал)'}`  ",
        f"**Дата замера:** {report_date}  ",
        "**Источники данных:** `Яндекс Cloud Search API v2` (region=149 Беларусь) + `Google XMLRiver` (country=by)  ",
        f"**Проверено живых URL в выдаче:** **{len(ok_pages)}** (ошибок загрузки: {len(failed_pages)})  ",
        "",
        "---",
        "",
        "## 1. Сводная таблица конкурентов из ТОП поисковой выдачи",
        "",
        "| № | Движок | URL | Источник | Заголовок (Title) | Слов | H2 / H3 | Таблица | FAQ | Цена | Цифры |",
        "|---|---|---|---|---|---|---|---|---|---|---|"
    ]

    for idx, c in enumerate(competitors, start=1):
        if c.get("status") == "ok":
            engine = c.get("engine", "-")
            url = c.get("url", "-")
            stype = c.get("source_type", "studio")
            title = c.get("title", "-")[:45] + ("..." if len(c.get("title", "")) > 45 else "")
            words = c.get("word_count", 0)
            h_count = f"{len(c.get('h2_list', []))} / {len(c.get('h3_list', []))}"
            tbl = "✅ Да" if c.get("has_table") else "❌ Нет"
            faq = "✅ Да" if c.get("has_faq") else "❌ Нет"
            price = "✅ Да" if c.get("has_price") else "❌ Нет"
            metrics = "✅ Да" if c.get("has_metrics") else "❌ Нет"

            lines.append(
                f"| {idx} | {engine} | [{url}]({url}) | `{stype}` | {title} | {words:,} | {h_count} | {tbl} | {faq} | {price} | {metrics} |"
            )
        else:
            engine = c.get("engine", "-")
            url = c.get("url", "-")
            lines.append(
                f"| {idx} | {engine} | [{url}]({url}) | `не получена` | *Ошибка загрузки ({c.get('error', 'error')})* | — | — | — | — | — | — |"
            )

    lines.extend([
        "",
        "---",
        "",
        "## 2. Фактическая статистика SERP и ландшафт выдачи",
        "",
        "**Распределение типов источников:**"
    ])

    for stype in ["reference", "studio", "media", "aggregator"]:
        count = type_counts.get(stype, 0)
        share = round(count / total_ok * 100, 1) if total_ok else 0.0
        lines.append(f"- **`{stype}`**: {count} стр. ({share}%)")

    lines.extend([
        "",
        "**Концентрация доменов:**",
        f"- Уникальных доменов в выборке: **{len(domain_counts)}** из {total_ok} URL",
        f"- Доменов из зоны `.by`: **{by_domains_count}**"
    ])

    if repeated_domains:
        rep_str = ", ".join(f"`{d}` ({cnt} стр.)" for d, cnt in repeated_domains.items())
        lines.append(f"- Домены, встречающиеся более одного раза: {rep_str}")
    else:
        lines.append("- Домены, встречающиеся более одного раза: *отсутствуют (все домены уникальны)*")

    lines.extend([
        "",
        "**Объём контента конкурентов (в словах):**",
        f"- Минимальный объём: **{min_words:,}** слов",
        f"- Максимальный объём: **{max_words:,}** слов",
        f"- Медианный объём: **{median_words:,}** слов",
        f"- Средний объём: **{avg_words:,}** слов",
        "",
        "**Наличие структурных элементов доверия:**",
        f"- Таблицы данных: **{table_count} / {total_ok}** ({round(table_count / total_ok * 100, 1) if total_ok else 0.0}%)",
        f"- FAQ-блоки / аккордеоны: **{faq_count} / {total_ok}** ({round(faq_count / total_ok * 100, 1) if total_ok else 0.0}%)",
        f"- Открытые цены / тарифы: **{price_count} / {total_ok}** ({round(price_count / total_ok * 100, 1) if total_ok else 0.0}%)",
        f"- Конкретные цифры и замеры: **{metrics_count} / {total_ok}** ({round(metrics_count / total_ok * 100, 1) if total_ok else 0.0}%)",
        "",
        "---",
        "",
        "## 3. Детальная структура заголовков конкурентов (H2/H3)",
        ""
    ])

    for idx, c in enumerate(ok_pages, start=1):
        lines.extend([
            f"### {idx}. {c.get('title')} ({c.get('engine')})",
            f"- **URL:** `{c.get('url')}`",
            f"- **Тип источника:** `{c.get('source_type')}` | **Объём:** {c.get('word_count')} слов",
            f"- **Элементы:** Таблица: {'Да' if c.get('has_table') else 'Нет'} | FAQ: {'Да' if c.get('has_faq') else 'Нет'} | Цены: {'Да' if c.get('has_price') else 'Нет'} | Цифры: {'Да' if c.get('has_metrics') else 'Нет'}",
            "",
            "**Структура разделов страницы:**",
            ""
        ])

        headings = c.get("all_headings", [])
        if headings:
            for h in headings[:15]:
                prefix = "  - " if h["tag"] == "H3" else "- **"
                suffix = "" if h["tag"] == "H3" else "**"
                lines.append(f"{prefix}[{h['tag']}] {h['text']}{suffix}")
            if len(headings) > 15:
                lines.append(f"- *...и ещё {len(headings) - 15} подзаголовков*")
        else:
            lines.append("- *(Заголовки H2/H3 не выделены в тексте)*")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 4. Сводный список H2-подвопросов конкурентов",
        "",
        "Ниже представлен перечень смысловых вопросов и разделов, раскрытых конкурентами в ТОП выдачи,",
        "с векторизацией локальной моделью `text-embedding-qwen3-embedding-8b`."
    ])

    our_cov = h2_analysis_res.get("our_coverage")
    if our_cov:
        lines.extend([
            "",
            f"**Сопоставление с нашей страницей (`{our_cov['our_url']}`):**",
            f"- Всего уникальных H2 конкурентов: **{h2_analysis_res['unique_h2_count']}**",
            f"- Число H2 на нашей странице: **{our_cov['our_h2_count']}**",
            f"- Закрыто у нас (Top-3 Average Cosine $\\ge 0.65$): **{our_cov['covered_count']}**",
            f"- Отсутствует / пробелы у нас (Top-3 Average Cosine $< 0.65$): **{our_cov['missing_count']}**",
            "",
            "| № | H2-вопрос конкурента | URL источника | Сходство с запросом | Среднее Top-3 совпадение с FastUp | Статус покрытия FastUp |",
            "|---|---|---|---|---|---|"
        ])
        for idx, item in enumerate(our_cov["items"], start=1):
            status_str = "❌ **ПРОБЕЛ (Добавить)**" if item["is_missing"] else f"✅ Закрыто ({item['avg_top3_score']})"
            url_short = item["url"].split("/")[2] if "//" in item["url"] else item["url"][:25]
            lines.append(
                f"| {idx} | {item['text']} | [{url_short}]({item['url']}) | {item.get('sim_to_query', '—')} | **{item['avg_top3_score']}** | {status_str} |"
            )
    else:
        lines.extend([
            "",
            f"**Ранжирование H2-подвопросов по семантической близости к запросу (всего уникальных: {h2_analysis_res['unique_h2_count']}):**",
            "",
            "| № | Ключевой H2-подвопрос конкурентов | Источник | Близость к целевому запросу (Cosine) |",
            "|---|---|---|---|"
        ])
        for idx, h in enumerate(h2_analysis_res.get("h2_analysis", []), start=1):
            url_short = h["url"].split("/")[2] if "//" in h["url"] else h["url"][:25]
            lines.append(f"| {idx} | {h['text']} | [{url_short}]({h['url']}) | **{h['sim_to_query']}** |")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[+] Successfully generated competitor intelligence report: {report_path}", flush=True)
    return report_path


# ---------------------------------------------------------------------------
# Intent Processing Pipeline
# ---------------------------------------------------------------------------

def process_intent_target(
    target: dict[str, Any],
    yc_key: str,
    folder_id: str,
    xml_user: str,
    xml_key: str,
    output_dir: Path,
    report_date: str,
    max_workers: int = 6,
    per_engine: int = 4
) -> dict[str, Any]:
    """Process a single intent target task and return summary metadata."""
    slug = target["slug"]
    query_text = target["query"]
    our_url = target.get("our_url")

    print("\n" + "=" * 70, flush=True)
    print(f"STARTING SERP INTELLIGENCE PIPELINE:", flush=True)
    print(f"  Query:   '{query_text}'", flush=True)
    print(f"  Slug:    '{slug}'", flush=True)
    print(f"  Our URL: {our_url or 'null (New Article)'}", flush=True)
    print("=" * 70, flush=True)

    # 1. Gather SERP results (4 URLs per engine, <= 2 per domain)
    serp_items = get_top_serp_competitors(query_text, yc_key, folder_id, xml_user, xml_key, per_engine=per_engine, max_per_domain=2)

    # 2. Download and parse competitor pages
    print(f"[*] Downloading and parsing {len(serp_items)} pages (threads: {min(max_workers, 10)})...", flush=True)
    parsed_pages = []
    
    session = requests.Session()
    with ThreadPoolExecutor(max_workers=min(max_workers, 10)) as executor:
        future_to_item = {
            executor.submit(fetch_and_parse_page, item["url"], session): item
            for item in serp_items
        }
        for future in as_completed(future_to_item):
            orig_item = future_to_item[future]
            try:
                page_data = future.result()
                page_data["engine"] = orig_item["engine"]
                parsed_pages.append(page_data)
                status_symbol = "OK" if page_data["status"] == "ok" else f"ERR ({page_data['error']})"
                print(f"    -> [{page_data['engine']}] {page_data['url'][:55]}... ({status_symbol}, {page_data['word_count']} слов)", flush=True)
            except Exception as e:
                print(f"    -> [!] Failed processing {orig_item['url']}: {e}", flush=True)
                parsed_pages.append({
                    "url": orig_item["url"],
                    "engine": orig_item["engine"],
                    "status": "не получена",
                    "error": str(e),
                    "source_type": classify_source(orig_item["url"])
                })

    # Sort pages in original SERP order (Yandex then Google)
    engine_order = {"Yandex": 0, "Google": 1}
    parsed_pages.sort(key=lambda p: (engine_order.get(p.get("engine"), 2), p.get("url")))

    # 3. Vectorize and evaluate H2 coverage
    print(f"[*] Local vectorization of H2 blocks in LM Studio ({MODEL_NAME})...", flush=True)
    h2_res = analyze_h2_coverage(parsed_pages, query_text, our_url)

    # 4. Generate Markdown report
    report_path = generate_markdown_report(
        slug=slug,
        query_text=query_text,
        our_url=our_url,
        competitors=parsed_pages,
        h2_analysis_res=h2_res,
        output_dir=output_dir,
        report_date=report_date
    )

    # Aggregate summary metrics
    ok_pages = [p for p in parsed_pages if p.get("status") == "ok"]
    studios_count = sum(1 for p in ok_pages if p.get("source_type") == "studio")
    media_count = sum(1 for p in ok_pages if p.get("source_type") == "media")
    ref_count = sum(1 for p in ok_pages if p.get("source_type") == "reference")
    agg_count = sum(1 for p in ok_pages if p.get("source_type") == "aggregator")
    
    by_domains = set()
    for p in ok_pages:
        try:
            d = urllib.parse.urlparse(p["url"]).netloc.lower()
            if d.endswith(".by"):
                by_domains.add(d)
        except Exception:
            pass

    word_counts = [p.get("word_count", 0) for p in ok_pages if p.get("word_count", 0) > 0]
    max_words = max(word_counts) if word_counts else 0

    has_tables = any(p.get("has_table") for p in ok_pages)
    has_faq = any(p.get("has_faq") for p in ok_pages)

    if h2_res.get("our_coverage"):
        missing_h2 = h2_res["our_coverage"]["missing_count"]
    else:
        missing_h2 = h2_res.get("unique_h2_count", 0)

    # Decision rules per TZ §4:
    # - Студий 0-1, остальное media/reference -> писать (поле пустое, дешевый вход)
    # - Студий 3+, старые домены -> сузить угол (высокая конкуренция)
    # - .by-доменов 0 -> примечание / сузить угол на Беларусь
    if studios_count >= 3:
        decision = "сузить угол"
    elif len(by_domains) == 0 and studios_count >= 2:
        decision = "сузить угол"
    else:
        decision = "писать"

    return {
        "slug": slug,
        "query": query_text,
        "our_url": our_url,
        "report_path": str(report_path),
        "total_competitors": len(ok_pages),
        "studios_count": studios_count,
        "media_count": media_count,
        "ref_count": ref_count,
        "agg_count": agg_count,
        "by_domains_count": len(by_domains),
        "by_domains_list": list(by_domains),
        "max_words": max_words,
        "has_tables": has_tables,
        "has_faq": has_faq,
        "missing_h2_count": missing_h2,
        "decision": decision
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", type=Path, help="Path to JSON task list file [{slug, query, our_url}]")
    parser.add_argument("--query", type=str, help="Single query string to evaluate")
    parser.add_argument("--slug", type=str, help="Slug identifier for single query")
    parser.add_argument("--our-url", type=str, default=None, help="Target FastUp URL for semantic comparison (optional)")
    parser.add_argument("--output-dir", type=Path, default=Path("geo"), help="Output directory for reports (default: geo/)")
    parser.add_argument("--workers", type=int, default=6, help="Number of concurrent worker threads (max 10)")
    parser.add_argument("--per-engine", type=int, default=4, help="Number of URLs per search engine (default: 4)")
    parser.add_argument("--date", type=str, default=None, help="Override report date (YYYY-MM-DD)")
    parser.add_argument("--summary-file", type=Path, default=None, help="Path for summary report when batch processing")
    args = parser.parse_args()

    env = load_env(REPO_ROOT)
    yc_key = env.get("YANDEX_CLOUD_API_KEY")
    folder_id = env.get("YANDEX_CLOUD_FOLDER_ID")
    xml_user = env.get("XMLRIVER_USER")
    xml_key = env.get("XMLRIVER_KEY")

    if not yc_key or not folder_id:
        sys.exit("Error: YANDEX_CLOUD_API_KEY или YANDEX_CLOUD_FOLDER_ID отсутствуют в .env!")
    if not xml_user or not xml_key:
        sys.exit("Error: XMLRIVER_USER или XMLRIVER_KEY отсутствуют в .env!")

    report_date = args.date or datetime.now().strftime("%Y-%m-%d")

    # Build target task list
    targets: list[dict[str, Any]] = []
    if args.input_file:
        if not args.input_file.exists():
            sys.exit(f"Error: Файл {args.input_file} не найден!")
        targets = json.loads(args.input_file.read_text(encoding="utf-8"))
    elif args.query:
        slug = args.slug or re.sub(r"[^a-z0-9_-]", "-", args.query.lower())
        targets = [{
            "slug": slug,
            "query": args.query,
            "our_url": args.our_url
        }]
    else:
        targets = [{
            "slug": "skvoznaya-analitika-i-utm-atributsiya-zayavok",
            "query": "сквозная аналитика и отслеживание источников заявок по utm меткам",
            "our_url": None
        }]

    workers = min(max(args.workers, 1), 10)
    print("=" * 70, flush=True)
    print("FastUp SERP Competitor Intelligence Engine v1.2 (Phase 1 Ready)", flush=True)
    print(f"Pending tasks: {len(targets)} | Threads: {workers} | URLs/engine: {args.per_engine} | Date: {report_date}", flush=True)
    print("=" * 70, flush=True)

    summary_items = []
    for target in targets:
        item_summary = process_intent_target(
            target=target,
            yc_key=yc_key,
            folder_id=folder_id,
            xml_user=xml_user,
            xml_key=xml_key,
            output_dir=args.output_dir,
            report_date=report_date,
            max_workers=workers,
            per_engine=args.per_engine
        )
        summary_items.append(item_summary)

    # Generate summary report if requested or multiple tasks run
    if args.summary_file or len(targets) > 1:
        summary_path = args.summary_file or (args.output_dir / f"{report_date}-serp-summary-11-tem.md")
        lines = [
            "---",
            f"date: {report_date}",
            "tags: [geo, serp, summary, 11-tem, intelligence]",
            "status: confirmed",
            "---",
            "",
            "# Сводка конкурентной SERP-разведки по 11 темам FastUp (Фаза 1)",
            "",
            f"**Дата анализа:** {report_date}  ",
            "**Поисковые движки:** `Яндекс Cloud Search API v2` (region=149 Беларусь) + `Google XMLRiver` (country=by)  ",
            f"**Параметры сбора:** до 4 URL с движка, не более 2 URL с домена  ",
            f"**Всего проанализировано тем:** {len(summary_items)}  ",
            "",
            "---",
            "",
            "## 1. Сводная таблица экономики и конкуренции по темам",
            "",
            "| № | Слаг темы | Студий в ТОП | .by доменов | Типы источников (Студии/Медиа/Справка/Агр) | Макс. объём (слов) | Таблицы у конкур. | FAQ у конкур. | Не закрыто у нас (H2) | Вывод (§4 ТЗ) |",
            "|---|---|---|---|---|---|---|---|---|---|"
        ]

        for idx, s in enumerate(summary_items, start=1):
            types_str = f"{s['studios_count']}/{s['media_count']}/{s['ref_count']}/{s['agg_count']}"
            tbl_str = "✅ Да" if s["has_tables"] else "❌ Нет"
            faq_str = "✅ Да" if s["has_faq"] else "❌ Нет"
            dec_badge = f"**`{s['decision']}`**"

            lines.append(
                f"| {idx} | [`{s['slug']}`]({Path(s['report_path']).name}) | **{s['studios_count']}** | {s['by_domains_count']} | `{types_str}` | {s['max_words']:,} | {tbl_str} | {faq_str} | **{s['missing_h2_count']}** | {dec_badge} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 2. Краткий реестр отчётов по всем 11 темам",
            ""
        ])

        for idx, s in enumerate(summary_items, start=1):
            lines.extend([
                f"### {idx}. {s['slug']}",
                f"- **Целевой запрос:** `{s['query']}`",
                f"- **Наш URL:** `{s['our_url'] or 'null (Новая статья)'}`",
                f"- **Отчёт:** [`{s['report_path']}`]({Path(s['report_path']).name})",
                f"- **Факты выдачи:** Студий: {s['studios_count']} | .by-доменов: {s['by_domains_count']} ({', '.join(s['by_domains_list']) or 'нет'}) | Макс. слов: {s['max_words']:,} | Незакрытых H2: {s['missing_h2_count']}",
                f"- **Решение по контуру (§4):** `{s['decision']}`",
                ""
            ])

        summary_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n[+] Multi-topic summary report saved: {summary_path}", flush=True)

    print("\n" + "=" * 70, flush=True)
    print(f"COMPLETED SUCCESSFULLY! Processed topics: {len(summary_items)}", flush=True)
    for s in summary_items:
        print(f"  -> {s['report_path']}", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
