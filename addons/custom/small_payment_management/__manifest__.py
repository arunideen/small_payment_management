{
    "name": "Small Payment Management",
    "summary": "Petty cash, employee expense & reimbursement with a model-agnostic "
               "dynamic approval engine (RFI, delegation, live add/remove, SLA), "
               "operational budgets, OWL dashboards and a full report pack.",
    "description": """
Small Payment Management
========================
A single, flat Odoo module containing all custom code for the enterprise petty
cash, employee expense & reimbursement solution. Functional areas are grouped
into files (no nested sub-packages):

* models/spm_base.py   — branch / expense-type / category / policy masters + security
* models/approval.py   — model-agnostic approval matrix engine (RFI, delegation,
                         live add/remove of approvers, SLA escalation, immutable audit)
* models/budget.py     — operational (pre-commitment) budgets + reservation ledger
* models/petty_cash.py — imprest floats, top-ups, disbursement vouchers, reconciliation
* models/expense.py    — hr_expense extensions, advances, reimbursement batches
* static/src/          — OWL management & "My Wallet" dashboards
* report/              — QWeb PDF + XLSX report pack

See odoo19-petty-cash-expense-solution-report.md for the full design.
""",
    "version": "19.0.1.0.0",
    "category": "Accounting/Expenses",
    "author": "Ideenkreise Tech",
    "website": "https://ideenkreisetech.com",
    "license": "OPL-1",
    "depends": [
        "base",
        "mail",
        "hr",
        "hr_expense",
        "account",
        "analytic",
        "web",
    ],
    "data": [
        # --- security: groups first, then rules, then access ---
        "security/spm_groups.xml",
        "security/approval_groups.xml",
        "security/spm_record_rules.xml",
        "security/approval_record_rules.xml",
        "security/ir.model.access.csv",
        # --- master & engine data (sequences, crons, mail templates) ---
        "data/spm_sequences.xml",
        "data/approval_data.xml",
        "data/petty_cash_data.xml",
        # --- actions (auto-generated views) ---
        "views/spm_base_views.xml",
        "views/approval_views.xml",
        "views/approval_wizard_views.xml",
        "views/budget_views.xml",
        "views/petty_cash_views.xml",
        "report/petty_cash_reports.xml",
        "views/expense_views.xml",
        "report/spm_reports.xml",
        # --- menus (reference the actions above) load last ---
        "views/spm_menus.xml",
    ],
    "demo": [
        "demo/spm_demo.xml",
        "demo/approval_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "small_payment_management/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
