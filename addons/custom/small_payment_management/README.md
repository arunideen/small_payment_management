# Small Payment Management

Single Odoo 19 module (technical name `small_payment_management`) containing
**all** custom code for the petty cash, employee expense & reimbursement
solution — including an optional **vendor electronic payout** integration
(UPI / cards / bank via an external payouts API). See the full design in
`../../../odoo19-petty-cash-expense-solution-report.md`.

Conventional flat layout — `models/`, `wizard/`, `views/`, `security/`,
`data/`, `report/`, `demo/`, `static/src/`, `tests/`. There are no nested
sub-modules; functional areas are just grouped into separate files.

> Note: the module's technical name is `small_payment_management`, but its
> data models keep the short `spm.*` prefix (e.g. `spm.branch`,
> `spm.petty.cash.voucher`) and source files keep `spm_*` names.

## Pain points addressed

- **Untracked petty cash** → imprest floats, thresholds, reconciliation (§6.3).
- **Slow, unauditable approvals; "approve low, raise later"** → dynamic approval matrix + immutable audit (§7).
- **Approver away / needs info / chain must change** → RFI, delegation, live add/remove of approvers (§7.5–7.7).
- **Overspend found only after posting** → pre-commitment budget with reservation ledger (§8).
- **Weak SoD; deleted history** → requester ≠ approver ≠ poster ≠ payout releaser; no delete after submit; append-only log (§7.8, §12).
- **No branch visibility/security** → branch dimension + analytic tagging + record rules (§4, §12).
- **Vendor payments made manually / double-paid / unreconciled** → electronic payouts (UPI/cards/bank): idempotent, signed webhooks, auto-reconciled `account.payment`, optional TDS (§6.5).

See the [Solution Report §1.1](../../../odoo19-petty-cash-expense-solution-report.md) for the detailed pain-point → solution mapping.

## Status

Skeleton: models, security, menus, actions, wizards and the stub approval
engine are in place and installable. Business-logic methods are marked `TODO`
against the report sections.

## Install

```bash
odoo-bin -d <db> -i small_payment_management --addons-path=...,addons/custom
```
