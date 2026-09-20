---
name: geo-rag-architect
description: >-
  Architect and audit commercial pages (FastUp or client) into self-contained, citable
  answer blocks optimized for generative AI extraction (Google AI Overviews, Perplexity,
  ChatGPT search). Enforces factual ground-truth from positioning/facts.md, eliminates
  hallucinated metrics, sequences user intent hierarchy, and preserves existing conversion blocks.
---

# GEO-RAG Architect: Commercial Page Structure for Passage Extraction

This skill governs the structural architecture of commercial landing pages and service pages. Generative search engines decompose user queries into sub-intents and extract self-contained text passages rather than ranking entire pages.

---

## 1. Skill Boundary Matrix

To prevent overlap across GEO capabilities:

| Intent | Assigned Skill / Agent |
|---|---|
| Design or restructure page architecture into extractable blocks | **`geo-rag-architect` (this skill)** |
| Diagnose live AI citations of competitors and test ranking hypotheses | `geo-hypothesis-engine` |
| Package completed client cases into outward authority articles | `case-writer-geo` |
| Technical crawler accessibility, robots.txt, Schema.org, SSR | `aeo-geo` |
| Drafting body copy for designed blocks | `content-writer` subagent |
| QA and anti-AI editorial review | `content-reviewer` subagent |

---

## 2. Verified Realities vs Unproven Assumptions

### Verified Mechanics:
- **Passage-Level Extraction:** Generative engines extract discrete sections that directly answer sub-queries. Each major section must be self-contained and intelligible in isolation.
- **Specifics Over Fluff:** Concrete figures (exact starting price "от N BYN", delivery days, legal guarantees, service scope) provide high-entropy tokens that AI models quote directly.
- **Entity Consistency:** Uniform company data across properties establishes reliable knowledge-graph identity. Single Source of Truth: `positioning/facts.md`.
- **Decision Hierarchy:** Structuring sections in descending order of commercial friction increases human conversion while naturally serving AI search intents.

### Banned Hallucinations & False Claims:
- **DO NOT claim local cosine similarity predicts live AI citations.** A local embedding model does not reflect Google or OpenAI's real index, link graph, or rerankers.
- **DO NOT claim arbitrary score thresholds (e.g. "0.85 = ground truth").** The scale is uncalibrated.
- **DO NOT present internal competitor similarity tables as public market metrics.** These measures are sensitive to query phrasing and risk comparative advertising violations.
- **DO NOT invent demand share percentages without search volume data.** Unverified numbers are assumptions, not analytics.

---

## 3. Page Architecture Workflow

### Step 0. Source Factual Anchor
Read `positioning/facts.md`. All pricing, delivery timelines, legal entity data, and guarantees must come strictly from this file. Missing facts must be escalated to founders, never hallucinated.

### Step 1. Collect Real Client Intents
Assemble actual questions and objections from:
- Target query demand in `content/research/`
- Competitor structures in `content/research/competitors/`
- Sales objections in `positioning/objections.md`
- Active production content in `content/live-pages/`

*Demand Check:* If search demand is near zero in Belarus/target geo, the page cannot rely on search traffic. Define its role upfront as sales collateral or a supporting entity page.

### Step 2. Build Gap & Intent Matrix
Map questions into a structured grid:
`Client Question` → `Current Page Coverage` → `Competitor Coverage` → `Deal-Closing Priority`.

### Step 3. Block Sequence Architecture
Organize blocks according to client decision progression:
1. **Hero Screen:** Clear service definition, target client segment, entry price ("от N BYN"), primary risk-reversal guarantee.
2. **Commercial Answers (H2 Blocks):** Deliverables, pricing tiers, production timeline in working days, post-launch support, and IP/code ownership.
3. **Comparative Grids:** Direct feature and trade-off comparisons where clients choose between options.
4. **Targeted FAQ:** High-friction technical and legal concerns marked up with `FAQPage` JSON-LD.

**Block Standard:** Exactly **one H2 per self-contained answer**. The opening paragraph should state the core resolution concisely (aim for ~35–45 words of dense, direct information).

### Step 4. Regression Defense
Cross-check proposed wireframes against `content/live-pages/`. Never drop blocks that currently handle vital conversion questions (e.g. turnaround time, analytics setup, warranty) on the live site.

### Step 5. Handoff to Copywriting & QA
- Page copy must be drafted by the `content-writer` subagent following the structural blueprint.
- Run the draft through `python scripts/check_ai_markers.py <file>` (must score LOW).
- Hand off to `content-reviewer` for adversarial stress-testing.
- Set WordPress publishing status to `draft` by default (`publish` requires founder sign-off).

---

## 4. Operational Boundaries

- **Off-Page Dominance:** On-page structure alone cannot overcome absent third-party validation (directories, brand mentions, customer reviews).
- **Revenue Alignment:** Validated success is measured by GA4 referral traffic from AI search surfaces (`chatgpt.com`, `perplexity.ai`, Google AI Mode/Overviews) and qualified CRM leads, not synthetic keyword scores.
