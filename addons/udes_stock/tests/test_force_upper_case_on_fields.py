from . import common
from odoo.exceptions import ValidationError


class TestForceUpperCaseOnFields(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestForceUpperCaseOnFields, cls).setUpClass()
        cls.u_force_upper_case_config = '{"product.product": "barcode,default_code", "stock.location": "barcode"}'
        cls.empty_u_force_upper_case_config = '{}'
        cls.warehouse_id = cls.env.ref("stock.warehouse0")
        cls.Location = cls.env["stock.location"]
        cls.lower_case_loc_vals = {'name': 'lower_case_location',
                                   'usage': 'internal',
                                   'barcode': 'lower_case_location'
                                   }
        cls.empty_barcode_loc_vals = {'name': 'empty_case_location',
                                      'usage': 'internal',
                                      }

    def _create_location_for_upper_case_validation(self, vals):
        # not using common.create_location as it always makes barcode in upper case
        location = self.Location.create(vals)
        return location

    def test_regular_product_and_location_creation(self):
        """
        test with empty_u_force_upper_case_config and lower case product/location barcode and default code.
        No upper case validation should be raised
        """
        self.warehouse_id.u_force_upper_case_config = self.empty_u_force_upper_case_config
        product = self.create_product("lower_case_product",
                                      default_code="dc_lower_case_product",
                                      barcode="br_lower_case_product")
        self.assertEqual(product.default_code, "dc_lower_case_product")
        self.assertEqual(product.barcode, "br_lower_case_product")
        location = self._create_location_for_upper_case_validation(self.lower_case_loc_vals)
        self.assertEqual(location.name, "lower_case_location")
        self.assertEqual(location.barcode, "lower_case_location")

    def test_regular_product_and_location_updation(self):
        """
        test with empty_u_force_upper_case_config and lower case product/location barcode and default code.
        No upper case validation should be raised
        """
        self.warehouse_id.u_force_upper_case_config = self.empty_u_force_upper_case_config
        product = self.create_product("lower_case_product2",
                                      default_code="dc_lower_case_product2",
                                      barcode="bc_lower_case_product2")
        self.assertEqual(product.default_code, "dc_lower_case_product2")
        self.assertEqual(product.barcode, "bc_lower_case_product2")
        product.write({
            'default_code': 'new_lower_case_ref',
            'barcode': 'new_lower_case_barcode'

        })
        self.assertEqual(product.default_code, "new_lower_case_ref")
        self.assertEqual(product.barcode, "new_lower_case_barcode")
        location = self._create_location_for_upper_case_validation(self.lower_case_loc_vals)
        location.write({'barcode':"new_lower_case_barcode"})
        self.assertEqual(location.barcode, "new_lower_case_barcode")

    def test_product_and_location_creation_with_u_force_upper_case_config(self):
        """
        test with u_force_upper_case_config and lower case product/location barcode and default code.
        upper case validation should be raised
        """
        self.warehouse_id.u_force_upper_case_config = self.u_force_upper_case_config
        with (self.assertRaises(ValidationError)):
            self.create_product("lower_case_product3",
                                default_code="dc_lower_case_product3",
                                barcode="bc_lower_case_product3")
            self._create_location_for_upper_case_validation(self.lower_case_loc_vals)

    def test_product_and_location_updation_with_u_force_upper_case_config(self):
        """
        test with u_force_upper_case_config and lower case product/location barcode and default code.
        upper case validation should be raised
        """
        self.warehouse_id.u_force_upper_case_config = self.u_force_upper_case_config
        product = self.create_product("lower_case_product3",
                                      default_code="",
                                      barcode="")
        location = self._create_location_for_upper_case_validation(self.empty_barcode_loc_vals)
        with (self.assertRaises(ValidationError)):
            product.write({'barcode': "lower_case_product3"})
            location.write({'barcode': "new_lower_case_barcode"})
