---
name: fastup-ads
description: >-
  Yandex.Direct advertising operations for FastUp and clients: campaign status,
  bidding, linting, negative keywords, search query reports, Wordstat semantics,
  and weekly performance reviews. Use whenever inspecting or managing Direct campaigns.
---

# FastUp Ads — Yandex.Direct Paid Traffic Management

Operational skill for managing paid search advertising across FastUp internal campaigns and client accounts.
All workflows are strictly regulated by `playbook/direct-campaign-launch.md` and `ads/README.md`.

---

## 1. Skill Scripts (`./scripts/`)

| Script | Purpose | Execution Example |
|---|---|---|
| `direct_status.py` | Rapid campaign status snapshot: balance, bids, pacing, active status | `python .claude/skills/fastup-ads/scripts/direct_status.py` |
| `ads_snapshot.py` | Multi-source snapshot (Direct + Metrika + Webmaster + Wordstat) saved to JSON | `python .claude/skills/fastup-ads/scripts/ads_snapshot.py --days 7` |
| `direct_lint.py` | Pre-launch campaign linter: bid checks, budget caps, negative keywords, cross-negation | `python .claude/skills/fastup-ads/scripts/direct_lint.py <campaign_id>` |
| `direct_apply.py` | Apply negative keywords and phrases from prepared JSON to Direct campaigns | `python .claude/skills/fastup-ads/scripts/direct_apply.py <file>.json [--apply]` |
| `direct_report.py` | Search queries and actual keyword match performance report | `python .claude/skills/fastup-ads/scripts/direct_report.py` |
| `direct_semantics.py` | Semantic core collection from Yandex Wordstat across seed phrases | `python .claude/skills/fastup-ads/scripts/direct_semantics.py` |
| `direct_create_campaign.py` | Assemble and upload a new Direct campaign structure from JSON specifications | `python .claude/skills/fastup-ads/scripts/direct_create_campaign.py <file>.json` |
| `market_dynamics.py` | Track niche commercial demand trends from historical Wordstat data | `python .claude/skills/fastup-ads/scripts/market_dynamics.py` |
| `market_chart.py` | Render interactive HTML trend charts from demand dynamics data | `python .claude/skills/fastup-ads/scripts/market_chart.py` |

> ℹ️ *All scripts are forward-compatible and executable via root proxies: `python scripts/<script_name>.py`.*

---

## 2. Mandatory Operational Directives

1. **Pre-Flight Linter Requirement:**
   Always run `direct_lint.py` before starting or unpausing any campaign. No campaign may go live until the linter passes with zero warnings.
2. **Safe Mutation Hygiene (Dry-Run by Default):**
   `direct_apply.py` runs in `--dry-run` mode by default, logging exact prospective diffs. Mutations are applied to production only with the explicit `--apply` flag and founder approval.
3. **Weekly Cadence Review:**
   Generate weekly multi-source snapshots with `ads_snapshot.py --days 7` and deliver them to the `ads-analyst` subagent. Consolidated analytical reports are archived in `ads/reports/`.
