# Small Payment Management

Single Odoo 19 module (technical name `small_payment_management`) containing
**all** custom code for the petty cash, employee expense & reimbursement
solution. See the full design in
`../../../odoo19-petty-cash-expense-solution-report.md`.

Conventional flat layout — `models/`, `wizard/`, `views/`, `security/`,
`data/`, `report/`, `demo/`, `static/src/`, `tests/`. There are no nested
sub-modules; functional areas are just grouped into separate files.

> Note: the module's technical name is `small_payment_management`, but its
> data models keep the short `spm.*` prefix (e.g. `spm.branch`,
> `spm.petty.cash.voucher`) and source files keep `spm_*` names.

## Status

Skeleton: models, security, menus, actions, wizards and the stub approval
engine are in place and installable. Business-logic methods are marked `TODO`
against the report sections.

## Install

```bash
odoo-bin -d <db> -i small_payment_management --addons-path=...,addons/custom
```
