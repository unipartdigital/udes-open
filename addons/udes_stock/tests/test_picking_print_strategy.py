"""Picking print strategy tests"""

from odoo.addons.print.tests.test_action_print import (
    ActionPrintTest,
    BuildTests,
)

class TestPrintStrategy(ActionPrintTest, metaclass=BuildTests):
    """Printing action tests for stock picking print strategy"""
    strategy_model = 'udes_stock.stock.picking.print.strategy'

    def setUp(self):
        super().setUp()

        Product = self.env['product.product']
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        Quant = self.env['stock.quant']
        Package = self.env['stock.quant.package']
        Location = self.env['stock.location']

        apple = Product.create({
            'type': 'product',
            'name': 'Apple',
            'barcode': 'Apple',
            'default_code': 'Apple',
        })
        quantity = 10

        package = Package.create({'name': 'test package'})

        location = Location.create({
            'name': 'print location 01',
            'barcode': 'LPRINT01',
            'location_id': self.env.ref('stock.stock_location_stock').id,
        })

        # picking types
        picking_type_in = self.env.ref('stock.picking_type_in')
        picking_type_in.write({'active': True})

        picking_type_pick = self.env.ref('udes_stock.picking_type_pick')
        picking_type_pick.write({'active': True})

        # pickings
        picking_in = Picking.create({
            'picking_type_id': picking_type_in.id,
            'location_id': picking_type_in.default_location_src_id.id,
            'location_dest_id': picking_type_in.default_location_dest_id.id,
            'origin': 'test_picking',
        })
        Move.create({
            'product_id': apple.id,
            'name': apple.name,
            'product_uom': apple.uom_id.id,
            'product_uom_qty': quantity,
            'location_id': picking_in.location_id.id,
            'location_dest_id': picking_in.location_dest_id.id,
            'picking_id': picking_in.id,
            'priority': picking_in.priority,
            'picking_type_id': picking_in.picking_type_id.id,
        })
        picking_in.action_confirm()

        Quant.create({
            'product_id': apple.id,
            'location_id': location.id,
            'quantity': quantity,
            'package_id': package.id,
        })

        picking_pick = Picking.create({
            'picking_type_id': picking_type_pick.id,
            'location_id': picking_type_pick.default_location_src_id.id,
            'location_dest_id': picking_type_pick.default_location_dest_id.id,
            'origin': 'test_picking',
        })
        Move.create({
            'product_id': apple.id,
            'name': apple.name,
            'product_uom': apple.uom_id.id,
            'product_uom_qty': quantity,
            'location_id': picking_pick.location_id.id,
            'location_dest_id': picking_pick.location_dest_id.id,
            'picking_id': picking_pick.id,
            'priority': picking_pick.priority,
            'picking_type_id': picking_pick.picking_type_id.id,
        })
        picking_pick.action_confirm()
        picking_pick.action_assign()

        self.picking_type_in = picking_type_in
        self.picking_type_pick = picking_type_pick
        self.picking_in = picking_in
        self.picking_pick = picking_pick

    @property
    def default_report(self):
        return self.env.ref('stock.action_report_delivery')

    @property
    def default_picking_type(self):
        """Return the default picking type"""
        return self.picking_type_in

    def action_context(self, obj):
        return super().action_context(self.picking_in)

    def benign_context(self, obj):
        return super().action_context(self.picking_pick)

    def create_strategy(self, name, report, printer,
                        safety=None, model=True, picking_type=True):
        if picking_type is True:
            picking_type = self.default_picking_type
        return super().create_strategy(name, report, printer,
                                       safety=safety, model=model,
                                       picking_type_id=picking_type.id)
