---
name: fastup-doc-ops
description: >-
  FastUp.by primary accounting documents: acceptance acts, client contracts, invoices, and payment receipts.
  Manages Google Docs and Google Drive via scripts/gdocs.py (list, create, copy, replace, upload, export-pdf),
  vector/scanned PDF normalization and stitching (PyMuPDF/fitz), strict A4 geometry compliance (595.3 x 841.9 pt,
  zero orphan lines), unbroken signature tables, pre-printed entity requisites, and anti-employment stop-words
  filtering under Art. 33 of the Tax Code of the Republic of Belarus (eliminating labor terms like salary, bonus,
  or daily rates for NPD/IP contractors). Use when creating, modifying, exporting, or stitching company legal docs.
---

# FastUp.by — Primary Document Operations Pipeline (fastup-doc-ops)

Engineering standards and automation for FastUp.by legal documentation. Eliminates manual browser workflows, physical printing defects, and tax misclassification risks when contracting self-employed specialists (Art. 33 Tax Code of Belarus).

---

## 0.0. Turnkey Client Deal Closing — `scripts/close_client_deal.py`

Execute full deal completion via a single command (Non-agentic first):
```bash
python scripts/close_client_deal.py --client "<CLIENT_NAME>" --contract-no <NUMBER> --amount <AMOUNT> --service "<SERVICE>"
```
The script deterministically:
1. Validates client entity requisites and payment status in CRM ledger.
2. Creates the CRM project if absent and records closed milestones (`status=done`).
3. Generates the final Acceptance Act in Google Docs and compiles a vector PDF via `doc_render`.
4. Creates exactly 1 open task for the account manager (`status=todo`): "Send Act to client for signature" with direct links to PDF and Doc.
5. Dispatches an interactive card to Telegram topic **581 ("Open Tasks")**.

Use `--dry-run` to preview validation and parameters without writing to CRM or generating files.

---

## 0.1. Contractor Payout Act (NPD / IP) — `scripts/run_contractor_payout.py`

Calculate compensation and issue an acceptance act for self-employed contractors (profiles: `leadgen`, `pm`, `dev`):
```bash
# 1. Preview calculation (validates calls, rates, and Art. 33 stop-words)
python scripts/run_contractor_payout.py --contractor "<SURNAME>" --profile leadgen --period-from 2026-09-01 --period-to 2026-09-15

# 2. Issue actual act, PDF, and accounting entries (after human confirmation)
python scripts/run_contractor_payout.py --contractor "<SURNAME>" --profile leadgen --period-from 2026-09-01 --period-to 2026-09-15 --confirm
```
Automated actions:
- Pulls live validated call counts from `crm_leadgen_report`.
- Generates service specifications strictly free of labor terms (zero "salary" or "bonuses").
- Invokes `act_create` on the `tools.fastup.by` server.
- Stores the compiled PDF directly into `📁 Распечатать и подписать` on Google Drive.
- Posts notification with link to internal chat.

---

## 0.2. Client Contract Generation: Example Cloning Only

Primary reference template: "Пример договора на разработку сайта и настройки рекламы" in "Договоры/Шаблоны" (`1dF7GNQachPk32GYxV3AKaOjpii1ByVQqYDGM-P_hKo8`). This is a real historical contract with SPLAVAR LLC: replace real historical entity values directly rather than building documents from scratch or using arbitrary placeholders.

1. `gdocs.py read <TEMPLATE_ID>` — extract all specific fields relating to the previous party (legal name, director, authority basis, contract number, date, scope, milestones, fees, banking requisites).
2. Fetch new client data from CRM (`crm_search_requisites` → `crm_get_requisite`) or founder prompt. Assign sequential contract number according to `integrations/crm.md` register (`crm_list_doc_numbers`).
3. `gdocs.py copy --template-id <TEMPLATE_ID> --title "Договор_<NUMBER>_<CLIENT>_ЧЕРНОВИК" --folder "Договоры/Клиенты"`.
4. `gdocs.py replace <NEW_ID> --pairs "ООО “СПЛАВАР”=ООО «Client»" ...` — execute batch literal replacements. Quote pairs containing spaces.
5. Verify zero lingering references to prior parties ("СПЛАВАР", previous director surname, prior contract numbers). Present draft checklist to founder (requisites, amounts, milestones, annexes). PDF export is permitted only after explicit human approval.

Other ad-hoc documents (letters, formal notices, custom proposals): use `doc_render` into folder "Черновики и тесты" with CRM requisites.

---

## 1. Google Docs & Drive CLI Tool: `scripts/gdocs.py`

All document operations are executed via `scripts/gdocs.py` through the Google Apps Script corporate gateway using a service identity. No local Google login is needed.
Requires `.env` secrets: `GDOCS_GAS_URL` and `GDOCS_GAS_SECRET`.

### 1.1. Core CLI Commands

| Operation | CLI Command | Notes |
|---|---|---|
| Search documents | `python scripts/gdocs.py list --query "Shepelenko"` | Case-insensitive title search on Drive |
| List folder | `python scripts/gdocs.py list --folder "Акты"` | Lists files in target folder |
| Read text | `python scripts/gdocs.py read <FILE_ID>` | Dumps full plaintext from Google Doc |
| Clone template | `python scripts/gdocs.py copy --template-id <ID> --title "Акт №..." --folder "Акты"` | Clones template preserving layout |
| Replace pairs | `python scripts/gdocs.py replace <FILE_ID> --pairs client="ООО Client" sum="500 BYN"` | Exact string replacements |
| Export PDF | `python scripts/gdocs.py export-pdf <FILE_ID> --name "Акт_№1.pdf" --folder "Акты"` | Pure vector PDF compiled to Drive |
| Upload file | `python scripts/gdocs.py upload <PATH> --name "...pdf" --folder-id <ID>` | Uploads signed scans or stitched PDFs |
| Move file | `python scripts/gdocs.py move <FILE_ID> --to <TARGET_FOLDER_ID>` | Organizes files into destination directory |
| Trash files | `python scripts/gdocs.py trash <FILE_ID_1> <FILE_ID_2>` | Safely trashes duplicate drafts |
| Organization | `python scripts/gdocs.py organize` / `cleanup` | Enforces folder hierarchy and removes clutter |

### 1.2. Key Google Drive Folder IDs

- **Contractor Acts:** `11bXxnljHCjVC8ae373v8iTbtTqwvPeDG` (`Акты/Подрядчики`)
- **Print Folder for Egor:** `1CPdpoix1DaMxZm9TUc4UI2DQI7rnMIsT` (`📁 Распечатать и подписать`)
- **NPD Receipts:** `1lSIoIOUPgJ-E1lWfHLS_o1P2Hy-Kt-lp` (`Чек-ордеры НПД`)
- **Documents Root:** `1YIvypoZFWwxmpQby2LOOXhI4LoeHFUDl`

---

## 2. Strict A4 Geometry & Print Quality Standards

Every document designated for physical signing or delivery must conform to `accounting/architecture/act-template-standard.md`:

1. **Strict A4 Dimensions (595.3 x 841.9 pt):**
   - Simple acts and standard agreements: **strictly 1 page**.
   - Acts with extensive milestone tables or itemized breakdowns: **strictly 2 pages**.
   - **Zero orphan lines:** It is strictly unacceptable for 2-3 signature lines or banking details to spill over onto an otherwise blank page 3.
   - Page margins: Top/Bottom 1.5–2.0 cm, Left 2.0 cm, Right 1.5 cm.
   - Line spacing: 1.0–1.15, block spacing: 6–8 pt.

2. **No Running Headers/Footers:**
   Per architectural decision: act number, date, and contract reference reside solely in the header block of page 1.

3. **Pre-Printed Requisites, Handwritten Signatures:**
   - Full legal entity names, UNP (УНП), IBAN, bank name, and BIC must be fully typed into the requisites table.
   - Signature line must remain an empty underline `______________________________`. Do NOT pre-print `/ Surname I.O. /` (causes spacing collision on long names).
   - Sole proprietorship (ИП) operates without an official seal: do NOT insert "М.П.".
   - Bold weight applies only to the main document title, section header "РЕКВИЗИТЫ И ПОДПИСИ СТОРОН", and final totals.

4. **Non-Breaking Signature Block:**
   The party requisites table must be configured with `keep_with_next` behavior so signatures never separate from company details across page breaks.

---

## 3. Anti-Labor Terminology Filter (Art. 33 Tax Code of Belarus)

Agreements and acceptance acts with self-employed contractors (NPD / IP) must NEVER contain employment vocabulary that risks reclassification under tax audit:

| Banned Employment Terminology | Required FastUp Service Phrasing |
|---|---|
| «Оклад», «должностной оклад» (Salary) | `Базовое вознаграждение за комплекс услуг по администрированию CRM...` |
| «Премия», «бонус за месяц» (Bonus) | `Дополнительное вознаграждение за успешное сопровождение сделки [Клиент]` |
| «Тарифная ставка», «за смену» (Shift rate) | `Абонентская плата за информационное сопровождение базы клиентов` |
| Day calculations (`500 BYN / 31 * X дней`) | `Вознаграждение за оказание услуг по этапу № [X] согласно смете` |
| «График работы», «часы», «с 9 до 18» (Work schedule) | `Срок сдачи услуг — не позднее [Дата]` |
| «Заработная плата», «аванс» (Wage/Advance) | `Оплата оказанных услуг по Акту сдачи-приёмки` |
| «Штатный сотрудник», «работник» (Employee) | `Исполнитель`, `Подрядчик` |

---

## 4. Multi-Page PDF Stitching (PyMuPDF / fitz)

When compiling composite documents (e.g. Page 1 = digital vector table from Google Docs, Page 2 = signed paper scan):

1. **Never take mobile phone photos of digital vector pages.** Export page 1 directly from Google Docs (`export-pdf`) to preserve crisp vector fonts.
2. **Normalize the scanned second page:**
   - Detect orientation and rotate to portrait (0°).
   - Crop page borders to match standard A4 aspect ratio (`1:1.414`).
   - Resolution: 200–300 DPI, JPEG quality 85–90% to balance file size and visual legibility.
3. **Stitch via PyMuPDF:**
   ```python
   import fitz  # PyMuPDF
   doc_vec = fitz.open("page1_vector.pdf")
   doc_scan = fitz.open("page2_scan.pdf")
   out = fitz.open()
   out.insert_pdf(doc_vec)
   out.insert_pdf(doc_scan)
   out.save("final_act.pdf", garbage=4, deflate=True)
   ```
4. **PII Masking:**
   When storing debug logs or repository examples, mask phone numbers (`+375 (XX) XXX-XX-XX`) and client emails (`info@fastup.by`).

---

## 5. File Verification & Access Controls

1. **Verify File Content, Not File Extension/Name:**
   Direct downloads from `drive.usercontent.google.com/download?id=...` without OAuth headers return an HTML login page (~939 KB) disguised as a PDF. Always download through Google Drive API.
2. **Inspect Identity Inside Document:**
   A filename like `12_Акт_Громыко_85BYN.pdf` is not proof of its inner contents. Always read file bytes to verify the contractor name, contract date, and sum match the ledger.
3. **Company Service Account Ownership:**
   All corporate documents must be created under the company workspace account so shared permissions and lifecycle ownership persist across team members.
4. **Access Rights Check Prior to Link Dispatch:**
   Before sharing Google Drive URLs with clients or external contractors, verify that folder or file permissions are explicitly granted (e.g. `anyone: reader`).
