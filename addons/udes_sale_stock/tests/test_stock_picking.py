from . import common


class TestStockPicking(common.BaseSaleUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockPicking, cls).setUpClass()

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
        cls.sale = cls.create_sale(cls.customer, requested_date="2020-01-03")
        cls.apple_sale_line = cls.create_sale_line(cls.sale, cls.apple, 15)
        cls.banana_sale_line = cls.create_sale_line(cls.sale, cls.banana, 15)
        cls.sale.action_confirm()

        # Get the assigned pickings
        cls.pickings = cls.sale.picking_ids.filtered(lambda x: x.state == "assigned")

    def test_doesnt_warn_picking_any_previous_pickings_not_complete_sale(self):
        """Test that no warning message is generated when all pickings
        are at the same stage.
        """
        self.assertFalse(
            self.pickings[0].warn_picking_any_previous_pickings_not_complete_sale(),
            "Assert we don't get a warning when all pickings are in the same state"
        )
        self.assertFalse(
            self.pickings[1].warn_picking_any_previous_pickings_not_complete_sale(),
            "Assert we don't get a warning when all pickings are in the same state"
        )

    def test_warn_picking_any_previous_pickings_not_complete_sale(self):
        """Test that a warning message is generated when not all pickings
        are at the same stage.
        """
        # Set the state of a picking to waiting rather than assigned
        self.pickings[0].state = "waiting"
        self.assertEqual(self.pickings[1].state, "assigned")

        message = self.pickings[1].warn_picking_any_previous_pickings_not_complete_sale()

        self.assertTrue(
            message,
            "Check we get a message with a warning that all pickings "
            "are not in the current state (or later)"
        )
        self.assertIsInstance(message, str)
