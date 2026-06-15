# Enterprise Petty Cash, Employee Expense & Reimbursement Solution
## Odoo 19 Community Edition — Fully Containerized, Built From Source

**Document type:** Solution Architecture & Implementation Report
**Target platform:** Odoo 19.0 Community Edition (LGPL v3), Docker, on-premise
**Scope:** Multi-company, multi-branch petty cash / employee expense / reimbursement with dynamic approval workflows, budget control, management & user dashboards, and full reporting
**Date:** June 2026

---

## 1. Executive Summary

This report specifies an enterprise-grade Small Payments Management System built on Odoo 19 Community Edition, delivered entirely inside Docker containers where the Odoo application is **built from the official GitHub source** (`odoo/odoo`, branch `19.0`) rather than pulled as a prebuilt Odoo image from Docker Hub.

The solution combines three layers:

1. **Odoo 19 CE core** — `account`, `hr_expense`, `analytic`, `hr`, multi-company framework.
2. **Free third-party / community modules** — Cybrosys **`base_accounting_kit`** (full accounting kit, v19-compatible), Cybrosys **`dynamic_accounts_report`** (dynamic financial reports, v19-compatible), Odoo Mates **`om_account_accountant` / `om_account_budget`** (accounting menu + budget management for CE), and OCA repositories (**`base_tier_validation`**, **`hr-expense`**, **`mis-builder`**, **`operating-unit`**, **`account-financial-reporting`**, **`web`**).
3. **A single custom module (`small_payment_management` — Small Payments Management)** that delivers, as one coherent installable, everything no off-the-shelf product covers: branch master, expense type/category masters with budget-check flags, petty cash float (imprest) management, budget reservation/utilization, the model-agnostic **dynamic approval engine** (auto-populated chains by company + dimensions + amount, **Request for Information**, **delegation by both admin and the active approver**, **live add/remove of approvers by admin**, SLA escalation, immutable audit), OWL dashboards for management and end users, and a consolidated reporting pack. **Per the consolidation requirement, all custom-developed code ships in this one module `small_payment_management`** — there is no separate add-on suite and no separately-packaged workflow engine. (Trade-off: this forgoes listing the approval engine as an independent paid App Store product; see §7.0.)

Key design decisions (justified in the body):

| Decision | Choice | Rationale |
|---|---|---|
| Deployment | Docker Compose, 2 containers (Odoo built from source + PostgreSQL 16) | Production standard; a single "everything in one container" variant is also documented in §10.6 for environments that mandate it |
| Branch dimension | OCA `operating_unit` if the 19.0 migration is available at install time; otherwise the custom `spm.branch` master (provided) | Operating Units are the de-facto OCA standard for branch-level security/reporting; the custom master guarantees independence from migration timing |
| Workflow engine | Custom approval-matrix engine, design aligned with OCA `base_tier_validation` concepts | Tier validation alone cannot auto-populate ordered, role-resolved approver chains from company/branch/type/category/amount; a matrix engine can, while remaining auditable |
| Budgets | `om_account_budget` (or OCA `mis_builder_budget`) for accounting-level budgets + custom `spm.budget` for operational, line-level pre-commitment control | Accounting budgets measure actuals after posting; petty-cash control needs *pre-approval* budget reservation, which only a custom layer provides |
| Reporting | Dynamic Accounts Report + custom QWeb/XLSX reports + MIS Builder for management packs | Covers statutory, operational and management reporting |

Estimated delivery effort: **10–14 weeks** with a 2–3 person team (1 senior Odoo dev, 1 dev, 1 functional consultant/QA). Roadmap in §13.

---

## 2. Requirements Analysis

### 2.1 Stated requirements → solution mapping

| # | Requirement | How it is met | Section |
|---|---|---|---|
| R1 | Odoo 19 CE, fully inside Docker, no prebuilt cloud Odoo image | Multi-stage Dockerfile starting from a minimal OS base, cloning `odoo/odoo` 19.0 from Git inside the build and running from source | §10 |
| R2 | Third-party accounting modules (Base Accounting Kit, Dynamic Accounting Reports, etc.) | `base_accounting_kit` 19.0, `dynamic_accounts_report` 19.0, `om_account_accountant`, `om_account_budget`, OCA repos — all fetched by an addon-fetch script during image build | §5, §10.4 |
| R3 | Petty cash management (imprest/float, top-ups, disbursements, reconciliation) | Petty cash subsystem of the `small_payment_management` module + petty cash journals from the accounting kit | §6.3 |
| R4 | Employee expense & reimbursement | Core `hr_expense` extended by `small_payment_management` (branch, type, category, workflow, budget hooks) | §6.4 |
| R5 | Dynamic workflow auto-populated by company, branch, expense type, expense category | Approval Matrix engine built into `small_payment_management` that resolves an ordered approver chain at submission time | §7 |
| R6 | Budget check optional per master ("if needed or ticked in masters") | `budget_check_required` boolean on expense type and category masters; enforcement modes: Off / Warn / Block | §8 |
| R7 | Budget utilization tracking | Committed / utilized / available computation with reservation at approval and consumption at posting; utilization report + dashboard widgets | §8 |
| R8 | Management reports & dashboard | OWL management dashboard (spend by company/branch/category, budget vs actual, approval cycle time, top spenders) + report pack | §9, §11 |
| R9 | Individual user dashboard (my requests, my actions) | OWL "My Wallet" dashboard: my requests by state, pending my approval, my floats, my reimbursements | §9.2 |
| R10 | Enterprise standards | Multi-company record rules, branch-level security, full audit trail (chatter + mail.activity), SoD, test coverage, CI-ready repo layout, backup/DR | §12 |
| R11 | Multi-company & multi-branch | Native Odoo multi-company + branch dimension on every transactional model, record rules on both | §4, §12.2 |

### 2.2 Functional scope (detailed)

**Petty cash (imprest system)**
- Branch-level petty cash floats with named custodians, float ceiling, replenishment threshold.
- Top-up requests (custodian → approval chain → accounting posts Bank→Petty Cash journal entry).
- Disbursement vouchers against the float (small payments to staff/vendors), each classified by expense type/category, receipt attachment mandatory above a configurable threshold.
- Periodic float reconciliation (cash count vs book balance, variance posting with approval).
- Auto-replenishment suggestion when float balance < threshold.

**Employee expense & reimbursement**
- Expense capture (mobile-friendly; receipt photo attachment), expense reports grouping multiple expenses.
- Two payment modes: *paid by employee → reimburse* and *paid from petty cash / company card*.
- Reimbursement batch processing → vendor-bill-style journal entries or payment registration against employee partner.
- Cash advance requests with settlement against subsequent expense claims (advance ledger per employee).

**Controls**
- Per-line and per-report policy limits (per category: max amount per claim, per day, per month; receipt-required threshold).
- Duplicate claim detection (same employee + date + amount + category heuristic).
- Budget check at submission and again at final approval (configurable).
- Full audit trail; no deletion of submitted documents (cancel + audit instead).

---

## 3. Solution Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Docker Host (on-prem)                        │
│                                                                      │
│  ┌──────────────────────────────┐   ┌─────────────────────────────┐  │
│  │  odoo19 container            │   │  db container               │  │
│  │  (built from Git source)     │   │  PostgreSQL 16              │  │
│  │                              │   │                             │  │
│  │  /opt/odoo/odoo      ← git   │   │  volume: pg_data            │  │
│  │  /opt/odoo/addons/           │   └─────────────────────────────┘  │
│  │    cybrosys/  (acct kit,     │                                    │
│  │               dyn reports)   │   ┌─────────────────────────────┐  │
│  │    odoomates/ (om_account_*) │   │  nginx (optional, TLS/proxy)│  │
│  │    oca/       (tier valid.,  │   └─────────────────────────────┘  │
│  │       mis_builder, op.unit,  │                                    │
│  │       hr-expense, web, ...)  │   volumes: odoo_filestore,         │
│  │    custom/    (small_payment_management)   │            addons (bind/named)     │
│  └──────────────────────────────┘                                    │
└──────────────────────────────────────────────────────────────────────┘
```

**Application layer composition**

```
                 ┌────────────────────────────────────────┐
                 │   small_payment_management (1 module)  │
                 │   (all custom code; flat layout)       │
                 │                                        │
                 │   • dashboards  (OWL: mgmt, my wallet) │
                 │   • reports     (QWeb/XLSX pack)       │
                 │   • petty_cash │ expense │ budget      │
                 │   • approval engine (matrix, RFI,      │
                 │     delegation, add/remove, escalation)│
                 │   • base masters (branch, type,        │
                 │     category, policies) + security     │
                 ├────────────────────────────────────────┤
                 │ 3rd-party: base_accounting_kit,        │
                 │ dynamic_accounts_report, om_account_*, │
                 │ OCA base_tier_validation, mis_builder, │
                 │ operating_unit, web_responsive         │
                 ├────────────────────────────────────────┤
                 │ Odoo 19 CE core: account, hr_expense,  │
                 │ hr, analytic, mail, base               │
                 └────────────────────────────────────────┘
```

---

## 4. Multi-Company & Multi-Branch Design

### 4.1 Company dimension (native)
- One Odoo database, N legal entities as `res.company` records, each with its own chart of accounts, currency, fiscal positions, sequences and journals.
- Inter-company petty-cash movements (e.g., HQ funds a subsidiary's float) handled via inter-company due-to/due-from accounts and mirrored journal entries (manual in CE; an automation hook is included in `models/petty_cash.py` as an optional cron).
- All `spm.*` models carry `company_id` with `check_company=True` on every relational field, and default from `self.env.company`.

### 4.2 Branch dimension (two interchangeable strategies)

**Strategy A — OCA Operating Unit (preferred when the 19.0 port is published).** The OCA `operating-unit` repo provides `operating.unit` as a sub-company business dimension with its own security rules and is widely used precisely for branch accounting. OCA migrations land per-version; verify the 19.0 branch of `OCA/operating-unit` and `OCA/account-operating-unit` before the build, and pin the commit.

**Strategy B — Custom `spm.branch` master (always shipped; default).** Guarantees the project never blocks on OCA migration timing:

- `spm.branch`: code, name, company_id, address, branch manager (`hr.employee`), analytic account (auto-created per branch under a "Branches" analytic plan), petty cash journal, active flag.
- `res.users.spm_branch_ids` (allowed branches) + `spm_default_branch_id`; record rules restrict transactional documents to allowed branches.
- Every transactional model (`spm.petty.cash.*`, expense extensions, budgets, approval matrices) carries `branch_id`.
- Branch → analytic account mapping means **all postings are automatically analytic-tagged by branch**, so branch P&L and branch budget reports come free via analytic filters in Dynamic Accounts Report / MIS Builder.

> If Strategy A is adopted later, `spm.branch` records map 1-to-1 onto operating units via a provided migration script; the rest of the module reads the dimension through a single mixin (`spm.branch.mixin`), so the switch is localized.

### 4.3 Dimensional model used everywhere

Every payment/expense line ultimately resolves to the tuple:

```
(company_id, branch_id, expense_type_id, expense_category_id,
 employee_id, analytic_distribution, account_id, date, amount)
```

This tuple is the key for workflow resolution (§7), budget control (§8), and all reporting cubes (§11).

---

## 5. Module Stack — Selection & Justification

### 5.1 Odoo 19 CE core modules (already in the Git source)

| Module | Role |
|---|---|
| `account` | Journals, journal entries, payments, taxes, partners-as-employees payable |
| `hr`, `hr_expense` | Employees, departments, expense capture, expense reports, basic approve/post/pay flow |
| `analytic` | Analytic plans/accounts — branch & category analytics |
| `mail` | Chatter, activities, notifications — the audit and to-do backbone |

> Note: Odoo 19 CE's `hr_expense` already provides capture → submit → manager approve → post → pay. The custom module **extends** rather than replaces it, preserving upgradability.

### 5.2 Third-party commercial-free modules (download from Odoo Apps Store / GitHub)

| Module | Vendor / Source | v19 status | Why included |
|---|---|---|---|
| `base_accounting_kit` (Full Accounting Kit) | Cybrosys — Odoo Apps Store / `CybroOdoo/CybroAddons` GitHub | **v19 available** (vendor confirms CE 19 compatibility) | Restores Enterprise-class accounting to CE: asset mgmt, PDC, lock dates, follow-ups, daybook/bankbook/**cashbook**, credit limits, customer statements. Cashbook + extra journals directly support petty cash accounting. Requires Python `openpyxl`, `ofxparse`, `qifparse` (handled in Dockerfile) |
| `dynamic_accounts_report` | Cybrosys | **v19 available** | Dynamic GL, Trial Balance, P&L, Balance Sheet, Cash Flow, Partner Ledger/Ageing, Daybook with drill-down, PDF/XLSX export — the statutory & management financial reporting layer for CE |
| `om_account_accountant` + `om_account_budget` (Odoo Mates) | Odoo Mates — GitHub `odoomates/odooapps` | **v19 available** (vendor lists financial reports, assets, **budget management**, bank import, recurring) | Lightweight alternative/complement; **`om_account_budget` restores account-level Budget Management** (budgetary positions, budget lines vs analytic) removed from core |
| `accounting_pdf_reports` | Odoo Mates | v19 available | Classic PDF pack: GL, TB, Aged Partner, P&L, BS, Tax, Journal Audit |

> Pick **one** primary "accounting completeness" base to avoid menu/feature overlap: recommended **`base_accounting_kit` as primary** + `om_account_budget` for budgets + `dynamic_accounts_report` for reporting. Install in a staging DB first and resolve any duplicate-menu conflicts (both vendors ship overlapping features).

### 5.3 OCA modules (GitHub, branch `19.0`, pin commits)

| Repo / Module | Role | 19.0 note |
|---|---|---|
| `OCA/server-ux` → `base_tier_validation` | Generic multi-tier validation framework; used as conceptual base and optional secondary gate on accounting documents | Check 19.0 migration status; widely and quickly ported |
| `OCA/hr-expense` → `hr_expense_tier_validation`, `hr_expense_advance_clearing`, `hr_expense_cancel`, `hr_expense_petty_cash` | Expense tier validation; **employee advance & clearing**; cancel posted expense; petty-cash-paid expenses with custodian journals | Cherry-pick per 19.0 availability; `hr_expense_advance_clearing` is the standard solution for cash advances |
| `OCA/mis-builder` → `mis_builder`, `mis_builder_budget` | Management KPI reports (rows=KPIs, cols=periods), budget vs actual columns, dashboard-embeddable, PDF/XLSX | Mature, multi-version; ideal for the management pack |
| `OCA/operating-unit` | Branch dimension (Strategy A, §4.2) | Verify 19.0 port |
| `OCA/account-financial-reporting` | Additional GL/TB/Open-items XLSX reports | Optional |
| `OCA/web` → `web_responsive` | Enterprise-style responsive backend UI — important for mobile expense capture on CE | Standard |

**Pinning policy (enterprise standard):** every third-party repo is cloned at a **specific commit hash** recorded in `addons.lock` (provided in §10.4), never floating `HEAD`. Upgrades go through staging.

### 5.4 Custom module `small_payment_management` (single module — all custom code)

**Per the consolidation requirement, every line of custom code lives in one Odoo module, `small_payment_management`** (technical name `small_payment_management`, application module). There is no `spm_*` suite and no separate `dynamic_approval_workflow` add-on, and **no nested sub-packages**: `small_payment_management` is one conventional flat Odoo module (`models/`, `wizard/`, `views/`, `security/`, `data/`, `report/`, `demo/`, `static/src/`, `tests/`). What were previously separate modules are now just **functional areas grouped into separate files**, wired together in a single `__manifest__.py` (full manifest in Appendix A, §15).

**Module declaration**

| Attribute | Value |
|---|---|
| Technical name | `small_payment_management` |
| Depends | `base`, `mail`, `hr`, `hr_expense`, `account`, `analytic`, `web` |
| License | **OPL-1** (single license for the whole module) |
| `application` | `True` |

**Functional areas (file groups within the one flat module — *not* sub-packages)**

| Area (primary files) | Delivers |
|---|---|
| Masters & security (`models/spm_base.py`, `security/*`) | Branch master, expense type & category masters, policy rules, `res.users` branch fields, branch security, groups, record rules, sequences, base mixins |
| Approval engine (`models/approval.py`, `wizard/approval_wizards.py`) | The generic, model-agnostic approval engine: matrices, runtime chains, **RFI**, **admin + active-approver delegation**, **live add/remove of approvers**, SLA escalation, immutable amendment audit (full design in §7). Wired directly onto the SPM documents via `approval.workflow.mixin` — no separate bridge module is needed |
| Budget (`models/budget.py`) | Operational budget master, reservation ledger, utilization compute, period locks |
| Petty cash (`models/petty_cash.py`) | Floats, top-ups, disbursement vouchers, reconciliation, replenishment |
| Expense (`models/expense.py`) | Branch/type/category on expenses, matrix workflow on expense reports, advances & reimbursement batches |
| Dashboards (`static/src/`, OWL) | Management Dashboard + My Wallet user dashboard |
| Reports (`report/`) | QWeb PDF + XLSX report pack (§11) |

> **Licensing note (consequence of consolidation).** Because the approval engine is now compiled into `small_payment_management` rather than shipped as a standalone `base`+`mail`-only module, it can no longer be listed and sold on the Odoo Apps Store as an independent product. The whole `small_payment_management` module is governed by **one** license: **OPL-1** (Odoo Proprietary License v1.0 — the App Store paid-app license), so the consolidated solution can be distributed as a single paid app. (If independent sale of the approval engine ever becomes a priority again, the approval-engine files — kept dependency-clean at `base`+`mail` only — can be split back out into their own module; that is the only thing the single-module design gives up.)

---

## 6. Functional Design

### 6.1 Master data (Configuration menus)

**Expense Type (`spm.expense.type`)** — the top classification (e.g., *Travel*, *Office Supplies*, *Utilities*, *Staff Welfare*, *Repairs & Maintenance*).

| Field | Notes |
|---|---|
| `code`, `name`, `company_ids` | Multi-company sharable or company-specific |
| `budget_check_required` | ✔ → budget engine engages for this type (R6) |
| `budget_enforcement` | `off / warn / block` (overridable per category) |
| `requires_attachment_above` | Monetary threshold for mandatory receipt |
| `default_journal_id`, `active` | |

**Expense Category (`spm.expense.category`)** — child of type (e.g., Travel → *Airfare, Hotel, Per-diem, Local transport*).

| Field | Notes |
|---|---|
| `type_id`, `code`, `name` | |
| `expense_account_id` (per company via property) | GL expense account for posting |
| `product_id` | Optional link to an `hr_expense` product so core expense flow posts correctly |
| `budget_check_required`, `budget_enforcement` | Overrides type when set |
| `max_per_claim`, `max_per_day`, `max_per_month` | Policy limits, currency of company |
| `tax_ids`, `analytic_required`, `active` | |

**Branch (`spm.branch`)** — §4.2. **Policy Rule (`spm.policy.rule`)** — optional fine-grained rules (employee grade × category limits) evaluated at submission.

### 6.2 Document lifecycle states (shared pattern)

```
draft → submitted → [under_approval: L1 → L2 → … → Ln] → approved
      → posted (journal entry) → paid/closed
any state before posted → rejected / cancelled (with reason, full trail)
```

State transitions are server-actions guarded by the workflow engine; users never edit `state` directly. Rejection returns to `draft` with mandatory reason; resubmission restarts the matrix (configurable: restart vs resume).

### 6.3 Petty cash subsystem (`models/petty_cash.py`)

**Float (`spm.petty.cash.float`)** — one per branch (or per custodian): custodian (`hr.employee` + `res.users`), `float_limit` (imprest amount), `replenish_threshold`, dedicated **cash journal** + GL account (auto-created `1010xx Petty Cash – <Branch>`), computed `book_balance`, `pending_disbursements`, `available`.

**Top-up / Replenishment (`spm.petty.cash.topup`)** — requested by custodian or auto-suggested by cron when `available < replenish_threshold`. On final approval, posts `Dr Petty Cash – Branch / Cr Bank` and (imprest mode) replenishes exactly the sum of approved vouchers since last top-up.

**Disbursement Voucher (`spm.petty.cash.voucher`)** — header (float, date, payee type employee/vendor/other, branch auto = float branch) + lines (category, description, amount, tax, analytic auto-filled = branch ∥ category). Submission runs policy checks, duplicate detection, **budget check (§8)**, then resolves the **approval matrix (§7)**. On approval+posting: `Dr Expense accounts (lines) / Cr Petty Cash – Branch`.

**Reconciliation (`spm.petty.cash.recon`)** — periodic cash count: denominations grid, system vs counted, variance line posts to a Cash Over/Short account through its own (typically stricter) approval matrix.

### 6.4 Employee expense & reimbursement (`models/expense.py`)

Extends core `hr.expense` / `hr.expense.sheet`:

- Adds `branch_id` (default from employee), `expense_type_id`, `expense_category_id` (domain-linked; category fills product/account/analytic), duplicate-claim warning.
- Replaces the single "manager approval" with the **matrix workflow**: `sheet.action_submit_sheet()` is overridden to generate approval lines; core `action_approve` is reachable only by the engine when the last tier approves (keeps core accounting posting intact = upgrade-safe).
- **Advances:** via OCA `hr_expense_advance_clearing` when available for 19.0 (advance request → approval → payment → clearing against claims), else the module's fallback `spm.advance` model implementing the same ledger.
- **Reimbursement batches (`spm.reimbursement.batch`)**: accountant selects approved & posted sheets per company/branch, generates payments (bank file export optional), marks sheets paid, notifies employees.

---

## 7. Dynamic Approval Workflow Engine — built-in approval engine & core differentiator

### 7.0 The approval engine as a built-in part of `small_payment_management`

The workflow engine is implemented as a **self-contained, model-agnostic approval engine inside the single `small_payment_management` module** (`models/approval.py` + `wizard/approval_wizards.py`). It is still written with **zero coupling to petty cash, expense or any other SPM concept** — every dependency it touches is `base` + `mail` only — so it remains a clean, reusable engine; it simply ships *inside* `small_payment_management` rather than as a separate installable, per the consolidation requirement.

| Engine attribute | Value |
|---|---|
| Location | `models/approval.py` + `wizard/approval_wizards.py` within the `small_payment_management` module (models `approval.*`, mixin `approval.workflow.mixin`) |
| Category | Productivity / Approvals (functionally) |
| Edition target | Odoo 19.0 **Community** (also runs on Enterprise) |
| Internal dependencies | Only `base` + `mail` semantics — the engine code references no SPM model, keeping it a clean, reusable layer |
| Genericity | Works on **any** Odoo model by inheriting one mixin (`approval.workflow.mixin`); the SPM documents, sale orders, purchase orders, vendor bills, expense sheets, stock pickings, or any custom model can all be governed by the same engine |
| License | Inherits the **single OPL-1 license of the `small_payment_management` module** (§5.4) — it is no longer separately licensed/priced |

Inside this solution there is **no separate bridge module**: the SPM documents inherit `approval.workflow.mixin` directly and map their dimensions (branch/type/category) onto the engine's generic matching dimensions within the same module. Everything below is the engine's design; the four key capabilities — **Request for Information**, **delegation (admin + active-approver)**, and **live add / remove of approvers by admin** — are first-class features of this engine.

> **Consequence of consolidation (was §1, repeated here for the engine):** folding the engine into `small_payment_management` means it can no longer be listed and sold on the Odoo Apps Store as an independent paid app (the previous design priced it at USD 5,000 under OPL-1). The code is deliberately kept dependency-clean (`base`+`mail` only) so that, *if* independent sale is ever wanted again, the approval-engine files can be lifted back out into their own module with minimal effort — but as delivered, it is part of the one `small_payment_management` module.

### 7.1 Concept

A configurable **Approval Matrix** that, at submission time, auto-populates an ordered chain of approvers on the target record based on a tuple of matching dimensions — **Company + (any number of custom dimensions, e.g. Branch / Expense Type / Category / Department) + Amount band + Model/Document type**. Dimensions beyond company/amount are declared by the host model, so the engine stays generic while still supporting the exact "auto-populate by company, branch, type, category, amount" behavior required here. Inspired by OCA `base_tier_validation` but extended with deterministic matrix selection by specificity, ordered sequential tiers, contextual role resolution, RFI, delegation, escalation, and **live, audited amendment of the running chain**.

### 7.2 Data model

**`approval.matrix`** (master, versioned via `active` + date range):

| Field | Purpose |
|---|---|
| `name`, `company_id`, `model_id` / `document_type` | Which model/flow this matrix governs |
| `match_dimension_ids` → `approval.matrix.dimension` | Generic key/value match rules (e.g. `branch_id in (…)`, `expense_type_id in (…)`); empty rule = "all" |
| `amount_from`, `amount_to` | Amount band (company currency; `amount_to = 0` ⇒ no upper bound) |
| `priority` | Specificity tie-breaker |
| `restart_policy` | On resubmit after reject / on amount change: `restart` vs `resume` |
| `allow_active_approver_delegation` | Permit the current approver to self-delegate (§7.6) |
| `line_ids` → **`approval.matrix.line`** | The tiers |

**`approval.matrix.line`**: `sequence`, `approver_type` (`user / role / group`), where role ∈ {document owner's manager (`hr.employee.parent_id`), department head, branch manager, branch finance, company finance manager, CFO, custom group}, `user_id` (fixed user), `min_amount` (tier skipped below it — one matrix serves "≤500: manager only; ≤5,000: +branch manager; >5,000: +CFO"), `approval_mode` (`single` vs `all` vs `quorum n` when a tier holds several approvers), `can_edit_amount`, `can_request_info`, `sla_hours` (escalation timer).

**`approval.request.line`** (runtime, on each record via `approval.workflow.mixin`): `sequence`, `approver_id` (resolved `res.users`), `role_label`, `state` (`waiting / pending / approved / rejected / skipped / escalated / info_requested / delegated / added / removed`), `acted_date`, `comment`, `delegated_to_id`, `delegated_by_id`, `origin` (`matrix / admin_added`), `added_by_id`, `removed_by_id`, `removal_reason`. The extra states/fields are what make delegation and live amendment fully auditable on the line itself.

Three supporting models back the new features:

- **`approval.delegation`** — standing delegation rules (§7.6).
- **`approval.info.request`** — RFI threads (§7.5).
- **`approval.amendment.log`** — immutable record of every live add/remove/delegation/RFI action on a running request (§7.8).

### 7.3 Resolution algorithm (executed at submit)

```python
def _resolve_matrix(self):
    base = [
        ('model_id.model', '=', self._name),
        ('company_id', '=', self.company_id.id),
        ('amount_from', '<=', self._approval_amount()),
        '|', ('amount_to', '=', 0), ('amount_to', '>=', self._approval_amount()),
    ]
    candidates = self.env['approval.matrix'].search(base)
    # Each matrix dimension must either be empty ("all") or contain the record's value
    candidates = candidates.filtered(lambda m: m._dimensions_match(self))
    if not candidates:
        raise UserError(_("No approval matrix is configured for this combination. "
                          "Contact your workflow administrator."))
    # Most specific wins: more explicit (non-empty) matched dimensions, then priority
    return candidates.sorted(key=lambda m: (-m._specificity(), m.priority))[0]
```

Role → user resolution happens against the **record's owner / company / dimension context** (e.g. "Branch Manager" = `record.branch_id.manager_id.user_id`). Unresolvable roles raise a blocking, actionable error at submit (never silently skipped) — a key enterprise control.

### 7.4 Runtime behavior (base flow)

- Tiers are **sequential**: tier *n+1* activates only when tier *n* is satisfied (`single` / `all` / `quorum` per `approval_mode`). The active approver(s) get a `mail.activity` (To-Do) + email + dashboard card; downstream tiers show "waiting".
- **Self-approval prevention**: if requester == resolved approver, the tier auto-escalates to that approver's manager (configurable: skip / escalate / block).
- **Escalation cron**: tier pending > `sla_hours` → reminder at 50%, escalate to approver's manager at 100% (configurable), event logged.
- **Reject** at any tier → record `rejected`, mandatory reason, requester notified; resubmission follows `restart_policy`.
- **Amount edits** during approval (if the tier allows) re-run matrix resolution when the new amount crosses a band — blocks "approve low, raise after".
- Every action is chatter-logged and mirrored to `approval.amendment.log` → a complete, immutable audit trail.

### 7.5 Feature — Request for Information (RFI)

An approver who needs clarification before deciding can, instead of approve/reject, raise a **Request for Information** (enabled per matrix line via `can_request_info`).

- **Action:** *Request Info* button on the approval bar opens a wizard (`approval.info.request.wizard`): free-text question, optional required-attachment flag, and a **target** = the requester (default) or any earlier participant in the chain.
- **State & clock:** the record moves to `info_requested`; **the SLA/escalation clock for that tier pauses** (so an approver isn't penalised for waiting on the requester). The active tier is preserved — the same approver resumes when the answer arrives.
- **Response loop:** the target receives an activity + email + a "My Wallet / portal" task; they answer in the RFI thread (`approval.info.request`, which is `mail.thread`-tracked) and attach documents. On submission of the answer, the record returns to `pending` for the **same** approver, who now sees the Q&A inline. No tier is lost, nothing restarts.
- **Multiple/loop RFIs** are allowed and individually logged; an open RFI blocks approval of that tier until answered or withdrawn.
- **Audit:** question, responder, answer, attachments, and the exact pause/resume timestamps are written to `approval.amendment.log` and chatter. This keeps approval-cycle-time reporting honest (RFI wait time is reported separately from approver dwell time).

### 7.6 Feature — Delegation (two independent mechanisms)

**(a) Standing delegation set up by an administrator** (`approval.delegation`, manager-only):
the workflow admin can create a delegation for **any** user — `delegator_id → delegate_id`, `date_from / date_to`, optional scope (`model_ids`, `matrix_ids`, amount ceiling). While active, any tier that resolves to the delegator is **auto-assigned to the delegate at activation time**, with both names shown ("acting for …"). This is the out-of-office / leave-cover case driven centrally by HR or the workflow admin. Overlapping rules are validated; a delegation cannot create a self-approval (delegate == requester triggers the §7.4 self-approval rule).

**(b) Self-delegation by the current approver** (allowed when the matrix has `allow_active_approver_delegation`):
the **active approver** can hand off their *own pending task* via a *Delegate* button → wizard (`approval.delegate.wizard`): choose `delegate_to` (domain limited to users with the requisite group/role), mandatory reason, and scope = **this document only** (one-off) or **create a standing rule** for a date range. The runtime line is reassigned (`delegated_to_id`, `delegated_by_id`, state `delegated → pending`), the new approver is notified, and the original approver drops out of that tier. Both identities are retained forever in the audit ("Approved by *D* on behalf of *A*").

Guardrails common to both: a delegate must satisfy the tier's role/group (no privilege escalation), delegation chains are flattened (A→B→C resolves to C, with the full path logged), and delegation never bypasses self-approval prevention or SoD constraints (§12).

### 7.7 Feature — Live amendment: add / remove approvers by admin

Authorised administrators (group **Approval / Workflow Administrator**) can modify the approver chain **on an in-flight record**, because real approvals need exception handling without cancelling and restarting. Both actions go through a single audited wizard (`approval.amend.wizard`) and write to `approval.amendment.log`.

**Add a user to the running workflow**
- Insert an approver at a chosen **position**: *before the active tier*, *after the active tier*, *at the end*, or *as an additional parallel approver inside an existing tier* (turning that tier into a `quorum`/`all` tier).
- The added line gets `origin = admin_added`, `added_by_id`, and a **mandatory reason**.
- If inserted at/ahead of the active position, the engine recomputes which tier is active and notifies the newcomer; already-approved tiers are untouched.

**Remove a user from the running workflow**
- Remove a **pending / waiting** approver (or a redundant member of a multi-approver tier) with a **mandatory reason**; the line is kept with state `removed` + `removed_by_id` + `removal_reason` (we **never hard-delete** approval history — removal is a tombstone, not an erasure).
- If the removed approver is the **currently active** one, the engine advances: it activates the next member of the same tier (quorum) or the next tier; if removal would leave the tier unsatisfiable, the engine re-evaluates `approval_mode`.

**Guardrails (enforced in code):**
1. Cannot remove or alter a tier that has already **approved** (history is immutable).
2. Cannot remove the **last remaining** path to completion — the chain must always retain at least one resolvable, non-requester approver, or the action is blocked.
3. Add/remove cannot introduce **self-approval** (requester) or violate **SoD** (the amending admin cannot insert themselves as approver of a document they then approve — constraint).
4. Every amendment is **reason-mandatory**, chatter-logged, and emits a notification to the requester and remaining approvers so the change is transparent.
5. Optional **`require_amendment_cosign`** company setting: high-value records (above a configurable threshold) require a second admin to co-sign an amendment before it takes effect.

### 7.8 Audit, transparency & SoD for the new features

`approval.amendment.log` is an append-only model (`unlink` overridden to raise) capturing, for every RFI / delegation / add / remove: `request_ref`, `action_type`, `actor_id`, `affected_user_id`, `from_state`, `to_state`, `reason`, `timestamp`, and a JSON `payload` snapshot of the line before/after. The document chatter shows a human-readable feed; the log model powers the **Approval Amendment & Exception report** (§11, report #9) so auditors can answer "who changed which approval chain, when, and why" without reading raw chatter. All four features respect record rules, the company switcher, and the SoD constraints in §12.

### 7.9 Why not plain `base_tier_validation` — and why this engine is the differentiator

Tier validation evaluates independent tier *definitions* per record; it does not (a) select among competing matrices by specificity, (b) resolve contextual roles (branch/department manager) per document, (c) guarantee a single ordered chain with per-tier SLA/quorum semantics, or (d) provide **RFI, dual-mode delegation, and live audited add/remove of approvers** — the exact gaps enterprises hit in production. The `small_payment_management` module packages all of that — a model-agnostic engine with demo data, multilingual translations, automated tests, and documentation — as part of one coherent deliverable. It remains *compatible* with `base_tier_validation` (the two can coexist on different models), but the matrix engine is the primary flow here.

### 7.10 Engine files (within the single flat module)

The engine has no manifest of its own — its files live in the one flat `small_payment_management` module (Appendix A, §15) alongside everything else, grouped by their `approval*` filenames so they stay easy to identify (and to lift out later if ever needed):

```python
# the approval-engine entries inside the one small_payment_management/__manifest__.py "data" list
"security/approval_groups.xml",
"security/approval_record_rules.xml",
# approval rows are part of the single security/ir.model.access.csv
"data/approval_data.xml",            # sequences + SLA escalation cron + mail templates
"views/approval_views.xml",          # matrix / request / delegation / amendment-log actions
"views/approval_wizard_views.xml",   # RFI / delegate / amend wizard forms
# engine menus are part of views/spm_menus.xml; demo in demo/approval_demo.xml
```
Engine code: `models/approval.py` (matrix, request line, delegation, RFI, amendment log, `approval.workflow.mixin`) and `wizard/approval_wizards.py`.

> Licensing: the engine inherits the **single license of `small_payment_management`** (§5.4). Its code still references only `base`+`mail` semantics, so the engine files stay a clean, liftable layer — but as delivered it is not a separately installable or separately sold product.

---

## 8. Budget Control & Utilization (`models/budget.py`)

### 8.1 Two-layer budget architecture

| Layer | Tool | Timing | Purpose |
|---|---|---|---|
| **Operational (pre-commitment)** | Custom `spm.budget` | At submit & at final approval — *before money moves* | Hard/soft stop on requests; reservation ledger |
| **Accounting (actuals)** | `om_account_budget` (budgetary positions vs analytic) and/or OCA `mis_builder_budget` | After posting | Financial budget vs actual reporting, board pack |

The branch/category **analytic accounts are shared by both layers**, so operational and accounting budgets reconcile by construction.

### 8.2 Operational budget model

**`spm.budget`**: company, branch (optional = company-wide), fiscal period (year + monthly/quarterly lines), state (`draft → confirmed → done/closed`), revision trail.
**`spm.budget.line`**: expense **type** and/or **category** (category-level wins when both exist), `period_start/end`, `planned_amount`, computed `reserved` (approved-not-posted), `utilized` (posted actuals from analytic lines), `available = planned − reserved − utilized`, `utilization_pct`.

**`spm.budget.reservation`** (ledger): document ref, budget line, amount, state (`reserved/consumed/released`). Reservations are created at final approval, consumed on posting, released on rejection/cancellation — giving an exact, auditable committed-cost picture (the same committed-vs-actuals concept MIS Builder demo data illustrates with purchase commitments).

### 8.3 Enforcement logic ("ticked in masters")

```python
def _budget_gate(self, line):
    cfg = line.expense_category_id or line.expense_type_id
    if not cfg.effective_budget_check:          # the master tick (R6)
        return
    bline = self.env['spm.budget.line']._find(  # company+branch+cat/type+date
        self.company_id, self.branch_id,
        line.expense_type_id, line.expense_category_id, self.date)
    mode = cfg.effective_enforcement            # off / warn / block
    if not bline:
        if mode == 'block':
            raise ValidationError(_("No budget defined for %s / %s / %s.")
                % (self.branch_id.name, line.display_category, self.date))
        return self._chatter_warn(_("No budget line found — proceeding (warn mode)."))
    if line.price_total > bline.available:
        msg = _("Budget exceeded: %(cat)s — available %(av)s, requested %(req)s "
                "(utilization %(pct).0f%%)", ...)
        if mode == 'block':
            raise ValidationError(msg)
        self._chatter_warn(msg)                 # + flag for approvers
        self.over_budget = True                 # visible badge in approval UI
```

- Checked at **submit** (early feedback) and re-checked at **final approval** (race-safe, with row locking on the budget line).
- Approvers see an **Over-budget badge + utilization bar** on the approval screen — informed approval, not blind.
- Optional **budget transfer** document (between lines/branches) with its own approval matrix.
- Period close locks budget lines (no new reservations) while allowing settlement of in-flight documents.

---

## 9. Dashboards (`static/src/`, OWL)

Built as OWL components (Odoo 19's native JS framework) backed by `read_group`/SQL view models; respects record rules, company switcher and branch security automatically. Charts via the bundled chart library in Odoo's web client.

### 9.1 Management Dashboard (group: SPM / Manager+)

Filters: company (multi), branch, period, expense type/category.

| Widget | Content |
|---|---|
| KPI strip | Total spend MTD/QTD/YTD, vs budget %, open requests #/value, avg approval cycle time, floats outstanding |
| Spend trend | Monthly line/bar, current vs previous year |
| Budget vs Actual | Per branch and per category, utilization bars with RAG thresholds (e.g., >85% amber, >100% red) |
| Breakdown donuts | Spend by category, by branch, by company |
| Pending approvals ageing | Buckets 0–2 / 3–5 / >5 days, drill to documents |
| Top 10 | Spenders (employees), categories, branches |
| Float health | Each float: balance vs ceiling, days since last reconciliation, variance history |
| Exceptions | Over-budget approvals granted, policy-limit overrides, duplicates flagged |

Every widget drills down to the underlying list view. The same KPIs are also published as a **MIS Builder report instance** for board-pack PDF/XLSX export.

### 9.2 My Wallet — individual user dashboard (all employees)

| Widget | Content |
|---|---|
| My requests | Cards by state (draft/submitted/under approval — with "waiting on *whom*" /approved/rejected/paid) |
| Awaiting my action | Approval queue with one-click Approve/Reject (+comment), SLA countdown |
| My reimbursements | Approved-unpaid balance, last payments |
| My advances | Outstanding advance balance, settlement status |
| My float (custodians only) | Balance, pending vouchers, "Request top-up" shortcut |
| Quick actions | New expense (camera-first), new petty cash voucher, new advance |
| My monthly spend | Personal trend + per-category vs policy limits |

---

## 10. Docker Implementation — Source Build, No Prebuilt Odoo Image

### 10.1 Interpretation of the constraint

"Don't fetch any images from cloud / keep Odoo files from Git and run locally" is implemented as: **no `FROM odoo:19` and no prebuilt application images**. The build starts from a minimal OS base image (`debian:bookworm-slim` — unavoidable as the root filesystem; it can be substituted by an internally mirrored base or one built with `debootstrap` for fully air-gapped sites, see §10.7), clones `https://github.com/odoo/odoo.git -b 19.0` **inside the build**, installs all dependencies, and runs Odoo from that source checkout. Source and addons live on named volumes so they persist and can be updated with `git pull` *inside* the container without re-pulling anything from a registry.

Prerequisites confirmed for Odoo 19: Python ≥ 3.10 (3.12 recommended), PostgreSQL ≥ 13 (15/16 recommended), wkhtmltopdf 0.12.6 patched-Qt for PDF reports.

### 10.2 Repository layout (project Git repo)

```
odoo19-spm/
├── docker/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── fetch_addons.sh
│   ├── addons.lock              # repo → commit pins
│   └── odoo.conf
├── docker-compose.yml
├── addons/
│   └── custom/
│       └── small_payment_management/                 # the single custom module (bind-mounted)
├── backups/                     # dump target
└── docs/
```

### 10.3 Dockerfile (multi-stage, source build)

```dockerfile
# syntax=docker/dockerfile:1
############################
# Stage 1 — fetch sources  #
############################
FROM debian:bookworm-slim AS fetcher
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates && rm -rf /var/lib/apt/lists/*

# Odoo 19 Community source from Git (shallow, pinned branch)
RUN git clone --depth 1 --branch 19.0 \
    https://github.com/odoo/odoo.git /opt/odoo/odoo

# Third-party & OCA addons (pinned commits — see fetch_addons.sh)
COPY docker/fetch_addons.sh docker/addons.lock /tmp/
RUN bash /tmp/fetch_addons.sh /opt/odoo/addons

############################
# Stage 2 — runtime        #
############################
FROM debian:bookworm-slim
ENV LANG=C.UTF-8 DEBIAN_FRONTEND=noninteractive

# System deps (Python 3.11 on bookworm satisfies Odoo 19's ≥3.10)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-dev build-essential \
    libxml2-dev libxslt1-dev zlib1g-dev libsasl2-dev libldap2-dev \
    libpq-dev libjpeg-dev libfreetype6-dev liblcms2-dev libwebp-dev \
    libharfbuzz-dev libfribidi-dev libxcb1 \
    git curl ca-certificates fonts-dejavu-core fonts-noto-cjk \
    postgresql-client node-less npm xz-utils \
 && rm -rf /var/lib/apt/lists/*

# wkhtmltopdf 0.12.6 (patched Qt) — required for QWeb PDF headers/footers
RUN curl -sSL -o /tmp/wkhtml.deb \
    https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
 && apt-get update && apt-get install -y /tmp/wkhtml.deb \
 && rm -f /tmp/wkhtml.deb && rm -rf /var/lib/apt/lists/*

# RTL support for Arabic etc. (optional)
RUN npm install -g rtlcss

RUN useradd -m -d /opt/odoo -s /bin/bash odoo
COPY --from=fetcher --chown=odoo:odoo /opt/odoo /opt/odoo

# Python deps: Odoo requirements + accounting-kit extras
RUN python3 -m venv /opt/odoo/venv \
 && /opt/odoo/venv/bin/pip install --no-cache-dir --upgrade pip wheel \
 && /opt/odoo/venv/bin/pip install --no-cache-dir \
      -r /opt/odoo/odoo/requirements.txt \
      openpyxl ofxparse qifparse xlsxwriter

COPY --chown=odoo:odoo docker/odoo.conf /etc/odoo/odoo.conf
COPY --chown=odoo:odoo docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
 && mkdir -p /var/lib/odoo && chown odoo:odoo /var/lib/odoo

USER odoo
EXPOSE 8069 8072
VOLUME ["/var/lib/odoo", "/opt/odoo/addons"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/opt/odoo/venv/bin/python3", "/opt/odoo/odoo/odoo-bin", "-c", "/etc/odoo/odoo.conf"]
```

> `qifparse`/`ofxparse`/`openpyxl` are the documented external dependencies of `base_accounting_kit`; baking them into the image avoids the most common install failure of that module.

### 10.4 `fetch_addons.sh` + `addons.lock` (pinned third-party fetch at build time)

```bash
#!/usr/bin/env bash
# fetch_addons.sh <target_dir> — clones pinned addon repos listed in addons.lock
set -euo pipefail
TARGET="$1"; mkdir -p "$TARGET"/{cybrosys,odoomates,oca}

clone_pin () { # url branch commit dest subdirs...
  local url=$1 branch=$2 commit=$3 dest=$4; shift 4
  local tmp; tmp=$(mktemp -d)
  git clone --branch "$branch" --filter=blob:none "$url" "$tmp"
  git -C "$tmp" checkout "$commit"
  if [ "$#" -gt 0 ]; then for m in "$@"; do cp -r "$tmp/$m" "$dest/"; done
  else cp -r "$tmp"/* "$dest/"; fi
  rm -rf "$tmp"
}

# ── Cybrosys (accounting kit + dynamic reports) ──
clone_pin https://github.com/CybroOdoo/CybroAddons.git 19.0 <PIN> \
  "$TARGET/cybrosys" base_accounting_kit dynamic_accounts_report

# ── Odoo Mates (accounting menu, PDF reports, BUDGETS) ──
clone_pin https://github.com/odoomates/odooapps.git 19.0 <PIN> \
  "$TARGET/odoomates" om_account_accountant om_account_budget accounting_pdf_reports

# ── OCA ──
clone_pin https://github.com/OCA/server-ux.git        19.0 <PIN> "$TARGET/oca" base_tier_validation
clone_pin https://github.com/OCA/hr-expense.git       19.0 <PIN> "$TARGET/oca" \
  hr_expense_tier_validation hr_expense_advance_clearing hr_expense_cancel
clone_pin https://github.com/OCA/mis-builder.git      19.0 <PIN> "$TARGET/oca" mis_builder mis_builder_budget
clone_pin https://github.com/OCA/operating-unit.git   19.0 <PIN> "$TARGET/oca" operating_unit || true
clone_pin https://github.com/OCA/web.git              19.0 <PIN> "$TARGET/oca" web_responsive
```

Replace each `<PIN>` with the verified commit hash recorded in `addons.lock` after staging validation. Modules whose 19.0 port is not yet published are skipped (`|| true`) — the custom `small_payment_management` module covers their function (§4.2, §7.5).

### 10.5 `docker-compose.yml` (recommended production topology)

```yaml
services:
  db:
    image: postgres:16          # data service; see §10.6 to avoid even this pull
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: ${DB_PASSWORD:?set in .env}
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U odoo"]
      interval: 10s
      retries: 5
    restart: unless-stopped

  odoo:
    build:
      context: .
      dockerfile: docker/Dockerfile
    depends_on:
      db: { condition: service_healthy }
    environment:
      HOST: db
      USER: odoo
      PASSWORD: ${DB_PASSWORD}
    ports:
      - "8069:8069"   # http
      - "8072:8072"   # longpolling / websocket
    volumes:
      - odoo_filestore:/var/lib/odoo
      - odoo_addons:/opt/odoo/addons          # 3rd-party (populated at build)
      - ./addons/custom:/opt/odoo/addons/custom   # small_payment_management module live-mounted
    restart: unless-stopped

volumes:
  pg_data:
  odoo_filestore:
  odoo_addons:
```

**`docker/odoo.conf` (production-tuned skeleton)**

```ini
[options]
addons_path = /opt/odoo/odoo/addons,
              /opt/odoo/addons/cybrosys,
              /opt/odoo/addons/odoomates,
              /opt/odoo/addons/oca,
              /opt/odoo/addons/custom
data_dir   = /var/lib/odoo
admin_passwd = ${STRONG_MASTER_PASSWORD}
db_host = db
db_user = odoo
db_password = ${DB_PASSWORD}
list_db = False
proxy_mode = True
workers = 4                 ; ≈ (2 × CPU) + 1, tune to host
max_cron_threads = 2
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_time_cpu = 600
limit_time_real = 1200
log_level = info
```

**Build & run**

```bash
docker compose build            # clones Odoo 19 + addons from Git inside the build
docker compose up -d
docker compose exec odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo/odoo-bin \
  -c /etc/odoo/odoo.conf -d spm_prod \
  -i base,account,hr_expense,base_accounting_kit,dynamic_accounts_report,om_account_budget,small_payment_management \
  --stop-after-init
docker compose restart odoo
```

Updating Odoo later **without any registry pull**: `docker compose exec odoo bash -lc "cd /opt/odoo/odoo && git pull"` then `-u all --stop-after-init` on staging first.

### 10.6 Single-container variant ("completely inside the container")

If policy mandates literally one container (including the database), a supervisord-based image is provided: same Dockerfile plus `postgresql-16` from Debian repos, `supervisord` launching `postgres` then Odoo, both data dirs on one named volume. Trade-offs (documented for sign-off): no independent scaling/restart, riskier upgrades, container-restart couples DB and app. Recommended only for kiosk/edge or strict single-artifact policies; otherwise use the two-container compose above — it still pulls **no Odoo image**, only the official PostgreSQL data-store image.

### 10.7 Fully air-gapped note

For sites where even `debian:bookworm-slim`/`postgres:16` must not come from Docker Hub: mirror them once into a private registry, or generate the base with `debootstrap` + `docker import`, and vendor the Git repos + pip wheels (`pip download -r requirements.txt -d wheels/`) into the build context. The Dockerfile accepts `--build-arg OFFLINE=1` switching pip to `--no-index --find-links /wheels`.

---

## 11. Reporting Pack

### 11.1 Financial / statutory (from third-party modules — zero custom effort)
Dynamic GL, Trial Balance, P&L, Balance Sheet, Cash Flow, Partner Ledger & Ageing, Daybook/Bankbook/**Cashbook**, Tax report, Journal Audit, Asset & PDC reports — all multi-company aware, filterable by analytic (= **branch & category**), exportable PDF/XLSX.

### 11.2 Custom operational reports (`report/` — QWeb PDF + XLSX)

| # | Report | Audience | Key columns / features |
|---|---|---|---|
| 1 | Petty Cash Register (per float/period) | Branch finance, audit | Opening, top-ups, vouchers (no., date, payee, category, amount), closing; matches journal |
| 2 | Disbursement Voucher (document print) | All | Numbered voucher with approval chain & signatures block |
| 3 | Float Reconciliation Statement | Audit | Denomination count vs book, variance, approver trail |
| 4 | Expense Claim / Report print | Employees, HR | Lines, receipts index, approval chain |
| 5 | Reimbursement Batch & Payment Advice | Finance | Per-employee payable summary, bank details |
| 6 | Budget Utilization | Management | Planned / Reserved / Utilized / Available / % by company→branch→type→category, RAG |
| 7 | Budget vs Actual (period comparison) | Management | Via MIS Builder template, board-ready |
| 8 | Approval Cycle / SLA report | Management, audit | Per matrix tier: avg/percentile hours, escalations, bottleneck approvers |
| 9 | Policy Exception report | Audit, compliance | Over-budget approvals, limit overrides, missing-receipt waivers, duplicates |
| 10 | Spend Analytics extract | BI | Flat cube (the §4.3 tuple) as XLSX/CSV for external BI |
| 11 | Advance Outstanding & Ageing | Finance | Per employee, settlement status |
| 12 | Custodian Activity & Variance history | Internal control | Per custodian risk view |

All custom reports respect company/branch record rules and carry the printing user, timestamp and filter header (audit standard).

---

## 12. Security, Compliance & Enterprise Standards

### 12.1 Role model (groups)

| Group | Rights (summary) |
|---|---|
| SPM / Employee | Create own expenses/advances; read own docs; My Wallet |
| SPM / Custodian | + own float, vouchers, top-up requests, reconciliation entry |
| SPM / Approver | + approve queue (resolved by matrix, not by group alone) |
| SPM / Branch Finance | + branch-wide read, reimbursement prep, registers |
| SPM / Finance Manager | + post/pay, budget edit (own companies), matrices read |
| SPM / Administrator | Masters, matrices, budgets, policies (no transaction posting — SoD) |
| SPM / Auditor | Read-everything, post-nothing |

**Segregation of duties enforced in code:** requester ≠ approver (§7.4); approver ≠ poster for the same document; matrix/budget editors cannot approve transactions they configured (constraint check).

### 12.2 Record rules

- Company rule: standard `company_ids` rule on every `spm.*` model.
- Branch rule: `['|', ('branch_id','=',False), ('branch_id','in', user.spm_branch_ids.ids)]` for non-manager groups.
- Portal/employee rule on expenses: `[('employee_id.user_id','=',user.id)]` unless elevated.

### 12.3 Audit & data integrity
- All documents inherit `mail.thread` + `mail.activity.mixin`; field tracking on state, amounts, approver lines.
- No unlink after submission (override raises; cancel-with-reason instead). Posted entries follow accounting lock dates (accounting kit provides lock-date management).
- Sequences per company+branch+doc type (e.g., `PCV/HQ-NBO/2026/00057`).
- Attachments: receipt images stored in filestore volume; checksum logged.

### 12.4 Quality engineering
- Python tests (`odoo.tests.TransactionCase`) per module: matrix resolution table-driven tests, budget race tests (concurrent approvals), posting assertions; tour tests for dashboards.
- Repo CI: lint (ruff/pylint-odoo), tests on a disposable compose stack, image build.
- Staging DB = anonymized prod copy; all addon-pin upgrades validated there first.

### 12.5 Operations
- **Backups:** nightly `pg_dump -Fc` + filestore tar via a cron sidecar to `./backups`, 30-day retention, restore drill monthly.
- **Monitoring:** Odoo `/web/health`, Postgres exporter, log shipping; worker memory limits set in `odoo.conf` (§10.5).
- **Reverse proxy:** nginx with TLS in front of 8069/8072 for production (config template included in repo).
- **Performance:** workers ≈ 2×CPU+1; PostgreSQL `shared_buffers` ≈ 25% RAM; pgbouncer optional at >100 concurrent users.

---

## 13. Implementation Roadmap

| Phase | Weeks | Deliverables |
|---|---|---|
| 0 — Foundation | 1 | Docker stack built from source; Odoo 19 + third-party modules installed on staging; addon pins recorded |
| 1 — Masters & security | 2 | Module scaffold + masters (`models/spm_base.py`): branches, types, categories, policies, groups, record rules; company/branch data load |
| 2 — Workflow engine | 2–3 | Approval engine (`models/approval.py`): matrices, runtime engine, delegation, escalation, tests |
| 3 — Petty cash | 2 | Petty cash (`models/petty_cash.py`): floats, top-ups, vouchers, reconciliation, postings |
| 4 — Expenses & reimbursement | 2 | Expense (`models/expense.py`): `hr_expense` extensions, advances, reimbursement batches |
| 5 — Budgets | 1–2 | Budget (`models/budget.py`) + `om_account_budget`/MIS budget wiring, transfers |
| 6 — Dashboards & reports | 2 | OWL dashboards, report pack, MIS board pack |
| 7 — UAT & hardening | 1–2 | UAT scripts per role, performance pass, backup/restore drill, training, go-live |

**Go-live checklist:** chart-of-accounts & petty cash GL per company ✓ · branches + analytic plan ✓ · types/categories with budget ticks ✓ · approval matrices signed off by finance ✓ · budgets loaded ✓ · opening float balances posted ✓ · user-role assignment ✓ · backup job verified ✓.

---

## 14. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Some OCA 19.0 ports not yet published at build time | Missing helper modules | Custom `small_payment_management` module is self-sufficient for branch & workflow (§4.2, §7); fetch script skips gracefully; re-pin when ports land |
| Overlap between Cybrosys kit and Odoo Mates modules | Duplicate menus/conflicts | Install minimal set; staging validation; primary = accounting kit, budgets = `om_account_budget` |
| `base_accounting_kit` Python deps missing | Module install failure | `openpyxl/ofxparse/qifparse` baked into image (§10.3) — the vendor-documented fix |
| Budget race on concurrent approvals | Over-commitment | Row-level lock + re-check at final approval (§8.3) |
| Odoo 19 dot-release changes (19.x source moves) | Regression | Source pinned to commit, not branch tip, in production builds; upgrades via staging |
| Single-container mandate | Ops fragility | Documented trade-offs + supervisord variant (§10.6) |

---

## 15. Appendix A — Custom module skeleton (excerpts)

**Single-module directory layout (`addons/custom/small_payment_management/`)** — one conventional flat Odoo module; functional areas are grouped into separate **files** (not sub-packages):
```
small_payment_management/
├── __init__.py            # from . import models / wizard
├── __manifest__.py        # the ONE manifest (below)
├── models/
│   ├── __init__.py
│   ├── spm_base.py        # branch + mixin, expense type/category, policy, res.users
│   ├── approval.py        # approval engine models + approval.workflow.mixin (§7)
│   ├── budget.py          # operational budget + reservation ledger (§8)
│   ├── petty_cash.py      # floats, top-ups, vouchers, reconciliation (§6.3)
│   └── expense.py         # hr_expense extensions, advances, reimbursement (§6.4)
├── wizard/
│   ├── __init__.py
│   └── approval_wizards.py   # RFI / delegate / amend wizards
├── security/
│   ├── spm_groups.xml
│   ├── approval_groups.xml
│   ├── spm_record_rules.xml
│   ├── approval_record_rules.xml
│   └── ir.model.access.csv   # single access file for ALL models
├── data/                  # sequences, crons, mail templates
├── views/                 # actions, wizard forms, menus
├── report/                # QWeb/XLSX report actions + templates (§11)
├── demo/                  # demo data
├── static/src/            # OWL dashboards: management_dashboard/, my_wallet/ (§9)
├── i18n/                  # translations
└── tests/                 # TransactionCase + tours
```

**`small_payment_management/__manifest__.py`** (the single manifest for all custom code)
```python
{
    "name": "SPM — Small Payments Management",
    "summary": "Petty cash, employee expense & reimbursement with a model-agnostic "
               "dynamic approval engine (RFI, delegation, live add/remove, SLA), "
               "operational budgets, OWL dashboards and a full report pack.",
    "version": "19.0.1.0.0",
    "category": "Accounting/Expenses",
    "license": "OPL-1",   # one license for the whole module (§5.4)
    "depends": ["base", "mail", "hr", "hr_expense", "account", "analytic", "web"],
    "data": [
        # — security: groups first, then rules, then access —
        "security/spm_groups.xml",
        "security/approval_groups.xml",
        "security/spm_record_rules.xml",
        "security/approval_record_rules.xml",
        "security/ir.model.access.csv",
        # — master & engine data (sequences, crons, mail templates) —
        "data/spm_sequences.xml",
        "data/approval_data.xml",
        "data/petty_cash_data.xml",
        # — actions & wizard forms —
        "views/spm_base_views.xml",
        "views/approval_views.xml",
        "views/approval_wizard_views.xml",
        "views/budget_views.xml",
        "views/petty_cash_views.xml",
        "report/petty_cash_reports.xml",
        "views/expense_views.xml",
        "report/spm_reports.xml",
        # — menus (reference the actions above) load last —
        "views/spm_menus.xml",
    ],
    "demo": ["demo/spm_demo.xml", "demo/approval_demo.xml"],
    "assets": {
        "web.assets_backend": [
            "small_payment_management/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
```

**Branch master (core fields)**
```python
class SpmBranch(models.Model):
    _name = "spm.branch"
    _description = "Branch / Operating Unit"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True,
                                 default=lambda s: s.env.company)
    manager_id = fields.Many2one("hr.employee", tracking=True)
    analytic_account_id = fields.Many2one("account.analytic.account",
                                          readonly=True, copy=False)
    petty_cash_journal_id = fields.Many2one(
        "account.journal", domain="[('type','=','cash'),"
                                  "('company_id','=',company_id)]")
    active = fields.Boolean(default=True)

    _sql_constraints = [("code_company_uniq", "unique(code, company_id)",
                         "Branch code must be unique per company.")]

    @api.model_create_multi
    def create(self, vals_list):
        branches = super().create(vals_list)
        branches._ensure_analytic()          # auto analytic account per branch
        return branches
```

**Workflow mixin hook — defined in `models/approval.py` of `small_payment_management`, inherited by every SPM document**
```python
class ApprovalWorkflowMixin(models.AbstractModel):
    _name = "approval.workflow.mixin"      # generic; any model can inherit
    approval_line_ids = fields.One2many("approval.request.line", "res_id",
        domain=lambda s: [("res_model", "=", s._name)])
    current_approver_id = fields.Many2one("res.users",
        compute="_compute_current_approver", store=True)
    approval_state = fields.Selection(
        [("draft", "Draft"), ("under_approval", "Under Approval"),
         ("info_requested", "Information Requested"),     # §7.5 RFI
         ("approved", "Approved"), ("rejected", "Rejected")],
        default="draft", tracking=True)

    def action_submit(self):
        for doc in self:
            doc._run_policy_checks()                  # host-model hook (e.g. SPM budget §8.3)
            matrix = doc._resolve_matrix()            # §7.3
            doc._generate_approval_lines(matrix)      # role → user, + active delegations §7.6
            doc._activate_tier(1)                     # activity + mail
            doc.approval_state = "under_approval"

    # Public entry points for the four enterprise features (full design §7.5–7.7):
    def action_request_info(self): ...                # §7.5
    def action_delegate(self): ...                    # §7.6(b) active-approver self-delegation
    def action_amend_approvers(self): ...             # §7.7 admin add/remove (audited)
```

> The SPM documents (petty cash voucher, expense sheet, etc.) inherit this mixin directly within the same `small_payment_management` module and add the budget gate in `_run_policy_checks`; the approval-engine code itself still references no petty-cash concept, keeping it a clean, liftable layer even though it ships inside `small_payment_management`.

---

## 16. Appendix B — Source & module reference list

| Component | Source |
|---|---|
| **`small_payment_management` (Small Payments Management)** | This project — the single custom module containing all bespoke code: masters, approval engine (§7), budgets, petty cash, expenses, dashboards and reports. Design throughout §4–§12 |
| Odoo 19 Community source | `https://github.com/odoo/odoo` (branch `19.0`) |
| Full Accounting Kit v19 (`base_accounting_kit`) | Odoo Apps Store `apps.odoo.com/apps/modules/19.0/base_accounting_kit` / `CybroOdoo/CybroAddons` |
| Dynamic Accounting Reports v19 (`dynamic_accounts_report`) | Apps Store `…/19.0/dynamic_accounts_report` / `CybroOdoo/CybroAddons` |
| Odoo Mates Accounting + Budget (`om_account_accountant`, `om_account_budget`, `accounting_pdf_reports`) | `github.com/odoomates/odooapps`, Apps Store 19.0 listings |
| OCA tier validation | `github.com/OCA/server-ux` → `base_tier_validation` |
| OCA expense extras | `github.com/OCA/hr-expense` (tier validation, advance clearing, petty cash helpers) |
| OCA MIS Builder (+ budget) | `github.com/OCA/mis-builder` |
| OCA Operating Unit | `github.com/OCA/operating-unit` |
| OCA responsive web | `github.com/OCA/web` → `web_responsive` |
| wkhtmltopdf 0.12.6 patched | `github.com/wkhtmltopdf/packaging` releases |
| Odoo 19 source-install requirements (Python ≥3.10, PostgreSQL ≥13) | `odoo.com/documentation/19.0/administration/on_premise/source.html` |

---

*End of report.*
