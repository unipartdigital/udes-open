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

    def test_can_obtain_priority_sequence(self):
        """The picking's priority's sequence can be read."""
        PickingType = self.env["stock.picking.type"]
        Picking = self.env["stock.picking"].with_context(
            default_picking_type_id=self.picking_type_pick.id
        )

        pickings = Picking.create({"priority": self.not_urgent.reference})
        pickings |= Picking.create({"priority": self.urgent.reference})

        for sequence, picking in zip([2, 0], pickings.sorted(key=lambda p: p.id)):
            with self.subTest(priority=picking.priority):
                self.assertEqual(picking.u_priority_sequence, sequence)

    def test_updates_priority_sequence_if_priority_is_updated(self):
        """The priority sequence will update if the priority is changed."""
        PickingType = self.env["stock.picking.type"]
        Picking = self.env["stock.picking"].with_context(
            default_picking_type_id=self.picking_type_pick.id
        )

        picking = Picking.create({"priority": self.not_urgent.reference})

        self.assertEqual(picking.u_priority_sequence, self.not_urgent.sequence)

        picking.priority = self.urgent.reference

        self.assertEqual(picking.u_priority_sequence, self.urgent.sequence)

    def test_updates_priority_sequence_if_updated_on_priority(self):
        """The priority sequence will update if the priority's sequence is changed."""
        PickingType = self.env["stock.picking.type"]
        Picking = self.env["stock.picking"].with_context(
            default_picking_type_id=self.picking_type_pick.id
        )

        picking = Picking.create({"priority": self.not_urgent.reference})

        self.assertEqual(picking.u_priority_sequence, self.not_urgent.sequence)

        new_sequence = 99
        self.not_urgent.sequence = 99

        self.assertEqual(picking.u_priority_sequence, new_sequence)

    def test_does_not_update_priority_on_cancelled_pickings(self):
        """The priority sequence on cancelled picks will not be changed."""
        expected_priority_sequence = self.not_urgent.sequence
        products_info = [{"product": self.apple, "qty": 2}]
        self.create_quant(self.apple.id, self.test_location_01.id, 2)
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=products_info,
            confirm=True,
            priority=self.not_urgent.reference,
        )

        self.assertEqual(picking.u_priority_sequence, expected_priority_sequence)

        picking.action_cancel()

        post_cancel_priority_sequence = picking.u_priority_sequence
        self.not_urgent.sequence = 99

        self.assertEqual(picking.u_priority_sequence, post_cancel_priority_sequence)

    def test_does_not_update_priority_on_done_pickings(self):
        """The priority sequence on completed picks will not be changed."""
        expected_priority_sequence = self.not_urgent.sequence
        products_info = [{"product": self.apple, "qty": 2}]
        self.create_quant(self.apple.id, self.test_location_01.id, 2)
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=products_info,
            confirm=True,
            assign=True,
            priority=self.not_urgent.reference,
        )

        self.assertEqual(picking.u_priority_sequence, expected_priority_sequence)

        for ml in picking.move_line_ids:
            ml.qty_done = ml.product_uom_qty
        picking.action_done()

        post_done_priority_sequence = picking.u_priority_sequence
        self.not_urgent.sequence = 99

        self.assertEqual(picking.u_priority_sequence, post_done_priority_sequence)
