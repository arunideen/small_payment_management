from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

APPROVER_TYPES = [
    ("user", "Specific User"),
    ("role", "Role"),
    ("group", "Group"),
]

LINE_STATES = [
    ("waiting", "Waiting"),
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("skipped", "Skipped"),
    ("escalated", "Escalated"),
    ("info_requested", "Info Requested"),
    ("delegated", "Delegated"),
    ("added", "Added"),
    ("removed", "Removed"),
]


class ApprovalMatrix(models.Model):
    _name = "approval.matrix"
    _description = "Approval Matrix"
    _order = "priority, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda s: s.env.company)
    model_id = fields.Many2one(
        "ir.model", string="Model", required=True, ondelete="cascade")
    amount_from = fields.Monetary(string="Amount From")
    amount_to = fields.Monetary(string="Amount To (0 = no upper bound)")
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    priority = fields.Integer(default=10, help="Specificity tie-breaker.")
    restart_policy = fields.Selection(
        [("restart", "Restart"), ("resume", "Resume")], default="restart")
    allow_active_approver_delegation = fields.Boolean(
        string="Allow Active-Approver Delegation")
    dimension_ids = fields.One2many(
        "approval.matrix.dimension", "matrix_id", string="Match Dimensions")
    line_ids = fields.One2many(
        "approval.matrix.line", "matrix_id", string="Tiers")

    def _specificity(self):
        """Number of non-empty matched dimensions (report §7.3)."""
        self.ensure_one()
        return len(self.dimension_ids)

    def _dimensions_match(self, record):
        """Stub: every declared dimension must match the record (report §7.3)."""
        self.ensure_one()
        # TODO: evaluate each dimension's field/operator/value against ``record``.
        return True


class ApprovalMatrixDimension(models.Model):
    _name = "approval.matrix.dimension"
    _description = "Approval Matrix Match Dimension"

    matrix_id = fields.Many2one(
        "approval.matrix", required=True, ondelete="cascade")
    field_name = fields.Char(string="Field", required=True)
    operator = fields.Selection(
        [("in", "in"), ("=", "=")], default="in")
    value_ref = fields.Char(string="Value(s)")


class ApprovalMatrixLine(models.Model):
    _name = "approval.matrix.line"
    _description = "Approval Matrix Tier"
    _order = "sequence, id"

    matrix_id = fields.Many2one(
        "approval.matrix", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    approver_type = fields.Selection(APPROVER_TYPES, default="role", required=True)
    role = fields.Selection(
        [("manager", "Document Owner's Manager"),
         ("dept_head", "Department Head"),
         ("branch_manager", "Branch Manager"),
         ("branch_finance", "Branch Finance"),
         ("finance_manager", "Company Finance Manager"),
         ("cfo", "CFO"),
         ("custom", "Custom Group")],
        string="Role")
    user_id = fields.Many2one("res.users", string="Fixed User")
    group_id = fields.Many2one("res.groups", string="Group")
    min_amount = fields.Monetary(string="Tier Applies Above")
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    approval_mode = fields.Selection(
        [("single", "Single"), ("all", "All"), ("quorum", "Quorum")],
        default="single")
    quorum = fields.Integer(default=1)
    can_edit_amount = fields.Boolean()
    can_request_info = fields.Boolean(default=True)
    sla_hours = fields.Float(string="SLA (hours)")


class ApprovalRequestLine(models.Model):
    _name = "approval.request.line"
    _description = "Approval Request Line (runtime)"
    _order = "res_model, res_id, sequence, id"

    # Generic link to any host record (mixin-driven, report §7.2).
    res_model = fields.Char(string="Document Model", required=True, index=True)
    res_id = fields.Integer(string="Document ID", required=True, index=True)
    matrix_id = fields.Many2one("approval.matrix", string="Matrix")
    sequence = fields.Integer(default=10)
    approver_id = fields.Many2one("res.users", string="Approver")
    role_label = fields.Char()
    state = fields.Selection(LINE_STATES, default="waiting", required=True)
    acted_date = fields.Datetime()
    comment = fields.Text()
    delegated_to_id = fields.Many2one("res.users", string="Delegated To")
    delegated_by_id = fields.Many2one("res.users", string="Delegated By")
    origin = fields.Selection(
        [("matrix", "Matrix"), ("admin_added", "Admin Added")],
        default="matrix")
    added_by_id = fields.Many2one("res.users", string="Added By")
    removed_by_id = fields.Many2one("res.users", string="Removed By")
    removal_reason = fields.Text()
    company_id = fields.Many2one(
        "res.company", default=lambda s: s.env.company)

    @api.model
    def _cron_escalate(self):
        """Escalate tiers pending beyond their SLA (report §7.4). Stub."""
        # TODO: reminders at 50%, escalate to manager at 100%.
        return True


class ApprovalDelegation(models.Model):
    _name = "approval.delegation"
    _description = "Approval Delegation Rule"

    delegator_id = fields.Many2one("res.users", required=True, string="Delegator")
    delegate_id = fields.Many2one("res.users", required=True, string="Delegate")
    date_from = fields.Date()
    date_to = fields.Date()
    model_ids = fields.Many2many("ir.model", string="Scope: Models")
    matrix_ids = fields.Many2many("approval.matrix", string="Scope: Matrices")
    amount_ceiling = fields.Monetary(string="Amount Ceiling")
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.company.currency_id)
    active = fields.Boolean(default=True)


class ApprovalInfoRequest(models.Model):
    _name = "approval.info.request"
    _description = "Approval Request for Information (RFI)"
    _inherit = ["mail.thread"]

    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    requested_by_id = fields.Many2one(
        "res.users", string="Asked By", default=lambda s: s.env.user)
    target_id = fields.Many2one("res.users", string="Asked To")
    question = fields.Text(required=True)
    answer = fields.Text()
    attachment_required = fields.Boolean()
    state = fields.Selection(
        [("open", "Open"), ("answered", "Answered"), ("withdrawn", "Withdrawn")],
        default="open", tracking=True)


class ApprovalAmendmentLog(models.Model):
    _name = "approval.amendment.log"
    _description = "Approval Amendment Log (append-only)"
    _order = "create_date desc"

    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    action_type = fields.Selection(
        [("rfi", "RFI"), ("delegate", "Delegation"),
         ("add", "Add Approver"), ("remove", "Remove Approver")],
        required=True)
    actor_id = fields.Many2one(
        "res.users", default=lambda s: s.env.user, string="Actor")
    affected_user_id = fields.Many2one("res.users", string="Affected User")
    from_state = fields.Char()
    to_state = fields.Char()
    reason = fields.Text()
    payload = fields.Text(help="JSON snapshot of the line before/after.")

    def unlink(self):
        raise UserError(_("Approval amendment log entries cannot be deleted."))


class ApprovalWorkflowMixin(models.AbstractModel):
    """Generic engine entry-point. Any model inherits it to be governed by the
    approval matrix (report §7, §15)."""

    _name = "approval.workflow.mixin"
    _description = "Approval Workflow Mixin"

    approval_line_ids = fields.One2many(
        "approval.request.line", compute="_compute_approval_lines",
        string="Approval Lines")
    current_approver_id = fields.Many2one(
        "res.users", compute="_compute_current_approver",
        string="Current Approver")
    approval_state = fields.Selection(
        [("draft", "Draft"),
         ("under_approval", "Under Approval"),
         ("info_requested", "Information Requested"),
         ("approved", "Approved"),
         ("rejected", "Rejected")],
        default="draft", tracking=True)

    def _compute_approval_lines(self):
        Line = self.env["approval.request.line"]
        for rec in self:
            rec.approval_line_ids = Line.search(
                [("res_model", "=", rec._name), ("res_id", "=", rec.id)])

    @api.depends("approval_line_ids.state")
    def _compute_current_approver(self):
        for rec in self:
            pending = rec.approval_line_ids.filtered(
                lambda line: line.state == "pending")[:1]
            rec.current_approver_id = pending.approver_id

    # ----- host-model hooks (override in the document model) -----
    def _approval_amount(self):
        """Amount used for matrix band selection. Override per document."""
        return 0.0

    def _run_policy_checks(self):
        """Policy / budget checks before chain generation. Override per host."""
        return True

    # ----- engine internals (stubs, full design report §7.3-7.4) -----
    def _resolve_matrix(self):
        self.ensure_one()
        base = [
            ("model_id.model", "=", self._name),
            ("company_id", "=", self.company_id.id),
            ("amount_from", "<=", self._approval_amount()),
        ]
        candidates = self.env["approval.matrix"].search(base).filtered(
            lambda m: (not m.amount_to or m.amount_to >= self._approval_amount())
            and m._dimensions_match(self))
        if not candidates:
            raise UserError(_(
                "No approval matrix is configured for this combination. "
                "Contact your workflow administrator."))
        return candidates.sorted(
            key=lambda m: (-m._specificity(), m.priority))[0]

    def _generate_approval_lines(self, matrix):
        # TODO: resolve roles -> users, apply standing delegations (§7.6).
        return self.env["approval.request.line"]

    def _activate_tier(self, sequence):
        # TODO: set tier pending, post mail.activity + email (§7.4).
        return True

    # ----- public actions -----
    def action_submit(self):
        for doc in self:
            doc._run_policy_checks()
            matrix = doc._resolve_matrix()
            doc._generate_approval_lines(matrix)
            doc._activate_tier(1)
            doc.approval_state = "under_approval"
        return True

    def action_request_info(self):
        # TODO: open approval.info.request.wizard (§7.5).
        raise UserError(_("Request for Information is not implemented yet."))

    def action_delegate(self):
        # TODO: open approval.delegate.wizard (§7.6b).
        raise UserError(_("Delegation is not implemented yet."))

    def action_amend_approvers(self):
        # TODO: open approval.amend.wizard (§7.7).
        raise UserError(_("Live amendment is not implemented yet."))
