from . import common


class TestCancelUnfulfillable(common.BaseSaleUDES):
    @classmethod
    def setUpClass(cls):
        super(TestCancelUnfulfillable, cls).setUpClass()
        cls.Sale = cls.env["sale.order"]

    def test01_test_cancel_in_order(self):
        """
        Test that sale order cancellation works as expected
        """

        quant = self.create_quant(
            self.apple.id, self.test_location_01.id, 30, package_id=self.create_package().id
        )
        quant2 = self.create_quant(
            self.cherry.id, self.test_location_01.id, 20, package_id=self.create_package().id
        )

        # Order 1
        sale = self.create_sale(self.customer, requested_date="2020-01-03")
        sale1l1 = self.create_sale_line(sale, self.apple, 15)
        sale1l2 = self.create_sale_line(sale, self.cherry, 2)

        # Order 2
        sale2 = self.create_sale(self.customer, requested_date="2020-01-04")
        sale2l1 = self.create_sale_line(sale2, self.apple, 10)
        sale2l2 = self.create_sale_line(sale2, self.cherry, 10)

        # Order 3
        sale3 = self.create_sale(self.customer, requested_date="2020-01-03")
        sale3l1 = self.create_sale_line(sale3, self.apple, 5)
        sale3l2 = self.create_sale_line(sale3, self.cherry, 8)

        # Confirm sales
        sales = sale | sale2 | sale3
        sales.action_confirm()

        # Cancel any without stock available
        self.Sale.cancel_orders_without_availability()

        # Unreserve moves, won't cancel sale lines with stock that is reserved
        sales.mapped("order_line.move_ids")._do_unreserve()

        # Verify all are confirmed
        self.assertTrue(all(x == "sale" for x in sales.mapped("state")))

        # Adjust quants and check availability again
        quant.quantity = 20
        quant2.quantity = 5
        self.Sale.cancel_orders_without_availability()

        self.assertEqual(sale.state, "sale")
        self.assertFalse(sale1l1.is_cancelled)
        self.assertFalse(sale1l2.is_cancelled)

        self.assertEqual(sale2.state, "cancel")
        self.assertTrue(sale2l1.is_cancelled)
        self.assertTrue(sale2l2.is_cancelled)

        self.assertEqual(sale3.state, "sale")
        self.assertFalse(sale3l1.is_cancelled)
        self.assertTrue(sale3l2.is_cancelled)

        # Adjust quants and check availability again
        quant.quantity = 14
        quant2.quantity = 2
        self.Sale.cancel_orders_without_availability()

        self.assertEqual(sale.state, "sale")
        self.assertTrue(sale1l1.is_cancelled)
        self.assertFalse(sale1l2.is_cancelled)

        self.assertEqual(sale2.state, "cancel")
        self.assertTrue(sale2l1.is_cancelled)
        self.assertTrue(sale2l2.is_cancelled)

        self.assertEqual(sale3.state, "sale")
        self.assertFalse(sale3l1.is_cancelled)
        self.assertTrue(sale3l2.is_cancelled)

        # Adjust quants and check availability again
        quant.quantity = 1
        quant2.quantity = 1
        self.Sale.cancel_orders_without_availability()

        # Check everything is cancelled
        self.assertTrue(all(x == "cancel" for x in sales.mapped("state")))
        self.assertTrue(all(sales.mapped("order_line.is_cancelled")))
