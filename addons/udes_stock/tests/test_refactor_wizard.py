# -*- coding: utf-8 -*-
from . import common


class TestRefactorWizard(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        """Setup test picks"""
        super(TestRefactorWizard, cls).setUpClass()
        cls.Picking = cls.env["stock.picking"]
        # Picking config
        cls.picking_type_pick.write(
            {
                "u_post_assign_action": "group_by_move_key",
                "u_move_key_format": "{location_dest_id.id}",
            }
        )
        cls.picking_type_pick.u_auto_unlink_empty = True

        # Create quants and pickings
        cls.create_quant(cls.apple.id, cls.test_location_01.id, 20)
        cls.create_quant(cls.banana.id, cls.test_location_01.id, 10)
        cls.batch01 = cls.create_batch()
        product_info_1 = [{"product": cls.apple, "qty": 5}]
        product_info_2 = [{"product": cls.apple, "qty": 10}, {"product": cls.banana, "qty": 10}]
        cls.pick_1 = cls.create_picking(
            cls.picking_type_pick, products_info=product_info_1, batch_id=cls.batch01.id
        )
        cls.pick_2 = cls.create_picking(
            cls.picking_type_pick,
            products_info=product_info_2,
            batch_id=cls.batch01.id,
            location_dest_id=cls.test_output_location_02.id,
        )

        (cls.pick_1 | cls.pick_2).action_assign()

        # Get the move_ids for later use
        cls.pick_1_move_ids = cls.pick_1.mapped("move_lines.id")
        cls.pick_2_move_ids = cls.pick_2.mapped("move_lines.id")

        # Change the destination location id for pick_2 to the same as pick_1 so it
        # can be refactored in the tests
        cls.pick_2.write({"location_dest_id": cls.pick_1.location_dest_id.id})

    def _is_refactored_correctly(self):
        """Helper to check that the picks in the setup have been refactored as expected"""

        # Check that everything is refactored correctly, i.e. we have one picking.
        # The pickings are merged, so pick_2 becomes empty
        self.assertTrue(self.pick_1.exists())
        self.assertFalse(self.pick_2.exists())
        refactored_picks = self.Picking.search(
            [("picking_type_id", "=", self.picking_type_pick.id)]
        )
        self.assertEqual(refactored_picks, self.pick_1)

        # Check refactored pick
        self.assertEqual(len(refactored_picks), 1)
        self.assertEqual(len(refactored_picks.move_lines), 3)
        self.assertEqual(len(refactored_picks.move_line_ids), 3)
        self.assertEqual(
            refactored_picks.mapped("move_lines.id"), self.pick_1_move_ids + self.pick_2_move_ids
        )
        self.assertEqual(refactored_picks.batch_id, self.batch01)

    def test00_test_setup(self):
        """Check that the test setup is correct"""
        # Check each pick is as expected
        self.assertEqual(self.pick_1.state, "assigned")
        self.assertEqual(len(self.pick_1_move_ids), 1)
        self.assertEqual(len(self.pick_1.move_line_ids), 1)
        self.assertEqual(self.pick_1.batch_id, self.batch01)

        self.assertEqual(self.pick_2.state, "assigned")
        self.assertEqual(len(self.pick_2_move_ids), 2)
        self.assertEqual(len(self.pick_2.move_line_ids), 2)
        self.assertEqual(self.pick_2.batch_id, self.batch01)

    def test01_refactor_stock_move_wizard(self):
        """Check that you can do a manual refactor of stock moves in the UI"""
        # The refactor wizard in the UI
        RefactorWizard = self.env["stock.move.refactor.wizard"]

        # Mimic a refactor using the wizard in the UI
        wizard = RefactorWizard.with_context(active_ids=self.pick_2_move_ids).create({})
        wizard.do_refactor()

        # Use helper to check refactoring
        self._is_refactored_correctly()

    def test02_refactor_pickings_wizard(self):
        """Check that you can do a manual refactor of pickings in the UI"""
        # The refactor wizard in the UI
        RefactorWizard = self.env["stock.picking.refactor.wizard"]

        # Mimic a refactor using the wizard in the UI
        wizard = RefactorWizard.with_context(active_ids=self.pick_2.mapped("id")).create({})
        wizard.do_refactor()

        # Use helper to check refactoring
        self._is_refactored_correctly()

    def test03_refactor_batches_wizard(self):
        """Check that you can do a manual refactor of batches in the UI"""
        # The refactor wizard in the UI
        RefactorWizard = self.env["stock.picking.batch.refactor.wizard"]

        # Change the state of the batch into waiting so that any empty picking is kicked
        # out of the batch and we can test it is unlinked
        self.batch01.mark_as_todo()

        # Mimic a refactor using the wizard in the UI
        batch_ids = self.pick_2.mapped("batch_id.id")
        wizard = RefactorWizard.with_context(active_ids=batch_ids).create({})
        wizard.do_refactor()

        # Use helper to check refactoring
        self._is_refactored_correctly()
