# FastUp Studio

> **Autonomous Operating System & Agentic Engineering Environment for FastUp.by**  
> Built strictly on **Google Cloud Non-Agentic First** principles and **Antigravity 2.0** multi-agent architecture.

[![Antigravity](https://img.shields.io/badge/Antigravity-2.0-blue.svg)](https://antigravity.google)
[![Python](https://img.shields.io/badge/Python-3.11+-brightgreen.svg)](https://python.org)
[![TypeScript / Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org)
[![DeepSeek API](https://img.shields.io/badge/DeepSeek-V3%20%2F%20R1-blueviolet.svg)](https://deepseek.com)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](#)

---

## 🏗️ Architecture Overview

FastUp Studio solves the agency complexity trap: instead of building chaotic multi-agent "circuses" or relying on brittle no-code platforms, it separates agency operations into **two decoupled, production-grade contours sharing a single CRM database and Git-backed operational memory**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  CONTOUR 1: 24/7 Deterministic Server Runtime (ISPmanager Hosting, Node.js + PHP CRM)   │
│                                                                                        │
│  90% DETERMINISTIC CODE (Zero LLM cost, 100% SLA, zero hallucination risk):           │
│  • Inbound webhooks & cold dialer pipelines → CRM DB transactions                     │
│  • Automated task dispatching into Telegram topics (549 Leads, 616 Deals, 581 Ops)     │
│  • 45-minute SLA escalation cron & callback monitors                                  │
│  • Atomic operator actions ("Claim Lead", "Spam", "Close Deal")                        │
│                                                                                        │
│  10% SELECTIVE LLM (Alesya Telegram Agent — direct official api.deepseek.com):        │
│  • On-demand knowledge retrieval from structured agency markdown / SQLite             │
│  • Background PM conversation analysis (`pm-scan`) to spot client intent signals      │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ Shared CRM Database (tools.fastup.by)
                                            │ Shared Repository Memory (Git)
┌───────────────────────────────────────────▼────────────────────────────────────────────┘
│  CONTOUR 2: Founder Studio Desk (Google Antigravity 2.0 / Gemini Pro Workspace)         │
│                                                                                        │
│  Unified Orchestrator: natural language & code interface for Agency Founders           │
│                                                                                        │
│  ├── 13 PROGRESSIVE SKILLS ("How to execute"):                                         │
│  │   • fastup-doc-ops    → Contract, act & tax calculation generation (A4 math/fitz)   │
│  │   • fastup-accountant → Income tax, FSZN, KUDiR, Belarusian sole proprietor ops     │
│  │   • fastup-ads        → Yandex.Direct bidding, negative semantics, linting, stats   │
│  │   • aeo-geo & rag     → AI Engine Optimization, GAS benchmarks, Perplexity citings │
│  │   • technical-seo     → Automated multi-page crawl, canonicals, CWV audits          │
│  │   • business-mentor   → Unit economics, commercial proposals ("от N BYN"), quotes   │
│  │                                                                                     │
│  ├── DETERMINISTIC MCP TOOLS ("Action execution in real world"):                        │
│  │   • tools.fastup.by API (53 endpoints: CRM cards, documents, leads, funnel stats)   │
│  │   • Local CLI automation (Python/Node scripts, deterministic PDF normalization)     │
│  │                                                                                     │
│  ├── ISOLATED SUBAGENTS (Only for noisy/heavy context containment):                    │
│  │   • technical-seo-auditor (crawls 100+ URLs without polluting orchestrator window)  │
│  │   • ads-analyst           (parses large campaign logs & search query reports)       │
│  │                                                                                     │
│  └── HUMAN-IN-THE-LOOP SAFEGUARDS:                                                     │
│      Financial transactions, tax filings, production deployment, and ad spend changes │
│      strictly require human diff inspection and explicit confirmation (`--apply`).     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Engineering Principles

1. **Non-Agentic First (Google Cloud Pattern):**
   Predictable or highly structured workloads must be executed with deterministic code. LLMs are only invoked where reasoning, intent synthesis, or natural language generation is strictly necessary.
2. **Deterministic Tools > LLM Hallucinations:**
   Calculations, primary accounting documents, tax rules, and database updates are driven by audited deterministic algorithms, never left to LLM guesswork.
3. **Markdown as the Single Source of Truth:**
   All memory, studio playbook, decisions, positioning, and case studies are version-controlled in Git as structured Markdown. Changes are committed and synchronized via automated lifecycle hooks.
4. **Context Pack Architecture:**
   Avoid indiscriminate context flooding. Targeted context packs are assembled dynamically based on domain tags (`text`, `decision`, `ads`, `geo`, `site`).

---

## 📂 Repository Structure

```
├── .agents/
│   ├── rules/          # System guardrails and role constraints
│   └── skills/         # 14 specialized engineering & business operational skills
├── architecture/       # Master plans, migration designs, and ADRs (Decision Records)
├── geo/                # Generative Engine Optimization benchmarks (GAS) & llms.txt specs
├── playbook/           # Step-by-step agency standard operating procedures (SOPs)
├── scripts/            # Deterministic Python & PHP automation toolchain
└── tests/              # Offline regression and invariant test suite (pytest)
```

---

## 🛠️ Toolchain & Automation CLI

FastUp Studio includes a deterministic CLI suite for all agency operations:

```bash
# Advertising operations
python scripts/run.py direct_status        # Real-time Yandex.Direct campaign health & spend
python scripts/run.py direct_lint          # Lint search campaigns against negative keyword rules

# CRM & Alesya tools
python scripts/run.py tools list           # List available server actions on tools.fastup.by
python scripts/tools.py lead_get <id>      # Inspect live CRM lead card and timeline

# Context & Memory operations
python scripts/context_pack.py "<query>" --task decision  # Assemble focused context pack
python scripts/search_memory.py "<query>"                # Fast regex/BM25 memory search

# Document operations (Google Docs & PDF)
python scripts/gdocs.py list                             # List primary accounting documents
python scripts/run.py generate_act --client <id>         # Generate compliant A4 acceptance act
```

---

## 🛡️ Security & Privacy Boundaries

- **Client Operational Data Isolation:** All client PII, private records, and unanonymized databases reside strictly in an external, isolated repository (`fastup-clients`). Only sanitized architectural patterns and verified case metrics enter this core repository.
- **Safety Flags:** Mutating commands require explicit `--apply` flags. Without flags, scripts run in safe `--dry-run` simulation mode.
- **Strict Role-Based Access:** Operational tokens are bound to distinct role scopes (`founder`, `operator`, `bot`) with strict write protection on financial endpoints.

---

## 👥 Authors & Maintainers

- **Egor Voronov** ([@Asmodey_dev](https://github.com/Asmodey-dev)) — Architecture, AI Systems, Infrastructure, Ads & SEO.
- **Evgeniy** ([@djsbrvv921](https://github.com/djsbrvv921)) — Art Direction, UI/UX, Client Proposals & Sales.

---
*FastUp Studio © 2024–2026. Internal Operating System.*
