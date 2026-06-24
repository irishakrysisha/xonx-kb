# Session log — Knowledge Base prototype

Session dates: 2026-05-29 (build) · 2026-05-31 (logged)
Owner: Iryna Oliinyk (iryna.oliinyk@x-on-x.com)
Working dir: `/Users/user/Claude/knowledge_base/`

---

## 1. Request

Design and build a **prototype Knowledge Base** for X-ON-X, built in Google Sheets
working together with Drive. Requirements stated:

- Complex, fully automated architecture.
- Used by three actor types: **human users**, **human contributors**, and **AI agents**
  (agents are both users AND contributors).
- Three levels of database: **precedents and templates** (decide if same or different
  levels), **researches**, **providers**.

## 2. Decisions made (Q&A)

| # | Question | Decision |
|---|----------|----------|
| 1 | Domain | **Legal practice X-ON-X**. Precedents = past matters/deals; Templates = documents; Researches = legal/market memos; Providers = external counsel/vendors/contractors. |
| 2 | Precedents vs Templates — same level? | **Different entity types, same level.** Precedent = an *event/instance* (closed matter); Template = a *reusable artifact*. Kept as separate tables. → 4 tables / 3 levels. |
| 3 | Sheets vs Drive split | **Hybrid + extract**: Sheets = index + text Summary (search + AI read this); Drive = the actual files. |
| 4 | Contribution / quality control | **Staging Inbox tab**: drafts land in Inbox, reviewed, then promoted into the published table. |
| 5 | Relationship model | **Peer-to-peer links** (rejected central-node model). Each record has a `Related` column = list of typed IDs; kept bidirectional by the API. |
| 6 | Access layer for agents + automation | **Python KB-API module** (gspread + Drive API on the cached OAuth token). One contract for humans and agents. |
| 7 | Prototype scope (first pass) | **Full thin slice**: all 4 tables + Inbox + taxonomy + Drive folders + KB-API + 2-3 seed records each. |
| 8 | Spec format | Per standing preference: **no markdown spec doc** — agreed design via Q&A, built straight in Sheets. |

## 3. Architecture delivered

**Hybrid Sheets + Drive.** Sheets holds the index/metadata + a text `Summary`
(what search and AI agents read); Drive holds the files.

- **4 tables / 3 levels**
  - L1 know-how: **Precedents** `PRE-`, **Templates** `TPL-`
  - L2 knowledge: **Researches** `RES-`
  - L3 resources: **Providers** `PRV-`
- **Peer links**: `Related` column = list of typed IDs (`PRE-0001, RES-0002`), kept bidirectional.
- **Inbox intake**: drafts (Review_status=pending) → review → `promote()` assigns real ID,
  moves any attached Drive file from `_Inbox/` into the section folder.
- **`_Taxonomy` tab** = controlled vocabulary → dropdown validation + API-level validation.
- **`Home` tab** = in-sheet documentation.
- **Governance enforced in `kb_api.py` (not the sheet)**: Summary mandatory, dropdown
  fields validated vs taxonomy, IDs generated centrally, links written on both sides,
  `Updated_at` stamped.

## 4. Stakeholders & how they use it

**Internal (X-ON-X):**

| Stakeholder | Role | Uses |
|---|---|---|
| Lawyer-users | consumers | `search()` / `get()` before doing work |
| Contributors (assistants, junior) | fillers | `propose()` → Inbox |
| Reviewers (senior) | quality control | review Inbox, `promote()` / `reject()` |
| AI agents (drafting / research bots) | consumers + fillers | same API: read Summary, propose drafts, link records |
| Admin (Iryna) | system owner | taxonomy, structure, rebuild |

**External (outside the firm):**

| Stakeholder | Relation to KB | Uses |
|---|---|---|
| Providers / local counsel (e.g. Mueller & Partner) | records in Providers table | appear in precedents; entered by internal staff, do not edit |
| Clients | indirect | beneficiaries (faster/better documents); no direct access — confidentiality |
| External AI agents / integrations | scoped `kb_api` access | may read / `propose()` only — never write to published tables directly |

**Trust boundary:** external actors never write to published tables directly — only
`propose()` → Inbox → internal review. That is the line between internal and external.

## 5. Files

| File | Role |
|------|------|
| `kb_client.py` | shared auth (gspread + Drive v3) on `~/.claude-sheets/token.json` |
| `kb_schema.py` | single source of truth: tables, columns, taxonomy, ID rules |
| `build_kb.py` | one-shot builder: Drive tree + spreadsheet + styling + seed |
| `kb_api.py` | runtime contract: search/get/propose/promote/reject/link/update |
| `kb_demo.py` | end-to-end agent demo |
| `kb_config.json` | written by build: spreadsheet id + Drive folder ids |
| `README.md` | usage doc |
| `SESSION_LOG.md` | this file |

## 6. Live artifacts

- Spreadsheet: https://docs.google.com/spreadsheets/d/1s_QPNG_XOG6EgnLLdFpRblqG5S2-vr_Uhx3oo5gU3jg
- Drive root: https://drive.google.com/drive/folders/1z_6nOQIn3Kv9oSDxpTY2_nPIrwxpJuu2
- Folder ids: see `kb_config.json`.

## 7. Verification (run 2026-05-29)

- **End-to-end demo** (`kb_demo.py`): agent search → `propose()`→Inbox (INB-0001) →
  `promote()` (created TPL-0003, links made bidirectional) → `link()` to PRV-0001 →
  `get()` with resolved related → back-link confirmed on PRE-0001. All passed.
- **Negative tests** (governance guards): empty Summary rejected, off-vocabulary
  Practice rejected, unknown ID prefix rejected. All passed.

Note: the demo wrote real data into the live sheet — **TPL-0003** and its links exist
as an example. Keep as a sample or remove via `update`/manually.

## 8. Possible next steps

- Real file uploads to Drive on `propose()` (currently links to folders/URLs).
- Per-table Inbox views / filter-views by status & practice.
- More seed data; scoped external-agent access path.
- Decide whether to keep or clean the TPL-0003 demo record.

---

## Session 2026-06-02 — rebuild to agreed schema + Сортувальник

Driven by the Notion design (Knowledge Base Project page), which evolved past the
first prototype. Two things done:

**1. Rebuilt the spreadsheet to the agreed schema** (`build_kb.py` re-run → NEW sheet).
- Tabs/columns are now **Ukrainian**, matching the agreed properties.
  - Прецеденти / Шаблони / Рісьорчі / Провайдери (same 4 types, UA field names).
  - Категорія = **1.1–1.6** (тип відносин), not Practice; Юрисдикція = UA/DE/US-DE/UK/EU/Multi;
    Оцінка = Recommended/Okay/Avoid; checkboxes for «...локалом»/Партнер.
- **Службові поля для AI** added on every table: `Опис + ключові слова` (=Summary),
  `Статус` (active/pending-PII/needs-review — AI sees only `active`), `Embedding`
  (hidden col, empty for now), `Звʼязки`, Хто створив/Створено/Оновлено.
- Gotcha fixed: BOOLEAN checkbox validation fills FALSE on every row in range →
  scoped checkbox validation to a 50-row buffer; cleared the junk tail.
- `kb_api.py` re-pointed to the new Ukrainian column names (constants in `kb_schema`).
- Live sheet: **https://docs.google.com/spreadsheets/d/1JSU6uqynwWKkxaIEqH2RNZiU9PDGN8FgSR_54b64Xqw**
  (old sheet `1s_QPN…` left intact as backup; can be deleted.)

**2. Built the Сортувальник** (`kb_sortuvalnyk.py`).
- Takes a raw dropped artifact → classifies type / category / jurisdiction, writes
  a Summary, scores confidence → `kb.propose()` into Inbox.
- Two modes: Anthropic Claude (if `ANTHROPIC_API_KEY`) + deterministic marker-based
  fallback (runs with no key). Marker matching is scored (best match, not first).
- Verified on 4 samples (translator→Перекладач, labour Q→1.4, template→Шаблони,
  investment→1.3/US-DE). Demo Inbox rows were cleared afterwards.

## Session 2026-06-03 — search ranking + PII flow

- **`kb_search.py`**: relevance ranking. TF-IDF cosine (no key, works now) + vector
  hook (Voyage/OpenAI) over the `Embedding` column when a provider key is set.
  `kb_api.search()` now returns ranked hits with `_score` + `_match` (lexical|vector),
  not substring. Verified: "warranty cap"→TPL-0001/RES-0001/PRE-0001, "jurisdiction
  clause"→PRE-0002/RES-0002, "нотаріус Київ"→PRV-0002.
- **`kb_api.embed_all()`**: fills the Embedding column when a provider exists; no-op
  (returns 0) without a key — confirmed.
- **Two-speed PII flow**: `promote()` puts Прецеденти as `pending-PII` (AI hidden)
  unless `pii_ok=True`; `clear_pii(id)` flips pending-PII→active. Verified end-to-end
  (PRE-0003 test row promoted→pending-PII→clear_pii→active, then removed). Seed data
  intact (2 rows/table), Inbox clean.

Still TODO: plug a real embeddings provider (Voyage/OpenAI key) then run `embed_all()`
for cross-lingual semantic search; real Drive file uploads on propose(); decide on
old sheet `1s_QPN…` deletion.

---

## Session 2026-06-17/24 — taxonomy split, fixes, AppSheet "library" front-end

### Shipped (code, pushed to repo)
- **Опис split** → `Опис` (short summary) + `Ключові слова` (tags). Classifier, search,
  Home `_Index` (hidden keyword col F), polish (providers show Опис, hide keywords),
  migration all updated. Verified keyword search works (apostille→Notarity etc).
- **File foldering on promote** (`relocate_file`): renames to `{ID} — {Назва}.ext`, moves
  into `Документи/{Категорія}/{Тип документа}/{Право}/[Precedents|Templates]` and
  `Рісьорчі/{Сфера}/{Право}`. PRE-0001 filed.
- **CRITICAL migrate bug fixed**: `migrate_taxonomy` read display text → flattened
  HYPERLINK cells (Файл/Папка) to plain «Файл ↗», losing URLs. Now reads FORMULA +
  writes USER_ENTERED. Recovered PRE-0001 Файл + 4 provider «Папка» links.
- **Checkboxes**: write real booleans (Партнер etc. were text "TRUE" → broken). polish
  normalizes + promote writes bools.
- **Providers**: added must-have «Хто приніс контакт»; Партнер=TRUE (all 4 are partners);
  contact person = initials **IO**; soft initials dropdown (IO/MM/VitD/VasD/VK/OK) on
  Поінт/Хто приніс/Власник; Magrat Тип послуги still «Сервіс-провайдер» (TODO: maybe Аудитор).
- **Taxonomy**: added «Disclosure letter» (Тип документа). 3 corrupted seed rows
  (TPL-0001/RES-0001/RES-0002) deleted via new `kb_api.delete()`.
- Catalog now: **PRE-0001** (pending-PII) + 4 providers; Шаблони/Рісьорчі empty.

### AppSheet app "library" front-end (built live via Kapture browser automation)
- App: **X-ON-X Knowledge Base**, appId `21e79118-ea65-4542-9daf-83e9c9d3ad8b`,
  run link `https://www.appsheet.com/start/21e79118-ea65-4542-9daf-83e9c9d3ad8b`.
- Done: added 4 shelf tables, **removed Home table** + dangling Home view (fixed
  "app did not load"), created **4 deck (card) views** in primary nav
  (Прецеденти/Провайдери/Рісьорчі/Шаблони), brand **primary colour = lime `#5A7A00`**.
  Saved & syncing; preview works (bottom nav of 4 sections, search, OPEN URL file links).
- Guide saved at `APPSHEET_SETUP.md`.

### OPEN / next session
1. **Sharing blocked**: app is **prototype → only creator can run**; colleague
   **misha.plachkov@x-on-x.com** gets "no access". FIX = **Deploy** (Manage → Deploy;
   Workspace Core licence included) then add Misha as App User. Team to test: VK
   (Viktoriia Kotliar), OK (Oleg Kotliar), Misha. (Was about to do this.)
2. **"More colours"** requested: do it via **Format Rules** (e.g. Оцінка
   Recommended=green/Okay=amber/Avoid=red; categories/spheres per colour). Remote
   browser automation of format rules proved UNRELIABLE (controls below fold, multiselect
   misfires, kapture ids churn) — best done in live editor or guided.
3. Optional: app logo, slice `[Статус]="active"` (hide pending-PII PRE-0001), emoji in
   view names for colourful nav.
4. PRE-0001 still `pending-PII` (hidden from AI until `clear_pii`).
5. Pre-existing TODOs: embeddings key + `embed_all()`; real Drive uploads on propose();
   delete old sheet `1s_QPN…`; `build_kb.py` seeds are stale (not used).

### Kapture note
Browser tab was connected (tabId 1112533621) on appsheet.com; toward the end element
queries started returning empty (editor re-render/stale) — refresh (Cmd+R) before
resuming automation.
