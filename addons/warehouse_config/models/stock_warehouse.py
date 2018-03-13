# -*- coding: utf-8 -*-

from odoo import models, fields


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    def _domain_u_damaged_location_id(self):
        """
        Domain for locations outside Stock
        """
        Location = self.env['stock.location']
        stock_children_locations = Location.search(
                [('id', 'child_of', self.env.ref('stock.stock_location_stock').id)]
            ).mapped('id')

        return [('id', 'not in', stock_children_locations)]

    u_handle_damages_picking_type_ids = fields.Many2many(
        comodel_name='stock.picking.type',
        relation='stock_warehouse_damages_picking_types_rel',
        string='Which Picking Types Handle Damages',
    )
    u_missing_stock_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='The Location Where Missing Stock Is Moved To',
    )
    u_print_labels_picking_type_ids = fields.Many2many(
        comodel_name='stock.picking.type',
        relation='stock_warehouse_print_label_picking_types_rel',
        string='Picking types which automatically print labels',
    )
    u_damaged_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='The Location Where Damaged Stock Is Moved To',
        domain=_domain_u_damaged_location_id,
        help="The damaged location is a location outside Stock (it cannot be a location under Stock/), "
             "because we do not want damaged stock to be picked",
    )
    u_temp_dangerous_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Dangerous Goods Location (staging location outside Stock)',
        help="Location that temporary stores the dangerous products waiting to be putaway."
    )
    u_probres_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='PROBRES Location',
        help="Location that temporary stores the products cannot be putaway,"
             " and require special attention",
    )
    u_incomplete_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Incomplete Location',
        help="Location that temporary stores the products partially dropped from a picking",
    )
    u_dangerous_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Dangerous Location (inside Stock)',
        help="The dangerous location is the location inside Stock where"
             " the dangerous products are stored. It might have sublocations.",
    )
    u_pallet_barcode_regex = fields.Char('Pallet Barcode Format', default='^PAL(\\d)+$')
    u_package_barcode_regex = fields.Char('Package Barcode Format', default='^PACK(\\d)+$')
    u_pi_count_move_picking_type = fields.Many2one(
        comodel_name='stock.picking.type',
        string='PI Count Picking Type',
        help="Picking type used to create PI Count move pickings."
    )
    u_stock_investigation_picking_type = fields.Many2one(
        comodel_name='stock.picking.type',
        string='Stock Investigation Picking Type',
        help="Picking type used to create stock investigation pickings."
    )

    def _prepare_info(self):
        """
            Prepares the following extra info of the warehouse in self:
            - u_missing_stock_location_id: int
            - u_damaged_location_id: int
            - u_temp_dangerous_location_id: int
            - u_probres_location_id: int
            - u_incomplete_location_id: int
            - u_dangerous_location_id: int
            - u_handle_damages_picking_type_ids: list(int)
            - u_print_labels_picking_type_ids: list(int)
            - u_pallet_barcode_regex: string
            - u_package_barcode_regex: string
        """
        info = super(StockWarehouse, self)._prepare_info()
        info.update({
            'u_missing_stock_location_id': self.u_missing_stock_location_id.id,
            'u_damaged_location_id': self.u_damaged_location_id.id,
            'u_temp_dangerous_location_id': self.u_temp_dangerous_location_id.id,
            'u_probres_location_id': self.u_probres_location_id.id,
            'u_incomplete_location_id': self.u_incomplete_location_id.id,
            'u_dangerous_location_id': self.u_dangerous_location_id.id,
            'u_handle_damages_picking_type_ids': self.u_handle_damages_picking_type_ids.ids,
            'u_print_labels_picking_type_ids': self.u_print_labels_picking_type_ids.ids,
            'u_pallet_barcode_regex': self.u_pallet_barcode_regex,
            'u_package_barcode_regex': self.u_package_barcode_regex,
            })
        return info
