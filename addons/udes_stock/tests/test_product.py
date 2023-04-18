from .common import BaseUDES
from odoo.exceptions import ValidationError


class TestProductMethods(BaseUDES):
    def test_assert_tracking_unique(self):
        self.starwberry_lot = self.create_lot(self.strawberry.id, "strawberry_lot")

        with self.assertRaises(ValidationError):
            self.strawberry.assert_tracking_unique([self.starwberry_lot.name, "test_lot"])
