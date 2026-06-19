# Small Payment Management — Odoo 19

Enterprise **petty cash, employee expense & reimbursement** solution for Odoo 19
Community Edition, delivered as a single custom module with a model-agnostic
**dynamic approval engine** (approval matrix, Request for Information, delegation,
live add/remove of approvers, SLA escalation, immutable audit), operational
budgets, OWL dashboards, a reporting pack, and an optional **vendor electronic
payout** integration (UPI / cards / bank via an external payouts API such as
RazorpayX / Cashfree).

## Contents

| Path | What |
|---|---|
| [`addons/custom/small_payment_management/`](addons/custom/small_payment_management/) | The single Odoo module (technical name `small_payment_management`) |
| [`odoo19-petty-cash-expense-solution-report.md`](odoo19-petty-cash-expense-solution-report.md) | Full solution architecture & implementation report |
| [`docs/workflow.md`](docs/workflow.md) | Workflow diagrams (end-to-end, lifecycle, approval engine, budget, **vendor payout**, petty cash) |
| [`docs/diagrams.html`](docs/diagrams.html) | Standalone HTML version of the workflow diagrams (Mermaid via CDN) |
| [`docs/statement-of-work.md`](docs/statement-of-work.md) | Statement of Work (scope, deliverables, timeline) |
| [`docs/vendor-payout-integration-research.md`](docs/vendor-payout-integration-research.md) | Vendor electronic payout integration — research & design |

## Pain points addressed

| Pain point (typical status quo) | How this solution fixes it |
|---|---|
| Petty cash on paper/spreadsheets — no live balance, reconciliation gaps, cash leakage | Imprest floats with computed balance, replenishment thresholds, cash-count reconciliation with variance posting |
| Approvals over email/chat — slow, lost, no audit; "approve low, raise later" abuse | Dynamic approval matrix by company/branch/type/category/amount; ordered tiers; amount-change re-resolution; immutable audit |
| Process stalls when an approver is away / needs info / the chain must change | Request for Information (pauses the SLA clock), standing + active-approver delegation, live audited add/remove of approvers |
| Overspend discovered only after posting | Operational pre-commitment budgets with a reservation ledger and off/warn/block enforcement |
| Weak segregation of duties; deleted records hide history | SoD in code (requester ≠ approver ≠ poster ≠ payout releaser); no delete after submit; append-only amendment log |
| No branch-level visibility or security | Branch dimension + analytic tagging on every transaction; branch record rules, dashboards and reports |
| Management & staff lack visibility | Management and "My Wallet" OWL dashboards + report pack (registers, utilization, SLA, exceptions) |
| Cash advances untracked; reimbursements slow | Advance ledger with settlement; reimbursement batches |
| **Vendor payments made manually** — disconnected from approval, keying errors, double-payments, no UTR/audit, slow, no TDS/KYC | **Electronic payouts** (UPI/cards/bank) from approved docs via an external API: pay-after-approval + segregated release, idempotency (no double-pay), signed webhooks → auto-reconciled `account.payment` with UTR, beneficiary KYC, optional TDS |
| Enterprise licensing / cloud lock-in | Community Edition built from source, on-prem Docker, OCA/free modules, no prebuilt Odoo image |

## Status

Installable skeleton: models, security, menus, actions, wizards and the stub
approval engine are in place. Business-logic methods are marked `TODO` against
the report sections.

## Install

```bash
odoo-bin -d <db> -i small_payment_management --addons-path=<core>,addons/custom
```

## License

OPL-1 (see the module manifest).
