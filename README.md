# Small Payment Management — Odoo 19

Enterprise **petty cash, employee expense & reimbursement** solution for Odoo 19
Community Edition, delivered as a single custom module with a model-agnostic
**dynamic approval engine** (approval matrix, Request for Information, delegation,
live add/remove of approvers, SLA escalation, immutable audit), operational
budgets, OWL dashboards and a reporting pack.

## Contents

| Path | What |
|---|---|
| [`addons/custom/small_payment_management/`](addons/custom/small_payment_management/) | The single Odoo module (technical name `small_payment_management`) |
| [`odoo19-petty-cash-expense-solution-report.md`](odoo19-petty-cash-expense-solution-report.md) | Full solution architecture & implementation report |
| [`docs/workflow.md`](docs/workflow.md) | Workflow diagrams (end-to-end, lifecycle, approval engine, budget, petty cash) |

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
