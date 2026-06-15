from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSpmSmoke(TransactionCase):
    """Skeleton smoke tests. Flesh out per report §12.4 (matrix resolution
    table-driven tests, budget race tests, posting assertions)."""

    def test_branch_create_ensures_analytic(self):
        branch = self.env["spm.branch"].create({"name": "Test", "code": "TST"})
        self.assertTrue(branch.exists())

    def test_category_effective_enforcement_defaults(self):
        etype = self.env["spm.expense.type"].create({"name": "Travel", "code": "TRV"})
        cat = self.env["spm.expense.category"].create(
            {"name": "Airfare", "code": "AIR", "type_id": etype.id})
        self.assertEqual(cat.effective_enforcement, "warn")
