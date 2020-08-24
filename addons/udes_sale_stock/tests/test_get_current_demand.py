from . import common
from collections import defaultdict


class TestGetCurrentDemand(common.BaseSaleUDES):
    @classmethod
    def setUpClass(cls):
        super(TestGetCurrentDemand, cls).setUpClass()
        cls.Sale = cls.env["sale.order"]
        cls.SaleLine = cls.env["sale.order.line"]

    def test_01_get_current_demand(self):
        """
        Test that sale order cancellation works as expected
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 30)
        self.create_quant(self.cherry.id, self.test_location_01.id, 20)

        # Order 1
        sale = self.create_sale(self.customer, requested_date="2020-01-03")
        self.create_sale_line(sale, self.apple, 15)
        self.create_sale_line(sale, self.cherry, 2)

        # Order 2
        sale2 = self.create_sale(self.customer, requested_date="2020-01-04")
        self.create_sale_line(sale2, self.apple, 10)
        self.create_sale_line(sale2, self.cherry, 10)

        # Order 3
        sale3 = self.create_sale(self.customer, requested_date="2020-01-03")
        self.create_sale_line(sale3, self.apple, 5)
        sale3l2 = self.create_sale_line(sale3, self.cherry, 8)

        sales = sale | sale2 | sale3

        # Confirm sales one by one and check demand
        sale.action_confirm()
        demand = self.Sale.get_current_demand()
        self.assertEqual(demand[self.apple], 15)
        self.assertEqual(demand[self.cherry], 2)

        sale2.action_confirm()
        demand = self.Sale.get_current_demand()
        self.assertEqual(demand[self.apple], 25)
        self.assertEqual(demand[self.cherry], 12)

        sale3.action_confirm()
        demand = self.Sale.get_current_demand()
        self.assertEqual(demand[self.apple], 30)
        self.assertEqual(demand[self.cherry], 20)

        # Cancel a line and check demand
        sale3l2.action_cancel()
        demand = self.Sale.get_current_demand(self.cherry)
        self.assertEqual(demand[self.cherry], 12)

        # Complete pickings and confirm no further demand
        pickings = sales.mapped("order_line.move_ids.picking_id")
        pickings.action_assign()
        for ml in pickings.move_line_ids:
            ml.write({"qty_done": ml.product_uom_qty})
        pickings.action_done()
        demand = self.Sale.get_current_demand()
        self.assertEqual(demand, defaultdict(int))
