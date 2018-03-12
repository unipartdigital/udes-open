# -*- coding: utf-8 -*-

from . import common

from odoo.exceptions import ValidationError


class TestGoodsInPickingBatch(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGoodsInPickingBatch, cls).setUpClass()
        User = cls.env['res.users']

        user_warehouse = User.get_user_warehouse()
        cls.picking_type_pick = user_warehouse.pick_type_id
        cls.picking_type_pick.u_reserve_as_packages = True
        cls.pack_4apples_info = [{'product': cls.apple,
                                  'qty': 4}]

    def setUp(self):
        super(TestGoodsInPickingBatch, self).setUp()
        Package = self.env['stock.quant.package']

        self.package_one = Package.get_package("test_package_one", create=True)

    def test01_check_user_id_raise_with_empty_id_string(self):
        """ Should error if passed an empty id """
        batch = self.create_batch()

        with self.assertRaises(ValidationError):
            batch._check_user_id("")

    def test02_check_user_id_valid_id(self):
        """ Should return a non empty string """
        batch = self.create_batch()
        checked_user_id = batch._check_user_id("42")

        self.assertEqual(checked_user_id, "42")

    def test03_check_user_id_default_id(self):
        """ Should return the current user id if passed None """
        batch = self.create_batch()
        user_id = batch._check_user_id(None)

        self.assertEqual(user_id, self.env.user.id)

    def test04_get_single_batch_no_batch_no_picking(self):
        """ Should not create anything if no picking exists """
        Batch = self.env['stock.picking.batch']
        batch = Batch.get_single_batch()

        self.assertIsNone(batch, "Unexpected batch created")

    def test05_get_single_batch_no_batch_one_picking(self):
        """
        Should create a batch for the current user when a single
        picking exists.

        """
        Batch = self.env['stock.picking.batch']

        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        self.create_picking(self.picking_type_pick,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)
        batch = Batch.get_single_batch()

        self.assertIsNotNone(batch, "No batch created")
        self.assertEqual(batch.user_id.id, self.env.user.id,
                         "Batch responsible is not the current user")
        self.assertEqual(len(batch.picking_ids), 1,
                         "Batch does not include single picking")

    def test06_get_single_batch_error_multiple_batches(self):
        """
        Should raise an error when the user already has (by
        instrumenting the datastore) multiple batches in the
        'in_progress' state associated with the user.

        """
        Batch = self.env['stock.picking.batch']

        self.create_batch(name="one", state='in_progress')
        self.create_batch(name="two", state='in_progress')
        batches = Batch.search([('user_id', '=', self.env.user.id)])

        # check pre-conditions
        self.assertEqual(len(batches), 2)

        with self.assertRaises(ValidationError):
            Batch.get_single_batch()

    def test07_get_single_batch_no_batch_multiple_pickings(self):
        """
        Should create a batch for the current user when a multiple
        pickings exists; the new batch should have only a single
        picking.

        """
        Batch = self.env['stock.picking.batch']
        Package = self.env['stock.quant.package']

        for idx in range(3):
            pack = Package.get_package("test_package_%d" % idx, create=True)
            self.create_quant(self.apple.id, self.test_location_01.id, 4,
                              package_id=pack.id)
            self.create_picking(self.picking_type_pick,
                                products_info=self.pack_4apples_info,
                                confirm=True,
                                assign=True)

        batch = Batch.get_single_batch()

        self.assertIsNotNone(batch, "No batch created")
        self.assertEqual(batch.user_id.id, self.env.user.id,
                         "Batch responsible is not the current user")
        self.assertEqual(len(batch.picking_ids), 1,
                         "Batch does not include single picking")

    def test08_create_batch_with_priorities(self):
        """
        Should create a batch by correctly filtering pickings by
        priority.

        """
        Batch = self.env['stock.picking.batch']
        Package = self.env['stock.quant.package']

        for idx in range(4):
            pack = Package.get_package("test_package_%d" % idx, create=True)
            self.create_quant(self.apple.id, self.test_location_01.id, 4,
                              package_id=pack.id)
            self.create_picking(self.picking_type_pick,
                                products_info=self.pack_4apples_info,
                                confirm=True,
                                assign=True,
                                priority=str(idx))

        batch = Batch.create_batch(["2"])

        self.assertIsNotNone(batch, "No batch created")
        self.assertEqual(len(batch.picking_ids), 1,
                         "Multiple pickings were included in the batch")
        self.assertEqual(batch.picking_ids[0].priority, "2",
                         "Does not have a picking with the expected priority")

    def test09_create_batch_user_already_has_completed_batch(self):
        """
        Should create a new batch in case the user already has a
        batch assigned to him but all the included pickings are
        complete.

        """
        Batch = self.env['stock.picking.batch']
        Package = self.env['stock.quant.package']

        # set a batch with a complete picking
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        batch = Batch.get_single_batch()
        picking.state = 'done'

        # create a new picking to be included in the new batch
        other_pack = Package.get_package("test_other_package", create=True)
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=other_pack.id)
        other_picking = self.create_picking(self.picking_type_pick,
                                            products_info=self.pack_4apples_info,
                                            confirm=True,
                                            assign=True)

        # check pre-conditions
        self.assertEqual(len(batch.picking_ids), 1)
        self.assertEqual(batch.state, 'in_progress')
        self.assertEqual(batch.picking_ids[0].state, 'done')

        # method under test
        new_batch = Batch.create_batch(None)

        # check outcome
        self.assertIsNotNone(new_batch, "No batch created")
        self.assertEqual(len(new_batch.picking_ids), 1,
                         "Multiple pickings were included in the batch")
        self.assertEqual(new_batch.picking_ids[0].id, other_picking.id,
                         "Does not include the expected picking")
        self.assertEqual(batch.state, 'done', "Old batch was not completed")

    def test10_create_batch_error_user_has_incomplete_batched_pickings(self):
        """
        Should error in case a the user already has a batch assigned
        to him with incomplete pickings.

        """
        Batch = self.env['stock.picking.batch']
        Package = self.env['stock.quant.package']

        # set a batch with a complete picking
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        batch = Batch.get_single_batch()
        picking.state = 'assigned'

        # create a new picking to be included in the new batch
        other_pack = Package.get_package("test_other_package", create=True)
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=other_pack.id)
        self.create_picking(self.picking_type_pick,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)

        # check pre-conditions
        self.assertEqual(len(batch.picking_ids), 1)
        self.assertEqual(batch.state, 'in_progress')
        self.assertEqual(batch.picking_ids[0].state, 'assigned')

        # method under test
        with self.assertRaises(ValidationError):
            Batch.create_batch(None)

    def test11_drop_off_picked(self):
        """ Marks the batch as done if the picking is complete """
        Batch = self.env['stock.picking.batch']

        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)
        batch = Batch.create_batch(None)
        picking.state = 'done'

        # check pre-conditions
        self.assertEqual(len(batch.picking_ids), 1)
        self.assertEqual(batch.state, 'in_progress')
        self.assertEqual(batch.picking_ids[0].state, 'done')

        # method under test
        batch.drop_off_picked(True, self.test_location_01.barcode)

        self.assertEqual(batch.state, 'done', "Batch was not completed")

    def _create_valid_batch_for_location_tests(self):
        Batch = self.env['stock.picking.batch']

        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=self.pack_4apples_info,
                                      confirm=True,
                                      assign=True)

        return picking, Batch.create_batch(None)

    def test12_is_valid_location_dest_success(self):
        """ Returns True for a valid location """
        _, batch = self._create_valid_batch_for_location_tests()

        self.assertTrue(
            batch.is_valid_location_dest_id(self.test_location_02.id),
            "A valid dest location is wrongly marked as invalid")

    def test13_is_valid_location_dest_failure_invalid_location(self):
        """ Returns False for a invalid location """
        Location = self.env['stock.location']

        some_location = Location.create(
            {'name': "some location name",
             'barcode': "LTEST13",
             'location_id': self.test_location_02.id})
        picking, batch = self._create_valid_batch_for_location_tests()
        picking.location_dest_id = some_location

        for ml in picking.mapped('move_line_ids'):
            ml.qty_done = 4

        # check pre-conditions
        self.assertEqual(len(batch.picking_ids), 1)
        self.assertEqual(batch.state, 'in_progress')
        self.assertEqual(batch.picking_ids[0].id, picking.id)
        self.assertEqual(batch.picking_ids[0].location_dest_id.id,
                         some_location.id)

        # method under test
        self.assertFalse(
            batch.is_valid_location_dest_id(self.test_location_02.id),
            "An invalid dest location is wrongly marked as valid")

    def test14_is_valid_location_dest_failure_unknown_location(self):
        """ Returns False for an unknown location """
        _, batch = self._create_valid_batch_for_location_tests()

        self.assertFalse(
            batch.is_valid_location_dest_id("this location does not exist"),
            "An invalid dest location is wrongly marked as valid")
