---
name: fastup-tools
description: >-
  Live CRM data and Alesya knowledge base tools executed via the studio tools server on hosting (tools.fastup.by) —
  leads, cards, tasks, projects, deals, payments, company requisites, document sequence register, sales funnel,
  cold dialer calls, direct SQL queries against CRM database, and sales playbook search. Executed via
  `python scripts/tools.py` using personal FASTUP_TOOLS_TOKEN in .env. Use for live CRM inspection
  ("check funnel", "find lead", "tasks for Sveta", "record deal payment", "weekly call volume") strictly
  AFTER consulting repository memory.
---

# FastUp Tools: CRM & Knowledge Base Operations

The server hosted on hb.by (`tools.fastup.by`) maintains authenticated connections to the CRM database.
Local machines require only the environment variable: `FASTUP_TOOLS_TOKEN` in `.env`.

---

## 1. CLI Commands

```bash
python scripts/tools.py list                              # Inspect available tools permitted by current token
python scripts/tools.py schema crm_list_tasks             # Inspect tool arguments and type schema
python scripts/tools.py crm_search_leads q=Romashka
python scripts/tools.py crm_get_lead id=911
python scripts/tools.py crm_sql_query --json args.json    # Pass structured or complex parameters via JSON
```

Key-value arguments (`key=value`): integers, booleans (`true`/`false`), and JSON arrays are parsed automatically.
Always inspect tool `schema` before first invocation rather than guessing arguments by trial and error.

---

## 2. Tool Mapping Matrix

| Objective | Recommended Tool Sequence |
|---|---|
| Search lead, view client card & activity feed | `crm_search_leads` → `crm_get_lead`, `crm_get_lead_activity` |
| Funnel health, callbacks, bottleneck analysis | `crm_funnel_health`, `crm_tm_reports` |
| Dialer performance, manager timeline, calls | `crm_leadgen_report`, `crm_leadgen_manager_timeline`, `crm_list_calls` |
| Tasks and client projects | `crm_list_tasks`, `crm_list_projects`, `crm_get_project_feed` |
| Commercial deals and payment status | `crm_list_deals`, `crm_set_deal_payment` |
| Company entity requisites, document numbers | `crm_search_requisites`, `crm_get_requisite`, `crm_list_doc_numbers` |
| Custom database analytics | `crm_sql_schema` → `crm_sql_query` (strictly read-only `SELECT`, enforced limit) |
| Query Alesya operator responses | `kb_search` |
| Train Alesya: view, add, update, delete KB item | `kb_list` → `kb_get` → `kb_add` / `kb_update` / `kb_delete` |
| Turnkey contractor acceptance act | `crm_search_requisites` → `act_create` (`dry_run=true`) → review → `act_create` (`pdf=true`) |
| Locate or read document on company Google Drive | `doc_find` → `doc_read` |
| Generate custom document from sample | `doc_find` → `doc_read` → `doc_render` (following text confirmation) |

---

## 3. Operational Rules & Boundaries

- **Mutations Require Explicit Human Confirmation:**
  Creating or updating tasks, projects, deals, payments, or company entity requisites is permitted ONLY after explicit user confirmation. Read operations may proceed autonomously.
- **Alesya Training Protocol:**
  Before invoking `kb_add`, execute `kb_list` with relevant keywords to update an existing answer rather than spawning duplicate entries. Answers must be crafted concisely, answering the operator question directly without conversational fluff.
- **Token Scope Restrictions:**
  If a tool is not listed in `list`, the active token lacks necessary permissions. Inform the user directly rather than seeking workarounds.
- **Lead Context Check Prior to Task Creation:**
  `crm_get_lead` provides the complete `activity` feed (including initial lead intake notes) and active `open_tasks`. Never create tasks without validating existing client activity.
- **Zero Client PII in Repository:**
  Never export raw client personal data into repository git history. Only sanitized analytical insights and patterns may be documented locally.
