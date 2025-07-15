from .common import BaseUDES
from odoo.exceptions import ValidationError, UserError
from unittest import skip
from odoo.tools import mute_logger
from psycopg2 import IntegrityError
from ..models.stock_move_line import MEASURE_TYPE_OPTIONS


class TestProductMethods(BaseUDES):

    @skip("We allow multiple lots")
    def test_assert_tracking_unique(self):
        self.starwberry_lot = self.create_lot(self.strawberry.id, "strawberry_lot")

        with self.assertRaises(ValidationError):
            self.strawberry.assert_tracking_unique([self.starwberry_lot.name, "test_lot"])


class TestProductAllowedTrackingValues(BaseUDES):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Change all products tracking to none, in order not to raise any error, when changing allowed
        # tracking types on the warehouse.
        cls.Product = cls.env["product.product"]
        products = cls.Product.search([])
        products.write({"tracking": "none"})

    def test_serial_not_in_allowed_tracking_types(self):
        self.warehouse.u_allowed_tracking_types = "lot,none"
        with self.assertRaises(UserError, msg="You aren't allowed to track a product by Serial Number."):
            self.strawberry.tracking = "serial"

    def test_lot_serial_not_in_allowed_tracking_types(self):
        self.warehouse.u_allowed_tracking_types = "none"
        with self.assertRaises(UserError, msg="You aren't allowed to track a product by Serial Number."):
            self.strawberry.tracking = "serial"

        with self.assertRaises(UserError, msg="You aren't allowed to track a product by Lots."):
            self.strawberry.tracking = "lot"

    def test_tracking_in_allowed_tracking_types(self):
        self.warehouse.u_allowed_tracking_types = "lot,none"
        self.strawberry.tracking = "lot"
        self.assertEqual(self.strawberry.tracking, "lot")
        self.strawberry.tracking = "none"
        self.assertEqual(self.strawberry.tracking, "none")

    def test_cannot_change_warehouse_allowed_tracking_types(self):
        with self.assertRaises(ValidationError):
            self.warehouse.u_allowed_tracking_types = "serial,lot"

    def test_get_product_from_barcodes(self):
        """Test getting product from barcode when the multi barcodes config is not enabled."""
        strawberry_barcode = self.strawberry.barcode
        product = self.Product.get_by_barcode(strawberry_barcode)
        self.assertEqual(self.strawberry, product)


class TestProductMultiBarcodes(BaseUDES):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.ProductBarcode = cls.env["product.barcode"]
        cls.Product = cls.env["product.product"]
        cls.warehouse.u_product_multiple_barcodes = True

    def test_unique_barcode_raise_error_on_same_product(self):
        """
        Testing adding multiple same barcodes raises error.
        """
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            barcodes = ["strawberry", "strawberry"]
            self.add_product_barcodes(self.strawberry, barcodes)

    def test_multi_barcodes_added_successfully(self):
        barcodes = ["bar-strawberry", "strawberry", "strw"]
        self.add_product_barcodes(self.strawberry, barcodes)
        expected_barcodes = self.strawberry.get_all_barcodes()
        self.assertEqual(sorted(barcodes), sorted(expected_barcodes))

    def test_get_product_from_barcodes(self):
        """Test getting product from several barcodes when the multi barcodes config is enabled."""
        barcodes = ["bar-strawberry", "strawberry", "strw"]
        self.add_product_barcodes(self.strawberry, barcodes)
        expected_barcodes = self.strawberry.get_all_barcodes()
        self.assertEqual(sorted(barcodes), sorted(expected_barcodes))
        for barcode in barcodes:
            with self.subTest(barcode=barcode):
                product = self.Product.get_by_barcode(barcodes)
                self.assertEqual(product, self.strawberry)

    def test_get_add_new_barcode(self):
        """
        Testing adding new barcodes will update the list of barcodes as expected.
        """
        barcodes = ["bar-strawberry", "strawberry"]
        self.add_product_barcodes(self.strawberry, barcodes)
        expected_barcodes = self.strawberry.get_all_barcodes()
        self.assertEqual(sorted(barcodes), sorted(expected_barcodes))
        added_barcodes = ["strw"]
        self.add_product_barcodes(self.strawberry, added_barcodes)
        barcodes += added_barcodes
        expected_barcodes = self.strawberry.get_all_barcodes()
        self.assertEqual(sorted(barcodes), sorted(expected_barcodes))


    def test_barcode_field_ignored_when_config_is_enabled(self):
        """
        Testing that when getting list of barcodes ignores the field barcode on the product if multi barcodes config
        is enabled.
        """
        strawberry_barcode = self.strawberry.barcode
        product = self.Product.get_by_barcode(strawberry_barcode)
        self.assertFalse(product)
        strawberry_barcodes = self.strawberry.get_all_barcodes()
        self.assertFalse(strawberry_barcodes)


class TestProductMeasureQuantityConvert(BaseUDES):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Setting different measure qty on product
        cls.strawberry.u_pack_qty = 4
        cls.strawberry.u_carton_qty = 2
        cls.strawberry.u_pallet_qty = 16
        cls.measure_types_factor_mapping = {
            "none": 1,
            "u_pack_qty": 4,
            "u_carton_qty": 2,
            "u_pallet_qty": 16,
        }

    def test_convert_measure_type_quantity(self):
        """Testing that convert measure qty works as expected"""
        for measure_type, _measure_type_label in MEASURE_TYPE_OPTIONS:
            with self.subTest(measure_type=measure_type):
                quantity, measure_qty, quantity_factor = self.strawberry.convert_measure_type_quantity(2, measure_type)
                self.assertEqual(self.measure_types_factor_mapping[measure_type], quantity_factor)
                self.assertEqual(measure_qty, 2)
                self.assertEqual(quantity, 2 * quantity_factor)

    def test_reverse_convert_measure_type_quantity(self):
        """Testing that reverse convert measure qty works as expected"""
        for measure_type, _measure_type_label in MEASURE_TYPE_OPTIONS:
            with self.subTest(measure_type=measure_type):
                quantity, measure_qty, quantity_factor = self.strawberry.convert_measure_type_quantity(
                    32, measure_type, reverse=True
                )
                self.assertEqual(self.measure_types_factor_mapping[measure_type], quantity_factor)
                self.assertEqual(quantity, 32)
                self.assertEqual(measure_qty, int(32 / quantity_factor))
