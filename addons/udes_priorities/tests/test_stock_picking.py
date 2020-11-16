# -*- coding: utf-8 -*-

from . import common


class TestPicking(common.BasePriorities):
    def test_picking_with_incorrect_value(self):
        Picking = self.env["stock.picking"].with_context(
            default_picking_type_id=self.picking_type_pick.id
        )

        with self.assertRaises(ValueError, msg="Allows invalid priority"):
            Picking.create({"priority": self.normal.reference})

    def test_correct_picking_type_or_no_picking_type_is_valid(self):
        PickingType = self.env["stock.picking.type"]
        Picking = self.env["stock.picking"].with_context(
            default_picking_type_id=self.picking_type_pick.id
        )

        self.assertEqual(self.urgent.picking_type_ids, self.picking_type_pick)
        Picking.create({"priority": self.urgent.reference})

        self.assertEqual(self.not_urgent.picking_type_ids, PickingType.browse())
        Picking.create({"priority": self.not_urgent.reference})

    def test_priority_after_adding_move_to_picking(self):
        Picking = self.env["stock.picking"].with_context(
            default_picking_type_id=self.picking_type_pick.id
        )
        Product = self.env["product.product"]
        Move = self.env["stock.move"]
        apple = Product.create(
            {"name": "Apple", "barcode": "bar-apple", "default_code": "APL", "type": "product",}
        )
        self.not_urgent.picking_type_ids = self.picking_type_pick
        self.assertEqual(self.not_urgent.picking_type_ids, self.picking_type_pick)
        pick = Picking.create({"priority": self.not_urgent.reference})
        self.assertEqual(pick.priority, self.not_urgent.reference)
        move = Move.create(
            {
                "product_id": apple.id,
                "name": apple.name,
                "product_uom": apple.uom_id.id,
                "product_uom_qty": 10,
                "location_id": self.picking_type_pick.default_location_src_id.id,
                "location_dest_id": self.picking_type_pick.default_location_dest_id.id,
                "priority": ""
            }
        )
        self.assertEqual(pick.priority, self.not_urgent.reference)
        move.picking_id = pick.id
        self.assertEqual(pick.priority, self.env.ref("udes_priorities.normal").reference)
