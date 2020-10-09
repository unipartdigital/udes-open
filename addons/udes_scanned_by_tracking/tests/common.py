from odoo.tests import common


@common.at_install(False)
@common.post_install(True)
class BaseScannedBy(common.SavepointCase):
    """These are duplicated from udes_stock however there was no other reason to
    add udes_stock as a dependency so duplication seemed like a better approach
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Picking types
        cls.picking_type_internal = cls.env.ref("stock.picking_type_internal")

        # Products
        cls.apple = cls.create_product("Apple")
        cls.banana = cls.create_product("Banana")

        # Locations
        Location = cls.env["stock.location"]
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.test_location_01 = Location.create(
            {
                "name": "Test location 01",
                "barcode": "LTEST01",
                "location_id": cls.stock_location.id,
            }
        )
        cls.test_location_02 = Location.create(
            {
                "name": "Test location 02",
                "barcode": "LTEST02",
                "location_id": cls.stock_location.id,
            }
        )
        cls.test_locations = cls.test_location_01 + cls.test_location_02

    @classmethod
    def create_product(cls, name, **kwargs):
        """ Create and return a product."""
        Product = cls.env["product.product"]
        vals = {
            "name": "Test product {}".format(name),
            "barcode": "product{}".format(name),
            "default_code": "product{}".format(name),
            "type": "product",
        }
        vals.update(kwargs)
        return Product.create(vals)

    @classmethod
    def create_quant(cls, product_id, location_id, qty, serial_number=None, **kwargs):
        """ Create and return a quant of a product at location."""
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
        return Quant.create(vals)

    @classmethod
    def create_user(cls, name, login, **kwargs):
        """ Create and return a user"""
        User = cls.env["res.users"]
        # Creating user without company
        # takes company from current user
        vals = {
            "name": name,
            "login": login,
        }
        vals.update(kwargs)
        user = User.create(vals)

        # some action require email setup even if the email is not really sent
        user.partner_id.email = login

        return user

    @classmethod
    def create_quant(cls, product_id, location_id, qty, serial_number=None, **kwargs):
        """ Create and return a quant of a product at location."""
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
        return Quant.create(vals)

    @classmethod
    def create_picking(
        cls, picking_type, products_info=False, confirm=False, assign=False, **kwargs
    ):
        """ Create and return a picking for the given picking_type."""
        Picking = cls.env["stock.picking"]
        vals = {
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
        }

        vals.update(kwargs)
        picking = Picking.create(vals)

        if products_info:
            for product_info in products_info:
                product_info.update(picking=picking)
                move = cls.create_move(**product_info)

        if confirm:
            picking.action_confirm()

        if assign:
            picking.action_assign()

        return picking

    @classmethod
    def create_move(cls, product, qty, picking, **kwargs):
        """ Create and return a move for the given product and qty."""
        Move = cls.env["stock.move"]
        vals = {
            "product_id": product.id,
            "name": product.name,
            "product_uom": product.uom_id.id,
            "product_uom_qty": qty,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
            "picking_id": picking.id,
            "priority": picking.priority,
            "picking_type_id": picking.picking_type_id.id,
        }
        vals.update(kwargs)
        return Move.create(vals)

    @classmethod
    def create_company(cls, name, **kwargs):
        """Create and return a company"""
        Company = cls.env["res.company"]
        vals = {"name": name}
        vals.update(kwargs)
        return Company.create(vals)
