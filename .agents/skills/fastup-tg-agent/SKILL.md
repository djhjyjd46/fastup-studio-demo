---
name: fastup-tg-agent
description: >-
  Telegram bot and AI agent operations for FastUp: Alesya (@FastupAgent_bot) — the studio's sole
  Telegram agent (operator support, inbound lead notifications 549/616, service alerts 626,
  knowledge base loop 606, KB files in bots/kb/); cold dialer (Telegram Mini App on Laravel,
  piece-rate payouts 0.10/0.05/5.00 BYN, 5 antifraud flags). Trigger whenever sending messages
  to topics, adjusting Alesya runtime behavior, updating KB answers, deploying dialer updates,
  managing operator lead queues, or inspecting hosting logs on tools.fastup.by.
---

# FastUp Telegram Agent & Bot Operations (fastup-tg-agent)

Primary architecture is detailed in `bots/README.md`. Repository documentation holds factual configuration (IDs, endpoints, tokens); this skill governs execution procedures.

| Objective | Primary Reference |
|---|---|
| Alesya bot runtime, forum topics, topic 606 loop, voice limit | `bots/fastup-agent-alesya.md` |
| Service topic 626 (antifraud, WP/CRM desync alerts, runtime failures) | `bots/fastup-agent-alesya.md` |
| Alesya knowledge base inspection and updates | `bots/knowledge-base.md`, `bots/kb/` |
| Dialer Mini App: queue routing, dispositions, antifraud heuristics, deployment | `bots/dialer-miniapp.md` |
| Tools and Agent server on hosting (`tools.fastup.by`) | `bots/fastup-agent-alesya.md`, `decisions/2026-09-15-tools-server-on-hosting-vps-fallback.md` |
| Legacy decommissioned bots (CRM-bot, HR-bot, Wiki-bot, OpenClaw VPS) | `bots/archive/`, `bots/README.md` |

---

## Five Critical Rules Learned from Production Incidents

1. **Mutate CRM Data Strictly via Laravel:**
   Never perform raw SQL queries or manual inserts into `leads`, `calls`, or `lead_events`. Bypassing Laravel skips `LeadObserver`, corrupting event synchronization to the CRM dashboard.
2. **Production Laravel Environment is Hosted on hb.by (Not CI):**
   GitHub Actions workflow in the `crm` repository targets legacy infrastructure. Deploy production files to hb.by via ISPmanager Panel API.
3. **Secrets Reside Exclusively in `.env`:**
   Hardcoding bot tokens or API credentials in repo commits triggers security invalidation and requires credential reissuance.
4. **Never Iterate `message_id` by Sequential Range:**
   In a Telegram forum supergroup, message IDs are sequentially shared across ALL topics (581 Tasks, 549 Hot Leads, 616 Callbacks, etc.). Blind batch loops (`editMessageReplyMarkup` / `deleteMessage`) destroy operational buttons across unrelated threads. Modify or delete messages **strictly using exact recorded IDs** saved in CRM (`_tm_tg_msgs`, `_crm_hot_msg_id`).
5. **48-Hour Deletion Window Ceiling:**
   Telegram Bot API returns `400 Bad Request: message can't be deleted` for messages older than 48 hours, even for bot administrators. Never use dummy text replacements ("Deleted" / `.`) to bypass this. If a message is older than 48h, escalate to a human admin to remove manually.

---

## Sending Messages to Topics & Managing Tasks

```bash
python scripts/tg_agent.py topics                         # List configured forum topics and aliases
python scripts/tg_agent.py send "<b>Report</b>" --topic digest
python scripts/tg_agent.py send "<b>Silent Log</b>" --topic archive  # Topic 547 is always silent (disable_notification=true)
python scripts/tg_agent.py send "Muted Text" --topic tasks --silent
python scripts/tg_agent.py delete <message_id>
python scripts/tg_agent.py create-topic "New Topic"        # Requires "Manage Topics" admin permission
python scripts/complete_task.py <task_id> [--note "text"]  # Resolves task in CRM and quietly archives to topic 547
```

- Authentication: `FASTUP_AGENT_BOT_TOKEN` in `.env`.
- Message format: Telegram HTML formatting, up to 4096 characters per message.
- Save returned `message_id`: Bot API does not provide chat history retrieval; edits require the exact message ID.
- **Silent Archive Directive:** Topic `547` ("Task Archive") strictly requires silent delivery (`disable_notification: true`) to prevent notification fatigue.

---

## Adjusting Alesya Agent Behavior

Alesya operates on shared hosting (`tools.fastup.by`); legacy VPS is powered off.
Editing `agent/ingest/src/tgrouter.ts` does NOT affect production.

1. Source files: `G:\OSPanel\domains\admin.microapps\agent\crm-mcp\src\bot\telegram.ts` (system prompt in `handleSupport`, group addressing logic in `isAddressedToBot`, markdown formatting in `mdToTelegramHtml`). Agent loop and tools: `src/agent/runtime.ts`.
2. Verify against support guidelines in Alesya documentation.
3. Run TypeScript check: `npx tsc -p .` in `agent/crm-mcp` (must pass with zero errors).
4. Deploy: `python scripts/deploy_tools_server.py upload`, then `restart`. Commit to `admin-microapps`.
5. Health verification: `python scripts/bot_cutover.py status` (verify hosting endpoint and empty `last_error_message`). Avoid excessive polling to prevent hosting WAF rate limits.

---

## Updating Alesya Knowledge Base

Two mechanisms (both write directly to `~/secrets/playbook.json` and rebuild the live vector index on hosting):
- Reply directly to a "Need Answer" card in forum topic `606`.
- Use tools `kb_list` / `kb_get` / `kb_add` / `kb_update` / `kb_delete` via `python scripts/tools.py` (`fastup-tools` skill) — always obtain founder confirmation before committing content.

Never use `deploy_tools_server.py state` to update the KB — it overwrites active chat modes and the 606 queue with stale local state.

---

## Service Topic 626 & Operational Noise Isolation

Forum topic `626` ("⚙️ Service Notifications") in supergroup `-1003819058234` isolates system-level noise:
- **Dialer Antifraud:** Daily audit at 21:00 (`php artisan dialer:audit-antifraud --notify`) and alerts across 5 benchmark flags.
- **Lead Synchronization Drift:** WP↔CRM reconciliation (`reconcile-sync.php`), `SyncLeadToWordPress` exceptions, and `health:check-sync` warnings. Never route sync errors to manager topic 616.
- **Bot Exceptions & Fallbacks:** `uncaughtException` and `unhandledRejection` telemetry from Alesya router.

### Hard Routing Boundaries:
- **Zero Tasks in Topic 626:** Task cards (`🎯 Задача #...` or `🆕 Новая задача`) must NEVER be routed to 626. Their exclusive destination is topic 581 ("Open Tasks").
- **Zero `forwardMessage` Calls for Debugging:** Never forward messages into company forum topics for "inspection" or debugging. All task telemetry must be queried deterministically via CRM API or SQL queries (`scripts/tools.py`).
- **Purity of Archive Topic 547:** Only human-validated completed tasks belong in the archive. Creating fake technical micro-tasks marked `done` for vanity reporting is strictly forbidden.

CLI Dispatch Example:
```bash
python scripts/tg_agent.py send "Service Alert Message" --topic service
```

---

## Dialer Mini App Architecture & Antifraud

- **Interface & Proxy:** Entry point `admin.microapps/microapps-v2/includes/rest-dialer.php`; templates in `includes/dialer/`, assets in `assets/dialer/`.
- **Backend & Antifraud Rules:** `crm/app/Http/Controllers/DialerController.php` and `crm/app/Services/DialerAntifraudService.php` (`config/dialer.php`).
- **Piece-Rate Compensation & Antifraud Safeguards:**
  - Payout scale: 0.10 BYN for effective call / scheduled callback / detailed objection (≥15s); 0.05 BYN for chip rejection; 0.00 BYN for no-answer (auto-recycled after 10 calls); 5.00 BYN for confirmed qualified lead ("В работе"). Daily cap: 100 paid actions (maximum risk ceiling 10 BYN/day).
  - 5 Antifraud Benchmarks: Calls <15s >30%, dials without pickup >40%, qualification rate >8%, comment length <40 chars >40%, call pace >70 dials/hour.
  - Fraud Detection: Daily payouts freeze immediately upon anomaly detection, dispatching an alert to topic 626.
