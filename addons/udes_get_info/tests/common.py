"""Common code for testing get_info methods."""
from odoo.tests import common, tagged
from odoo.fields import Datetime
from datetime import timedelta
from itertools import count

@tagged("post_install", "-at_install")
class BaseTestCase(common.SavepointCase):
    """Helper methods for get_info unit tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Counter to ensure stock.quant are created in order
        cls.quant_counter = count()

    @classmethod
    def create_location(cls, name, **kwargs):
        """Create a location for testing."""
        Location = cls.env["stock.location"]

        vals = {"barcode": f"L{name.upper()}", "name": name, **kwargs}
        return Location.create(vals)

    @classmethod
    def create_product(cls, name, **kwargs):
        """Create product for testing."""
        Product = cls.env["product.product"]

        vals = {
            "name": f"Test product {name}",
            "barcode": f"product{name}",
            "default_code": f"product{name}",
            "type": "product",
            **kwargs,
        }
        return Product.create(vals)

    @classmethod
    def create_package(cls, **kwargs):
        """Create package for testing."""
        Package = cls.env["stock.quant.package"]

        vals = {
            **kwargs,
        }
        return Package.create(vals)

    @classmethod
    def create_quant(cls, product_id, location_id, qty, serial_number=None, **kwargs):
        """Create and return a quant of a product at location."""
        Quant = cls.env["stock.quant"]
        vals = {
            "product_id": product_id,
            "location_id": location_id,
            "quantity": qty,
        }
        if serial_number:
            lot = cls.create_lot(product_id, serial_number)
            vals["lot_id"] = lot.id
        vals.update(kwargs)
        #Ensure quants are reserved in order of creation
        vals.setdefault("in_date", Datetime.now() + timedelta(0, next(cls.quant_counter)))
        return Quant.create(vals)

    @classmethod
    def create_lot(cls, product_id, serial_number, **kwargs):
        """Create a lot for testing."""
        Lot = cls.env["stock.production.lot"]
        company = cls.env.ref("base.main_company")

        vals = {
            "company_id": company.id,
            "name": serial_number,
            "product_id": product_id,
        }
        vals.update(kwargs)
        return Lot.create(vals)

    @classmethod
    def get_picking_type_by_name(cls, name):
        """Fetch a picking type by name."""
        # Use existing picking types to avoid having to create new ones.
        PickingType = cls.env["stock.picking.type"]

        # Some picking types are disabled, but that doesn't matter for our
        # tests.
        return PickingType.with_context(active_test=False).search([("name", "=", name)])

    @classmethod
    def create_picking(cls, picking_type, products_info, **kwargs):
        """Create a picking with the provided picking type."""
        Picking = cls.env["stock.picking"]

        confirm = kwargs.pop("confirm", False)
        assign = kwargs.pop("assign", False)

        vals = {
            "picking_type_id": picking_type.id,
            **kwargs,
        }
        picking = Picking.create(vals)
        for product_info in products_info:
            product = product_info["product"]
            product_uom_qty = product_info["qty"]
            move_vals = {
                "location_dest_id": picking.location_dest_id.id,
                "location_id": picking.location_id.id,
                "name": product.name,
                "product_id": product.id,
                "product_uom_qty": product_uom_qty,
            }
            cls.create_move(picking, **move_vals)
        if confirm:
            picking.action_confirm()
        if assign:
            picking.action_assign()
        return picking

    @classmethod
    def create_move(cls, picking, **kwargs):
        """Create a stock move."""
        Move = cls.env["stock.move"]
        unit = cls.env.ref("uom.product_uom_unit")

        vals = {
            "picking_id": picking.id,
            "product_uom": unit.id,
            **kwargs,
        }
        return Move.create(vals)


class GetInfoTestMixin:
    """
    Mixin class for common tests.

    Classes inheriting from this class should define two class-level attributes:
        - object_under_test: the object on which get_info will be called
        - expected_keys: the keys expected in a basic call to get_info
    """

    def test_returns_expected_top_level_keys(self):
        """Check we get the expected keys from the _get_info_field_names field."""
        info = self.object_under_test.get_info()

        self.assertSetEqual(set(info[0].keys()), self.expected_keys)
