# -*- coding: utf-8 -*-

from odoo.tests import common
from collections import namedtuple

SECURITY_GROUPS = [
    ('inbound', 'udes_stock.group_inbound_user'),
    ('outbound', 'udes_stock.group_outbound_user'),
    ('stock', 'udes_stock.group_stock_user'),
    ('inventory_manager', 'stock.group_stock_manager'),
]


@common.at_install(False)
@common.post_install(True)
class BaseUDES(common.SavepointCase):

    @classmethod
    def setUpClass(cls):
        super(BaseUDES, cls).setUpClass()

        # Products
        ## Untracked
        cls.apple = cls.create_product('Apple')
        cls.banana = cls.create_product('Banana')
        cls.cherry = cls.create_product('Cherry')
        cls.damson = cls.create_product('Damson')
        cls.elderberry = cls.create_product('Elderberry')
        cls.fig = cls.create_product('Fig')
        cls.grape = cls.create_product('Grape')

        ## Serial/Lot tracking
        cls.strawberry = cls.create_product('Strawberry', tracking='serial')
        cls.tangerine = cls.create_product('Tangerine', tracking='lot')

        cls.setup_default_warehouse()

    @classmethod
    def setup_default_warehouse(cls):
        ''' Sets a warehouse with:
            * test locations
                test_input_01, test_stock_01, test_stock_02, test_output_01
            * all picking types as a copy of the default with TEST_ prepended
            * a simple inbound route goods_in->putaway
            * a simple outbound route pick->goods_out
        '''
        cls._setup_picking_types()
        cls._setup_locations()
        cls._setup_routes()
        # Security groups
        cls.security_groups = {name: cls.env.ref(reference)
                               for (name, reference) in SECURITY_GROUPS}
        cls._setup_users()

    @classmethod
    def _setup_picking_types(cls):
        cls._set_test_picking_type('in')
        cls._set_test_picking_type('pick')
        # this order is important as int is overwritten
        cls._set_test_picking_type('int', 'putaway')
        cls._set_test_picking_type('int', 'internal')
        cls._set_test_picking_type('out')

    @classmethod
    def _set_test_picking_type(cls, ptype, name=None):
        User = cls.env['res.users']
        user_warehouse = User.get_user_warehouse()

        if name is None:
            name = ptype

        copy_vals = {'name': 'TEST_{}'.format(name.upper()), 'active': True}
        wh_attr =  getattr(user_warehouse, '{}_type_id'.format(ptype))
        new_pt = wh_attr.copy(copy_vals)
        setattr(cls, 'picking_type_{}'.format(name), new_pt)
        setattr(user_warehouse, '{}_type_id'.format(ptype), new_pt)

    @classmethod
    def _setup_locations(cls):

        Location = cls.env['stock.location']
        cls.stock_location = cls.env.ref('stock.stock_location_stock')

        input_zone = cls.stock_location.copy({'name': 'TEST_INPUT'})
        cls.received_location = Location.create({
            'name': "TEST_RECEIVED",
            'barcode': "LTESTRECEIVED",
            'location_id': input_zone.id,
        })

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

        cls.out_location = cls.picking_type_pick.default_location_dest_id.copy({
            'name': 'TEST_OUT',
            'active': True,
        })
        cls.test_output_location_01 = Location.create({
            'name': "Test output location 01",
            'barcode': "LTESTOUT01",
            'location_id': cls.out_location.id})

    @classmethod
    def _setup_check_location(cls):
        Location = cls.env['stock.location']
        cls.check_location = cls.picking_type_pick.default_location_dest_id.copy({
            'name': 'TEST_CHECK',
            'active': True,
        })
        cls.test_check_location_01 = Location.create({
            'name': "Test check location 01",
            'barcode': "LTESCHECK01",
            'location_id': cls.check_location.id})


    @classmethod
    def _setup_routes(cls):

        cls.picking_type_in.write({
            'default_location_src_id': cls.env.ref('stock.stock_location_suppliers').id,
            'default_location_dest_id': cls.received_location.id,
        })

        cls.picking_type_putaway.write({
            'default_location_src_id': cls.received_location.id,
            'default_location_dest_id': cls.stock_location.id,
        })

        cls.picking_type_internal.write({
            'default_location_src_id': cls.stock_location.id,
            'default_location_dest_id': cls.stock_location.id,
        })

        cls.picking_type_pick.write({
            'default_location_src_id': cls.stock_location.id,
            'default_location_dest_id': cls.out_location.id,
        })

        cls.picking_type_out.write({
            'default_location_src_id': cls.out_location.id,
            'default_location_dest_id': cls.env.ref('stock.stock_location_customers').id,
        })

        cls.create_simple_inbound_route(
            cls.picking_type_in, cls.picking_type_putaway)
        cls.create_simple_outbound_route(
            cls.picking_type_pick, cls.picking_type_out)

    @classmethod
    def _setup_users(cls):

        # create user with inbound security group
        inbound_types = cls.picking_type_in | cls.picking_type_putaway
        inbound_params = {
            'name': 'inbound_user',
            'login': 'inbound_user_login',
            'group_name': 'inbound',
            'picking_types': inbound_types,
        }
        cls.inbound_user = cls.create_user_with_group(**inbound_params)

        # create user with security group
        outbound_types = cls.picking_type_pick | cls.picking_type_out
        outbound_types |= cls.picking_type_internal
        outbound_params = {
            'name': 'outbound_user',
            'login': 'outbound_user_login',
            'group_name': 'outbound',
            'picking_types': outbound_types,
        }
        cls.outbound_user = cls.create_user_with_group(**outbound_params)

        # create user with security group
        stock_types = cls.picking_type_pick | cls.picking_type_internal
        stock_params = {
            'name': 'stock_user',
            'login': 'stock_user_login',
            'group_name': 'stock',
            'picking_types': stock_types,
        }
        cls.stock_user = cls.create_user_with_group(**stock_params)



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

        if confirm:
            picking.action_confirm()

        if assign:
            picking.action_assign()

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
    def _prepare_group(cls, group, picking_types=None):
        if picking_types:
            group.u_picking_type_ids = picking_types

        return [(4, group.id, 0)]

    @classmethod
    def add_group_to_user(cls, user, group_name,
                          picking_types=None):
        groups = cls._prepare_group(
            cls.security_groups[group_name],
            picking_types=picking_types)

        user.write({'groups_id': groups})

    @classmethod
    def create_user_with_group(cls, name, login, group_name,
                               picking_types=None):
        """ Create user for a security group and add picking types to
            the security group.
        """
        groups = cls._prepare_group(
            cls.security_groups[group_name],
            picking_types=picking_types)
        test_user = cls.create_user(name, login, groups_id=groups)

        return test_user

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
        user = User.create(vals)

        # some action require email setup even if the email is not really sent
        user.partner_id.email = login

        return user

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

        route_vals = {
            "name": "TestPutaway",
            "sequence": 10,
            "product_selectable": False,
            "warehouse_selectable": True,
            "warehouse_ids": [(6, 0, [picking_type_internal.warehouse_id.id])]
        }
        route = Route.create(route_vals)

        # PUTAWAY
        sequence_putaway = Sequence.create({"name": "TestPutaway",
                                            "prefix": "TESTPUT",
                                            "padding": 5})
        picking_type_internal.write({'sequence_id': sequence_putaway.id,
                                     'sequence': 13})

        location_path_vals = {
            "name": "TestPutaway",
            "route_id": route.id,
            "sequence": 20,
            "location_from_id": picking_type_in.default_location_dest_id.id,
            "location_dest_id": picking_type_internal.default_location_dest_id.id,
            "picking_type_id": picking_type_internal.id,
        }
        path_in_putaway = Path.create(location_path_vals)

    @classmethod
    def create_simple_outbound_route(cls, picking_type_pick, picking_type_out):
        Route = cls.env['stock.location.route']
        Path = cls.env['stock.location.path']
        Sequence = cls.env['ir.sequence']
        Location = cls.env['stock.location']

        route_vals = {
            "name": "TestGoodsOut",
            "sequence": 10,
            "product_selectable": False,
            "warehouse_selectable": True,
            "warehouse_ids": [(6, 0, [picking_type_out.warehouse_id.id])]
        }
        route = Route.create(route_vals)

        # Goods out
        sequence_vals = {
            "name": "TestGoodsOut",
            "prefix": "TESTGOODSOUT",
            "padding": 5,
        }
        sequence_goodsout = Sequence.create(sequence_vals)

        out_vals = {
            'sequence_id': sequence_goodsout.id,
            'sequence': 13,
        }
        picking_type_out.write(out_vals)

        # set goods-out source location = pick dest location
        picking_type_out.default_location_src_id = picking_type_pick.default_location_dest_id
        if not picking_type_out.default_location_dest_id:
            picking_type_out.default_location_dest_id = Location.search([('name', '=', 'Customers')])[0]

        location_path_vals = {
            "name": "TestGoodsOut",
            "route_id": route.id,
            "sequence": 20,
            "location_from_id": picking_type_pick.default_location_dest_id.id,
            "location_dest_id": picking_type_out.default_location_dest_id.id,
            "picking_type_id": picking_type_out.id,
        }
        path_out_goodsout = Path.create(location_path_vals)

    @classmethod
    def create_batch(cls, user=None, **kwargs):
        Batch = cls.env['stock.picking.batch']
        if not user:
            user = cls.env.user.id
        vals = {"user_id": user.id}
        vals.update(kwargs)
        return Batch.create(vals)

    def create_package(self, **kwargs):
        """Create and return a new package
        """
        Package = self.env['stock.quant.package']
        vals = {}
        vals.update(kwargs)
        return Package.create(vals)
