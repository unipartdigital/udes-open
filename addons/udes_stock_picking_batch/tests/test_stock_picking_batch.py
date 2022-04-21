from odoo.addons.udes_stock.tests import common
from odoo.tests import common as odoo_common
from odoo.exceptions import ValidationError


class TestBatchState(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.package_one = cls.create_package(name="00001")
        cls.package_two = cls.create_package(name="00002")

        cls.pack_4apples_info = [{"product": cls.apple, "qty": 4}]

        cls.batch01 = cls.create_batch(user=False)

        cls.picking01 = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls.pack_4apples_info,
            confirm=True,
            batch_id=cls.batch01.id,
        )

        cls.picking02 = cls.create_picking(
            cls.picking_type_pick, products_info=cls.pack_4apples_info, confirm=True
        )

        # TODO - Fix to be outbound user when users are implemented
        cls.outbound_user = cls.env.user

    @classmethod
    def draft_to_ready(cls):
        """
        Setup method for moving 'draft' to 'ready'.
        Note, this assumes picking01 to still have batch01 as batch.
        """
        cls.batch01.action_confirm()
        cls.create_quant(
            cls.apple.id, cls.test_stock_location_01.id, 4, package_id=cls.package_one.id
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

    def test_empty_simple_flow(self):
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

    def test_ready_to_waiting(self):
        """Get to ready then check that we can move back to waiting"""
        self.draft_to_ready()
        # Add another picking to go back!
        self.picking02.batch_id = self.batch01.id
        self.assertEqual(self.batch01.state, "waiting")

        # Remove picking to go back to ready...
        self.picking02.batch_id = False
        self.assertEqual(self.batch01.state, "ready")

    def test_waiting_to_in_progess(self):
        """ Assign user to check we get in_progress, then move back"""
        self.draft_to_ready()
        self.assign_user()
        self.assertEqual(self.batch01.state, "in_progress")
        # Check that removing user moves back to ready
        self.batch01.user_id = False
        self.assertEqual(self.batch01.state, "ready")

    def test_cancel_pick_to_done(self):
        """ Cancel pick and confirm state 'done'"""
        self.draft_to_ready()
        self.assign_user()
        # Cancel the pick and confirm we reach state done
        self.picking01.action_cancel()
        self.assertEqual(self.batch01.state, "done")

    def test_potential_assignment(self):
        """ Add picking which is not ready leads to removal from batch"""
        self.draft_to_ready()
        self.assign_user()
        self.picking02.batch_id = self.batch01
        self.assertNotIn(self.picking02, self.batch01.picking_ids)

    def test_remove_batch_id(self):
        """ Remove batch_id from picking and confirm state 'done'"""
        self.draft_to_ready()
        self.assign_user()
        self.picking01.batch_id = False
        self.assertEqual(self.batch01.state, "done")

    def test_ready_picking_to_batch(self):
        """Add picking in state 'assigned' to 'draft' batch, goes to 'ready'
        on action_confirm.
        """
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=self.package_one.id
        )
        self.picking01.action_assign()
        self.batch01.action_confirm()
        self.assertEqual(self.batch01.state, "ready")

    def test_partial_completion(self):
        """Check state remains in_progress when batch pickings partially
        completed.
        """
        self.draft_to_ready()
        self.assign_user()
        self.assertEqual(self.batch01.state, "in_progress")

        # Create second quant and assign picking, confirm 'in_progress' state
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=self.package_two.id
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

    def test_check_computing_simple(self):
        """Checking that we are going into _compute_state as expected
        i.e. with the right object
        """
        self.assertEqual(self.batch01.state, "draft")

        self.batch01.action_confirm()
        self.assertEqual(self.batch01.state, "waiting")

        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=self.package_one.id
        )

        self.picking01.action_assign()
        self.assertEqual(self.batch01.state, "ready")
        # put in state 'in_progress'
        self.assign_user()
        self.assertEqual(self.batch01.state, "in_progress")

        # complete picks and check state done
        self.complete_pick(self.picking01, call_done=False)
        self.picking01._action_done()
        self.assertEqual(self.batch01.state, "done")

    def test_check_computing_cancel(self):
        """ Test done with cancel to check computation"""
        self.draft_to_ready()
        self.assign_user()

        # Cancel the pick and confirm we reach state done
        self.picking01.action_cancel()
        self.assertEqual(self.batch01.state, "done")

    def test_check_computing_cancel(self):
        """ Test done with cancel to check computation"""
        self.draft_to_ready()
        self.assign_user()

        # set batch_id to False and check state 'done'
        self.picking01.batch_id = False
        self.assertEqual(self.batch01.state, "done")

    def test_computing_ready_picking_to_batch(self):
        """ Test done with ready picking to check computation"""
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=self.package_one.id
        )
        # assign picking before adding to batch
        # called when no pick.state change occurs
        self.picking01.action_assign()
        self.assertEqual(self.batch01.state, "draft")

        # confirm picking and check compute_state is run
        self.batch01.action_confirm()
        self.assertEqual(self.batch01.state, "ready")

    def test_computing_partial_assignment(self):
        """ Test done with partially complete pickings to check computation"""
        self.draft_to_ready()
        self.assign_user()

        # Create second quant and assign picking, confirm 'in_progress' state
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=self.package_two.id
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


class TestBatchMultiDropOff(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pack_2prods_info = [{"product": cls.apple, "qty": 4}, {"product": cls.banana, "qty": 4}]
        # TODO - Fix to be outbound user when users are implemented
        cls.outbound_user = cls.env.user

    @classmethod
    def product_str(cls, product, qty):
        return "{} x {}".format(product.display_name, qty)

    @classmethod
    def complete_pick(cls, picking):
        for line in picking.move_line_ids:
            line.write(
                {
                    "qty_done": line.product_uom_qty,
                }
            )

    def test_next_drop_off_by_products(self):
        """ Test next drop off criterion by products """
        MoveLine = self.env["stock.move.line"]
        Batch = self.env["stock.picking.batch"]
        Batch = Batch.with_user(self.outbound_user)

        self.picking_type_pick.u_drop_criterion = "by_products"
        out_location = self.test_goodsout_location_01.barcode
        # Create quants and picking for one order and two products
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 4)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 4)
        picking = self.create_picking(
            self.picking_type_pick, products_info=self.pack_2prods_info, confirm=True, assign=True
        )
        # Create batch for outbound user
        priority = picking.priority
        batch = Batch.create_batch(self.picking_type_pick.id, [priority])
        # Mark all move lines to done
        self.complete_pick(picking)
        # Get next drop off info for apples
        info = batch.get_next_drop_off(self.apple.barcode)
        drop_mls = MoveLine.browse(info["move_line_ids"])
        summary = info["summary"]
        last = info["last"]

        # Check there are move lines to drop, the summary is for 4 apples and
        # it is not the last drop off (still bananas to drop)
        self.assertTrue(len(drop_mls.exists()) > 0)
        self.assertTrue(self.product_str(self.apple, 4) in summary)
        self.assertFalse(last)

        # Drop off apple move lines, and check expected state of the batch
        batch_after = batch.drop_off_picked(
            continue_batch=True,
            move_line_ids=drop_mls.ids,
            location_barcode=out_location,
            result_package_name=None,
        )
        self.assertEqual(batch, batch_after)
        self.assertNotEqual(batch.state, "done")

        # Get next drop off info for apples
        info = batch.get_next_drop_off(self.apple.barcode)
        drop_mls = MoveLine.browse(info["move_line_ids"])
        summary = info["summary"]
        last = info["last"]

        # Check there are not more apple move lines to drop, the summary is
        # empty and it is not the last drop off (still bananas to drop)
        self.assertEqual(len(drop_mls.exists()), 0)
        self.assertEqual(len(summary), 0)
        self.assertFalse(last)

        # Get next drop off info for bananas
        info = batch.get_next_drop_off(self.banana.barcode)
        drop_mls = MoveLine.browse(info["move_line_ids"])
        summary = info["summary"]
        last = info["last"]

        # Check there are move lines to drop, the summary is for 4 bananas and
        # it is the last drop off (nothing else to drop)
        self.assertTrue(len(drop_mls.exists()) > 0)
        self.assertTrue(self.product_str(self.banana, 4) in summary)
        self.assertTrue(last)

        # Drop off banana move lines, and check expected state of the batch
        batch_after = batch.drop_off_picked(
            continue_batch=True,
            move_line_ids=drop_mls.ids,
            location_barcode=out_location,
            result_package_name=None,
        )
        self.assertEqual(batch, batch_after)
        self.assertEqual(batch.state, "done")

    def test_next_drop_off_by_orders(self):
        """ Test next drop off criterion by orders """
        MoveLine = self.env["stock.move.line"]
        Batch = self.env["stock.picking.batch"]
        Batch = Batch.with_user(self.outbound_user)

        self.picking_type_pick.u_drop_criterion = "by_orders"

        out_location = self.test_goodsout_location_01.barcode
        out_location2 = self.test_goodsout_location_02.barcode

        # Create quants and picking for two orders and two products
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 8)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 8)
        picking1 = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_2prods_info,
            confirm=True,
            assign=True,
            origin="test_order_01",
        )
        # Create batch for outbound user
        priority = picking1.priority
        batch = Batch.create_batch(self.picking_type_pick.id, [priority])

        picking2 = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_2prods_info,
            confirm=True,
            assign=True,
            origin="test_order_02",
        )
        # Add the second pick to the batch
        picking2.batch_id = batch

        # Mark all move lines to done for both pickings
        self.complete_pick(picking1)
        self.complete_pick(picking2)

        # Get next drop off info for picking2
        info = batch.get_next_drop_off(picking2.origin)
        drop_mls = MoveLine.browse(info["move_line_ids"])
        summary = info["summary"]
        last = info["last"]

        # Check there are move lines to drop, the summary is for 4 apples and 4
        # bananas and it is not the last drop off (still another order to drop)
        self.assertTrue(len(drop_mls.exists()) > 0)
        self.assertTrue(self.product_str(self.apple, 4) in summary)
        self.assertTrue(self.product_str(self.banana, 4) in summary)
        self.assertFalse(last)

        # Drop off picking2 move lines, and check expected state of the batch
        batch_after = batch.drop_off_picked(
            continue_batch=True,
            move_line_ids=drop_mls.ids,
            location_barcode=out_location2,
            result_package_name=None,
        )
        self.assertEqual(batch, batch_after)
        self.assertNotEqual(batch.state, "done")
        # Check state of pickings are as expected
        self.assertEqual(picking1.state, "assigned")
        self.assertEqual(picking2.state, "done")

        # Get next drop off info for picking2
        info = batch.get_next_drop_off(self.apple.barcode)
        drop_mls = MoveLine.browse(info["move_line_ids"])
        summary = info["summary"]
        last = info["last"]

        # Check there are not more picking2 move lines to drop, the summary is
        # empty and it is not the last drop off (still another order to drop)
        self.assertEqual(len(drop_mls.exists()), 0)
        self.assertEqual(len(summary), 0)
        self.assertFalse(last)

        # Get next drop off info for picking1
        info = batch.get_next_drop_off(picking1.origin)
        drop_mls = MoveLine.browse(info["move_line_ids"])
        summary = info["summary"]
        last = info["last"]

        # Check there are move lines to drop, the summary is for 4 apples and 4
        # bananas and it is the last drop off (nothing else to drop)
        self.assertTrue(len(drop_mls.exists()) > 0)
        self.assertTrue(self.product_str(self.apple, 4) in summary)
        self.assertTrue(self.product_str(self.banana, 4) in summary)
        self.assertTrue(last)

        # Drop off banana move lines, and check expected state of the batch
        batch_after = batch.drop_off_picked(
            continue_batch=True,
            move_line_ids=drop_mls.ids,
            location_barcode=out_location,
            result_package_name=None,
        )
        self.assertEqual(batch, batch_after)
        self.assertEqual(batch.state, "done")

    def test_next_drop_off_nothing_to_drop(self):
        """ Test next drop off criterion by products but nothing to drop """
        MoveLine = self.env["stock.move.line"]
        Batch = self.env["stock.picking.batch"]
        Batch = Batch.with_user(self.outbound_user)

        self.picking_type_pick.u_drop_criterion = "by_products"

        # Create quants and picking for one order and two products
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 4)
        self.create_quant(self.banana.id, self.test_stock_location_02.id, 4)
        picking = self.create_picking(
            self.picking_type_pick, products_info=self.pack_2prods_info, confirm=True, assign=True
        )
        # Create batch for outbound user
        priority = picking.priority
        batch = Batch.create_batch(self.picking_type_pick.id, [priority])

        # Get next drop off info for apples when nothing has been picked
        info = batch.get_next_drop_off(self.apple.barcode)
        drop_mls = MoveLine.browse(info["move_line_ids"])
        summary = info["summary"]
        last = info["last"]

        # Check there are not any apple move lines to drop, the summary is
        # empty and it is the last drop off
        self.assertEqual(len(drop_mls.exists()), 0)
        self.assertEqual(len(summary), 0)
        self.assertTrue(last)


class TestPalletReservation(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO - Fix to be outbound user when users are implemented
        cls.outbound_user = cls.env.user

    def test_conflicting_reservation(self):
        batch1 = self.create_batch()
        batch1.state = "in_progress"
        batch1.reserve_pallet("UDES11111")

        batch2 = self.create_batch(user=self.outbound_user)
        batch2.state = "in_progress"
        expected_error = "This pallet is already being used for batch %s." % batch1.name
        with self.assertRaisesRegex(ValidationError, expected_error, msg="Incorrect error thrown"):
            batch2.reserve_pallet("UDES11111")

    def test_reservation_expiry_when_done(self):
        batch1 = self.create_batch(user=self.outbound_user)
        batch1.state = "in_progress"
        batch1.reserve_pallet("UDES11111")
        batch1.state = "done"

        batch2 = self.create_batch(user=self.outbound_user)
        batch2.state = "in_progress"
        batch2.reserve_pallet("UDES11111")

    def test_reservation_switch(self):
        batch1 = self.create_batch(user=self.outbound_user)
        batch1.state = "in_progress"
        batch1.reserve_pallet("UDES11111")
        batch1.reserve_pallet("UDES11112")

        batch2 = self.create_batch(user=self.outbound_user)
        batch2.state = "in_progress"
        batch2.reserve_pallet("UDES11111")
        expected_error = "This pallet is already being used for batch %s." % batch1.name
        with self.assertRaisesRegex(ValidationError, expected_error, msg="Incorrect error thrown"):
            batch2.reserve_pallet("UDES11112")

    def test_rereservation_for_same_batch(self):
        batch = self.create_batch(user=self.outbound_user)
        batch.state = "in_progress"

        batch.reserve_pallet("UDES11111")
        batch.reserve_pallet("UDES11111")


class TestBatchGetNextTask(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Package = cls.env["stock.quant.package"]

        quant_quantity = 4
        # TODO - Fix to be outbound user when users are implemented
        cls.outbound_user = cls.env.user
        cls.package_a = Package.get_or_create("1", create=True)
        cls.package_b = Package.get_or_create("2", create=True)
        cls.apple_quant = cls.create_quant(
            cls.apple.id, cls.test_stock_location_01.id, quant_quantity, package_id=cls.package_a.id
        )
        cls.banana_quant = cls.create_quant(
            cls.banana.id,
            cls.test_stock_location_02.id,
            quant_quantity,
            package_id=cls.package_b.id,
        )
        pack_2prods_info = [
            {"product": cls.apple, "qty": quant_quantity},
            {"product": cls.banana, "qty": quant_quantity},
        ]
        cls.picking = cls.create_picking(
            cls.picking_type_pick, products_info=pack_2prods_info, confirm=True, assign=True
        )
        cls.batch = cls.create_batch(user=cls.outbound_user)
        cls.picking.batch_id = cls.batch.id

    def test_picking_ordering_is_persisted_in_task(self):
        """ Ensure that get_next_task respects the ordering criteria """
        criteria = lambda ml: (int(ml.package_id.name))
        task = self.batch.get_next_task(task_grouping_criteria=criteria)

        # We should get the move line related to package named '1'
        self.assertEqual(task["package_id"]["name"], "1")
        task = self.batch.get_next_task(task_grouping_criteria=criteria)
        # Calling get_next_task again should give the same task
        self.assertEqual(task["package_id"]["name"], "1")
        self.package_a.write({"name": "10"})
        task = self.batch.get_next_task(task_grouping_criteria=criteria)
        # As package_a is now named '10', the criteria should give the '2'
        self.assertEqual(task["package_id"]["name"], "2")
        self.package_b.write({"name": "12341234"})
        task = self.batch.get_next_task(task_grouping_criteria=criteria)
        # In the same way, we should now get '10'
        self.assertEqual(task["package_id"]["name"], "10")

    def test_get_next_tasks(self):
        """Test that get_next_tasks returns multiple remaining tasks"""
        criteria = lambda ml: (int(ml.package_id.name))
        tasks = self.batch.get_next_tasks(task_grouping_criteria=criteria, limit=100)
        self.assertEqual(len(tasks), 2)
        # The first task should be for package '1'
        self.assertEqual(tasks[0]["package_id"]["name"], "1")
        # The second task should be for package '2'
        self.assertEqual(tasks[1]["package_id"]["name"], "2")

    def test_skip_products(self):
        """Test that get_next_task respects skipped products"""
        # Assert that the specified product is not in the next task
        for product_id in [self.apple.id, self.banana.id]:
            task = self.batch.get_next_task(skipped_product_ids=[product_id])
            task_quants = task["package_id"]["quant_ids"]
            task_products = [quant["product_id"]["id"] for quant in task_quants]
            self.assertNotIn(product_id, task_products)

    def test_skip_products_return(self):
        """Test that get_next_task can return to skipped products
        if u_return_to_skipped is True.
        """
        # First assert if we skip everything with default config, the returned task is empty
        task = self.batch.get_next_task(skipped_product_ids=[self.apple.id, self.banana.id])
        self.assertFalse(task["move_line_ids"])
        self.assertFalse(task.get("package_id"))
        # Change config to allow returning to skipped tasks
        self.picking_type_pick.u_return_to_skipped = True
        # First returned task should include the first skipped product
        for product_ids in [[self.apple.id, self.banana.id], [self.banana.id, self.apple.id]]:
            task = self.batch.get_next_task(skipped_product_ids=product_ids)
            task_quants = task["package_id"]["quant_ids"]
            task_products = [quant["product_id"]["id"] for quant in task_quants]
            self.assertIn(product_ids[0], task_products)
            self.assertNotIn(product_ids[1], task_products)

    def test_skip_move_lines(self):
        """Test that get_next_task respects skipped products"""
        move_line_ids = self.batch.picking_ids.mapped("move_line_ids.id")
        # Assert that the specified move_line_id is not in the next task
        for move_line_id in move_line_ids:
            task = self.batch.get_next_task(skipped_move_line_ids=[move_line_id])
            self.assertNotIn(move_line_id, task["move_line_ids"])

    def test_skip_move_lines_return(self):
        """Test that get_next_task can return to skipped products
        if u_return_to_skipped is True.
        """
        move_line_ids = self.batch.picking_ids.mapped("move_line_ids.id")
        # First assert if we skip everything with default config, the returned task is empty
        task = self.batch.get_next_task(skipped_move_line_ids=move_line_ids)
        self.assertFalse(task["move_line_ids"])
        self.assertFalse(task.get("package_id"))
        # Change config to allow returning to skipped tasks
        self.picking_type_pick.u_return_to_skipped = True
        # First returned task should include the first skipped move_line_id
        for skipped_move_line_ids in [move_line_ids, [ml for ml in reversed(move_line_ids)]]:
            task = self.batch.get_next_task(skipped_move_line_ids=skipped_move_line_ids)
            self.assertIn(skipped_move_line_ids[0], task["move_line_ids"])
            self.assertNotIn(skipped_move_line_ids[1], task["move_line_ids"])

    def test_get_completed_tasks(self):
        """Test that we can retrieve a list of completed tasks"""
        move_lines = self.batch.picking_ids.mapped("move_line_ids")
        # First check we dont get any tasks when no tasks have been completed
        tasks = self.batch.get_completed_tasks()
        self.assertFalse(tasks)

        # Set move lines to complete
        for ml in move_lines:
            ml.qty_done = ml.product_uom_qty
        tasks = self.batch.get_completed_tasks()
        # Check that returned tasks have the move lines in them
        self.assertEqual(len(tasks), 2)
        completed_move_line_ids = []
        for task in tasks:
            completed_move_line_ids += task["move_line_ids"]
        self.assertCountEqual(completed_move_line_ids, move_lines.mapped("id"))


class TestBatchAddRemoveWork(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # TODO - Fix to be outbound user when users are implemented
        cls.outbound_user = cls.env.user

        Batch = cls.env["stock.picking.batch"]
        Batch = Batch.with_user(cls.outbound_user)

        cls.pack_info = [{"product": cls.apple, "qty": 4}]
        cls.multipack_info = [{"product": cls.apple, "qty": 2}, {"product": cls.banana, "qty": 4}]

        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 12)
        cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 8)

        cls.picking = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls.pack_info,
            confirm=True,
            assign=True,
            name="pickingone",
        )
        cls.picking2 = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls.pack_info,
            confirm=True,
            assign=True,
            name="pickingtwo",
        )
        cls.picking3 = cls.create_picking(
            cls.picking_type_goods_in,
            products_info=cls.multipack_info,
            confirm=True,
            assign=True,
            name="pickingthree",
        )
        cls.picking4 = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls.multipack_info,
            confirm=True,
            assign=True,
            name="pickingfour",
        )

        cls.batch = Batch.create_batch(
            cls.picking_type_pick.id, [cls.picking.priority], picking_id=cls.picking.id
        )

    @classmethod
    def complete_pick(cls, picking):
        for move in picking.move_lines:
            move.write(
                {
                    "quantity_done": move.product_uom_qty,
                    "location_dest_id": cls.test_goodsout_location_01.id,
                })
                
    def test_get_single_batch_no_batch_multiple_pickings(self):
        """
        Get single batch returns none when no batch has been
        created for the current user, even having multiple pickings.

        """
        Batch = self.env["stock.picking.batch"]
        Package = self.env["stock.quant.package"]
        Batch = Batch.with_user(self.outbound_user)

        for idx in range(3):
            pack = Package.get_or_create("test_package_%d" % idx, create=True)
            self.create_quant(self.apple.id, self.test_stock_location_01.id, 4, package_id=pack.id)
            self.create_picking(
                self.picking_type_pick,
                products_info=self.pack_4apples_info,
                confirm=True,
                assign=True,
            )

    def test_add_extra_pickings(self):
        """ Ensure that add extra picking adds pickings correctly"""

        batch = self.batch

        # We only have one picking at the moment
        self.assertEqual(len(batch.picking_ids), 1)
        self.assertEqual(batch.picking_ids[0].name, "pickingone")

        # Add extra pickings
        batch.add_extra_pickings(self.picking_type_pick.id)
        self.assertEqual(len(batch.picking_ids), 2)
        # Add extra pickings
        batch.add_extra_pickings(self.picking_type_pick.id)

        # Check that we now have three pickings including "pickingfour" and "pickingtwo"
        self.assertEqual(len(batch.picking_ids), 3)
        self.assertIn("pickingfour", batch.mapped("picking_ids.name"))
        self.assertIn("pickingtwo", batch.mapped("picking_ids.name"))

        # Should be no more work now, check error is raised
        with self.assertRaises(ValidationError) as err:
            batch.add_extra_pickings(self.picking_type_pick.id)
    
    def test_check_user_id_default_id(self):
        """Should return the current user id if passed None"""
        batch = self.create_batch(user=self.outbound_user)
        batch = batch.with_user(self.outbound_user)

        user_id = batch._check_user_id(None)

        self.assertEqual(user_id, self.outbound_user.id)

    def test_get_batches_assigned_to_a_user(self):
        batch = self.create_batch(user=self.outbound_user)
        batch = batch.with_user(self.outbound_user)
        
        picking_putaway = self.create_picking(
            self.picking_type_putaway,
            products_info=[{"product": self.apple, "qty": 4}],
            confirm=True,
            assign=True,
            batch_id=batch.id,
        )

        batch.write({"state": "in_progress"})

        searched_batch = batch.get_user_batches(user_id=self.outbound_user.id)

        self.assertEqual(batch, searched_batch)

    def test_assign_batches_for_batch_with_multiple_picking_types(self):
        """
        Create two pickings, assign the pickings to the batch, put the batch in a ready state and then request that the
        one of the pickings
        """
        self.create_quant(self.apple.id, self.test_received_location_01.id, 4)
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 4)

        batch = self.create_batch(user=self.outbound_user)

        picking_putaway = self.create_picking(
            self.picking_type_putaway,
            products_info=[{"product": self.apple, "qty": 4}],
            confirm=True,
            assign=True,
            batch_id=batch.id,
        )

        picking_pick = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.banana, "qty": 4}],
            confirm=True,
            assign=True,
            batch_id=batch.id,
        )

        batch.write({"state": "ready"})

        batch = batch.assign_batch(picking_type_id=self.picking_type_pick.id)

        self.assertEqual(bool(batch), False)

    def test_assign_batches_for_batch_with_single_picking_type(self):
        """
        Create two pickings, assign the pickings to the batch, put the batch in a ready state and then request that the
        one of the pickings.
        """
        self.create_quant(self.apple.id, self.test_received_location_01.id, 4)
        self.create_quant(self.banana.id, self.test_received_location_01.id, 4)

        batch = self.create_batch(user=self.outbound_user)

        picking_putaway_1 = self.create_picking(
            self.picking_type_putaway,
            products_info=[{"product": self.apple, "qty": 4}],
            confirm=True,
            assign=True,
            batch_id=batch.id,
        )

        picking_putaway_2 = self.create_picking(
            self.picking_type_putaway,
            products_info=[{"product": self.banana, "qty": 4}],
            confirm=True,
            assign=True,
            batch_id=batch.id,
        )

        batch.write({"state": "ready"})

        batch = batch.assign_batch(picking_type_id=self.picking_type_putaway.id)

        self.assertEqual(batch.user_id.id, self.env.user.id)

    def test_create_batch_with_priorities(self):
        """
        Should create a batch by correctly filtering pickings by
        priority.
        """
        Batch = self.env["stock.picking.batch"]
        Package = self.env["stock.quant.package"]
        Batch = Batch.with_user(self.outbound_user)

        for idx in range(2):
            pack = Package.get_or_create("test_package_%d" % idx, create=True)
            self.create_quant(self.apple.id, self.test_stock_location_01.id, 4, package_id=pack.id)
            self.create_picking(
                self.picking_type_pick,
                products_info=self.pack_4apples_info,
                confirm=True,
                assign=True,
                priority=str(idx),
            )

        batch = Batch.create_batch(self.picking_type_pick.id, ["1"])

        self.assertIsNotNone(batch, "No batch created")
        self.assertEqual(len(batch.picking_ids), 1, "Multiple pickings were included in the batch")
        self.assertEqual(
            batch.picking_ids[0].priority,
            "1",
            "Does not have a picking with the expected priority",
        )

    def test_create_batch_user_already_has_completed_batch(self):
        """
        When dropping off a partially reserved picking, a backorder in state
        confirmed is created and remains in the batch. This backorder should
        be removed from the batch, allowing the batch to be automatically
        completed and the user should be able to create a new batch without
        any problem.

        """
        Batch = self.env["stock.picking.batch"]
        Package = self.env["stock.quant.package"]
        Batch = Batch.with_user(self.outbound_user)

        # set a batch with a complete picking
        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            2,
            package_id=self.package_one.id,
        )
        # Create a picking partially reserved
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )
        batch = Batch.create_batch(self.picking_type_pick.id, None)
        self.assertEqual(batch.picking_ids[0], picking)
        for ml in picking.move_line_ids:
            ml.qty_done = ml.product_qty
        # On drop off a backorder is created for the remaining 2 units,
        # but _check_batches() removes it from the batch since it is not ready
        batch.drop_off_picked(
            continue_batch=True,
            move_line_ids=None,
            location_barcode=self.test_received_location_01.name,
            result_package_name=None,
        )

        # check the picking is done and the backorder is not in the batch
        self.assertEqual(len(batch.picking_ids), 1)
        self.assertEqual(batch.state, "done")
        self.assertEqual(batch.picking_ids[0].state, "done")

        # create a new picking to be included in the new batch
        other_pack = Package.get_or_create("test_other_package", create=True)
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=other_pack.id
        )
        other_picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        new_batch = Batch.create_batch(self.picking_type_pick.id, None)

        # check outcome
        self.assertIsNotNone(new_batch, "No batch created")
        self.assertEqual(
            len(new_batch.picking_ids),
            1,
            "Multiple pickings were included in the batch",
        )
        self.assertEqual(
            new_batch.picking_ids[0].id,
            other_picking.id,
            "Does not include the expected picking",
        )
        self.assertEqual(batch.state, "done", "Old batch was not completed")

    def test_create_batch_error_user_has_incomplete_batched_pickings(self):
        """
        Should error in case a the user already has a batch assigned
        to him with incomplete pickings.

        """
        Batch = self.env["stock.picking.batch"]
        Package = self.env["stock.quant.package"]
        Batch = Batch.with_user(self.outbound_user)

        # set a batch with a complete picking
        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            4,
            package_id=self.package_one.id,
        )
        self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )
        batch = Batch.create_batch(self.picking_type_pick.id, None)

        # create a new picking to be included in the new batch
        other_pack = Package.get_or_create("test_other_package", create=True)
        self.create_quant(
            self.apple.id, self.test_stock_location_01.id, 4, package_id=other_pack.id
        )
        self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        # check pre-conditions
        self.assertEqual(len(batch.picking_ids), 1)
        self.assertEqual(batch.state, "in_progress")
        self.assertEqual(batch.picking_ids[0].state, "assigned")

        # method under test
        with self.assertRaises(ValidationError) as err:
            Batch.create_batch(self.picking_type_pick.id, None)

        self.assertTrue(err.exception.args[0].startswith("The user already has pickings"))

    def test_automatic_batch_done(self):
        """Verifies the batch is done if the picking is complete"""
        Batch = self.env["stock.picking.batch"]
        Batch = Batch.with_user(self.outbound_user)

        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            4,
            package_id=self.package_one.id,
        )
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
            location_dest_id=self.test_trailer_location_01.id,
        )
        batch = Batch.create_batch(self.picking_type_pick.id, None)
        self.complete_picking(picking, validate=True)

        # check pre-conditions
        self.assertEqual(len(batch.picking_ids), 1)
        self.assertEqual(batch.state, "done")
        self.assertEqual(batch.picking_ids[0].state, "done")

    def _create_valid_batch(self):
        Batch = self.env["stock.picking.batch"]
        Batch = Batch.with_user(self.outbound_user)

        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            4,
            package_id=self.package_one.id,
        )
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        return picking, Batch.create_batch(self.picking_type_pick.id, None)


class TestContinuationBatchProcessing(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pack_4apples_info = [{"product": cls.apple, "qty": 4}]
        User = cls.env["res.users"]
        cls.outbound_user = User.create({"name": "Outbound User", "login": "out_log"})

    def test_preserves_user_id_on_closed_batch(self):
        batch = self.create_batch(user=self.outbound_user, u_ephemeral=False)
        batch = batch.with_user(self.outbound_user)
        batch.close()
        self.assertEqual(batch.user_id, self.outbound_user)

    def test_moves_outstanding_pickings_to_continuation_batch(self):
        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            4,
        )

        batch = self.create_batch(user=self.outbound_user)
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
            batch_id=batch.id,
        )
        batch.state = "in_progress"
        batch.close()
        self.assertNotEqual(picking.batch_id, batch)

    def test_adds_sequence_to_original_batch_name(self):
        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            4,
        )

        batch = self.create_batch(user=self.outbound_user)
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
            batch_id=batch.id,
        )
        batch.state = "in_progress"
        batch.close()
        self.assertRegex(picking.batch_id.name, r"BATCH/\d+-01")

    def test_increments_sequence_for_continuation_batch(self):
        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            4,
        )

        batch01 = self.create_batch(user=self.outbound_user)
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
            batch_id=batch01.id,
        )
        batch01.state = "in_progress"
        batch01.close()
        batch02 = picking.batch_id
        batch02.close()
        self.assertRegex(picking.batch_id.name, r"BATCH/\d+-02")

    def test_sets_original_name(self):
        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            4,
        )

        batch = self.create_batch(user=self.outbound_user)
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
            batch_id=batch.id,
        )
        batch.state = "in_progress"
        batch.close()
        self.assertEqual(picking.batch_id.u_original_name, batch.name)


class TestBatchAddRemoveWork(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestBatchAddRemoveWork, cls).setUpClass()

        User = cls.env["res.users"]
        cls.outbound_user = User.create({"name": "Outbound User", "login": "out_log"})

        Batch = cls.env["stock.picking.batch"]
        Batch = Batch.with_user(cls.outbound_user)

        cls.pack_info = [{"product": cls.apple, "qty": 4}]
        cls.multipack_info = [
            {"product": cls.apple, "qty": 2},
            {"product": cls.banana, "qty": 4},
        ]

        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 12)
        cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 8)

        cls.picking = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls.pack_info,
            confirm=True,
            assign=True,
            name="pickingone",
        )
        cls.picking2 = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls.pack_info,
            confirm=True,
            assign=True,
            name="pickingtwo",
        )
        cls.picking3 = cls.create_picking(
            cls.picking_type_goods_in,
            products_info=cls.multipack_info,
            confirm=True,
            assign=True,
            name="pickingthree",
        )
        cls.picking4 = cls.create_picking(
            cls.picking_type_pick,
            products_info=cls.multipack_info,
            confirm=True,
            assign=True,
            name="pickingfour",
        )

        cls.batch = Batch.create_batch(cls.picking_type_pick.id, [cls.picking.priority])
        cls.picking.batch_id = cls.batch.id

    @classmethod
    def complete_pick(cls, picking):
        for move in picking.move_lines:
            move.write(
                {
                    "quantity_done": move.product_uom_qty,
                    "location_dest_id": cls.test_received_location_01.id,
                }
            )

    def test_test_remove_unfinished_work(self):
        """Ensure that remove unfinished work removes picks
        and backorders moves correctly"""

        picking = self.picking
        picking2 = self.picking2
        picking4 = self.picking4
        batch = self.batch

        pickings = picking2 + picking4
        pickings.write({"batch_id": batch.id})

        # We have three pickings in this batch now
        self.assertEqual(len(batch.picking_ids), 3)

        # Complete pick2
        self.complete_pick(picking2)

        # semi complete pick3
        picking4.move_lines[0].write(
            {
                "quantity_done": 2,
                "location_dest_id": self.test_received_location_01.id,
            }
        )

        # Record which move lines were complete and which weren't
        done_moves = picking4.move_lines[0] + picking2.move_lines[0]
        incomplete_moves = picking.move_lines[0] + picking4.move_lines[1]

        # Remove unfinished work
        batch.remove_unfinished_work()

        # Pickings with incomplete work are removed, complete pickings remain
        self.assertFalse(picking.batch_id)
        self.assertEqual(picking2.batch_id, batch)
        self.assertFalse(picking4.batch_id)

        # Ensure both done moves remain in batch
        self.assertEqual(done_moves.mapped("picking_id.batch_id"), batch)

        # Ensure incomplete moves are in pickings that are not in batches
        self.assertFalse(incomplete_moves.mapped("picking_id.batch_id"))
