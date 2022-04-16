import unittest

from odoo.addons.udes_stock.tests import common
from unittest.mock import patch


class TestBatchState(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestBatchState, cls).setUpClass()

        cls.outbound_user = cls.env.user

        cls.package_one = cls.create_package(name="test_package_one")
        cls.package_two = cls.create_package(name="test_package_two")

        cls.pack_4apples_info = [{"product": cls.apple, "qty": 4}]

        cls.batch01 = cls.create_batch(user=False)

        cls.picking01 = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls.pack_4apples_info,
            confirm=True,
            batch_id=cls.batch01.id,
            location_id=cls.test_received_location_01.id,
            location_dest_id=cls.test_received_location_02.id,
        )

        cls.picking02 = cls.create_picking(
            cls.picking_type_pick, products_info=cls.pack_4apples_info, confirm=True
        )

        cls.compute_patch = patch.object(cls.batch01.__class__, "_compute_state", autospec=True)

    @classmethod
    def draft_to_ready(cls):
        """
            Setup method for moving 'draft' to 'ready'.
            Note, this assumes picking01 to still have batch01 as batch.
        """
        cls.batch01.confirm_picking()
        cls.create_quant(
            cls.apple.id, cls.test_received_location_01.id, 4, package_id=cls.package_one.id
        )
        cls.picking01.action_assign()

    @classmethod
    def assign_user(cls):
        """Method to attach outbound user to batch"""
        cls.batch01.user_id = cls.outbound_user.id

    @classmethod
    def complete_pick(cls, picking, call_done=True):
        for move in picking.move_lines:
            move.write(
                {
                    "quantity_done": move.product_uom_qty,
                    "location_dest_id": cls.test_goodsout_location_01.id,
                }
            )
        picking.move_line_ids.write({"location_dest_id": cls.test_goodsout_location_01.id})

        if call_done:
            picking._action_done()

    def test00_empty_simple_flow(self):
        """Create and try to go through the stages"""

        self.assertEqual(self.batch01.state, "draft")
        self.assertEqual(self.batch01.picking_ids.state, "confirmed")

        # Move from draft to ready, check batch state ready
        self.draft_to_ready()
        self.assertEqual(self.picking01.state, "assigned")
        self.assertEqual(self.batch01.state, "ready")

        # Attach user to ready batch, check that it becomes in progress
        self.assign_user()
        self.assertEqual(self.batch01.state, "in_progress")

        # Perform moves and action_done, confirm batch and pickings 'done'
        self.complete_pick(self.picking01)
        self.assertEqual(self.picking01.state, "done")
        self.assertEqual(self.batch01.state, "done")

    def test01_ready_to_waiting(self):
        """Get to ready then check that we can move back to waiting"""
        self.draft_to_ready()
        # Add another picking to go back!
        self.picking02.batch_id = self.batch01.id
        self.assertEqual(self.batch01.state, "waiting")

        # Remove picking to go back to ready...
        self.picking02.batch_id = False
        self.assertEqual(self.batch01.state, "ready")

    def test02_waiting_to_in_progess(self):
        """ Assign user to check we get in_progress, then move back"""
        self.draft_to_ready()
        self.assign_user()
        self.assertEqual(self.batch01.state, "in_progress")
        # Check that removing user moves back to ready
        self.batch01.user_id = False
        self.assertEqual(self.batch01.state, "ready")

    def test03_cancel_pick_to_done(self):
        """ Cancel pick and confirm state 'done'"""
        self.draft_to_ready()
        self.assign_user()
        # Cancel the pick and confirm we reach state done
        self.picking01.action_cancel()
        self.assertEqual(self.batch01.state, "done")

    def test04_potential_assignment(self):
        """ Add picking which is not ready leads to removal from batch"""
        self.draft_to_ready()
        self.assign_user()
        self.picking02.batch_id = self.batch01
        self.assertNotIn(self.picking02, self.batch01.picking_ids)

    def test05_remove_batch_id(self):
        """ Remove batch_id from picking and confirm state 'done'"""
        self.draft_to_ready()
        self.assign_user()
        self.picking01.batch_id = False
        self.assertEqual(self.batch01.state, "done")

    def test06_ready_picking_to_batch(self):
        """ Add picking in state 'assigned' to 'draft' batch, goes to 'ready'
            on confirm_picking.
        """
        self.create_quant(
            self.apple.id, self.test_received_location_01.id, 4, package_id=self.package_one.id
        )
        self.picking01.action_assign()
        self.batch01.confirm_picking()
        self.assertEqual(self.batch01.state, "ready")

    def test07_partial_completion(self):
        """ Check state remains in_progress when batch pickings partially
            completed.
        """
        self.draft_to_ready()
        self.assign_user()
        self.assertEqual(self.batch01.state, "in_progress")

        # Create second quant and assign picking, confirm 'in_progress' state
        self.create_quant(
            self.apple.id, self.test_received_location_01.id, 4, package_id=self.package_two.id
        )
        self.picking02.action_assign()
        self.picking02.batch_id = self.batch01
        self.assertEqual(self.batch01.state, "in_progress")

        # Move and complete picking01, confirm batch remains 'in_progress'
        self.complete_pick(self.picking01)
        self.assertEqual(self.picking01.state, "done")
        self.assertEqual(self.batch01.state, "in_progress")

        # Move and complete picking02, confirm batch 'done' state
        self.complete_pick(self.picking02)
        self.assertEqual(self.batch01.state, "done")

    def test08_check_computing_simple(self):
        """ Checking that we are going into _compute_state as expected
            i.e. with the right object
        """
        self.assertEqual(self.batch01.state, "draft")
        self.batch01.confirm_picking()
        self.assertEqual(self.batch01.state, "waiting")

        self.create_quant(
            self.apple.id, self.test_received_location_01.id, 4, package_id=self.package_one.id
        )

        self.picking01.action_assign()
        self.assertEqual(self.batch01.state, "ready")
        # put in state 'in_progress', can't be tested with patch as decorator
        self.assign_user()
        self.assertEqual(self.batch01.state, "in_progress")

        # complete picks and check state done, forcibly compute_state
        self.complete_pick(self.picking01, call_done=False)
        self.picking01._action_done()

        # self.batch01._compute_state()
        self.assertEqual(self.batch01.state, "done")

    def test09_check_computing_cancel(self):
        """ Test done with cancel to check computation"""
        self.draft_to_ready()
        self.assign_user()

        # Cancel the pick and confirm we reach state done, compute state
        self.picking01.action_cancel()

        self.assertEqual(self.batch01.state, "done")

    def test10_check_computing_cancel(self):
        """ Test done with cancel to check computation"""
        self.draft_to_ready()
        self.assign_user()

        # set batch_id to False and check state 'done',
        self.picking01.batch_id = False

        self.assertEqual(self.batch01.state, "done")

    def test11_computing_ready_picking_to_batch(self):
        """ Test done with ready picking to check computation"""
        self.create_quant(
            self.apple.id, self.test_received_location_01.id, 4, package_id=self.package_one.id
        )
        # assign picking before adding to batch
        self.picking01.action_assign()

        self.assertEqual(self.batch01.state, "draft")

        # confirm picking and check compute_state is run
        self.batch01.confirm_picking()

        self.assertEqual(self.batch01.state, "ready")

    def test12_computing_partial_assignment(self):
        """ Test done with partially complete pickings to check computation"""
        self.draft_to_ready()
        self.assign_user()

        # Create second quant and assign picking, confirm 'in_progress' state
        self.create_quant(
            self.apple.id, self.test_received_location_01.id, 4, package_id=self.package_two.id
        )

        self.picking02.action_assign()
        self.picking02.batch_id = self.batch01

        self.assertEqual(self.batch01.state, "in_progress")

        # complete pick1 and check state 'in_progress', forcibly compute_state
        self.complete_pick(self.picking01, call_done=False)
        self.picking01._action_done()

        self.assertEqual(self.batch01.state, "in_progress")

        # complete pick2 and check state 'done', forcibly compute_state
        self.complete_pick(self.picking02, call_done=False)
        self.picking02._action_done()

        self.assertEqual(self.batch01.state, "done")
