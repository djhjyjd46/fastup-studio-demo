---
name: fastup-content
description: >-
  Craft public and client-facing copy for FastUp that a real person reads with interest
  and trust. Use WHENEVER writing or rewriting any outward text: website (About, services,
  landing pages), posts (LinkedIn, Google Business, Habr, vc.ru, Telegram), articles/GEO,
  meta descriptions, outreach pitches, and proposal introductions (КП). TRIGGER EVEN FOR
  A TINY ASK ("fix headline", "write profile bio") — short copy is where defensive hedging
  and AI markers do the most visible damage. Produces confident, benefit-driven copy
  grounded in studio facts (cases/, expert/, facts.md).
---

# FastUp Content Engine

## 1. Core Principles

1. **Benefit-First (Для читателя, а не про нас):**
   - Every sentence must answer: *"What does this give the client?"*
   - Never open with internal company trivia ("We work without an office", "We use modern AI stacks"). Frame directly around client outcomes.
   - Ban negative contrasts: rewrite "X, and not Y" as direct affirmations.

2. **Zero Defensive Hedging (Оговорки вычёркивать сразу):**
   - Eliminate defensive caveats from commercial copy: "Results may vary", "This is not a guarantee", "Depends on many factors".
   - Address edge cases, dependencies, and guarantees strictly in FAQ or verbal sales calls, never in the commercial hero/pricing section.
   - Promises we keep are stated as promises: "Сдаём сайт в зелёной зоне PageSpeed" — not "стремимся к быстрой загрузке".

3. **Language of Real Practitioners (Язык практиков-работяг):**
   - Most clients in Belarus are real-world operators: builders, furniture manufacturers, offline shops, production facilities.
   - **Ban IT bird-language:** Never use "PageSpeed 90+", "ACF Pro", "LTV", "Quiz-funnel", "Enterprise Edition" in client-facing copy. Translate to human reality: «сайт открывается мгновенно», «кнопка подбора дивана под размер комнаты», «не нужно учиться админке — написали в чат 'поменяй цену на 1200' и готово».
   - **Never count the client's money:** Never say "sell 3 sofas and pay off the website" — this is tactless and irritates business owners. Show ROI by stopping ad waste and cutting SaaS constructor fees.
   - **Presentation:** Strict, clean light theme (clean white paper, readable typography, mobile-first). No dark startup aesthetics for commercial proposals.

4. **Pricing Standard:**
   - **Strictly formatted as "от N BYN"** (starting from N BYN).
   - Fixed all-inclusive pricing does not exist in our studio model. Scope defines the budget.

---

## 2. Voice & Tone ("Спокойная уверенность")

- **Tone:** Direct, warm, grounded, calm confidence. No corporate buzzwords, no hype, no exclamation mark spam.
- **Rhythm:** Short sentences, conversational syntax, natural Russian word order.
- **Formatting:** One thought per paragraph. Place the core insight in the first sentence.
- **Punctuation:** Minimize em-dashes (`—`). Use periods, commas, colons.

---

## 3. The Quality Gate

Before presenting any drafted or edited copy, answer this single gate question:
> **"Does the edit make the text sell STRONGER or WEAKER?"**

- If weaker: Reject the edit immediately. Find an alternative phrasing that protects against legal/factual risk without killing commercial traction.
- Never weaken a copy promise down to sterile neutrality just to avoid friction.
- Only remove without replacement if the claim carries legal or financial exposure (defaming competitors, unsubstantiated guarantees, demonstrably false market claims).

---

## 4. AI-Tells to Eliminate (Anti-Bot Checklist)

Review every line against these signature AI artifacts:
1. **Self-Invented Explanatory Glosses:** Do not add unasked contrasting qualifiers (e.g., if human says "on real tasks", do NOT append ", not synthetic benchmarks").
2. **Unasked Future Promises:** Do not tack on generic tail phrases («…и приводим клиентов», «делаем так, чтобы вас находили»).
3. **List-like Service Dumps:** Avoid comma-separated noun dumps («SEO, реклама, сайты»). Use verbs inside living sentences: «настраиваем контекстную рекламу, выводим сайт в поиск и собираем каталоги».
4. **Symmetry & Parallel Syntax:** Avoid artificially uniform bullet lengths or repeating "X, which Y" patterns.
5. **Telegraphic Resume Style:** In personal posts, blogs, or author intros, always greet and introduce yourself naturally («Привет, я Егор Воронов»), never open with dry badges («Разработчик и фаундер FastUp. В этом видео...»).
6. **Double Highlighting:** If a block is already visually formatted (quote card, callout), never prepend redundant labels like "Коротко:".

---

## 5. Review Protocol: Ask Questions, Do Not Hallucinate

When reviewing a draft (human- or agent-written):
1. **Never invent filler content:** If an argument, case metric, or bridge is missing, do NOT hallucinate or draft placeholder facts.
2. **Ask 1–2 direct, concrete questions** to the founder to extract the real fact/quote from personal experience.
3. Once answered, incorporate the authentic response with minimal grammatical adjustment.

---

## 6. Format-Specific Guides

- **Commercial Website Pages (Services, About, Landing):** 3–5 tight benefit-led blocks. Titles must express client value. Deploy as draft via WordPress REST API.
- **Proposals (КП):** Clear structure: client's bottleneck → what we build → timeline → price "от N BYN" → next step. Written in practitioner language on a clean light theme.
- **Articles & GEO Content:** Follow `content/PIPELINE.md`. Open with core substance (fact, anomaly, data), never with an author bio or agency promo. Ground E-E-A-T by linking named entities (FastUp, Belarus, SEO, AI, Egor Voronov) naturally.
  - **Mandatory Commercial Cross-Linking (Перелинковка):** Every article intended for `fastup.by` MUST contain at least:
    1) One contextual link to the corresponding core service page (`/geo-prodvizhenie/`, `/razrabotka-saitov/`, `/seo-prodvizhenie/`, `/kontekstnaya-reklama/`, `/graficheskiy-i-veb-dizayn/`).
    2) One link to an agency proof asset (case study `/keys-*/`, audit system `/geo-audit-system/`, or related benchmark).
    3) A natural CTA in the conclusion/next-steps block leading to the relevant service or audit.
    Articles without commercial cross-linking are non-functional for lead generation and will be rejected.
- **Metadata & Snippets:** 1–2 sentences naming the exact paid outcome.

---

## 7. Mandatory Verification Tooling

Before handing any copy over to human review:
1. Run automated rhythm and cliché check:
   ```bash
   python scripts/check_ai_markers.py <file>
   ```
   Risk level MUST be **`LOW`**. If markers or low burstiness are flagged, revise sentence variety before submission.
2. For long-form copy (articles, full pages, proposals), run the `content-reviewer` subagent as a second-pair-of-eyes pass.
