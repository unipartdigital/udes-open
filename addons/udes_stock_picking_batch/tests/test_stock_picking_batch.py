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
