from .common import BaseUDES
from odoo.exceptions import ValidationError


class TestProductMethods(BaseUDES):
    def test_assert_serial_numbers(self):
        self.starwberry_lot = self.create_lot(self.strawberry.id, "strawberry_lot")

        with self.assertRaises(ValidationError):
            self.strawberry.assert_serial_numbers([self.starwberry_lot.name, "test_lot"])
