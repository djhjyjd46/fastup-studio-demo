---
name: fastup-client-audit
description: >-
  End-to-end client website express audit (SEO, GEO, technical defects, speed),
  generates client report in fastup-clients/<slug>/, deploys presentation to fastup.by/tz/<slug>/,
  and posts exactly one actionable task for sales manager (Evgeniy) in Telegram topic "Open Tasks" (581).
  Trigger whenever asked to "audit client website", "check client site", "prepare audit for Zhenya",
  or when processing a warm inbound lead from the cold dialer.
---

# FastUp Client Audit — Turnkey Client Website Audit

This skill executes a deterministic pipeline that extracts technical crawl data, evaluates on-page and GEO defects, and integrates directly with CRM and Telegram:

1. **Crawling:** Extracts live site data via `scripts/site_crawl.py` (`robots.txt`, `sitemap.xml`, `llms.txt`, Title, Meta Description, H1/H2 hierarchy, layout artifacts, speed metrics).
2. **Data Isolation:** Audit reports and raw JSON crawl snapshots are stored strictly outside the repository in `FASTUP_CLIENTS_DIR/<client>/` (`g:/fastup-clients/<client>/`).
3. **Presentation Generation & Deployment:** Automatically compiles an interactive HTML audit presentation from FastUp's branded template and deploys it to `fastup.by/tz/<slug>/` via `scripts/deploy_static_file.py`.
4. **Human Escalation (Zero Bureaucracy):** Dispatches exactly ONE actionable task to CRM and Telegram topic "Open Tasks" (ID 581) for Evgeniy to present the audit to the client with the direct URL `https://fastup.by/tz/<slug>/`. No duplicate or fake technical micro-tasks are created.

---

## Single-Command Invocation

```bash
python scripts/run_client_audit.py --url <URL> --lead-id <LEAD_ID> --client-name "<CLIENT_NAME>"
```

### CLI Parameters:
- `--url`: Target website URL (required, e.g. `https://example.by`).
- `--lead-id`: CRM lead ID (if originating from dialer or inbound form).
- `--client-name`: Human-readable company name for report headers and task titles.

---

## Deliverables & Artifacts

- **Public Presentation URL:** `https://fastup.by/tz/<slug>/`
- **Local Interactive HTML:** `<FASTUP_CLIENTS_DIR>/<client>/index.html`
- **Clean Markdown Audit (for Commercial Proposals):** `<FASTUP_CLIENTS_DIR>/<client>/audit.md`
- **Raw Crawler Snapshot:** `<FASTUP_CLIENTS_DIR>/<client>/crawl.json`
- **CRM Task:** Exactly 1 open task created for Evgeniy (`status=todo`, `notify=false`).
- **Telegram Topic 581 Notification:** Interactive task card with buttons `[✅ Done]`, `[❌ Close]`, `[🔗 Open in CRM]`.

---

## Sales Manager Task Card Standard

**Strictly forbidden: developer jargon, wall-of-text explanations, or complex technical treatises.** The sales manager reads this card on a mobile screen between client calls.

The audit summary card in CRM and Telegram **must strictly conform to a compact format (up to 5 lines)**:
1. **Core Business Pain (exactly 1 sentence):** The plain-language commercial bottleneck costing the client revenue (e.g., broken search snippets, critical mobile rendering lag, unindexed product catalog).
2. **Pre-Priced Solution Packages (formatted as "от N BYN"):**
   - *SEO & Snippet Polish (от 450 BYN, 2 business days):* High-converting snippet in Google/Yandex search and maps.
   - *Yandex.Direct Paid Traffic (от 700 BYN):* Inbound commercial leads from high-intent search within one week.
   - *Complete Growth Bundle (SEO + Direct): от 1 100 BYN.*
3. **Direct Presentation Link:** `https://fastup.by/tz/<slug>/` (for instant delivery into WhatsApp/Telegram during sales calls).
