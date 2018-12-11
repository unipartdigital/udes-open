from . import common
from odoo.exceptions import ValidationError

class TestLocationCategory(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestLocationCategory, cls).setUpClass()
        cls.picking_type_pick.u_use_location_categories = True
        cls.pack_4apples_info = [{'product': cls.apple, 'qty': 4}]

    def setUp(self):
        super(TestLocationCategory, self).setUp()
        Package = self.env['stock.quant.package']

        self.package_one = Package.get_package("test_package_one", create=True)
        self.package_two = Package.get_package("test_package_two", create=True)

    def test01_user_location_categories(self):
        """ Test set/get location categories for the current user
        """
        Users = self.env['res.users']

        Users = Users.sudo(self.outbound_user)

        self.assertEqual(len(self.outbound_user.u_location_category_ids), 0)
        category_ids = self.location_category_high.ids
        self.assertTrue(Users.set_user_location_categories(category_ids))
        categories = Users.get_user_location_categories()
        self.assertEqual(len(categories), 1)

    def test02_batch_location_categories(self):
        """ Test batch creation using location categories.
        """
        Batch = self.env['stock.picking.batch']
        Users = self.env['res.users']

        Batch = Batch.sudo(self.outbound_user)
        Users = Users.sudo(self.outbound_user)

        self.test_location_01.u_location_category_id = self.location_category_ground
        self.test_location_02.u_location_category_id = self.location_category_high

        # set user setting to pick high locations
        category_ids = self.location_category_high.ids
        self.assertTrue(Users.set_user_location_categories(category_ids))

        self.create_quant(self.apple.id, self.test_location_01.id, 4,
                          package_id=self.package_one.id)
        ground_pick = self.create_picking(self.picking_type_pick,
                                          products_info=self.pack_4apples_info,
                                          confirm=True,
                                          assign=True)
        self.assertEqual(ground_pick.u_location_category_id,
                         self.location_category_ground)

        self.create_quant(self.apple.id, self.test_location_02.id, 4,
                          package_id=self.package_two.id)
        high_pick = self.create_picking(self.picking_type_pick,
                                        products_info=self.pack_4apples_info,
                                        confirm=True,
                                        assign=True)
        self.assertEqual(high_pick.u_location_category_id,
                         self.location_category_high)
        priority = high_pick.priority

        # since ground_pick is older than high_pick create_batch() should
        # assign it to the user, but since the picking type has location
        # categories enabled and the user setting is to pick high locations
        # it will assign high_pick instead
        batch = Batch.create_batch(self.picking_type_pick.id, [priority])
        self.assertEqual(batch.picking_ids, high_pick)
        self.assertEqual(batch.u_location_category_id,
                         self.location_category_high)

        batch.unlink()

        # change user setting to ground locations
        category_ids = self.location_category_ground.ids
        self.assertTrue(Users.set_user_location_categories(category_ids))

        # now create batch should assign ground_pick as expected
        batch = Batch.create_batch(self.picking_type_pick.id, [priority])
        self.assertEqual(batch.picking_ids, ground_pick)
        self.assertEqual(batch.u_location_category_id,
                         self.location_category_ground)

        batch.unlink()

        # changing the category of the location is propagated to the pick
        self.test_location_01.u_location_category_id = self.location_category_super_high
        # now ground_pick is super high pick
        self.assertEqual(ground_pick.u_location_category_id,
                         self.location_category_super_high)
        super_high_pick = ground_pick

        # change user setting to high locations
        category_ids = self.location_category_high.ids
        self.assertTrue(Users.set_user_location_categories(category_ids))

        # now create batch when user setting is high should assign super high
        # pick because is older than high pick and super high category is child
        # of high category
        batch = Batch.create_batch(self.picking_type_pick.id, [priority])
        self.assertEqual(batch.picking_ids, super_high_pick)
        self.assertEqual(batch.u_location_category_id,
                         self.location_category_super_high)
