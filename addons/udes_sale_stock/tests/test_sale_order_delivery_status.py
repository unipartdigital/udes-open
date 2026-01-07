from odoo.addons.udes_stock.tests import common
from odoo import fields
from datetime import datetime
from .common import BaseSaleUDES


class TestDeliveryStatusOfSaleOrder(common.BaseUDESPullOutboundRoute, BaseSaleUDES):

    @classmethod
    def setUpClass(cls):
        super(TestDeliveryStatusOfSaleOrder, cls).setUpClass()

        Location = cls.env["stock.location"]
        cls.customer = cls.create_partner(
            "Test Customer Outbound",
        )
        picking_zone = Location.create(
            {
                "name": "Picking Zone",
                "barcode": "PZVIEW",
                "usage": "view",
                "location_id": cls.warehouse.id,
            }
        )
        cls.pick_location = Location.create(
            {
                "name": "Pick Location 01",
                "barcode": "PZ1",
                "usage": "internal",
                "location_id": cls.stock_location.id,
            }
        )
        picking_zone2 = Location.create(
            {
                "name": "Picking Zone 2",
                "barcode": "PZ2VIEW",
                "usage": "view",
                "location_id": cls.warehouse.id,
            }
        )
        cls.pick_location_2 = Location.create(
            {
                "name": "Pick Location 02",
                "barcode": "PZ2",
                "usage": "internal",
                "location_id": cls.stock_location.id,
            }
        )
        cls.picking_type_pick.default_location_src_id = picking_zone
        cls.test_quant_apple = cls.create_quant(
            product_id=cls.apple.id,
            location_id=cls.pick_location.id,
            qty=100.0,
        )
        cls.test_quant_banana = cls.create_quant(
            product_id=cls.banana.id,
            location_id=cls.pick_location_2.id,
            qty=100.0,
        )
        cls.sale_line_route = cls.create_sale_line_route()
        cls.picking_type_pick2 = cls.picking_type_pick.copy(
            {"default_location_src_id": picking_zone2.id}
        )
        cls.no_stock_product = cls.create_product("no_stock_product")

    @classmethod
    def create_sale_line_route(cls):
        Route = cls.env["stock.location.route"]
        Rule = cls.env["stock.rule"]
        route_vals = {
            "name": "TestSaleLineRoute",
            "sequence": 10,
            "product_selectable": False,
            "warehouse_selectable": True,
            "sale_selectable": True,
            "warehouse_ids": [(6, 0, [cls.picking_type_goods_out.warehouse_id.id])],
            "u_pick_operation_type_ids": [(6, 0, [cls.picking_type_pick.id])],
            "u_pack_operation_type_ids": [(6, 0, [cls.picking_type_check.id])],
        }
        cls.sale_line_route = Route.create(route_vals)
        cls.pack_rule = Rule.create(
            {
                "name": "TestPickzone",
                "route_id": cls.sale_line_route.id,
                "picking_type_id": cls.picking_type_pick.id,
                "location_src_id": cls.pick_location.id,
                "location_id": cls.picking_type_pick.default_location_dest_id.id,
                "action": "push",
                "procure_method": "make_to_order",
            }
        )
        cls.goods_out_rule = Rule.create(
            {
                "name": "TestGoodsOut",
                "route_id": cls.sale_line_route.id,
                "picking_type_id": cls.picking_type_goods_out.id,
                "location_src_id": cls.picking_type_goods_out.default_location_src_id.id,
                "location_id": cls.picking_type_goods_out.default_location_dest_id.id,
                "action": "push",
                "procure_method": "make_to_order",
            }
        )
        cls.trailer_dispatch_rule = Rule.create(
            {
                "name": "TestDispatch",
                "route_id": cls.sale_line_route.id,
                "location_src_id": cls.picking_type_trailer_dispatch.default_location_src_id.id,
                "location_id": cls.picking_type_trailer_dispatch.default_location_dest_id.id,
                "picking_type_id": cls.picking_type_trailer_dispatch.id,
                "action": "push",
                "procure_method": "make_to_order",
            }
        )
        return cls.sale_line_route

    def test_u_delivery_line_state_set_to_allocated(self):
        """
        Test to check after pick picking reservation u_delivery_line_state and
        u_delivery_state set to "Allocated"
        """
        self.sale = self.create_sale(
            self.customer, client_order_ref="ORD1010", requested_date=datetime.now()
        )
        self.sale_line1 = self.create_sale_line(self.sale, self.apple, 1)
        self.sale_line2 = self.create_sale_line(self.sale, self.banana, 1)
        self.sale_line1.update({"route_id": self.sale_line_route.id})
        self.sale_line2.update({"route_id": self.sale_line_route.id})
        self.sale.action_confirm()
        pick_picking = self.sale.picking_ids.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )

        pick_picking.action_assign()
        self.assertEqual(self.sale_line1.u_delivery_line_state, "allocated")
        self.assertEqual(self.sale_line2.u_delivery_line_state, "allocated")
        self.assertEqual(self.sale.u_delivery_state, "allocated")

    def test_u_delivery_line_state_set_to_no_stock(self):
        """
        Test to check if an order lines has no on-hand(qty_available) quantity,
        order line's u_delivery_line_state is set "no_stock" and sales order's
        u_delivery_state is set to "no_stock" regardless if any other lines have
        any stock or not.
        """
        self.sale = self.create_sale(
            self.customer, client_order_ref="ORD1011", requested_date=datetime.now()
        )
        self.sale_line1 = self.create_sale_line(self.sale, self.apple, 1)
        self.sale_line2 = self.create_sale_line(self.sale, self.no_stock_product, 1)
        self.sale_line1.update({"route_id": self.sale_line_route.id})
        self.sale_line2.update({"route_id": self.sale_line_route.id})
        self.sale.action_confirm()
        self.assertEqual(self.sale_line1.u_delivery_line_state, "allocated")
        self.assertEqual(self.sale_line2.u_delivery_line_state, "no_stock")
        self.assertEqual(self.sale.u_delivery_state, "no_stock")

    def test_u_delivery_line_state_set_to_correct_state_linearly(self):
        """
        Start with creating and confirming sales order.
        Find and validate pickings separately. Once validated status should be updated
        as below.
        Pickings              : pick   -> pack(check) -> goods out -> trailer dispatch
                                |         |              |                |
        u_delivery_line_state : picked -> packed      -> packed    ->  done
        """
        self.sale = self.create_sale(
            self.customer, client_order_ref="ORD1012", requested_date=datetime.now()
        )
        self.sale_line1 = self.create_sale_line(self.sale, self.apple, 1)
        self.sale_line2 = self.create_sale_line(self.sale, self.banana, 1)
        self.sale_line1.update({"route_id": self.sale_line_route.id})
        self.sale_line2.update({"route_id": self.sale_line_route.id})
        self.sale.action_confirm()
        pick_picking = self.sale.picking_ids.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        pick_picking.action_assign()
        self.assertEqual(pick_picking.state, "assigned")
        pick_move_lines = pick_picking.move_line_ids.prepare(
            location_dest=self.test_check_location_01
        )
        for mls, mls_values in pick_move_lines.items():
            mls.mark_as_done(mls_values)
        pick_picking.validate_picking()
        self.assertEqual(self.sale_line1.u_delivery_line_state, "picked")
        self.assertEqual(self.sale_line2.u_delivery_line_state, "picked")
        self.assertEqual(self.sale.u_delivery_state, "picked")
        pack_picking = self.sale.picking_ids.filtered(
            lambda x: x.picking_type_id == self.picking_type_check
        )
        pack_picking.action_assign()
        self.assertEqual(pack_picking.state, "assigned")
        pick_move_lines = pack_picking.move_line_ids.prepare(
            location_dest=self.test_goodsout_location_01
        )
        for mls, mls_values in pick_move_lines.items():
            mls.mark_as_done(mls_values)
        pack_picking.validate_picking()
        self.assertEqual(self.sale_line1.u_delivery_line_state, "packed")
        self.assertEqual(self.sale_line2.u_delivery_line_state, "packed")
        self.assertEqual(self.sale.u_delivery_state, "packed")
        goods_out_picking = self.sale.picking_ids.filtered(
            lambda x: x.picking_type_id == self.picking_type_goods_out
        )
        goods_out_picking.action_assign()
        self.assertEqual(goods_out_picking.state, "assigned")
        pick_move_lines = goods_out_picking.move_line_ids.prepare(
            location_dest=self.test_trailer_location_01
        )
        for mls, mls_values in pick_move_lines.items():
            mls.mark_as_done(mls_values)
        goods_out_picking.validate_picking()
        self.assertEqual(self.sale_line1.u_delivery_line_state, "packed")
        self.assertEqual(self.sale_line2.u_delivery_line_state, "packed")
        self.assertEqual(self.sale.u_delivery_state, "packed")
        trailer_dispatch = self.sale.picking_ids.filtered(
            lambda x: x.picking_type_id == self.picking_type_trailer_dispatch
        )
        trailer_dispatch.action_assign()
        self.assertEqual(trailer_dispatch.state, "assigned")
        pick_move_lines = trailer_dispatch.move_line_ids.prepare(
            location_dest=self.env.ref("stock.stock_location_customers")
        )
        for mls, mls_values in pick_move_lines.items():
            mls.mark_as_done(mls_values)
        trailer_dispatch.validate_picking()
        self.assertEqual(self.sale_line1.u_delivery_line_state, "done")
        self.assertEqual(self.sale_line2.u_delivery_line_state, "done")
        self.assertEqual(self.sale.u_delivery_state, "done")

    def test_u_delivery_line_state_set_to_cancelled(self):
        """
        Test once sales order is cancelled u_delivery_line_state in all order lines
        and u_delivery_state on sale order are set to "Cancelled"
        """
        self.sale = self.create_sale(
            self.customer, client_order_ref="ORD1013", requested_date=datetime.now()
        )
        self.sale_line1 = self.create_sale_line(self.sale, self.apple, 1)
        self.sale_line2 = self.create_sale_line(self.sale, self.banana, 1)
        self.sale_line1.update({"route_id": self.sale_line_route.id})
        self.sale_line2.update({"route_id": self.sale_line_route.id})
        self.sale.action_cancel()
        self.assertEqual(self.sale_line1.u_delivery_line_state, "cancelled")
        self.assertEqual(self.sale_line2.u_delivery_line_state, "cancelled")
        self.assertEqual(self.sale.u_delivery_state, "cancelled")
        self.assertEqual(self.sale.state, "cancel")

    def test_u_delivery_line_state_set_to_correct_state_with_multiple_picks(self):
        """
        Start with creating and confirming a sales order with two order lines.
        Validate pick picking partially to generate a back order.
        Now we have two pick pickings. First pick picking is in done state and second
        backorder pick picking is in assigned state.
        Check after validating first pick picking u_delivery_line_state moves to "Picked"
        state and sales order u_delivery_state remains in the "Allocated" state as second
        back order pick picking is yet to validate.
        After back order pick picking validation u_delivery_line_state and u_delivery_state
        should move to "Picked" state
        """
        self.sale = self.create_sale(
            self.customer, client_order_ref="ORD1014", requested_date=datetime.now()
        )
        self.sale_line1 = self.create_sale_line(self.sale, self.apple, 2)
        self.sale_line2 = self.create_sale_line(self.sale, self.banana, 1)
        self.sale_line1.update({"route_id": self.sale_line_route.id})
        self.sale_line2.update({"route_id": self.sale_line_route.id})
        self.sale.action_confirm()
        pick_picking = self.sale.picking_ids.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        pick_picking.action_assign()
        self.assertEqual(pick_picking.state, "assigned")
        pick_move_lines = pick_picking.move_line_ids.prepare(
            location_dest=self.test_check_location_01,
            product_ids=[{"barcode": self.sale_line1.product_id.barcode, "uom_qty": 2}],
        )
        for mls, mls_values in pick_move_lines.items():
            mls.mark_as_done(mls_values)
        pick_picking.validate_picking(create_backorder=True)
        self.assertEqual(self.sale_line1.u_delivery_line_state, "picked")
        self.assertEqual(self.sale_line2.u_delivery_line_state, "allocated")
        self.assertEqual(self.sale.u_delivery_state, "allocated")
        back_order = self.env["stock.picking"].search([("backorder_id", "=", pick_picking.id)])
        self.assertEqual(len(back_order), 1)
        back_order.action_assign()
        self.assertEqual(back_order.state, "assigned")
        pick_move_lines = back_order.move_line_ids.prepare(
            location_dest=self.test_check_location_01,
        )
        for mls, mls_values in pick_move_lines.items():
            mls.mark_as_done(mls_values)
        back_order.validate_picking()
        self.assertEqual(self.sale_line1.u_delivery_line_state, "picked")
        self.assertEqual(self.sale_line2.u_delivery_line_state, "picked")
        self.assertEqual(self.sale.u_delivery_state, "picked")
