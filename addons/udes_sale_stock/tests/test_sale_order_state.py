from . import common


class TestSaleOrderState(common.BaseSaleUDES):
    @classmethod
    def setUpClass(cls):
        super(TestSaleOrderState, cls).setUpClass()

        Customer = cls.env["res.partner"]

        cls.customer = Customer.create(
            {
                "name": "Bob",
                "street": "1 Bobs House",
                "street2": "Bobs street",
                "city": "The city of Bob",
                "zip": "EN1 4LS",
            }
        )

        cls.apple_quant = cls.create_quant(
            cls.apple.id,
            cls.test_location_01.id,
            30,
            package_id=cls.create_package().id,
        )
        cls.banana_quant = cls.create_quant(
            cls.banana.id,
            cls.test_location_02.id,
            30,
            package_id=cls.create_package().id,
        )

        # Create sale order
        sale = cls.create_sale(cls.customer, requested_date="2020-01-03")
        cls.apple_sale_line = cls.create_sale_line(sale, cls.apple, 15)
        cls.banana_sale_line = cls.create_sale_line(sale, cls.banana, 15)
        sale.action_confirm()
        cls.sale = sale

        cls.first_picking = sale.picking_ids.filtered(lambda x: x.state == "assigned")
        assert cls.first_picking.u_next_picking_ids

    def complete_picking(self, picking):
        """
        Completes a picking.
        """
        Location = self.env["stock.location"]

        picking.ensure_one()

        # Select a non-view location as the destination
        dest_location = picking.location_dest_id
        if dest_location.usage == "view":
            dest_location = Location.search(
                [
                    ("id", "child_of", picking.location_dest_id.id),
                    ("usage", "=", "internal"),
                ]
            )[0]

        for ml in picking.move_line_ids:
            if ml.state == "assigned":
                ml.write(
                    {
                        "qty_done": ml.product_uom_qty,
                        "location_dest_id": dest_location.id,
                    }
                )

        picking.action_done()
        self.assertEqual(picking.state, "done")

    def test01_test_done(self):
        """
        Test that a sale order is done when all its pickings have been
        completed.
        """
        # Complete the pickings in order
        picking = self.first_picking
        while picking:
            self.assertEqual(self.sale.state, "sale")
            self.assertFalse(self.apple_sale_line.is_cancelled)
            self.assertFalse(self.banana_sale_line.is_cancelled)

            # Complete the picking
            self.assertEqual(picking.state, "assigned")
            self.complete_picking(picking)
            self.assertEqual(picking.state, "done")

            picking = picking.u_next_picking_ids

        # Check that the sale order is done
        self.assertEqual(self.sale.state, "done")
        self.assertFalse(self.apple_sale_line.is_cancelled)
        self.assertFalse(self.banana_sale_line.is_cancelled)

    def test02_test_last_picking_cancelled(self):
        """
        Test that a sale order is cancelled when all but the final picking is
        complete and the final picking is cancelled.
        """
        # Complete all but the final picking in order
        picking = self.first_picking
        while picking.u_next_picking_ids:
            self.assertEqual(self.sale.state, "sale")
            self.assertFalse(self.apple_sale_line.is_cancelled)
            self.assertFalse(self.banana_sale_line.is_cancelled)

            # Complete the picking
            self.assertEqual(picking.state, "assigned")
            self.complete_picking(picking)
            self.assertEqual(picking.state, "done")

            picking = picking.u_next_picking_ids

        # Cancel the last picking
        last_picking = picking
        self.assertEqual(last_picking.state, "assigned")
        last_picking.action_cancel()
        self.assertEqual(last_picking.state, "cancel")

        # Check that the sale order is cancelled
        self.assertEqual(self.sale.state, "cancel")
        self.assertTrue(self.apple_sale_line.is_cancelled)
        self.assertTrue(self.banana_sale_line.is_cancelled)

    def test03_test_some_pickings_cancelled(self):
        """
        Test that a sale order is done when at least one of the final pickings
        is complete even if there are other cancelled pickings.
        """
        self.banana_sale_line.action_cancel()

        # Complete the pickings in order
        # The chain should split after the first picking because of the
        # cancellation.
        pickings = self.first_picking
        while pickings:
            for picking in pickings.filtered(lambda x: x.state == "assigned"):
                self.assertEqual(self.sale.state, "sale")
                self.assertFalse(self.apple_sale_line.is_cancelled)
                self.assertTrue(self.banana_sale_line.is_cancelled)

                # Complete the picking
                self.assertEqual(picking.state, "assigned")
                self.complete_picking(picking)
                self.assertEqual(picking.state, "done")

            pickings = pickings.mapped("u_next_picking_ids")

        # Check that there are now two final pickings, one done and one
        # cancelled
        final_pickings = self.sale.picking_ids.filtered(
            lambda x: not x.u_next_picking_ids
        )
        self.assertEqual(len(final_pickings.filtered(lambda x: x.state == "done")), 1)
        self.assertEqual(len(final_pickings.filtered(lambda x: x.state == "cancel")), 1)

        # Check that the sale order is done
        self.assertEqual(self.sale.state, "done")
        self.assertFalse(self.apple_sale_line.is_cancelled)
        self.assertTrue(self.banana_sale_line.is_cancelled)
