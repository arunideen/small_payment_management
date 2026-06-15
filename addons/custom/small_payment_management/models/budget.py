from odoo import api, fields, models


class SpmBudget(models.Model):
    _name = "spm.budget"
    _description = "Operational Budget"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company)
    branch_id = fields.Many2one("spm.branch", string="Branch")
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"),
         ("done", "Done"), ("closed", "Closed")],
        default="draft", tracking=True)
    line_ids = fields.One2many("spm.budget.line", "budget_id", string="Lines")


class SpmBudgetLine(models.Model):
    _name = "spm.budget.line"
    _description = "Operational Budget Line"

    budget_id = fields.Many2one(
        "spm.budget", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="budget_id.company_id", store=True)
    branch_id = fields.Many2one(related="budget_id.branch_id", store=True)
    currency_id = fields.Many2one(related="budget_id.currency_id", store=True)
    type_id = fields.Many2one("spm.expense.type", string="Expense Type")
    category_id = fields.Many2one("spm.expense.category", string="Category")
    period_start = fields.Date()
    period_end = fields.Date()
    planned_amount = fields.Monetary(string="Planned")
    reserved = fields.Monetary(
        compute="_compute_amounts", string="Reserved", store=False)
    utilized = fields.Monetary(
        compute="_compute_amounts", string="Utilized", store=False)
    available = fields.Monetary(
        compute="_compute_amounts", string="Available", store=False)
    utilization_pct = fields.Float(
        compute="_compute_amounts", string="Utilization %", store=False)

    @api.depends("planned_amount")
    def _compute_amounts(self):
        # TODO: sum reservation ledger (reserved) + posted analytic (utilized).
        for line in self:
            line.reserved = 0.0
            line.utilized = 0.0
            line.available = line.planned_amount
            line.utilization_pct = 0.0

    @api.model
    def _find(self, company, branch, type_id, category_id, date):
        """Locate the budget line for a (company, branch, cat/type, date) tuple
        (report §8.3). Returns an empty recordset when none matches."""
        domain = [
            ("company_id", "=", company.id),
            ("period_start", "<=", date),
            ("period_end", ">=", date),
        ]
        if branch:
            domain.append(("branch_id", "=", branch.id))
        if category_id:
            domain.append(("category_id", "=", category_id.id))
        elif type_id:
            domain.append(("type_id", "=", type_id.id))
        return self.search(domain, limit=1)


class SpmBudgetReservation(models.Model):
    _name = "spm.budget.reservation"
    _description = "Budget Reservation Ledger"

    budget_line_id = fields.Many2one(
        "spm.budget.line", required=True, ondelete="cascade")
    res_model = fields.Char(index=True)
    res_id = fields.Integer(index=True)
    amount = fields.Monetary()
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    state = fields.Selection(
        [("reserved", "Reserved"), ("consumed", "Consumed"),
         ("released", "Released")],
        default="reserved")
