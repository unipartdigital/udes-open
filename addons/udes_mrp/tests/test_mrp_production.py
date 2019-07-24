from odoo.tests import common
from odoo.addons.mrp.tests.common import TestMrpCommon

from datetime import datetime, timedelta


@common.at_install(False)
@common.post_install(True)
class TestManufacturingOrder(TestMrpCommon):
    def test01_filters(self):
        """Tests that BOMs in different states are filtered and counted properly."""
        MrpProduction = self.env['mrp.production'].sudo()

        # Cancel and remove all the testing orders so changes there don't break the count
        test_orders = MrpProduction.search([])
        test_orders.action_cancel()
        test_orders.unlink()

        # Set up the picking type
        picking_type = self.env['stock.picking.type'].create({
            'name': 'Manufacturing',
            'code': 'mrp_operation',
            'sequence_id': self.env['ir.sequence'].search([('code', '=', 'mrp.production')], limit=1).id,
        })

        # Order 1: waiting, not todo, late
        test_date_planned = datetime.now() - timedelta(days=1)
        test_quantity = 2.0
        order_1 = MrpProduction.create({
            'name': 'Stick-0',
            'product_id': self.product_4.id,
            'product_uom_id': self.product_4.uom_id.id,
            'product_qty': test_quantity,
            'bom_id': self.bom_1.id,
            'date_planned_start': test_date_planned,
            'location_src_id': self.location_1.id,
            'location_dest_id': self.warehouse_1.wh_output_stock_loc_id.id,
            'picking_type_id': picking_type.id
        })

        self.assertEqual(order_1.availability, 'waiting', 'Order should be waiting since there are no source'
                                                        ' products.')
        self.assertEqual(order_1.picking_type_id.count_mo_waiting, 1, 'The count of waiting orders should '
                                                                    'now equal one.')
        self.assertEqual(order_1.picking_type_id.count_mo_todo, 0, 'The count of todo orders should '
                                                                 'now equal zero.')
        self.assertEqual(order_1.picking_type_id.count_mo_late, 1, 'The count of late orders should '
                                                                 'now equal one.')

        # Order 2: waiting, todo, not late
        order_2 = MrpProduction.create({
            'name': 'Stick-1',
            'product_id': self.product_5.id,
            'product_uom_id': self.product_5.uom_id.id,
            'product_qty': test_quantity,
            'bom_id': self.bom_2.id,
            'date_planned_start': datetime.now(),
            'location_src_id': self.location_1.id,
            'location_dest_id': self.warehouse_1.wh_output_stock_loc_id.id,
            'picking_type_id': picking_type.id
        })

        order_2.picking_type_id.invalidate_cache()
        self.assertEqual(order_2.availability, 'waiting', 'Order should be waiting since there are no source'
                                                          ' products.')
        self.assertEqual(order_2.picking_type_id.count_mo_waiting, 2, 'The count of waiting orders should '
                                                                      'now equal two.')
        self.assertEqual(order_2.picking_type_id.count_mo_todo, 0, 'The count of todo orders should '
                                                                   'now equal zero.')
        self.assertEqual(order_2.picking_type_id.count_mo_late, 1, 'The count of late orders should '
                                                                   'now equal one.')

        # Stock products for Order 2
        inventory = self.env['stock.inventory'].create({
            'name': 'Test Inventory',
            'filter': 'partial',
            'line_ids': [(0, 0, {
                'product_id': self.product_3.id,
                'product_uom_id': self.product_3.uom_id.id,
                'product_qty': 60,
                'location_id': self.location_1.id
            }), (0, 0, {
                'product_id': self.product_4.id,
                'product_uom_id': self.product_4.uom_id.id,
                'product_qty': 60,
                'location_id': self.location_1.id
            })]
        })
        inventory.action_start()
        inventory.action_done()
        order_2.action_assign()
        order_2.picking_type_id.invalidate_cache()

        self.assertEqual(order_2.availability, 'assigned', 'The order should have assigned source products.')
        self.assertEqual(order_2.state, 'confirmed', 'The order should be confirmed.')

        self.assertEqual(order_2.picking_type_id.count_mo_waiting, 1, 'The count of waiting orders should '
                                                                      'now equal one.')
        self.assertEqual(order_2.picking_type_id.count_mo_todo, 1, 'The count of todo orders should '
                                                                   'now equal one.')
        self.assertEqual(order_2.picking_type_id.count_mo_late, 1, 'The count of late orders should '
                                                                   'now equal one.')
