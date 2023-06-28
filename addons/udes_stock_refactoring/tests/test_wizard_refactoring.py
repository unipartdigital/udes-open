from .test_refactoring import TestRefactoringBase
from ..registry.refactor_group_by_move_line_key import GroupByMoveLineKey
from odoo.tests import Form


class TestRefactoringWizard(TestRefactoringBase):
    def setUp(self):
        self.Picking = self.env["stock.picking"]
        # Picking config
        self.picking_type_pick.write(
            {
                "u_post_assign_action": "group_by_move_key",
                "u_move_key_format": "{location_dest_id.id}",
                "u_move_line_key_format": "{product_id.id}",
            }
        )
        self.picking_type_pick.u_auto_unlink_empty = True
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 30)
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 10)
        self.batch01 = self.create_batch()
        self.product_info_1 = [{"product": self.apple, "uom_qty": 5}]
        self.product_info_2 = [
            {"product": self.apple, "uom_qty": 10},
            {"product": self.banana, "uom_qty": 10},
        ]

        super(TestRefactoringWizard, self).setUp()

    def create_refactoring_wizard(
        self,
        active_model,
        active_ids,
        wizard_class_name,
        refactor_action=None,
    ):
        """Create and return refactoring wizard."""
        # We use a form to pass the context properly to the depends_context move_line_ids field
        context = {"active_model": active_model, "active_ids": active_ids}
        with Form(self.env[wizard_class_name].with_context(context)) as wizard_form:
            wizard_form.refactor_action = refactor_action
        wizard = wizard_form.save()
        return wizard


class TestDefaultRefactoringWizard(TestRefactoringWizard):
    def setUp(self):
        """Setup test picks for wizards default action of refactoring"""
        super(TestDefaultRefactoringWizard, self).setUp()

        self.pick_1 = self.create_picking(
            self.picking_type_pick, products_info=self.product_info_1, batch_id=self.batch01.id
        )
        self.pick_2 = self.create_picking(
            self.picking_type_pick,
            products_info=self.product_info_2,
            batch_id=self.batch01.id,
            location_dest_id=self.test_goodsout_location_01.id,
        )

        # Refactoring both pickings , but as they don't met the criteria to be merged
        # the only change will be group_id that will be added on both pickings
        (self.pick_1 | self.pick_2).action_assign()
        # Get the move_ids for later use
        self.pick_1_move_ids = self.pick_1.mapped("move_lines.id")
        self.pick_2_move_ids = self.pick_2.mapped("move_lines.id")
        # Change the destination location id for pick_2 to the same as pick_1 so it
        # can be refactored in the tests
        self.pick_2.write({"location_dest_id": self.pick_1.location_dest_id.id})

    def _is_default_refactored_correctly(self):
        """Helper to check that the picks in the setup have been refactored as expected"""

        # Check that everything is refactored correctly, i.e. we have one picking.
        # The pickings are merged, so pick_2 becomes empty
        self.assertTrue(self.pick_1.exists())
        self.assertFalse(self.pick_2.exists())
        refactored_picks = self.Picking.search(
            [("picking_type_id", "=", self.picking_type_pick.id), ("group_id", "!=", False)]
        )
        self.assertEqual(refactored_picks, self.pick_1)
        pick_moves_count = len(self.pick_1_move_ids + self.pick_2_move_ids)
        # Check refactored pick
        self.assertEqual(len(refactored_picks), 1)
        self.assertEqual(len(refactored_picks.move_lines), pick_moves_count)
        self.assertEqual(len(refactored_picks.move_line_ids), pick_moves_count)
        self.assertEqual(
            refactored_picks.mapped("move_lines.id"), self.pick_1_move_ids + self.pick_2_move_ids
        )
        self.assertEqual(refactored_picks.batch_id, self.batch01)

    def test_default_refactoring_wizard_setup(self):
        """Check that the test wizard setup is correct"""
        # Check each pick is as expected
        self.assertEqual(self.pick_1.state, "assigned")
        self.assertEqual(len(self.pick_1_move_ids), 1)
        self.assertEqual(len(self.pick_1.move_line_ids), 1)
        self.assertEqual(self.pick_1.batch_id, self.batch01)
        self.assertEqual(self.pick_1.group_id.name, str(self.pick_1.location_dest_id.id))

        self.assertEqual(self.pick_2.state, "assigned")
        self.assertEqual(len(self.pick_2_move_ids), 2)
        self.assertEqual(len(self.pick_2.move_line_ids), 2)
        self.assertEqual(self.pick_2.batch_id, self.batch01)
        self.assertEqual(self.pick_2.group_id.name, str(self.test_goodsout_location_01.id))

    def test_default_refactoring_stock_move_wizard(self):
        """Check that you can do a manual refactor of stock moves in the UI"""
        move_refactoring_wizard = self.create_refactoring_wizard(
            active_model="stock.move",
            active_ids=self.pick_2_move_ids,
            wizard_class_name="stock.move.refactor.wizard",
        )
        move_refactoring_wizard.do_refactor()
        # Use helper to check refactoring
        self._is_default_refactored_correctly()

    def test_default_refactoring_pickings_wizard(self):
        """Check that you can do a manual refactor of pickings in the UI"""
        picking_refactoring_wizard = self.create_refactoring_wizard(
            active_model="stock.picking",
            active_ids=self.pick_2.mapped("id"),
            wizard_class_name="stock.picking.refactor.wizard",
        )
        picking_refactoring_wizard.do_refactor()
        # Use helper to check refactoring
        self._is_default_refactored_correctly()

    def test_default_refactoring_batches_wizard(self):
        """Check that you can do a manual refactor of batches in the UI"""
        batch_refactoring_wizard = self.create_refactoring_wizard(
            active_model="stock.picking.batch",
            active_ids=self.pick_2.mapped("batch_id.id"),
            wizard_class_name="stock.picking.batch.refactor.wizard",
        )
        # Change the state of the batch into waiting so that any empty picking is kicked
        # out of the batch and we can test it is unlinked
        # TODO mark_as_todo method has not been ported from udes11 into udes14
        # self.batch01.mark_as_todo()
        batch_refactoring_wizard.do_refactor()
        # Use helper to check refactoring
        self._is_default_refactored_correctly()


class TestCustomRefactoringWizard(TestRefactoringWizard):
    def setUp(self):
        """Setup test picks for wizards default action of refactoring"""
        super(TestCustomRefactoringWizard, self).setUp()

        self.pick_1 = self.create_picking(
            self.picking_type_pick, products_info=self.product_info_1, batch_id=self.batch01.id
        )
        self.pick_2 = self.create_picking(
            self.picking_type_pick,
            products_info=self.product_info_1,
            batch_id=self.batch01.id,
            location_dest_id=self.test_goodsout_location_01.id,
        )

        # Refactoring both pickings , but as they don't met the criteria to be merged
        # the only change will be group_id that will be added on both pickings
        (self.pick_1 | self.pick_2).action_assign()
        # Get the move_ids for later use
        self.pick_1_move_ids = self.pick_1.mapped("move_lines.id")
        self.pick_2_move_ids = self.pick_2.mapped("move_lines.id")
        # Change the destination location id for pick_2 to the same as pick_1 so it
        # can be refactored in the tests , this time refactoring will be for product
        self.pick_2.write({"location_dest_id": self.pick_1.location_dest_id.id})

    def _is_custom_refactored_correctly(self):
        """Helper to check that the picks in the setup have been refactored as expected"""

        # Check that everything is refactored correctly, i.e. we have one picking.
        # The pickings are merged into a new picking, so pick_1 and pick_2 becomes empty
        self.assertFalse(self.pick_1.exists())
        self.assertFalse(self.pick_2.exists())
        refactored_picks = self.Picking.search(
            [("picking_type_id", "=", self.picking_type_pick.id), ("group_id", "!=", False)]
        )
        pick_moves_count = len(self.pick_1_move_ids + self.pick_2_move_ids)
        # Check refactored pick
        self.assertEqual(len(refactored_picks), 1)
        self.assertEqual(len(refactored_picks.move_lines), pick_moves_count)
        self.assertEqual(len(refactored_picks.move_line_ids), pick_moves_count)
        self.assertEqual(
            refactored_picks.mapped("move_lines.id"), self.pick_1_move_ids + self.pick_2_move_ids
        )

    def test_default_refactoring_wizard_setup(self):
        """Check that the test wizard setup is correct"""
        # Check each pick is as expected
        self.assertEqual(self.pick_1.state, "assigned")
        self.assertEqual(len(self.pick_1_move_ids), 1)
        self.assertEqual(len(self.pick_1.move_line_ids), 1)
        self.assertEqual(self.pick_1.batch_id, self.batch01)
        self.assertEqual(self.pick_1.group_id.name, str(self.pick_1.location_dest_id.id))

        self.assertEqual(self.pick_2.state, "assigned")
        self.assertEqual(len(self.pick_2_move_ids), 1)
        self.assertEqual(len(self.pick_2.move_line_ids), 1)
        self.assertEqual(self.pick_2.batch_id, self.batch01)
        self.assertEqual(self.pick_2.group_id.name, str(self.test_goodsout_location_01.id))

    def test_custom_refactoring_stock_move_wizard(self):
        """Check that you can do a manual refactor of stock moves in the UI"""
        move_refactoring_wizard = self.create_refactoring_wizard(
            active_model="stock.move",
            active_ids=self.pick_1_move_ids + self.pick_2_move_ids,
            wizard_class_name="stock.move.refactor.wizard",
            refactor_action="group_by_move_line_key",
        )
        move_refactoring_wizard.do_refactor()
        # Use helper to check refactoring
        self._is_custom_refactored_correctly()

    def test_custom_refactoring_pickings_wizard(self):
        """Check that you can do a manual refactor of stock moves in the UI"""
        picking_refactoring_wizard = self.create_refactoring_wizard(
            active_model="stock.picking",
            active_ids=self.pick_1.mapped("id") + self.pick_2.mapped("id"),
            wizard_class_name="stock.picking.refactor.wizard",
            refactor_action="group_by_move_line_key",
        )
        picking_refactoring_wizard.do_refactor()
        # Use helper to check refactoring
        self._is_custom_refactored_correctly()
