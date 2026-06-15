from odoo import api, fields, models

BUDGET_ENFORCEMENT = [
    ("off", "Off"),
    ("warn", "Warn"),
    ("block", "Block"),
]


class SpmBranchMixin(models.AbstractModel):
    """Adds the branch dimension to any transactional document.

    Keeps the branch strategy (custom ``spm.branch`` vs OCA operating unit)
    localised to a single mixin (see report §4.2).
    """

    _name = "spm.branch.mixin"
    _description = "SPM Branch Dimension Mixin"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company)
    branch_id = fields.Many2one(
        "spm.branch", string="Branch", index=True, tracking=True,
        check_company=True)


class SpmBranch(models.Model):
    _name = "spm.branch"
    _description = "Branch / Operating Unit"
    _inherit = ["mail.thread"]
    _order = "code"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company)
    manager_id = fields.Many2one(
        "hr.employee", string="Branch Manager", tracking=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Analytic Account",
        readonly=True, copy=False)
    petty_cash_journal_id = fields.Many2one(
        "account.journal", string="Petty Cash Journal",
        domain="[('type', '=', 'cash'), ('company_id', '=', company_id)]")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)",
         "Branch code must be unique per company."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        branches = super().create(vals_list)
        branches._ensure_analytic()
        return branches

    def _ensure_analytic(self):
        """Auto-create one analytic account per branch (stub).

        TODO: create the analytic account under a dedicated 'Branches' plan
        and tag every branch posting with it (report §4.2).
        """
        return True


class SpmExpenseType(models.Model):
    _name = "spm.expense.type"
    _description = "Expense Type"
    _order = "code"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    company_ids = fields.Many2many("res.company", string="Companies")
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    budget_check_required = fields.Boolean(string="Budget Check Required")
    budget_enforcement = fields.Selection(
        BUDGET_ENFORCEMENT, default="warn", string="Budget Enforcement")
    requires_attachment_above = fields.Monetary(string="Receipt Required Above")
    default_journal_id = fields.Many2one("account.journal")
    active = fields.Boolean(default=True)

    # Effective values used by the budget gate when no category overrides them.
    effective_budget_check = fields.Boolean(
        compute="_compute_effective", string="Budget Check (effective)")
    effective_enforcement = fields.Selection(
        BUDGET_ENFORCEMENT, compute="_compute_effective",
        string="Enforcement (effective)")

    @api.depends("budget_check_required", "budget_enforcement")
    def _compute_effective(self):
        for rec in self:
            rec.effective_budget_check = rec.budget_check_required
            rec.effective_enforcement = rec.budget_enforcement or "warn"


class SpmExpenseCategory(models.Model):
    _name = "spm.expense.category"
    _description = "Expense Category"
    _order = "type_id, code"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    type_id = fields.Many2one(
        "spm.expense.type", string="Expense Type", required=True,
        ondelete="cascade")
    expense_account_id = fields.Many2one(
        "account.account", string="Expense Account")
    product_id = fields.Many2one("product.product", string="Expense Product")
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    budget_check_required = fields.Boolean()
    budget_enforcement = fields.Selection(BUDGET_ENFORCEMENT)
    max_per_claim = fields.Monetary()
    max_per_day = fields.Monetary()
    max_per_month = fields.Monetary()
    tax_ids = fields.Many2many("account.tax", string="Taxes")
    analytic_required = fields.Boolean()
    active = fields.Boolean(default=True)

    # Category overrides the type when set, else falls back to the type.
    effective_budget_check = fields.Boolean(
        compute="_compute_effective", string="Budget Check (effective)")
    effective_enforcement = fields.Selection(
        BUDGET_ENFORCEMENT, compute="_compute_effective",
        string="Enforcement (effective)")

    @api.depends("budget_check_required", "budget_enforcement",
                 "type_id.budget_check_required", "type_id.budget_enforcement")
    def _compute_effective(self):
        for rec in self:
            rec.effective_budget_check = (
                rec.budget_check_required or rec.type_id.budget_check_required)
            rec.effective_enforcement = (
                rec.budget_enforcement
                or rec.type_id.budget_enforcement
                or "warn")


class SpmPolicyRule(models.Model):
    _name = "spm.policy.rule"
    _description = "Policy Rule"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    category_id = fields.Many2one("spm.expense.category", string="Category")
    employee_grade = fields.Char(string="Employee Grade")
    max_amount = fields.Monetary(string="Max Amount")
    active = fields.Boolean(default=True)


class ResUsers(models.Model):
    _inherit = "res.users"

    spm_branch_ids = fields.Many2many(
        "spm.branch", "spm_branch_users_rel", "user_id", "branch_id",
        string="Allowed Branches")
    spm_default_branch_id = fields.Many2one(
        "spm.branch", string="Default Branch")
