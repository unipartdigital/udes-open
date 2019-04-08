"""
Tests for the StockPicking.reserve_stock method.

These tests are separated because they require management of an internal
savepoint because the method manages its own commits and rollbacks.
"""

import logging
import unittest

from odoo.tests import common as odoocommon
from . import common

_logger = logging.getLogger(__name__)


SECURITY_GROUPS = [
    ('inbound', 'udes_stock.group_inbound_user'),
    ('outbound', 'udes_stock.group_outbound_user'),
    ('stock', 'udes_stock.group_stock_user'),
    ('inventory_manager', 'stock.group_stock_manager'),
]


# odoo.commom.SavepointCase doesn't seem to like commits/rollbacks happening
# inside the reserve_stock method for for now base our test case class on
# odoo.common.TransactionCase.


@odoocommon.at_install(False)
@odoocommon.post_install(True)
class BaseUDESTransactionCase(odoocommon.TransactionCase):

    def setUp(self):
        super(BaseUDESTransactionCase, self).setUp()

        # Products
        ## Untracked
        self.apple = self.create_product('Apple')
        self.banana = self.create_product('Banana')
        self.cherry = self.create_product('Cherry')
        self.damson = self.create_product('Damson')
        self.elderberry = self.create_product('Elderberry')
        self.fig = self.create_product('Fig')
        self.grape = self.create_product('Grape')

        ## Serial/Lot tracking
        self.strawberry = self.create_product('Strawberry', tracking='serial')
        self.tangerine = self.create_product('Tangerine', tracking='lot')

        self.setup_default_warehouse()

    def setup_default_warehouse(self):
        ''' Sets a warehouse with:
            * test locations
                test_input_01, test_stock_01, test_stock_02, test_output_01
            * all picking types as a copy of the default with TEST_ prepended
            * a simple inbound route goods_in->putaway
            * a simple outbound route pick->goods_out
        '''
        self._setup_picking_types()
        self._setup_locations()
        self._setup_routes()
        # Security groups
        self.security_groups = {name: self.env.ref(reference)
                               for (name, reference) in SECURITY_GROUPS}
        self._setup_users()

    def _setup_picking_types(self):
        self._set_test_picking_type('in')
        self._set_test_picking_type('pick')
        # this order is important as int is overwritten
        self._set_test_picking_type('int', 'putaway')
        self._set_test_picking_type('int', 'internal')
        self._set_test_picking_type('out')

    def _set_test_picking_type(self, ptype, name=None):
        User = self.env['res.users']
        user_warehouse = User.get_user_warehouse()

        if name is None:
            name = ptype

        copy_vals = {'name': 'TEST_{}'.format(name.upper()), 'active': True}
        wh_attr =  getattr(user_warehouse, '{}_type_id'.format(ptype))
        new_pt = wh_attr.copy(copy_vals)
        setattr(self, 'picking_type_{}'.format(name), new_pt)
        setattr(user_warehouse, '{}_type_id'.format(ptype), new_pt)

    def _setup_locations(self):

        Location = self.env['stock.location']
        Category = self.env['stock.location.category']
        self.stock_location = self.env.ref('stock.stock_location_stock')

        input_zone = self.stock_location.copy({'name': 'TEST_INPUT'})
        self.received_location = Location.create({
            'name': "TEST_RECEIVED",
            'barcode': "LTESTRECEIVED",
            'location_id': input_zone.id,
        })

        self.test_location_01 = Location.create({
                'name': "Test location 01",
                'barcode': "LTEST01",
                'location_id': self.stock_location.id,
            })
        self.test_location_02 = Location.create({
                'name': "Test location 02",
                'barcode': "LTEST02",
                'location_id': self.stock_location.id,
            })
        self.test_locations = self.test_location_01 + self.test_location_02

        self.out_location = self.picking_type_pick.default_location_dest_id.copy({
            'name': 'TEST_OUT',
            'active': True,
        })
        self.test_output_location_01 = Location.create({
            'name': "Test output location 01",
            'barcode': "LTESTOUT01",
            'location_id': self.out_location.id})

        self.test_output_location_02 = Location.create({
            'name': "Test output location 02",
            'barcode': "LTESTOUT02",
            'location_id': self.out_location.id})

        self.test_output_locations = self.test_output_location_01 + \
            self.test_output_location_02

        self.location_category_high = Category.create({'name': 'High'})
        self.location_category_super_high = Category.create({
            'name': 'Super',
            'parent_id': self.location_category_high.id
        })
        self.location_category_ground= Category.create({'name': 'Ground'})
        self.location_categories = self.location_category_high + \
                                  self.location_category_super_high + \
                                  self.location_category_ground

    def _setup_check_location(self):
        Location = self.env['stock.location']
        self.check_location = self.picking_type_pick.default_location_dest_id.copy({
            'name': 'TEST_CHECK',
            'active': True,
        })
        self.test_check_location_01 = Location.create({
            'name': "Test check location 01",
            'barcode': "LTESCHECK01",
            'location_id': self.check_location.id})


    def _setup_routes(self):

        self.picking_type_in.write({
            'default_location_src_id': self.env.ref('stock.stock_location_suppliers').id,
            'default_location_dest_id': self.received_location.id,
        })

        self.picking_type_putaway.write({
            'default_location_src_id': self.received_location.id,
            'default_location_dest_id': self.stock_location.id,
        })

        self.picking_type_internal.write({
            'default_location_src_id': self.stock_location.id,
            'default_location_dest_id': self.stock_location.id,
        })

        self.picking_type_pick.write({
            'default_location_src_id': self.stock_location.id,
            'default_location_dest_id': self.out_location.id,
        })

        self.picking_type_out.write({
            'default_location_src_id': self.out_location.id,
            'default_location_dest_id': self.env.ref('stock.stock_location_customers').id,
        })

        self.create_simple_inbound_route(
            self.picking_type_in, self.picking_type_putaway)
        self.create_simple_outbound_route(
            self.picking_type_pick, self.picking_type_out)

    def _setup_users(self):

        # create user with inbound security group
        inbound_types = self.picking_type_in | self.picking_type_putaway
        inbound_params = {
            'name': 'inbound_user',
            'login': 'inbound_user_login',
            'group_name': 'inbound',
            'picking_types': inbound_types,
        }
        self.inbound_user = self.create_user_with_group(**inbound_params)

        # create user with security group
        outbound_types = self.picking_type_pick | self.picking_type_out
        outbound_types |= self.picking_type_internal
        outbound_params = {
            'name': 'outbound_user',
            'login': 'outbound_user_login',
            'group_name': 'outbound',
            'picking_types': outbound_types,
        }
        self.outbound_user = self.create_user_with_group(**outbound_params)

        # create user with security group
        stock_types = self.picking_type_pick | self.picking_type_internal
        stock_params = {
            'name': 'stock_user',
            'login': 'stock_user_login',
            'group_name': 'stock',
            'picking_types': stock_types,
        }
        self.stock_user = self.create_user_with_group(**stock_params)



    def create_inventory_line(self, inventory, product, **kwargs):
        """ Create and return an inventory line for the given inventory and product."""
        InventoryLine = self.env['stock.inventory.line']
        vals = {
            'product_id': product.id,
            'location_id': inventory.location_id.id,
            'inventory_id': inventory.id,
        }
        vals.update(kwargs)
        return InventoryLine.create(vals)

    def create_inventory(self, location, **kwargs):
        """ Create and return an inventory for the given location."""
        Inventory = self.env['stock.inventory']
        vals = {
            'location_id': location.id,
            'name': location.name,
        }
        vals.update(kwargs)
        return Inventory.create(vals)

    def create_move_line(self, move, qty, **kwargs):
        """ Create and return a move line for the given move and qty."""
        MoveLine = self.env['stock.move.line']
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

    def create_move(self, product, qty, picking, **kwargs):
        """ Create and return a move for the given product and qty."""
        Move = self.env['stock.move']
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

    def create_picking(self, picking_type, products_info=False,
                       confirm=False, assign=False, **kwargs):
        """ Create and return a picking for the given picking_type."""
        Picking = self.env['stock.picking']
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
                move = self.create_move(**product_info)

        if confirm:
            picking.action_confirm()

        if assign:
            picking.action_assign()

        return picking

    def create_product(self, name, **kwargs):
        """ Create and return a product."""
        Product = self.env['product.product']
        vals = {
            'name': 'Test product {}'.format(name),
            'barcode': 'product{}'.format(name),
            'default_code': 'product{}'.format(name),
            'type': 'product',
        }
        vals.update(kwargs)
        return Product.create(vals)

    def create_quant(self, product_id, location_id, qty, serial_number=None, **kwargs):
        """ Create and return a quant of a product at location."""
        Quant = self.env['stock.quant']
        vals = {
            'product_id': product_id,
            'location_id': location_id,
            'quantity': qty,
        }
        if serial_number:
            lot = self.create_lot(product_id, serial_number)
            vals['lot_id'] = lot.id
        vals.update(kwargs)
        return Quant.create(vals)

    def create_lot(self, product_id, serial_number, **kwargs):
        Lot = self.env['stock.production.lot']

        vals = {
            'name': serial_number,
            'product_id': product_id,
        }
        vals.update(kwargs)
        return Lot.create(vals)

    def _prepare_group(self, group, picking_types=None):
        if picking_types:
            group.u_picking_type_ids = picking_types

        return [(4, group.id, 0)]

    def add_group_to_user(self, user, group_name,
                          picking_types=None):
        groups = self._prepare_group(
            self.security_groups[group_name],
            picking_types=picking_types)

        user.write({'groups_id': groups})

    def create_user_with_group(self, name, login, group_name,
                               picking_types=None):
        """ Create user for a security group and add picking types to
            the security group.
        """
        groups = self._prepare_group(
            self.security_groups[group_name],
            picking_types=picking_types)
        test_user = self.create_user(name, login, groups_id=groups)

        return test_user

    def create_user(self, name, login, **kwargs):
        """ Create and return a user"""
        User = self.env['res.users']
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

    def create_company(self, name, **kwargs):
        """Create and return a company"""
        Company = self.env['res.company']
        vals = {
            'name': name
        }
        vals.update(kwargs)
        return Company.create(vals)

    def create_simple_inbound_route(self, picking_type_in, picking_type_internal):
        Route = self.env['stock.location.route']
        Path = self.env['stock.location.path']
        Sequence = self.env['ir.sequence']

        route_vals = {
            "name": "TestPutaway",
            "sequence": 10,
            "product_selectable": False,
            "warehouse_selectable": True,
            "warehouse_ids": [(6, 0, [picking_type_internal.warehouse_id.id])]
        }
        self.route_in = Route.create(route_vals)

        # PUTAWAY
        sequence_putaway = Sequence.create({"name": "TestPutaway",
                                            "prefix": "TESTPUT",
                                            "padding": 5})
        picking_type_internal.write({'sequence_id': sequence_putaway.id,
                                     'sequence': 13})

        location_path_vals = {
            "name": "TestPutaway",
            "route_id": self.route_in.id,
            "sequence": 20,
            "location_from_id": picking_type_in.default_location_dest_id.id,
            "location_dest_id": picking_type_internal.default_location_dest_id.id,
            "picking_type_id": picking_type_internal.id,
        }
        self.push_putaway = Path.create(location_path_vals)

    def create_simple_outbound_route(self, picking_type_pick, picking_type_out):
        Route = self.env['stock.location.route']
        Path = self.env['stock.location.path']
        Rule = self.env['procurement.rule']
        Sequence = self.env['ir.sequence']
        Location = self.env['stock.location']

        route_vals = {
            "name": "TestGoodsOut",
            "sequence": 10,
            "product_selectable": False,
            "warehouse_selectable": True,
            "warehouse_ids": [(6, 0, [picking_type_out.warehouse_id.id])]
        }
        self.route_out = Route.create(route_vals)

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
            "route_id": self.route_out.id,
            "sequence": 20,
            "location_from_id": picking_type_pick.default_location_dest_id.id,
            "location_dest_id": picking_type_out.default_location_dest_id.id,
            "picking_type_id": picking_type_out.id,
        }
        path_out_goodsout = Path.create(location_path_vals)

        self.rule_pick = Rule.create({
            'name': "TestPick",
            'route_id': self.route_out.id,
            'picking_type_id': picking_type_pick.id,
            'location_id': picking_type_pick.default_location_dest_id.id,
            'location_src_id': picking_type_pick.default_location_src_id.id,
            'action': 'move',
            'procure_method': 'make_to_stock',
        })
        self.rule_out = Rule.create({
            'name': "TestOut",
            'route_id': self.route_out.id,
            'picking_type_id': picking_type_out.id,
            'location_id': picking_type_out.default_location_dest_id.id,
            'location_src_id': picking_type_out.default_location_src_id.id,
            'action': 'move',
            'procure_method': 'make_to_order',
        })

    def create_batch(self, user=None, **kwargs):
        Batch = self.env['stock.picking.batch']

        vals = {}
        if user is not False:
            if user is None:
                user = self.env.user
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

    def create_category(self, **kwargs):
        ProductCategory = self.env['product.category']
        return ProductCategory.create(kwargs)

    def create_partner(self, name, **kwargs):
        Partner = self.env['res.partner']
        vals = {'name': name}
        vals.update(kwargs)
        return Partner.create(vals)


class StockPickingReserveStockTestCase(BaseUDESTransactionCase):
    """Stock picking reserve stock test case."""

    def test00_does_not_reserve_if_reservable_pickings_is_zero(self):
        """Test behaviour when reservable pickings is zero."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 0
        picking_type.u_reserve_batch = True
        picking_type.u_handle_partials = True

        # Create stock.
        quant = self.create_quant(self.apple.id, self.test_location_01.id, 100,
                                  package_id=self.create_package().id)

        # Set up batch and picking.
        batch = self.create_batch(self.stock_user)
        products_info = [{'product': self.apple, 'qty': 10}]
        test_picking = self.create_picking(picking_type,
                                           origin="test_picking_origin",
                                           products_info=products_info,
                                           batch_id=batch.id,
                                           confirm=True)
        batch.mark_as_todo()

        # Reserve stock.
        test_picking.reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(0, int(quant.reserved_quantity))

    def test01_reserves_stock_to_limit_if_available(self):
        """Test behaviour when stock is a available and reservable pickings is positive."""
        # Set up picking type.
        picking_type = self.picking_type_pick
        picking_type.u_num_reservable_pickings = 1
        picking_type.u_reserve_batch = True
        picking_type.u_handle_partials = True

        # Create stock.
        quant = self.create_quant(self.apple.id, self.test_location_01.id, 100,
                                  package_id=self.create_package().id)

        # Set up batch and picking.
        batch = self.create_batch(self.stock_user)
        products_info = [{'product': self.apple, 'qty': 10}]
        test_picking = self.create_picking(picking_type,
                                           origin="test_picking_origin",
                                           products_info=products_info,
                                           batch_id=batch.id,
                                           confirm=True)
        batch.mark_as_todo()

        # Reserve stock.
        test_picking.reserve_stock()

        # Test that stock has been reserved.
        self.assertEqual(10, int(quant.reserved_quantity))
