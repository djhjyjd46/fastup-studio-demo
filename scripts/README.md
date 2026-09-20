# scripts/ — Tooling Architecture & Universal Dispatcher

## Architecture: Clean Single Source of Truth + Universal Dispatcher

This repository enforces a strict **Domain Isolation & Single Source of Truth** engineering standard:
1. **Domain tools live solely inside their dedicated skill:**
   All script sources reside exclusively in the `scripts/` directory of their respective skill within `.claude/skills/<skill>/scripts/` (mirrored in `.agents/skills/<skill>/scripts/`). There are **no duplicate proxy files** in root `scripts/`.
2. **Universal Dispatcher (`scripts/run.py`):**
   To execute any domain tool without typing full paths, use the universal CLI dispatcher:
   ```bash
   python scripts/run.py <tool_name> [args...]
   python scripts/run.py --list
   ```
3. **Root `scripts/` contains strictly Studio Core Runtime Infrastructure:**
   - `run.py` — Universal domain tool CLI dispatcher.
   - `git_sync.py` — Automated git sync hook at session start and turn end.
   - `session_card.py` — Sprint task display and stale item auditor.
   - `context_pack.py` — Studio memory pack assembler (RAG).
   - `search_memory.py` — SQLite FTS5 search across repository memory.
   - `build_index.py` — Maps of Content (MOC) and backlinks graph builder.
   - `env_load.py` — Secure `.env` credential loader.
   - `sync_codex.py` — Knowledge base codex synchronizer.
   - `tool_envelope.py` — Standardized JSON envelope wrapper for agent tool outputs.
   - `escalate.py` — Escalation handler for blocking errors.
   - Temporary scratch files belong solely in `scratch/` (gitignored).

---

## Domain Mapping Matrix

| Domain | Skill | Core Scripts |
|---|---|---|
| **AEO / GEO & AI Search** | `aeo-geo` | `geo_check.py` (FastUp GAS benchmark runner), `index_measure.py`, `geo_embed.py`, `geo_keywords.py`, `fetch_serp_competitors_per_intent.py` |
| **Traditional SEO & Search Engines** | `technical-seo` | `gsc_report.py`, `yandex_webmaster_report.py`, `yandex_metrika_report.py`, `yandex_recrawl.py`, `submit_google_indexing.py`, `yandex_external_links.py` |
| **Paid Advertising (Yandex.Direct)** | `fastup-ads` | `direct_status.py`, `ads_snapshot.py`, `direct_lint.py`, `direct_apply.py`, `direct_report.py`, `direct_semantics.py` |
| **Primary Documents & Google Drive** | `fastup-doc-ops` | `gdocs.py`, `close_client_deal.py`, `run_contractor_payout.py`, `stitch_signed_acts.py` |
| **Client Site Audit & Sales TZ** | `fastup-client-audit` | `run_client_audit.py`, `site_crawl.py`, `pagespeed_check.py` |
| **Telegram Agent & Bots** | `fastup-tg-agent` | `tg_agent.py`, `complete_task.py`, `sync_kb.py`, `inspect_operator_lead.py` |
| **CRM & Knowledge Base** | `fastup-tools` | `tools.py`, `deploy_tools_server.py` |
| **Hosting & Deployment** | `ispmanager-hosting` | `deploy_static_file.py`, `deploy_theme.py`, `deploy_theme_file.py`, `clear_page_cache.py`, `deploy_crm.py` |
| **Content & WordPress Publishing** | `fastup-content` | `check_ai_markers.py`, `wp_publish.py`, `download_live_site_pages.py`, `update_faq.py` |

---

## Script Index by Category

### Studio Memory & Knowledge Graphs
- `search_memory.py` — SQLite FTS5 search across repository memory. Invoked by `CLAUDE.md` and git hooks (`post-commit` / `post-merge`).
- `build_index.py` — Generates Maps of Content (MOC) and backlinks across: `notes/raw/`, `notes/`, `expert/opinions/`, `decisions/`, `cases/`, `geo/`, `content/`, `positioning/`, `promotion/`, `playbook/`. Hooked in `pre-commit`.

### Website: Publishing & Production Sync
- `wp_publish.py` — Publish/update drafts via WordPress REST API. Shared library.
- `update_faq.py` — Syncs structured FAQ schema into WordPress ACF fields.
- `download_live_site_pages.py` — Pulls live HTML mirrors into `content/live-pages/`.
- `deploy_theme.py` — Uploads theme templates via ISPmanager API and rebuilds Tailwind CSS.
- `deploy_static_file.py` — Atomic deployment of static assets (`llms.txt`, `robots.txt`, `.htaccess`) to ISPmanager without SSH.

### Site Audit (Internal & Client)
- `site_crawl.py` — Deterministic crawler for status codes, canonicals, meta tags, and alt text.
- `pagespeed_check.py` — Core Web Vitals (LCP, CLS, TBT) measurement via Google PageSpeed API.
- `run_client_audit.py` — Orchestrates crawl, speed check, HTML generation, and task dispatch to Telegram topic 581.

### AEO / GEO: AI Search Visibility
- `geo_check.py` — FastUp GAS benchmark runner measuring live citations across Google AI Overviews, Yandex Alice, and ChatGPT Search.
- `geo_embed.py` — Embedding generation, text chunking, and cosine similarity calculations.
- `geo_keywords.py` — Semantic intent keyword extraction.

### Yandex.Direct Paid Traffic
- `direct_status.py` — Instant campaign health check: pacing, bids, balance, and over-bid warnings.
- `direct_lint.py` — Pre-flight linter: negative keyword conflicts, duplicate phrases, and budget limits.
- `ads_snapshot.py` — Consolidated JSON snapshot across Direct, Metrika, Webmaster, and Wordstat.
- `direct_apply.py` — Apply negative keyword modifications (dry-run by default).
- `direct_report.py` — Search query performance reporting.

### Search Console & Indexing Analytics
- `gsc_report.py` — Google Search Console queries, CTR, impressions, and positions.
- `yandex_webmaster_report.py` — Yandex Webmaster crawl status and query impressions.
- `yandex_metrika_report.py` — Yandex Metrika goals and conversion analytics.
- `yandex_recrawl.py` — Submit URLs to Yandex priority reindexing.
- `submit_google_indexing.py` — Batch URL submission via Google Indexing API.

---

## Secret Hygiene Directive

All API keys and credentials must strictly load from process environment variables or `.env` files. Hardcoding secrets in script code is strictly prohibited.
