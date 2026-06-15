from odoo import fields, models


class ApprovalInfoRequestWizard(models.TransientModel):
    _name = "approval.info.request.wizard"
    _description = "Request for Information Wizard"

    res_model = fields.Char()
    res_id = fields.Integer()
    question = fields.Text(required=True)
    target_id = fields.Many2one("res.users", string="Ask")
    attachment_required = fields.Boolean()

    def action_send(self):
        # TODO: create approval.info.request, pause SLA, notify target (§7.5).
        return {"type": "ir.actions.act_window_close"}


class ApprovalDelegateWizard(models.TransientModel):
    _name = "approval.delegate.wizard"
    _description = "Active-Approver Delegation Wizard"

    res_model = fields.Char()
    res_id = fields.Integer()
    delegate_to_id = fields.Many2one("res.users", string="Delegate To", required=True)
    reason = fields.Text(required=True)
    scope = fields.Selection(
        [("document", "This Document Only"), ("standing", "Create Standing Rule")],
        default="document")
    date_from = fields.Date()
    date_to = fields.Date()

    def action_delegate(self):
        # TODO: reassign the active line / create standing rule (§7.6b).
        return {"type": "ir.actions.act_window_close"}


class ApprovalAmendWizard(models.TransientModel):
    _name = "approval.amend.wizard"
    _description = "Approver Add/Remove Wizard"

    res_model = fields.Char()
    res_id = fields.Integer()
    mode = fields.Selection(
        [("add", "Add Approver"), ("remove", "Remove Approver")],
        default="add", required=True)
    user_id = fields.Many2one("res.users", string="Approver")
    position = fields.Selection(
        [("before", "Before Active Tier"),
         ("after", "After Active Tier"),
         ("end", "At the End"),
         ("parallel", "Parallel in Active Tier")],
        default="after")
    reason = fields.Text(required=True)

    def action_apply(self):
        # TODO: insert/tombstone line, guardrails + amendment log (§7.7).
        return {"type": "ir.actions.act_window_close"}
