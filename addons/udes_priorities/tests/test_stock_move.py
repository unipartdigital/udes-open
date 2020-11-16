# -*- coding: utf-8 -*-

from . import common


class TestMove(common.BasePriorities):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.move_values = {
            "product_id": cls.apple.id,
            "product_uom": cls.apple.uom_id.id,
            "product_uom_qty": 5,
            "location_id": cls.picking_type_pick.default_location_src_id.id,
            "location_dest_id": cls.picking_type_pick.default_location_dest_id.id,
            "picking_type_id": cls.picking_type_pick.id,
        }

    def test_with_incorrect_value(self):
        Move = self.env["stock.move"].with_context(
            default_picking_type_id=self.picking_type_pick.id
        )

        with self.assertRaises(ValueError, msg="Allows invalid priority"):
            vals = self.move_values.copy()
            vals.update({"name": "normal stock move", "priority": self.normal.reference})
            Move.create(vals)

    def test_correct_picking_type_or_no_picking_type_is_valid(self):
        MoveType = self.env["stock.picking.type"]
        Move = self.env["stock.move"].with_context(
            default_picking_type_id=self.picking_type_pick.id
        )

        self.assertEqual(self.urgent.picking_type_ids, self.picking_type_pick)
        vals_urgent = self.move_values.copy()
        vals_urgent.update(
            {"name": "urgent stock move", "priority": self.urgent.reference,}
        )
        Move.create(vals_urgent)
        self.assertEqual(self.not_urgent.picking_type_ids, MoveType.browse())
        vals_not_urgent = self.move_values.copy()
        vals_not_urgent.update(
            {"name": "not urgent stock move", "priority": self.not_urgent.reference,}
        )
        Move.create(vals_not_urgent)
