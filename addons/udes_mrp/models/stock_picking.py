# Copyright (c) 2019, Unipart Digital
# Derived from Odoo.

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def _get_mo_count(self):
        """Override _get_mo_count so waiting orders don't show also as todo."""
        mrp_picking_types = self.filtered(lambda picking: picking.code == 'mrp_operation')
        if not mrp_picking_types:
            return
        domains = {
            'count_mo_waiting': [('availability', '=', 'waiting')],
            'count_mo_todo': [('state', 'in', ('confirmed', 'planned', 'progress')),
                              ('availability', '<>', 'waiting')],
            'count_mo_late': [('date_planned_start', '<', fields.Date.today()), ('state', '=', 'confirmed')],
        }
        for field in domains:
            data = self.env['mrp.production'].read_group(domains[field] +
                                                         [('state', 'not in', ('done', 'cancel')), ('picking_type_id', 'in', self.ids)],
                                                         ['picking_type_id'], ['picking_type_id'])
            count = {x['picking_type_id'] and x['picking_type_id'][0]: x['picking_type_id_count'] for x in data}
            for record in mrp_picking_types:
                record[field] = count.get(record.id, 0)

