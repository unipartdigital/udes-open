from . import common
from odoo.exceptions import ValidationError

class TestGenerateLot(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGenerateLot, cls).setUpClass()
        cls.picking_type_in.u_target_storage_format = 'product'

    def test01_update_picking_missing_lot(self):
        """ Update picking of a tracked product without lot_name should raise
            a ValidationError when u_scan_tracking is yes.
        """
        self.picking_type_in.u_scan_tracking = 'yes'
        create_info = [{'product': self.tangerine, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        picking = picking.sudo(self.inbound_user)
        self.assertEqual(picking.move_lines.quantity_done, 0)

        product_ids = [{'barcode': self.tangerine.barcode, 'qty': 4}]

        msg = 'Missing tracking info for product Test product Tangerine tracked by lot'
        with self.assertRaises(ValidationError) as e:
            picking.update_picking(product_ids=product_ids)
        self.assertEqual(e.exception.name, msg)

    def test02_update_picking_generate_lot(self):
        """ Update picking of a tracked product without lot_name shouldn't raise
            any error when u_scan_tracking is no, and a lot name should be
            automatically generated.
        """
        self.picking_type_in.u_scan_tracking = 'no'

        create_info = [{'product': self.tangerine, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        picking = picking.sudo(self.inbound_user)
        self.assertEqual(picking.move_lines.quantity_done, 0)
        self.assertEqual(picking.mapped('move_line_ids.lot_name'), [False])

        product_ids = [{'barcode': self.tangerine.barcode, 'qty': 4}]

        picking.update_picking(product_ids=product_ids)
        self.assertEqual(picking.move_lines.quantity_done, 4)
        self.assertNotEqual(picking.mapped('move_line_ids.lot_name'), [False])

    def test03_button_validate_generate_lot(self):
        """ Calling button_validate on a picking generates lot names if they
            are not set and u_scan_tracking is no.
        """
        self.picking_type_in.u_scan_tracking = 'no'

        create_info = [{'product': self.tangerine, 'qty': 4}]
        picking = self.create_picking(self.picking_type_in,
                                      products_info=create_info,
                                      confirm=True)
        picking = picking.sudo(self.inbound_user)
        self.assertEqual(picking.move_lines.quantity_done, 0)
        self.assertEqual(picking.mapped('move_line_ids.lot_name'), [False])

        for ml in picking.move_line_ids:
            ml.qty_done = ml.product_uom_qty

        picking.button_validate()

        self.assertEqual(picking.move_lines.quantity_done, 4)
        self.assertNotEqual(picking.mapped('move_line_ids.lot_name'), [False])
