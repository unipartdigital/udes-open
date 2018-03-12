# -*- coding: utf-8 -*-

from odoo.tests import common


class BaseUDES(common.SavepointCase):

    @classmethod
    def setUpClass(cls):
        super(BaseUDES, cls).setUpClass()
        Location = cls.env['stock.location']

        # Locations
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.test_location_01 = Location.create({
                'name': "Test location 01",
                'barcode': "LTEST01",
                'location_id': cls.stock_location.id,
            })
        cls.test_location_02 = Location.create({
                'name': "Test location 02",
                'barcode': "LTEST02",
                'location_id': cls.stock_location.id,
            })
        cls.test_locations = cls.test_location_01 + cls.test_location_02

        # Products

        # Untracked
        cls.apple = cls.create_product('Apple')
        cls.banana = cls.create_product('Banana')
        cls.cherry = cls.create_product('Cherry')
        cls.damson = cls.create_product('Damson')
        cls.elderberry = cls.create_product('Elderberry')
        cls.fig = cls.create_product('Fig')
        cls.grape = cls.create_product('Grape')

        # Serial tracking
        cls.strawberry = cls.create_product('Strawberry', tracking='serial')
        cls.tangerine = cls.create_product('Tangerine', tracking='serial')

        # Picking types
        cls.picking_type_internal = cls.env.ref('stock.picking_type_internal')

    @classmethod
    def create_inventory_line(cls, inventory, product, **kwargs):
        """ Create and return an inventory line for the given inventory and product."""
        InventoryLine = cls.env['stock.inventory.line']
        vals = {
            'product_id': product.id,
            'location_id': inventory.location_id.id,
            'inventory_id': inventory.id,
        }
        vals.update(kwargs)
        return InventoryLine.create(vals)

    @classmethod
    def create_inventory(cls, location, **kwargs):
        """ Create and return an inventory for the given location."""
        Inventory = cls.env['stock.inventory']
        vals = {
            'location_id': location.id,
            'name': location.name,
        }
        vals.update(kwargs)
        return Inventory.create(vals)

    @classmethod
    def create_move_line(cls, move, qty, **kwargs):
        """ Create and return a move line for the given move and qty."""
        MoveLine = cls.env['stock.move.line']
        vals = {
            'product_id': move.product_id.id,
            'product_uom_id': move.product_id.uom_id.id,
            'product_uom_qty': qty,
            'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id,
            'move_id': move.id,
        }
        vals.update(kwargs)
        return MoveLine.create(vals)

    @classmethod
    def create_move(cls, product, qty, picking, **kwargs):
        """ Create and return a move for the given product and qty."""
        Move = cls.env['stock.move']
        vals = {
            'product_id': product.id,
            'name': product.name,
            'product_uom': product.uom_id.id,
            'product_uom_qty': qty,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'picking_id': picking.id,
            'priority': picking.priority,
            'picking_type_id': picking.picking_type_id.id,
        }
        vals.update(kwargs)
        return Move.create(vals)

    @classmethod
    def create_picking(cls, picking_type, products_info=False,
                       confirm=False, assign=False, **kwargs):
        """ Create and return a picking for the given picking_type."""
        Picking = cls.env['stock.picking']
        vals = {
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
        }

        vals.update(kwargs)
        picking = Picking.create(vals)

        if products_info:
            for product_info in products_info:
                product_info.update(picking=picking)
                move = cls.create_move(**product_info)

        if assign:
            picking.action_assign()

        if confirm:
            picking.action_confirm()

        return picking

    @classmethod
    def create_product(cls, name, **kwargs):
        """ Create and return a product."""
        Product = cls.env['product.product']
        vals = {
            'name': 'Test product {}'.format(name),
            'barcode': 'product{}'.format(name),
            'default_code': 'product{}'.format(name),
            'type': 'product',
        }
        vals.update(kwargs)
        return Product.create(vals)

    @classmethod
    def create_quant(cls, product_id, location_id, qty, serial_number=None, **kwargs):
        """ Create and return a quant of a product at location."""
        Quant = cls.env['stock.quant']
        vals = {
            'product_id': product_id,
            'location_id': location_id,
            'quantity': qty,
        }
        if serial_number:
            lot = cls.create_lot(product_id, serial_number)
            vals['lot_id'] = lot.id
        vals.update(kwargs)
        return Quant.create(vals)

    @classmethod
    def create_lot(cls, product_id, serial_number, **kwargs):
        Lot = cls.env['stock.production.lot']

        vals = {
            'name': serial_number,
            'product_id': product_id,
        }
        vals.update(kwargs)
        return Lot.create(vals)

    @classmethod
    def create_user(cls, name, login, **kwargs):
        """ Create and return a user"""
        User = cls.env['res.users']
        # Creating user without company
        # takes company from current user
        vals = {
            'name': name,
            'login': login,
        }
        vals.update(kwargs)
        return User.create(vals)

    @classmethod
    def create_company(cls, name, **kwargs):
        """Create and return a company"""
        Company = cls.env['res.company']
        vals = {
            'name': name
        }
        vals.update(kwargs)
        return Company.create(vals)

    @classmethod
    def create_simple_inbound_route(cls, picking_type_in, picking_type_internal):
        Route = cls.env['stock.location.route']
        Path = cls.env['stock.location.path']
        Sequence = cls.env['ir.sequence']
        Rule  = cls.env['procurement.rule']

        route_vals = {
            "name": "TestPutaway",
            "sequence": 10,
            "product_selectable": False,
            "warehouse_selectable": True,
            "warehouse_ids": [(6, 0, [picking_type_internal.warehouse_id.id])]
        }
        route = Route.create(route_vals)

        # PUTAWAY
        sequence_putaway = Sequence.create({"name": "TestPutaway", "prefix": "TESTPUT", "padding": 5}).id
        picking_type_internal.write({
                                        'sequence_id': sequence_putaway,
                                        'sequence':13
                                     })

        location_path_vals = {
            "name": "TestPutaway",
            "route_id": route.id,
            "sequence": 20,
            "location_from_id": picking_type_in.default_location_dest_id.id,
            "location_dest_id": picking_type_internal.default_location_dest_id.id,
            "picking_type_id": picking_type_internal.id,
        }
        path_in_putaway = Path.create(location_path_vals)

        # procurement_in_putaway_vals = {
        #     "name": "Putaway",
        #     "route_id": route.id,
        #     "sequence": 20,
        #     "location_src_id": picking_type_in.default_location_dest_id.id,
        #     "location_id": picking_type_internal.default_location_dest_id.id,
        #     "action": "move",
        #     "picking_type_id": picking_type_internal.id,
        # }
        # procurement_in_putaway = Rule.create(procurement_in_putaway_vals)

    @classmethod
    def create_batch(cls, **kwargs):
        Batch = cls.env['stock.picking.batch']
        vals = {"user_id": cls.env.user.id}
        vals.update(kwargs)
        return Batch.create(vals)
