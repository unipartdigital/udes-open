# -*- coding: utf-8 -*-

from . import common

from odoo.exceptions import ValidationError


class TestGoodsInPickingBatch(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGoodsInPickingBatch, cls).setUpClass()
        User = cls.env['res.users']
        Location = cls.env['stock.location']

        user_warehouse = User.get_user_warehouse()
        cls.user_warehouse = user_warehouse
        # create new pick picking type to avoid problems with existing picks
        wh_picking_type_pick = user_warehouse.pick_type_id.copy({'name': 'TEST PICK'})
        cls.picking_type_pick = wh_picking_type_pick.copy({'name': 'TEST PICK'})
        user_warehouse.pick_type_id = cls.picking_type_pick
        # create new internal picking type to avoid problems
        cls.picking_type_internal = cls.picking_type_internal.copy({'name': 'TEST INTERNAL'})
        user_warehouse.int_type_id = cls.picking_type_internal
        cls.pack_4apples_info = [{'product': cls.apple,
                                  'qty': 4}]

        cls.test_output_location_01 = Location.create({
            'name': "Test output location 01",
            'barcode': "LTESTOUT01",
            'location_id': user_warehouse.pick_type_id.default_location_dest_id.id})

    def setUp(self):
        super(TestGoodsInPickingBatch, self).setUp()
        Package = self.env['stock.quant.package']

        self.package_one = Package.get_package("test_package_one", create=True)
        self.package_two = Package.get_package("test_package_two", create=True)

    def test01_check_user_id_raise_with_empty_id_string(self):
        """ Should error if passed an empty id """
        batch = self.create_batch()

        with self.assertRaises(ValidationError) as err:
            batch._check_user_id("")

        self.assertEqual(err.exception.name, "Cannot determine the user.")

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
        Get single batch returns none when no batch has been
        created for the current user.

        """
        Batch = self.env['stock.picking.batch']

        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        self.create_picking(self.picking_type_pick,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)
        batch = Batch.get_single_batch()

        self.assertIsNone(batch, "Unexpected batch found")

    def test06_get_single_batch_error_multiple_batches(self):
        """
        Should raise an error when the user already has (by
        instrumenting the datastore) multiple batches in the
        'in_progress' state associated with the user.

        """
        Batch = self.env['stock.picking.batch']

        self.create_batch(state='in_progress')
        self.create_batch(state='in_progress')
        batches = Batch.search([('user_id', '=', self.env.user.id),
                                ('state', '=', 'in_progress')])

        # check pre-conditions
        self.assertEqual(len(batches), 2)

        with self.assertRaises(ValidationError) as err:
            Batch.get_single_batch()

        self.assertEqual(
            err.exception.name,
            "Found 2 batches for the user, please contact administrator.")

    def test07_get_single_batch_no_batch_multiple_pickings(self):
        """
        Get single batch returns none when no batch has been
        created for the current user, even having multiple pickings.

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

        self.assertIsNone(batch, "Unexpected batch found")

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
        batch = Batch.create_batch(None)
        picking.update_picking(force_validate=True,
                               location_dest_id=self.test_output_location_01.id)

        # create a new picking to be included in the new batch
        other_pack = Package.get_package("test_other_package", create=True)
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=other_pack.id)
        other_picking = self.create_picking(self.picking_type_pick,
                                            products_info=self.pack_4apples_info,
                                            confirm=True,
                                            assign=True)

        # check pre-conditions
        self.assertEqual(picking.state, 'done')
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
        self.create_picking(self.picking_type_pick,
                            products_info=self.pack_4apples_info,
                            confirm=True,
                            assign=True)
        batch = Batch.create_batch(None)

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
        with self.assertRaises(ValidationError) as err:
            Batch.create_batch(None)

        self.assertTrue(
            err.exception.name.startswith("The user already has pickings"))

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
        picking.update_picking(force_validate=True,
                               location_dest_id=self.test_output_location_01.id)

        # check pre-conditions
        self.assertEqual(len(batch.picking_ids), 1)
        self.assertEqual(batch.state, 'in_progress')
        self.assertEqual(batch.picking_ids[0].state, 'done')

        # method under test
        batch.drop_off_picked(False, self.test_location_01.barcode)

        self.assertEqual(batch.state, 'done', "Batch was not completed")

    def _create_valid_batch(self):
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
        picking, batch = self._create_valid_batch()
        picking.update_picking(package_name=self.package_one.name)

        self.assertTrue(
            batch.is_valid_location_dest_id(self.test_output_location_01.id),
            "A valid dest location is wrongly marked as invalid")

    def test13_is_valid_location_dest_failure_invalid_location(self):
        """ Returns False for a invalid location """
        _, batch = self._create_valid_batch()

        self.assertTrue(
            batch.is_valid_location_dest_id(self.test_location_02.id),
            "A valid dest location is wrongly marked as invalid")

    def test14_is_valid_location_dest_failure_unknown_location(self):
        """ Returns False for an unknown location """
        picking, batch = self._create_valid_batch()
        picking.update_picking(package_name=self.package_one.name)

        self.assertFalse(
            batch.is_valid_location_dest_id("this location does not exist"),
            "An invalid dest location is wrongly marked as valid")

    def test15_unpickable_item_single_move_line_success_default_type(self):
        """
        Tests that the picking is confirmed and an internal transfer is created
        if a picking type is not specified. The picking remains confirmed
        because there isn't more stock available.
        """
        picking, batch = self._create_valid_batch()
        move_line = picking.move_line_ids[0]
        reason = 'missing item'
        batch.unpickable_item(package_name=move_line.package_id.name,
                              reason=reason,
                              picking_type_id=None)
        internal_picking = self.package_one.find_move_lines().picking_id

        self.assertEqual(picking.state, 'confirmed',
                         'picking was not confirmed')
        self.assertEqual(batch.state, 'done',
                         'batch state was not completed')
        self.assertEqual(internal_picking.picking_type_id,
                         self.picking_type_internal,
                         'internal picking type not set by unpickable_item')
        self.assertEqual(internal_picking.state, 'assigned',
                         'internal picking creation has not completed')

    def test16_unpickable_item_single_move_line_success_specified_type(self):
        """
        Tests that the picking is confirmed and the specified picking type
        is created for the unpickable stock. The picking remains confirmed
        because there isn't more stock available.
        """
        picking, batch = self._create_valid_batch()
        move_line = picking.move_line_ids[0]
        reason = 'missing item'

        # It doesn't actually matter what the picking type is for this test.
        # The important thing is that the new picking is of type picking_type
        picking_type = self.picking_type_pick
        batch.unpickable_item(package_name=move_line.package_id.name,
                              reason=reason,
                              picking_type_id=picking_type.id)
        internal_picking = self.package_one.find_move_lines().picking_id

        self.assertEqual(picking.state, 'confirmed',
                         'picking was not confirmed')
        self.assertEqual(batch.state, 'done',
                         'batch state was not completed')
        self.assertEqual(internal_picking.picking_type_id, picking_type,
                         'internal picking type not set by unpickable_item')
        self.assertEqual(internal_picking.state, 'assigned',
                         'internal picking creation has not completed')

    def test17_unpickable_item_package_not_found(self):
        """
        Tests that a ValidationError is raised if the package cannot be
        found in the system
        """
        Package = self.env['stock.quant.package']
        picking, batch = self._create_valid_batch()

        reason = 'missing item'
        package_name = "NOTAPACKAGENAME666"

        self.assertFalse(Package.search([('name', '=', package_name)]),
                         'Package %s already exists' % package_name)
        expected_error = 'Package not found for identifier %s' % package_name
        with self.assertRaisesRegex(ValidationError, expected_error,
                                    msg='Incorrect error thrown'):
            batch.unpickable_item(package_name=package_name,
                                  reason=reason,
                                  picking_type_id=None)

    def test18_unpickable_item_wrong_batch(self):
        """
        Tests that a ValidationError is raised if the package is not on
        the Batch that we requested.
        """
        picking, batch = self._create_valid_batch()
        # Create a quant and picking for a different package
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_two.id)
        different_picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True)
        move_line = different_picking.move_line_ids[0]
        reason = 'missing item'

        expected_error = 'Cannot find move lines todo for unpickable item ' \
                         'in this batch'
        with self.assertRaisesRegex(ValidationError, expected_error,
                                    msg='Incorrect error thrown'):
            batch.unpickable_item(package_name=move_line.package_id.name,
                                  reason=reason,
                                  picking_type_id=None)

    def test19_unpickable_item_invalid_state_cancel(self):
        """
        Tests that a ValidationError is raised if the package move lines
        cannot be found in the wave because the picking is on a state of
        cancel
        """
        picking, batch = self._create_valid_batch()
        # Not ideal but it allows the test to pass.  If we did:
        # picking.action_cancel() it would delete the move_lines which would
        # cause this test to fail incorrectly.
        picking.state = 'cancel'
        move_line = picking.move_line_ids[0]
        reason = 'missing item'

        expected_error = 'Cannot find move lines todo for unpickable item ' \
                         'in this batch'
        with self.assertRaisesRegex(ValidationError, expected_error,
                                    msg='Incorrect error thrown'):
            batch.unpickable_item(package_name=move_line.package_id.name,
                                  reason=reason,
                                  picking_type_id=None)

    def test20_unpickable_item_invalid_state_done(self):
        """
        Tests that a ValidationError is raised if the package move lines
        cannot be found in the wave because the picking is on a state of
        done
        """
        picking, batch = self._create_valid_batch()
        picking.update_picking(force_validate=True,
                               location_dest_id=self.test_output_location_01.id)

        move_line = picking.move_line_ids[0]
        reason = 'missing item'

        expected_error = 'Cannot find move lines todo for unpickable item ' \
                         'in this batch'
        with self.assertRaisesRegex(ValidationError, expected_error,
                                    msg='Incorrect error thrown'):
            batch.unpickable_item(package_name=move_line.package_id.name,
                                  reason=reason,
                                  picking_type_id=None)

    def test21_unpickable_item_multiple_move_lines_different_packages(self):
        """
        Tests that a backorder is created and confirmed if there are multiple
        move lines on the picking. The original picking should continue to
        have the still pickable product on it.
        """
        Batch = self.env['stock.picking.batch']
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        self.create_quant(self.banana.id, self.test_location_01.id, 4,
                          package_id=self.package_two.id)
        products_info = [{'product': self.apple,
                          'qty': 4},
                         {'product': self.banana,
                          'qty': 4}]
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=products_info,
                                      confirm=True,
                                      assign=True)
        batch = Batch.create_batch(None)

        self.assertTrue(len(picking.move_line_ids) > 1,
                        'number of move_lines not expected')
        unpickable_move_line = picking.move_line_ids[0]
        unpickable_package = unpickable_move_line.package_id

        reason = 'missing item'

        batch.unpickable_item(package_name=unpickable_package.name,
                              reason=reason,
                              picking_type_id=None)

        new_picking = unpickable_package.find_move_lines().picking_id

        # Because there are other move_line_ids that are still pickable we
        # need to ensure that the original picking is still assigned
        self.assertEqual(picking.state, 'assigned',
                         'picking was not assigned')

        # TODO: add a new test like this one but where we have stock,
        #       which means the moves/move_lines of the backorder will
        #       be moved back to original picking and the backorder deleted

        # Check backorder has been created
        self.assertEqual(len(picking.u_created_back_orders), 1)
        # Check backorder state
        self.assertEqual(picking.u_created_back_orders.state, 'confirmed')

        # Ensure that our unpickable move_line is not in the picking
        self.assertNotIn(unpickable_move_line, picking.move_line_ids,
                         'unpickable_move_line has not been removed '
                         'from picking')

        # Ensure investigation picking is assigned and with the reason
        self.assertEqual(new_picking.state, 'assigned',
                         'picking creation has not completed properly')
        self.assertEqual(new_picking.group_id.name, reason,
                         'reason was not assigned correctly')

    def test22_unpickable_item_multiple_move_lines_same_package(self):
        """
        Tests that if there are multiple move lines on the same package
        that the picking remains in state confirmed and a new picking
        is created of type picking_types
        """
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        self.create_quant(self.banana.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        products_info = [{'product': self.apple,
                          'qty': 4},
                         {'product': self.banana,
                          'qty': 4}]
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=products_info,
                                      confirm=True,
                                      assign=True)
        Batch = self.env['stock.picking.batch']
        batch = Batch.create_batch(None)

        self.assertTrue(len(picking.move_line_ids) > 1,
                        'number of move_lines not expected')
        unpickable_move_line = picking.move_line_ids[0]
        unpickable_package = unpickable_move_line.package_id

        reason = 'missing item'

        batch.unpickable_item(package_name=unpickable_package.name,
                              reason=reason,
                              picking_type_id=None)

        new_picking = unpickable_package.find_move_lines().mapped('picking_id')
        self.assertEqual(picking.state, 'confirmed',
                         'picking was not confirmed')
        # Check no backorder has been created
        self.assertEqual(len(picking.u_created_back_orders), 0)

        self.assertEqual(new_picking.state, 'assigned',
                         'picking creation has not completed properly')
        self.assertEqual(new_picking.group_id.name, reason,
                         'reason was not assigned correctly')

    def test23_unpickable_item_product_validation_error_missing_location(self):
        """
        Tests that calling unpickable item for a product without location
        raises an error.
        """
        quant = self.create_quant(self.apple.id, self.test_location_01.id, 4)

        products_info = [{'product': self.apple, 'qty': 1}]
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=products_info,
                                      confirm=True,
                                      assign=True)
        # check that only 1 unit of the quant is reserved
        self.assertEqual(quant.reserved_quantity, 1)

        Batch = self.env['stock.picking.batch']
        batch = Batch.create_batch(None)

        self.assertIn(picking, batch.picking_ids)

        reason = 'missing item'
        move_line = picking.move_line_ids[0]

        expected_error = 'Missing location parameter for unpickable' \
                         ' product %s' % move_line.product_id.name
        with self.assertRaisesRegex(ValidationError, expected_error,
                                    msg='Incorrect error thrown'):
            batch.unpickable_item(product_id=move_line.product_id.id,
                                  reason=reason,
                                  picking_type_id=None)

    def test24_unpickable_item_product_ok(self):
        """
        Tests that calling unpickable item for a product with location
        ends up with all the quant reserved for the stock investigation
        and the picking remains in state confirmed since there is no
        more stock.
        """
        quant = self.create_quant(self.apple.id, self.test_location_01.id, 4)

        products_info = [{'product': self.apple, 'qty': 1}]
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=products_info,
                                      confirm=True,
                                      assign=True)
        # check that only 1 unit of the quant is reserved
        self.assertEqual(quant.reserved_quantity, 1)

        Batch = self.env['stock.picking.batch']
        batch = Batch.create_batch(None)

        self.assertIn(picking, batch.picking_ids)

        reason = 'missing item'
        move_line = picking.move_line_ids[0]

        batch.unpickable_item(product_id=move_line.product_id.id,
                              location_id=move_line.location_id.id,
                              reason=reason,
                              picking_type_id=None)
        # after unickable all the quant should be reserved
        self.assertEqual(quant.reserved_quantity, 4)
        # picking state should be confirmed
        self.assertEqual(picking.state, 'confirmed',
                         'picking was not confirmed')
        # Check no backorder has been created
        self.assertEqual(len(picking.u_created_back_orders), 0)

    def test25_unpickable_item_product_ok_multiple_lines(self):
        """
        Tests that calling unpickable item for a product with location
        ends up with all the quant reserved for the stock investigation.
        In this case we have multiple move lines at the picking, so a
        backorder is created and its state is confirmed since there
        is no more stock.
        """
        quant_apple = self.create_quant(self.apple.id, self.test_location_01.id, 4)
        quant_banana = self.create_quant(self.banana.id, self.test_location_01.id, 3)

        products_info = [{'product': self.apple, 'qty': 1},
                         {'product': self.banana, 'qty': 2}]
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=products_info,
                                      confirm=True,
                                      assign=True)
        # check that only 1 unit of the quant is reserved
        self.assertEqual(quant_apple.reserved_quantity, 1)
        self.assertEqual(quant_banana.reserved_quantity, 2)

        Batch = self.env['stock.picking.batch']
        batch = Batch.create_batch(None)

        self.assertIn(picking, batch.picking_ids)

        reason = 'missing item'
        move_line = picking.move_line_ids[0]

        batch.unpickable_item(product_id=move_line.product_id.id,
                              location_id=move_line.location_id.id,
                              reason=reason,
                              picking_type_id=None)
        # after unickable all the quant should be reserved
        self.assertEqual(quant_apple.reserved_quantity, 4)
        # picking state should be assigned
        self.assertEqual(picking.state, 'assigned',
                         'picking was not assigned')

        # TODO: add a new test like this one but where we have stock,
        #       which means the moves/move_lines of the backorder will
        #       be moved back to original picking and the backorder deleted

        # Check no backorder has been created
        self.assertEqual(len(picking.u_created_back_orders), 1)
        # Check backorder state
        self.assertEqual(picking.u_created_back_orders.state, 'confirmed')

    def test26_unpickable_item_product_ok_two_picks(self):
        """
        Tests that calling unpickable item for a product with location
        ends up with all the quant reserved for the stock investigation
        and the picking remains in state confirmed since there is no
        more stock. In case the quant is reserved for more than one picking
        the stock investigation will contain only the quantity of the
        unpickable + available quantity of the quant.
        Example: quant of 4, 1 unit reserved in two pickings, leaves
                 an available quantity of 2, so when unpickable of one
                 of the pickings will create an investigation of 3.
        """
        Batch = self.env['stock.picking.batch']
        Picking = self.env['stock.picking']

        quant = self.create_quant(self.apple.id, self.test_location_01.id, 4)

        products_info = [{'product': self.apple, 'qty': 1}]
        picking = self.create_picking(self.picking_type_pick,
                                      products_info=products_info,
                                      confirm=True,
                                      assign=True)
        # check that only 1 unit of the quant is reserved
        self.assertEqual(quant.reserved_quantity, 1)

        picking_2 = self.create_picking(self.picking_type_pick,
                                      products_info=products_info,
                                      confirm=True,
                                      assign=True)
        # check that now 2 units of the quant are reserved
        self.assertEqual(quant.reserved_quantity, 2)

        batch = Batch.create_batch(None)

        self.assertIn(picking, batch.picking_ids)

        reason = 'missing item'
        move_line = picking.move_line_ids[0]

        batch.unpickable_item(product_id=move_line.product_id.id,
                              location_id=move_line.location_id.id,
                              reason=reason,
                              picking_type_id=self.picking_type_internal.id)
        # after unickable all the quant should be reserved
        self.assertEqual(quant.reserved_quantity, 4)
        # picking state should be confirmed
        self.assertEqual(picking.state, 'confirmed',
                         'picking was not confirmed')
        # Check no backorder has been created
        self.assertEqual(len(picking.u_created_back_orders), 0)

        # check that the investigation has reserved 3 only
        inv_picking = Picking.search([('picking_type_id', '=', self.picking_type_internal.id)])
        self.assertEqual(len(inv_picking), 1)
        self.assertEqual(len(inv_picking.move_line_ids), 1)
        self.assertEqual(inv_picking.move_line_ids[0].product_qty, 3)

