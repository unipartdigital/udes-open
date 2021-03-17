"""Tests for manual sale order line cancellation"""
from odoo.exceptions import ValidationError

from . import common


class TestManualSaleOrderLineCancellation(common.BaseSaleUDES):
    """Tests for manual sale order line cancellation"""

    @classmethod
    def setUpClass(cls):
        super(TestManualSaleOrderLineCancellation, cls).setUpClass()

        cls.apple_quant = cls.create_quant(
            cls.apple.id, cls.test_location_01.id, 30, package_id=cls.create_package().id,
        )
        cls.banana_quant = cls.create_quant(
            cls.banana.id, cls.test_location_02.id, 30, package_id=cls.create_package().id,
        )

        # Create sale order
        sale = cls.create_sale(cls.customer)
        cls.apple_sale_line = cls.create_sale_line(sale, cls.apple, 15, route_id=cls.route_out.id)
        cls.banana_sale_line = cls.create_sale_line(sale, cls.banana, 15, route_id=cls.route_out.id)
        sale.action_confirm()
        cls.sale = sale
        cls.sale.warehouse_id.u_allow_manual_sale_order_line_cancellation = True

        cls.first_picking = sale.picking_ids.filtered(lambda p: p.state == "assigned")

    def test01_not_allowed_by_warehouse_config(self):
        """Test that cancellation is rejected if the warehouse config does not allow it"""
        self.sale.warehouse_id.u_allow_manual_sale_order_line_cancellation = False
        with self.assertRaises(ValidationError) as e:
            self.apple_sale_line.ui_is_cancelled = True
        self.assertEqual(
            e.exception.name,
            "Manual cancellation of individual order lines is not "
            "allowed by the warehouse config",
        )

    def test02_cancellation(self):
        """Test cancellation of a sale order line"""
        self.apple_sale_line.ui_is_cancelled = True

        # The apple sale order line should be cancelled
        self.assertTrue(self.apple_sale_line.is_cancelled)
        self.assertEqual({"cancel"}, set(self.apple_sale_line.move_ids.mapped("state")))

        # The banana sale order line should still be processable
        self.assertEqual(self.sale.state, "sale")
        self.assertFalse(self.banana_sale_line.is_cancelled)
        self.assertEqual(
            {"assigned", "waiting"}, set(self.banana_sale_line.move_ids.mapped("state"))
        )
        self.assertEqual(
            {"assigned", "waiting"}, set(self.banana_sale_line.move_ids.mapped("picking_id.state"))
        )

    def test03_cannot_uncancel(self):
        """Test that uncancellation of a sale order line is not allowed"""
        self.apple_sale_line.ui_is_cancelled = True
        with self.assertRaises(ValidationError) as e:
            self.apple_sale_line.ui_is_cancelled = False
        self.assertEqual(
            e.exception.name, "Cannot uncancel order lines: %s" % (self.apple.name,),
        )

    def test04_cannot_cancel_with_completed_picking(self):
        """Test that cancellation of a sale order line with a completed picking is not allowed"""
        for move_line in self.first_picking.move_line_ids:
            move_line.write(
                {
                    "qty_done": move_line.product_uom_qty,
                    "location_dest_id": self.test_output_location_01.id,
                }
            )
        self.first_picking.action_done()
        self.assertEqual(self.first_picking.state, "done")

        with self.assertRaises(ValidationError) as e:
            self.apple_sale_line.ui_is_cancelled = True
        self.assertEqual(
            e.exception.name,
            "Cannot cancel order lines with pickings in progress: %s" % (self.apple.name,),
        )

    def test05_cannot_cancel_with_assigned_batch(self):
        """Test that cancellation of a sale order line with an in progress batch is not allowed"""
        Batch = self.env["stock.picking.batch"]

        # Put the first picking in a batch and assign it to a user
        batch = Batch.create({})
        self.first_picking.batch_id = batch
        batch.mark_as_todo()
        batch.user_id = self.outbound_user
        self.assertEqual(batch.state, "in_progress")

        with self.assertRaises(ValidationError) as e:
            self.apple_sale_line.ui_is_cancelled = True
        self.assertEqual(
            e.exception.name,
            "Cannot cancel order lines with pickings in progress: %s" % (self.apple.name,),
        )

    def test06_cannot_cancel_with_quantity_done(self):
        """Test that cancellation of a sale order line with an in progress picking is not allowed

        Pickings are considered in progress if any of their move lines have been
        partially or fully picked.
        """
        move_lines = self.first_picking.move_line_ids
        banana_move_line = move_lines.filtered(lambda ml: ml.product_id == self.banana)
        banana_move_line.qty_done = 1

        with self.assertRaises(ValidationError) as e:
            self.apple_sale_line.ui_is_cancelled = True
        self.assertEqual(
            e.exception.name,
            "Cannot cancel order lines with pickings in progress: %s" % (self.apple.name,),
        )

    def test07_can_cancel_full_line_backorder(self):
        """Test that cancellation of a backordered full sale order line is allowed"""
        # Pick only bananas and backorder all the apples for the first picking
        move_lines = self.first_picking.move_line_ids
        banana_move_line = move_lines.filtered(lambda ml: ml.product_id == self.banana)
        banana_move_line.write(
            {
                "qty_done": banana_move_line.product_uom_qty,
                "location_dest_id": self.test_output_location_01.id,
            }
        )
        self.first_picking.action_done()
        self.assertEqual(self.first_picking.state, "done")

        # No ValidationError should be raised
        self.apple_sale_line.ui_is_cancelled = True
        self.assertTrue(self.apple_sale_line.is_cancelled)

    def test08_cannot_cancel_split_line_backorder(self):
        """Test that cancellation of a backordered partial sale order line is not allowed"""
        # Pick a single apple for the first picking and backorder the rest
        move_lines = self.first_picking.move_line_ids
        apple_move_line = move_lines.filtered(lambda ml: ml.product_id == self.apple)
        apple_move_line.write(
            {"qty_done": 1, "location_dest_id": self.test_output_location_01.id}
        )
        self.first_picking.action_done()
        self.assertEqual(self.first_picking.state, "done")
        self.assertTrue(self.first_picking.u_created_back_orders)

        with self.assertRaises(ValidationError) as e:
            self.apple_sale_line.ui_is_cancelled = True
        self.assertEqual(
            e.exception.name,
            "Cannot cancel order lines with pickings in progress: %s" % (self.apple.name,),
        )
