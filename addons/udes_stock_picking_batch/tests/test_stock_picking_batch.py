from odoo.addons.udes_stock.tests import common
from odoo.tests import common as odoo_common
from odoo.exceptions import ValidationError


class TestStockPickingBatch(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockPickingBatch, cls).setUpClass()
        cls.pack_4apples_info = [{"product": cls.apple, "qty": 4}]
        User = cls.env["res.users"]
        cls.outbound_user = User.create({"name": "Outbound User", "login": "out_log"})

    def setUp(self):
        super(TestStockPickingBatch, self).setUp()
        Package = self.env["stock.quant.package"]

        self.package_one = Package.get_or_create("test_package_one", create=True)
        self.package_two = Package.get_or_create("test_package_two", create=True)
        self.package_three = Package.get_or_create("test_package_three", create=True)
        self.package_four = Package.get_or_create("test_package_four", create=True)

    def test_get_single_batch_no_batch_no_picking(self):
        """Should not create anything if no picking exists"""
        Batch = self.env["stock.picking.batch"]
        Batch = Batch.with_user(self.outbound_user)

        batch = Batch.get_single_batch()

        self.assertIsNone(batch, "Unexpected batch created")

    def test_get_single_batch_no_batch_one_picking(self):
        """
        Get single batch returns none when no batch has been
        created for the current user.

        """
        Batch = self.env["stock.picking.batch"]
        Batch = Batch.with_user(self.outbound_user)

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
        batch = Batch.get_single_batch()

        self.assertIsNone(batch, "Unexpected batch found")

    def test_get_single_batch_error_multiple_batches(self):
        """
        Should raise an error when the user already has (by
        instrumenting the datastore) multiple batches in the
        'in_progress' state associated with the user.

        """
        Batch = self.env["stock.picking.batch"]
        Batch = Batch.with_user(self.outbound_user)

        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            4,
            package_id=self.package_one.id,
        )
        self.create_quant(
            self.apple.id,
            self.test_stock_location_01.id,
            4,
            package_id=self.package_two.id,
        )

        batch01 = self.create_batch(user=self.outbound_user)
        self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
            batch_id=batch01.id,
        )
        batch01.state = "in_progress"

        batch02 = self.create_batch(user=self.outbound_user)
        self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
            batch_id=batch02.id,
        )
        batch02.state = "in_progress"

        batches = Batch.search(
            [("user_id", "=", self.outbound_user.id), ("state", "=", "in_progress")]
        )

        # check pre-conditions
        self.assertEqual(len(batches), 2)

        with self.assertRaises(ValidationError) as err:
            Batch.get_single_batch()

        self.assertEqual(
            err.exception.args[0],
            "Found 2 batches for the user, please contact administrator.",
        )

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
            self.create_quant(
                self.apple.id, self.test_stock_location_01.id, 4, package_id=pack.id
            )
            self.create_picking(
                self.picking_type_pick,
                products_info=self.pack_4apples_info,
                confirm=True,
                assign=True,
            )

        batch = Batch.get_single_batch()

        self.assertIsNone(batch, "Unexpected batch found")

    def test_check_user_id_raise_with_empty_id_string(self):
        """Should error if passed an empty id"""
        batch = self.create_batch(user=self.outbound_user)
        batch = batch.with_user(self.outbound_user)

        with self.assertRaises(ValidationError) as err:
            batch._check_user_id("")

        self.assertEqual(err.exception.args[0], "Cannot determine the user.")

    def test_check_user_id_valid_id(self):
        """Should return a non empty string"""
        batch = self.create_batch(user=self.outbound_user)
        batch = batch.with_user(self.outbound_user)

        checked_user_id = batch._check_user_id("42")

        self.assertEqual(checked_user_id, "42")

    def test_check_user_id_default_id(self):
        """Should return the current user id if passed None"""
        batch = self.create_batch(user=self.outbound_user)
        batch = batch.with_user(self.outbound_user)

        user_id = batch._check_user_id(None)

        self.assertEqual(user_id, self.outbound_user.id)

    def test_get_batches_assigned_to_a_user(self):
        batch = self.create_batch(user=self.outbound_user, state="in_progress")
        batch = batch.with_user(self.outbound_user)

        searched_batch = batch.get_user_batches(user_id=self.outbound_user.id)

        self.assertEqual(batch, searched_batch)

    def test_assign_batches_for_batch_with_multiple_picking_types(self):
        """
        Create two pickings, assign the pickings to the batch, put the batch in a ready state and then request that the
        one of the pickings
        """
        self.create_quant(self.apple.id, self.test_received_location_01.id, 4)
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 4)

        batch = self.create_batch(user=self.outbound_user, state="ready")

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

        batch = batch.assign_user(picking_type_id=self.picking_type_pick.id)

        self.assertEqual(batch, False)

    def test_assign_batches_for_batch_with_single_picking_type(self):
        """
        Create two pickings, assign the pickings to the batch, put the batch in a ready state and then request that the
        one of the pickings.
        """
        self.create_quant(self.apple.id, self.test_received_location_01.id, 4)
        self.create_quant(self.banana.id, self.test_received_location_01.id, 4)

        batch = self.create_batch(user=self.outbound_user, state="ready")

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

        batch = batch.assign_user(picking_type_id=self.picking_type_putaway.id)

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
            self.create_quant(
                self.apple.id, self.test_stock_location_01.id, 4, package_id=pack.id
            )
            self.create_picking(
                self.picking_type_pick,
                products_info=self.pack_4apples_info,
                confirm=True,
                assign=True,
                priority=str(idx),
            )

        batch = Batch.create_batch(self.picking_type_pick.id, ["1"])

        self.assertIsNotNone(batch, "No batch created")
        self.assertEqual(
            len(batch.picking_ids), 1, "Multiple pickings were included in the batch"
        )
        self.assertEqual(
            batch.picking_ids[0].priority,
            "2",
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
            location_barcode=self.test_output_location_01.name,
            result_package_name=None,
        )

        # check the picking is done and the backorder is not in the batch
        self.assertEqual(len(batch.picking_ids), 1)
        self.assertEqual(batch.state, "done")
        self.assertEqual(batch.picking_ids[0].state, "done")

        # create a new picking to be included in the new batch
        other_pack = Package.get_package("test_other_package", create=True)
        self.create_quant(
            self.apple.id, self.test_location_01.id, 4, package_id=other_pack.id
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
        other_pack = Package.get_package("test_other_package", create=True)
        self.create_quant(
            self.apple.id, self.test_location_01.id, 4, package_id=other_pack.id
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

        self.assertTrue(err.exception.name.startswith("The user already has pickings"))

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
            location_dest_id=self.test_output_location_01.id,
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
            self.apple.id, self.test_location_01.id, 4, package_id=self.package_one.id
        )
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True,
        )

        return picking, Batch.create_batch(self.picking_type_pick.id, None)
