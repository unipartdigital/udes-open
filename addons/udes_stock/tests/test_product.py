from .common import BaseUDES
from odoo.exceptions import ValidationError, UserError
from unittest import skip


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
        Product = cls.env["product.product"]
        products = Product.search([])
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
