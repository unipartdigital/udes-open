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
