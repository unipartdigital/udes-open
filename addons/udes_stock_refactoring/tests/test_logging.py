from odoo.addons.udes_stock.tests import common
from .test_refactoring import TestRefactoringBase
import inspect
import logging
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
        self.pick_1_move_ids = self.pick_1.move_lines.ids
        self.pick_2_move_ids = self.pick_2.move_lines.ids
        # Change the destination location id for pick_2 to the same as pick_1 so it
        # can be refactored in the tests
        self.pick_2.write({"location_dest_id": self.pick_1.location_dest_id.id})


    def test_logging_wizard(self):
        """
        Verify the correct log output is produced from a refactor done 
        through a manual wizard refactor
        """
        move_refactoring_wizard = self.create_refactoring_wizard(
            active_model="stock.move",
            active_ids=self.pick_2.move_lines.ids,
            wizard_class_name="stock.move.refactor.wizard",
        )

        with self.assertLogs("odoo.addons.udes_stock_refactoring.models.stock_move", level=logging.INFO) as cm:
             new_moves = move_refactoring_wizard.do_refactor()

        log_output = "\n".join(cm.output)

        pickings = new_moves.picking_id
        picking_info = [f"{pick.id}, {(pick.name)}" for pick in pickings]

        picking_types = new_moves.picking_type_id
        picking_type_info = ";".join(f"{pt.id}, {pt.name}" for pt in picking_types)   

        expected_logs = {
            "original_moves": f"Original moves: {sorted(self.pick_2_move_ids)}",
            "new_moves": f"New moves: {sorted(new_moves.ids)}",
            "move_lines": f"Move lines: {sorted(new_moves.move_line_ids.ids)}",
            "pickings": f"Pickings: {sorted(picking_info)}",
            "picking_type": f"Picking type: {picking_type_info}"
        }

        for label, expected in expected_logs.items():
            with self.subTest(check=label):
                self.assertIn(expected, log_output)


class TestRefactorLogging(common.BaseUDES):
    def setUp(self):
        self.Picking = self.env["stock.picking"]
        self.picking_type_pick.write(
            {
                "u_post_assign_action": "group_by_move_key",
                "u_move_key_format": "{location_dest_id.id}",
                "u_move_line_key_format": "{product_id.id}",
            }
        )

        self.create_quant(self.apple.id, self.test_stock_location_01.id, 30)
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 10)
        self.batch01 = self.create_batch()
        self.product_info_1 = [{"product": self.apple, "uom_qty": 5}]
        self.product_info_2 = [
            {"product": self.apple, "uom_qty": 10},
            {"product": self.banana, "uom_qty": 10},
        ]
        self.pick_1 = self.create_picking(
            self.picking_type_pick, 
            products_info=self.product_info_1, 
            batch_id=self.batch01.id
        )
        self.pick_2 = self.create_picking(
            self.picking_type_pick,
            products_info=self.product_info_2,
            batch_id=self.batch01.id,
            location_dest_id=self.test_goodsout_location_01.id,
        )

        (self.pick_1 | self.pick_2).action_confirm()
        (self.pick_1 | self.pick_2).action_assign()

        self.pick_2.write({"location_dest_id": self.pick_1.location_dest_id.id})

        self.moves = (self.pick_1 | self.pick_2).move_lines
    
    def test_refactor_logging(self):
        """
        Verify the correct log output is produced from _action_refactor on stock moves
        """
        
        with self.assertLogs("odoo.addons.udes_stock_refactoring.models.stock_move", level=logging.INFO) as cm:
            new_moves = (self.pick_1 | self.pick_2).move_lines._action_refactor()

        log_output = "\n".join(cm.output)
        pickings = new_moves.mapped("picking_id")
        picking_info = [f"{pick.id}, {(pick.name)}" for pick in pickings]

        picking_types = new_moves.picking_type_id
        picking_type_info = ";".join(f"{pt.id}, {pt.name}" for pt in picking_types)   

        expected_logs = {
            "original_moves": f"Original moves: {sorted(self.moves.ids)}",
            "new_moves": f"New moves: {sorted(new_moves.ids)}",
            "move_lines": f"Move lines: {sorted(new_moves.move_line_ids.ids)}",
            "pickings": f"Pickings: {sorted(picking_info)}",
            "picking_type": f"Picking type: {picking_type_info}"
        }

        for label, expected in expected_logs.items():
            with self.subTest(check=label):
                self.assertIn(expected, log_output)

