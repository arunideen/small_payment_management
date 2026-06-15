from odoo import api, fields, models


class HrExpense(models.Model):
    _inherit = "hr.expense"

    branch_id = fields.Many2one("spm.branch", string="Branch")
    expense_type_id = fields.Many2one("spm.expense.type", string="Expense Type")
    expense_category_id = fields.Many2one(
        "spm.expense.category", string="Expense Category",
        domain="[('type_id', '=', expense_type_id)]")


class HrExpenseSheet(models.Model):
    _name = "hr.expense.sheet"
    _inherit = ["hr.expense.sheet", "approval.workflow.mixin"]

    branch_id = fields.Many2one("spm.branch", string="Branch")

    def _approval_amount(self):
        self.ensure_one()
        return self.total_amount

    def action_submit_sheet(self):
        """Route submission through the matrix engine (report §6.4).

        TODO: generate approval lines instead of the single manager approval;
        core ``action_approve`` should only be reachable from the last tier.
        """
        return super().action_submit_sheet()


class SpmAdvance(models.Model):
    _name = "spm.advance"
    _description = "Cash Advance"
    _inherit = ["mail.thread", "approval.workflow.mixin"]

    name = fields.Char(default="New", copy=False)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    branch_id = fields.Many2one("spm.branch", string="Branch")
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    amount = fields.Monetary(string="Amount")
    settled_amount = fields.Monetary(string="Settled")
    outstanding = fields.Monetary(
        compute="_compute_outstanding", store=True, string="Outstanding")

    @api.depends("amount", "settled_amount")
    def _compute_outstanding(self):
        for rec in self:
            rec.outstanding = rec.amount - rec.settled_amount

    def _approval_amount(self):
        self.ensure_one()
        return self.amount


class SpmReimbursementBatch(models.Model):
    _name = "spm.reimbursement.batch"
    _description = "Reimbursement Batch"
    _inherit = ["mail.thread"]

    name = fields.Char(default="New", copy=False)
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company)
    branch_id = fields.Many2one("spm.branch", string="Branch")
    date = fields.Date(default=fields.Date.context_today)
    sheet_ids = fields.Many2many("hr.expense.sheet", string="Expense Reports")
    state = fields.Selection(
        [("draft", "Draft"), ("paid", "Paid")], default="draft", tracking=True)
