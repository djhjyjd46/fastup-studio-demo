---
name: technical-seo
description: >-
  Technical SEO audit of any website (client's or FastUp's own): crawling, status codes,
  redirects, canonicals, duplicate titles/descriptions, Core Web Vitals (LCP, CLS, TBT),
  image alts, mobile vs desktop issues. Use when user asks for "SEO-аудит", "технический аудит",
  "техаудит сайта", "проверь техническое SEO". Does NOT evaluate AI search visibility or
  generative engine citations (for that use `aeo-geo`).
---

# Technical SEO Audit (Traditional Search Engine Audit)

This skill executes comprehensive technical SEO audits for website crawlability, indexation health, and Core Web Vitals performance in Google and Yandex search engines.

---

## 1. Clear Boundaries: Technical SEO vs AEO/GEO vs Commercial Client Audit

| Task | Responsible Skill | Scope & Deliverable |
|---|---|---|
| **Traditional Technical SEO Audit** | **`technical-seo` (this skill)** | Page crawling, broken links, 4xx/5xx redirect chains, meta tags (Title/Desc), canonicals, duplicate content, Core Web Vitals (LCP, CLS, TBT). |
| **AEO/GEO (AI Search & LLM Citations)** | **`aeo-geo`** | Visibility in ChatGPT Search, Google AI Overviews, Yandex Alice; AI crawler permissions (GPTBot, ClaudeBot); FastUp GAS benchmark score. |
| **Landing Page Passage Architecture** | **`geo-rag-architect`** | On-page layout engineering for AI passage extraction (H2 sections, 134–167 words, entity citations, objection answers). |
| **Commercial Client Audit for Sales** | **`fastup-client-audit`** | Rapid turnkey sales audit with interactive HTML presentation deployed to `fastup.by/tz/<slug>/` and a single task assigned to Evgeniy in Telegram (topic 581). |

---

## 2. Skill Scripts (`./scripts/`)

| Script | Purpose | Execution Example |
|---|---|---|
| `site_crawl.py` | Technical crawler: robots.txt, sitemap, HTTP status codes, meta tags, duplicates, alt tags | `python .claude/skills/technical-seo/scripts/site_crawl.py <URL> --max-pages 30` |
| `pagespeed_check.py` | Core Web Vitals measurement (LCP, CLS, TBT) via Google PageSpeed Insights API | `python .claude/skills/technical-seo/scripts/pagespeed_check.py <URL1> <URL2>` |
| `gsc_report.py` | Google Search Console impressions, clicks, CTR, and search queries report | `python .claude/skills/technical-seo/scripts/gsc_report.py` |
| `yandex_webmaster_report.py` | Yandex Webmaster indexation state, search queries, and crawling errors | `python .claude/skills/technical-seo/scripts/yandex_webmaster_report.py` |
| `yandex_recrawl.py` | Force recrawl priority submission for URLs in Yandex Webmaster | `python .claude/skills/technical-seo/scripts/yandex_recrawl.py <URL>` |

> ℹ️ *All scripts are forward-compatible and executable via root proxies: `python scripts/<script_name>.py`.*

---

## 3. Audit Execution Workflow

1. **Website Crawl:**
   ```bash
   python scripts/site_crawl.py https://example.by --max-pages 30 --out /path/to/crawl.json
   ```

2. **Speed & Core Web Vitals Verification:**
   ```bash
   python scripts/pagespeed_check.py https://example.by https://example.by/catalog/ --out /path/to/pagespeed.json
   ```

3. **Analysis Against `playbook/site-works-checklist.md` Standards:**
   - Server response codes: zero redirect chains, zero 4xx/5xx broken links.
   - Title & Meta Description: strict length adherence, uniqueness, zero duplicate snippets.
   - Heading hierarchy: strictly one H1 per page, sequential H2-H3 nesting.
   - Indexation directives: valid `canonical` tags, accurate `robots.txt` and `sitemap.xml`.
   - Core Web Vitals thresholds: LCP < 2.5s, CLS < 0.1, TBT < 200ms.
