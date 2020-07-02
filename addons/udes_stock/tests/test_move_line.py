from . import common
from odoo.exceptions import ValidationError


# NB(ale): the drop location constraint is also tested in
# test_update_picking::TestUpdatePickingMarksMoveLinesAsDone
# via Picking::update_picking

class TestValidateLocationDest(common.BaseUDES):
    ''' Tests the drop location constraint '''

    @classmethod
    def setUpClass(cls):
        super(TestValidateLocationDest, cls).setUpClass()
        cls.picking_type_in.u_target_storage_format = 'product'
        cls._pick_info = [{'product': cls.apple, 'qty': 4}]

    def test01_drop_location_not_suggested_enforced_failure(self):
        """ When the constraint is `enforce`, an error is thrown when
            a valid, but not suggested, drop off location is used.
        """
        self.picking_type_putaway.u_drop_location_constraint = 'enforce'
        self.picking_type_putaway.u_drop_location_policy     = 'by_products'

        self.create_quant(self.apple.id, self.test_location_01.id, 4)
        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4)
        picking = self.create_picking(self.picking_type_putaway,
                                      products_info=self._pick_info,
                                      confirm=True,
                                      assign=True)
        mls = picking.move_line_ids
        locations = picking.get_suggested_locations(mls)

        # We'll use loc 02 to drop off, so we check the assumption
        self.assertEqual(locations, self.test_location_01)
        err_msg = "Drop off location must be one of the suggested locations"

        for ml in mls:
            e = None

            with self.assertRaises(ValidationError) as e:
                ml.write({'location_dest_id': self.test_location_02.id})

            self.assertEqual(e.exception.name, err_msg)

    def test02_drop_location_not_suggested_enforced_with_empty_success(self):
        """ When the constraint is `enforce_with_empty`, no error is thrown
            when an empty, but not suggested, drop off location is used.
        """
        self.picking_type_putaway.u_drop_location_constraint = 'enforce_with_empty'
        self.picking_type_putaway.u_drop_location_policy     = 'by_products'

        self.create_quant(self.apple.id, self.test_location_01.id, 4)
        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4)
        picking = self.create_picking(self.picking_type_putaway,
                                      products_info=self._pick_info,
                                      confirm=True,
                                      assign=True)
        mls = picking.move_line_ids
        locations = picking.get_suggested_locations(mls)

        # We'll use loc 02 to drop off, so we check the assumption
        self.assertEqual(locations, self.test_location_01)

        for ml in mls:
            # Expecting no error
            ml.write({'location_dest_id': self.test_location_02.id})

    def test03_drop_location_not_suggeested_not_enforced(self):
        """ When the constraint is `suggest`, NO error is thrown when a
            valid, but not suggested, drop off location is used.
            NB: same as test01, but with 'suggest' constraint.
        """
        self.picking_type_putaway.u_drop_location_constraint = 'suggest'
        self.picking_type_putaway.u_drop_location_policy = 'by_products'

        self.create_quant(self.apple.id, self.test_location_01.id, 4)

        self.create_quant(self.apple.id,
                          self.picking_type_putaway.default_location_src_id.id,
                          4)
        picking = self.create_picking(self.picking_type_putaway,
                                      products_info=self._pick_info,
                                      confirm=True,
                                      assign=True)
        mls = picking.move_line_ids
        locations = picking.get_suggested_locations(mls)

        # We'll use loc 02 to drop off, so we check the assumption
        self.assertEqual(locations, self.test_location_01)

        for ml in mls:
            # Expecting no error
            ml.write({'location_dest_id': self.test_location_02.id})


    def test04_suggested_drop_location_enforced_success(self):
        """ When the constraint is `enforce` or `enforce_with_empty`,
            NO error is thrown when a suggested drop off location
            is used.
        """
        for constraint in ['enforce', 'enforce_with_empty']:
            self.picking_type_putaway.u_drop_location_constraint = constraint
            self.picking_type_putaway.u_drop_location_policy = 'by_products'

            self.create_quant(self.apple.id, self.test_location_01.id, 4)

            self.create_quant(self.apple.id,
                              self.picking_type_putaway.default_location_src_id.id,
                              4)
            picking = self.create_picking(self.picking_type_putaway,
                                          products_info=self._pick_info,
                                          confirm=True,
                                          assign=True)
            mls = picking.move_line_ids
            locations = picking.get_suggested_locations(mls)

            # We'll use loc 01 to drop off, so we check the assumption
            self.assertEqual(locations, self.test_location_01)

            for ml in mls:
                # Expecting no error
                ml.write({'location_dest_id': self.test_location_01.id})

    def test05_damages_drop_location_enforced_success(self):
        """ When the constraint is `enforce` or `enforce_with_empty`
            and the picking type is configured to handle damages,
            no error is thrown when the damaged stock location is used for
            drop off, even if not suggested.
        """
        Users = self.env['res.users']

        warehouse = Users.get_user_warehouse()
        warehouse.write({
            'u_handle_damages_picking_type_ids': [(4, self.picking_type_putaway.id)]
        })
        warehouse.u_damaged_location_id = self.test_location_02

        for constraint in ['enforce', 'enforce_with_empty']:
            self.picking_type_putaway.u_drop_location_constraint = constraint
            self.picking_type_putaway.u_drop_location_policy     = 'by_products'

            self.create_quant(self.apple.id, self.test_location_01.id, 4)
            self.create_quant(self.apple.id,
                              self.picking_type_putaway.default_location_src_id.id,
                              4)
            picking = self.create_picking(self.picking_type_putaway,
                                          products_info=self._pick_info,
                                          confirm=True,
                                          assign=True)
            mls = picking.move_line_ids
            locations = picking.get_suggested_locations(mls)

            # We'll use loc 02 to drop off, so we check the assumption
            self.assertEqual(locations, self.test_location_01)
            err_msg = "Drop off location must be one of the suggested locations"

            for ml in mls:
                # Expecting no error
                ml.write({'location_dest_id': self.test_location_02.id})
