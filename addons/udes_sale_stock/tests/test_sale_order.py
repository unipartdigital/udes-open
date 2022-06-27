from odoo.addons.udes_stock.tests import common
from odoo import fields


class TestSaleOrder(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestSaleOrder, cls).setUpClass()
        # Unlink the TestGoodsOut pull_push rule as it was causing the route to misbehave. 
        # The rule was not being triggered when a sale order was created in the customer location i.e.
        # no pickings were being created for GoodsOut or Pick.
        # Add in the final step to the route which links customers and the warehouse i.e. Trailer Dispatch rule
        Rule = cls.env["stock.rule"]
        cls.Picking = cls.env["stock.picking"]

        Rule.search([("name", "=", "TestGoodsOut")]).unlink()
        cls.rule_out = Rule.create(
            {
                "name": "TestTrailer",
                "route_id": cls.route_out.id,
                "picking_type_id": cls.picking_type_trailer_dispatch.id,
                "location_id": cls.picking_type_trailer_dispatch.default_location_dest_id.id,
                "location_src_id": cls.picking_type_trailer_dispatch.default_location_src_id.id,
                "action": "pull",
                "procure_method": "make_to_order",
            }
        )

    def test_all_created_pickings_are_attached_to_sale_order(self):
        """
        Create the sale order for a single product. Check all the pickings created due to sale order are attached to the sale order.
        """
        sale_order = self._create_sale_order(self.apple.id, 10)
        sale_order.action_confirm()

        all_created_pickings = self.Picking.search([])
        for created_picking in all_created_pickings:
            with self.subTest(created_picking=created_picking):
                self.assertIn(created_picking, sale_order.picking_ids)

    def test_all_pickings_created_by_sale_order_are_cancelled(self):
        """
        Create a sale order for a single product, then cancel the sale order. Check all the pickings created due to the sale order are cancelled.
        """
        sale_order = self._create_sale_order(self.apple.id, 10)
        sale_order.action_confirm()

        all_created_pickings = self.Picking.search([])
        sale_order.action_cancel()

        for picking in all_created_pickings:
            with self.subTest(picking=picking):
                self.assertEqual(picking.state, "cancel")

    def test_only_moves_created_by_sale_order_are_cancelled(self):
        """
        Create multiple sale orders for a single product, mimic refactoring by merging the pickings.
        Then cancel one of the sale orders and check that then entire merged picking is not cancelled,
        only the moves associated with the cancelled sale order are cancelled.
        """
        Move = self.env["stock.move"]

        first_sale_order = self._create_sale_order(self.apple.id, 10)
        first_sale_order.action_confirm()
        first_picking = self.Picking.search([("picking_type_id", "=", self.picking_type_pick.id)])
        first_move = first_picking.move_lines

        second_sale_order = self._create_sale_order(self.apple.id, 5)
        second_sale_order.action_confirm()
        second_picking = self.Picking.search(
            [("picking_type_id", "=", self.picking_type_pick.id), ("id", "!=", first_picking.id)]
        )
        second_move = Move.search(
            [("picking_type_id", "=", self.picking_type_pick.id), ("id", "!=", first_move.id)]
        )

        created_picks = self.Picking.search([("picking_type_id", "=", self.picking_type_pick.id)])
        self.assertEqual(len(created_picks), 2)
        second_picking.move_lines.write({"picking_id": first_picking.id})
        self.assertEqual(len(first_picking.move_lines), 2)

        second_sale_order.action_cancel()
        self.assertEqual(second_move.state, "cancel")
    
    def _create_sale_order(self, product_id, product_uom_qty):
        """
        Create a sale order for a product_id
        """
        SaleOrder = self.env["sale.order"]
        SaleOrderLine = self.env["sale.order.line"]

        partner = self.env.ref("base.partner_admin")
        datetime_now = fields.Datetime.now()
        sale_order = SaleOrder.create(
            {
                "partner_id": partner.id,
                "client_order_ref": "sale order",
                "commitment_date": datetime_now,
                "requested_date": datetime_now,
            }
        )
        SaleOrderLine.create(
            {"order_id": sale_order.id, "product_id": product_id, "product_uom_qty": product_uom_qty}
        )
        return sale_order


