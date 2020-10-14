from odoo.exceptions import UserError

from odoo.addons.udes_delivery_control.tests import common


class TestDeliveryControlWorkflow(common.TestDeliveryControl):
    @classmethod
    def setUpClass(cls):
        super(TestDeliveryControlWorkflow, cls).setUpClass()

        cls.picking_type_goods_in = cls.env.ref("stock.picking_type_in")

    @classmethod
    def create_goods_in_picking_from_delivery_control(cls, picking, create_move=True, **kwargs):
        """
        Manually create and link a Goods In picking from supplied Delivery Control picking

        Create a move for 1 apple if create move flag set to True (default)

        Return the created Goods In picking
        """
        picking.ensure_one()

        picking_vals = {
            "name": "Goods In Pick",
            "u_delivery_control_picking_id": picking.id,
        }
        picking_vals.update(**kwargs)

        products_info = False
        if create_move:
            products_info = [{"product": cls.apple, "qty": 1}]

        goods_in_picking = cls.create_picking(
            cls.picking_type_goods_in, products_info=products_info, **picking_vals
        )
        picking.u_goods_in_picking_id = goods_in_picking

        return goods_in_picking

    def _assert_picking_state(self, picking, expected_state):
        """Assert that supplied picking's state matches the expected state"""
        picking.ensure_one()

        self.assertEqual(
            picking.state,
            expected_state,
            f"Picking '{picking.name}' should be in '{expected_state}' state",
        )

    def _assert_goods_in_picking(self, goods_in_picking, delivery_control_picking):
        """
        Assert that Goods In picking has been correctly setup by verifying the following:

        - Is in draft state
        - Has the right Picking Type set
        - Is linked to supplied Delivery Control picking
        - Has pulled across supplier from Delivery Control picking
        - Has pulled across origin from Delivery Control picking
        """
        self._assert_picking_state(goods_in_picking, "draft")

        self.assertEqual(
            goods_in_picking.picking_type_id,
            self.picking_type_goods_in,
            "Goods In picking should have the Goods In picking type",
        )
        self.assertEqual(
            goods_in_picking.u_delivery_control_picking_id,
            delivery_control_picking,
            "Goods In picking should be linked to Delivery Control picking",
        )

        fields_to_check_between_pickings = ["partner_id", "origin"]

        for field in fields_to_check_between_pickings:
            self.assertEqual(
                goods_in_picking[field],
                delivery_control_picking[field],
                f"Value for '{field}' should be {delivery_control_picking[field]}",
            )

    def test_assert_delivery_control_workflow_progresses_without_stock_moves(self):
        """
        Assert that a Delivery Control picking can progress to done without needing to add
        any Stock Moves
        """
        # Confirm Delivery Control picking - should go into assigned state (aka "Ready")
        self.delivery_control_picking.action_confirm()
        self._assert_picking_state(self.delivery_control_picking, "assigned")

        # Set Delivery Control picking to done using method used in the UI
        self.delivery_control_picking.button_validate()
        self._assert_picking_state(self.delivery_control_picking, "done")

    def test_assert_goods_in_generated_when_delivery_control_complete(self):
        """
        Assert that a Goods In picking is generated when a Delivery Control picking is completed,
        and is correctly setup
        """
        # Mark the Delivery Control picking as done
        self.delivery_control_picking.action_confirm()
        self.delivery_control_picking.action_done()
        self._assert_picking_state(self.delivery_control_picking, "done")

        # Assert that a Goods In picking was generated
        goods_in_picking = self.delivery_control_picking.u_goods_in_picking_id
        self.assertEqual(
            len(goods_in_picking),
            1,
            "Completed Delivery Control picking should have generated a Goods In picking",
        )

        # Assert that Goods In picking has been setup correctly
        self._assert_goods_in_picking(goods_in_picking, self.delivery_control_picking)

    def test_assert_duplicate_goods_in_not_generated(self):
        """
        When a Delivery Control picking is completed and it already has a linked Goods In picking,
        assert that no duplicate Goods In picking is generated
        """
        # Create Goods In picking and link it to Delivery Control picking
        goods_in_picking = self.create_goods_in_picking_from_delivery_control(
            self.delivery_control_picking
        )

        goods_in_search_domain = [("picking_type_id", "=", self.picking_type_goods_in.id)]
        goods_in_picking_count_before = self.Picking.search_count(goods_in_search_domain)

        # Mark the Delivery Control picking as done
        self.delivery_control_picking.action_confirm()
        self.delivery_control_picking.action_done()

        # Assert that the original Goods In picking was not replaced
        self.assertEqual(
            self.delivery_control_picking.u_goods_in_picking_id,
            goods_in_picking,
            "Delivery Control picking should not have a new Goods In picking",
        )

        # Assert that no new Goods In pickings were created
        goods_in_picking_count_after = self.Picking.search_count(goods_in_search_domain)
        self.assertEqual(
            goods_in_picking_count_before,
            goods_in_picking_count_after,
            "A new Goods In picking should not have been created",
        )

    def test_assert_goods_in_progress_dependant_on_completed_delivery_control(self):
        """
        Assert that a Goods In picking cannot be completed if it is linked to a pending
        Delivery Control picking
        """
        # Create Goods In picking and link it to Delivery Control picking
        goods_in_picking = self.create_goods_in_picking_from_delivery_control(
            self.delivery_control_picking
        )

        # Confirm Delivery Control picking
        self.delivery_control_picking.action_confirm()

        # Confirm Goods In picking - apple stock should be assigned
        goods_in_picking.action_confirm()
        self._assert_picking_state(goods_in_picking, "assigned")

        # Set Goods In move line quantity done values to match match requested quantity
        # Set destination location for move lines to Input/Received
        input_received_location = self.env.ref("udes_stock.location_input_received")
        for ml in goods_in_picking.move_line_ids:
            ml.qty_done = ml.product_uom_qty
            ml.location_dest_id = input_received_location

        # Attempt to complete the Goods In picking, and assert that relevant error is raised
        with self.assertRaisesRegex(
            UserError,
            f"Cannot validate {goods_in_picking.name} until all of its"
            " preceding pickings are done.",
        ):
            goods_in_picking.action_done()

        # Complete Delivery Control picking
        self.delivery_control_picking.action_done()

        # Note: Need to manually recompute pending as it doesn't get recomputed in the test
        goods_in_picking._compute_pending()

        # Complete the Goods In picking now that the Delivery Control picking is no longer pending
        goods_in_picking.action_done()
        self._assert_picking_state(goods_in_picking, "done")

    def test_assert_cancelling_delivery_control_cancels_goods_in(self):
        """
        Assert that cancelling a Delivery Control picking will also cancel linked Goods In picking
        """
        # Create Goods In picking and link it to Delivery Control picking
        goods_in_picking = self.create_goods_in_picking_from_delivery_control(
            self.delivery_control_picking
        )

        # Cancel Delivery Control picking
        self.delivery_control_picking.action_cancel()

        # Assert that both Delivery Control and Goods In picking have been cancelled
        self._assert_picking_state(self.delivery_control_picking, "cancel")
        self._assert_picking_state(goods_in_picking, "cancel")
