from odoo.addons.udes_stock.tests import common


class TestStockPickingBatch(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockPickingBatch, cls).setUpClass()
