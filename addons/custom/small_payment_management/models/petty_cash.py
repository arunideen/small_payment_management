from odoo import api, fields, models


class SpmPettyCashFloat(models.Model):
    _name = "spm.petty.cash.float"
    _description = "Petty Cash Float (Imprest)"
    _inherit = ["mail.thread", "spm.branch.mixin"]

    name = fields.Char(required=True, tracking=True)
    custodian_employee_id = fields.Many2one("hr.employee", string="Custodian")
    custodian_user_id = fields.Many2one("res.users", string="Custodian User")
    journal_id = fields.Many2one(
        "account.journal", string="Cash Journal",
        domain="[('type', '=', 'cash')]")
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    float_limit = fields.Monetary(string="Imprest Amount")
    replenish_threshold = fields.Monetary(string="Replenishment Threshold")
    book_balance = fields.Monetary(
        compute="_compute_balances", string="Book Balance")
    pending_disbursements = fields.Monetary(
        compute="_compute_balances", string="Pending Disbursements")
    available = fields.Monetary(
        compute="_compute_balances", string="Available")
    active = fields.Boolean(default=True)

    @api.depends("float_limit")
    def _compute_balances(self):
        # TODO: derive from posted journal items + open vouchers.
        for rec in self:
            rec.book_balance = rec.float_limit
            rec.pending_disbursements = 0.0
            rec.available = rec.float_limit

    @api.model
    def _cron_check_replenishment(self):
        """Suggest a top-up when available < threshold (report §6.3). Stub."""
        return True


class SpmPettyCashTopup(models.Model):
    _name = "spm.petty.cash.topup"
    _description = "Petty Cash Top-up / Replenishment"
    _inherit = ["mail.thread", "spm.branch.mixin", "approval.workflow.mixin"]

    name = fields.Char(default="New", copy=False)
    float_id = fields.Many2one(
        "spm.petty.cash.float", string="Float", required=True)
    date = fields.Date(default=fields.Date.context_today)
    amount = fields.Monetary(string="Amount")
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)

    def _approval_amount(self):
        self.ensure_one()
        return self.amount


class SpmPettyCashVoucher(models.Model):
    _name = "spm.petty.cash.voucher"
    _description = "Petty Cash Disbursement Voucher"
    _inherit = ["mail.thread", "spm.branch.mixin", "approval.workflow.mixin"]

    name = fields.Char(default="New", copy=False)
    float_id = fields.Many2one(
        "spm.petty.cash.float", string="Float", required=True)
    date = fields.Date(default=fields.Date.context_today)
    payee_type = fields.Selection(
        [("employee", "Employee"), ("vendor", "Vendor"), ("other", "Other")],
        default="employee")
    partner_id = fields.Many2one("res.partner", string="Payee")
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    line_ids = fields.One2many(
        "spm.petty.cash.voucher.line", "voucher_id", string="Lines")
    amount_total = fields.Monetary(
        compute="_compute_amount_total", store=True, string="Total")
    over_budget = fields.Boolean()

    @api.depends("line_ids.price_total")
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped("price_total"))

    def _approval_amount(self):
        self.ensure_one()
        return self.amount_total


class SpmPettyCashVoucherLine(models.Model):
    _name = "spm.petty.cash.voucher.line"
    _description = "Petty Cash Voucher Line"

    voucher_id = fields.Many2one(
        "spm.petty.cash.voucher", required=True, ondelete="cascade")
    category_id = fields.Many2one("spm.expense.category", string="Category")
    expense_type_id = fields.Many2one(related="category_id.type_id", store=True)
    expense_category_id = fields.Many2one(related="category_id", store=True)
    description = fields.Char()
    currency_id = fields.Many2one(related="voucher_id.currency_id", store=True)
    price_unit = fields.Monetary(string="Amount")
    tax_ids = fields.Many2many("account.tax", string="Taxes")
    price_total = fields.Monetary(
        compute="_compute_price_total", store=True, string="Total")

    @api.depends("price_unit")
    def _compute_price_total(self):
        for line in self:
            line.price_total = line.price_unit


class SpmPettyCashRecon(models.Model):
    _name = "spm.petty.cash.recon"
    _description = "Petty Cash Reconciliation"
    _inherit = ["mail.thread", "spm.branch.mixin", "approval.workflow.mixin"]

    name = fields.Char(default="New", copy=False)
    float_id = fields.Many2one(
        "spm.petty.cash.float", string="Float", required=True)
    date = fields.Date(default=fields.Date.context_today)
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    counted_amount = fields.Monetary(string="Counted")
    book_amount = fields.Monetary(string="Book Balance")
    variance = fields.Monetary(compute="_compute_variance", store=True)

    @api.depends("counted_amount", "book_amount")
    def _compute_variance(self):
        for rec in self:
            rec.variance = rec.counted_amount - rec.book_amount

    def _approval_amount(self):
        self.ensure_one()
        return abs(self.variance)
