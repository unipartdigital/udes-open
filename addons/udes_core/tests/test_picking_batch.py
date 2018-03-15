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
        cls.picking_type_pick = user_warehouse.pick_type_id
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

        self.create_batch(state='in_progress')
        self.create_batch(state='in_progress')
        batches = Batch.search([('user_id', '=', self.env.user.id)])

        # check pre-conditions
        self.assertEqual(len(batches), 2)

        with self.assertRaises(ValidationError) as err:
            Batch.get_single_batch()

        self.assertEqual(
            err.exception.name,
            "Found 2 batches for the user, please contact administrator.")

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
        batch = Batch.get_single_batch()

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
        picking, batch = self._create_valid_batch_for_location_tests()
        picking.update_picking(package_name=self.package_one.name)

        self.assertTrue(
            batch.is_valid_location_dest_id(self.test_output_location_01.id),
            "A valid dest location is wrongly marked as invalid")

    def test13_is_valid_location_dest_failure_invalid_location(self):
        """ Returns False for a invalid location """
        _, batch = self._create_valid_batch_for_location_tests()

        self.assertTrue(
            batch.is_valid_location_dest_id(self.test_location_02.id),
            "A valid dest location is wrongly marked as invalid")

    def test14_is_valid_location_dest_failure_unknown_location(self):
        """ Returns False for an unknown location """
        picking, batch = self._create_valid_batch_for_location_tests()
        picking.update_picking(package_name=self.package_one.name)

        self.assertFalse(
            batch.is_valid_location_dest_id("this location does not exist"),
            "An invalid dest location is wrongly marked as valid")

    def test15_unpickable_item_single_move_line_has_package_success_internal_transfer(self):  # noqa
        """
        Tests that the picking is cancelled and an internal transfer is created
        if a picking type is not specified.
        """
        picking, batch = self._create_valid_batch_for_location_tests()
        picking.update_picking(package_name=self.package_one.name)
        move_line_id = picking.move_line_ids[0].id
        reason = 'missing item'
        batch.unpickable_item(move_line_id=move_line_id,
                              reason=reason,
                              picking_type_id=None)
        picking_type = self.package_one.move_line_ids.picking_id.picking_type_id  # noqa

        self.assertEqual(picking.state, 'cancel')
        self.assertEqual(batch.state, 'done')
        self.assertEqual(picking_type.name, 'Internal Transfer')

    def test16_unpickable_item_single_move_line_has_package_success_picking_type_specified(self):  # noqa
        """
        Tests that the picking is cancelled and the specified picking type
        is created for the unpickable stock
        """
        picking, batch = self._create_valid_batch_for_location_tests()
        picking.update_picking(package_name=self.package_one.name)
        move_line_id = picking.move_line_ids[0].id
        reason = 'missing item'

        # It doesn't actually matter what the picking type is for this test.
        # The important thing is that the new picking is of type picking_type
        picking_type = self.picking_type_pick
        batch.unpickable_item(move_line_id=move_line_id,
                              reason=reason,
                              picking_type_id=picking_type.id)
        new_picking_type = self.package_one.move_line_ids.picking_id.picking_type_id  # noqa

        self.assertEqual(picking.state, 'cancel')
        self.assertEqual(batch.state, 'done')
        self.assertEqual(new_picking_type.name, picking_type.name)

    def test17_unpickable_item_move_line_not_found(self):
        """
        Tests that a ValidationError is raised if the move_line_id cannot be
        found
        """
        picking, batch = self._create_valid_batch_for_location_tests()
        picking.state = 'done'
        reason = 'missing item'

        with self.assertRaises(ValidationError) as err:
            batch.unpickable_item(move_line_id=999,
                                  reason=reason,
                                  picking_type_id=None)
            self.assertEqual(err.exception.name,
                             'Cannot find the operation')

    def test18_unpickable_item_wrong_batch(self):
        """
        Tests that a ValidationError is raised if the move_line_id is not on
        the Batch that we requested.
        """
        picking, batch = self._create_valid_batch_for_location_tests()
        # Create a quant and picking for a different package
        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_two.id)
        different_picking = self.create_picking(
            self.picking_type_pick,
            products_info=self.pack_4apples_info,
            confirm=True,
            assign=True)
        different_picking.update_picking(package_name=self.package_two.name)
        move_line_id = different_picking.move_line_ids[0].id
        reason = 'missing item'
        with self.assertRaises(ValidationError) as err:
            batch.unpickable_item(move_line_id=move_line_id,
                                  reason=reason,
                                  picking_type_id=None)
            self.assertEqual(err.exception.name,
                             'Move line is not part of the batch')

    def test19_unpickable_item_invalid_state_cancel(self):
        """
        Tests that a ValidationError is raised if the picking is on a state
        of cancel
        """
        picking, batch = self._create_valid_batch_for_location_tests()
        picking.state = 'cancel'
        move_line_id = picking.move_line_ids[0].id
        reason = 'missing item'
        with self.assertRaises(ValidationError) as err:
            batch.unpickable_item(move_line_id=move_line_id,
                                  reason=reason,
                                  picking_type_id=None)
            self.assertEqual(err.exception.name,
                             'Cannot mark a move line as unpickable '
                             'when it is part of a completed Picking')

    def test20_unpickable_item_invalid_state_done(self):
        """
        Tests that a ValidationError is raised if the picking is on a state of
        done
        """
        picking, batch = self._create_valid_batch_for_location_tests()
        picking.state = 'done'
        move_line_id = picking.move_line_ids[0].id
        reason = 'missing item'
        with self.assertRaises(ValidationError) as err:
            batch.unpickable_item(move_line_id=move_line_id,
                                  reason=reason,
                                  picking_type_id=None)
            self.assertEqual(err.exception.name,
                             'Cannot mark a move line as unpickable '
                             'when it is part of a completed Picking')

    def test18_unpickable_item_no_package_vaidation_error(self):
        """
        Tests that ValidationError is raised if the move_line does not have
        a package.  This functionality is not yet handled by the system.
        :return:
        """
        picking, batch = self._create_valid_batch_for_location_tests()
        reason = 'missing item'
        move_line = picking.move_line_ids[0]
        # Make the move_line not have a package.
        move_line.package_id = None
        with self.assertRaises(ValidationError) as err:
            batch.unpickable_item(move_line_id=move_line.id,
                                  reason=reason,
                                  picking_type_id=None)

            self.assertEqual(err.exception.name,
                             'Not Implemented')

    def test19_unpickable_item_multiple_move_lines(self):
        """
        Tests that a backorder is created if there are multiple move lines
        on the picking
        """
        Picking = self.env['stock.picking']
        PickingType = self.env['stock.picking.type']
        picking_type = PickingType.search([('name', '=', 'Internal Transfer')])
        picking, batch = self._create_valid_batch_for_location_tests()

        unpickable_move_line = picking.move_line_ids[0]
        bananas_pack = {'product': self.banana,
                        'picking': picking,
                        'qty': 7}
        # Create another move_line_id that is still pickable
        move = self.create_move(**bananas_pack)
        self.create_move_line(move=move,
                              qty=7,
                              picking_id=picking.id)
        reason = 'missing item'

        batch.unpickable_item(move_line_id=unpickable_move_line.id,
                              reason=reason,
                              # We use a picking type here so it's easier to
                              # assert that the move_line was created on a new
                              # picking
                              picking_type_id=picking_type.id)
        # Because there are other move_line_ids that are still pickable we
        # need to ensure that the original picking is not cancelled
        investigation_picking = Picking.search(
            [('picking_type_id', '=', picking_type.id,),
             ('product_id', '=', self.apple.id)])

        self.assertNotEqual(picking.state, 'cancel')
        # Ensure that our unpickable move_line is not in the picking
        self.assertNotEqual(unpickable_move_line, picking.move_line_ids)
        self.assertEqual(investigation_picking.picking_type_id.name,
                         'Internal Transfer')
