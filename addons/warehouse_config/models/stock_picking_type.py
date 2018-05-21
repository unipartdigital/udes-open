# -*- coding: utf-8 -*-

from odoo import models, fields

class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_allow_swapping_packages = fields.Boolean('Allow swapping packages')
    u_skip_allowed = fields.Boolean(
            string='Skip allowed',
            default=False,
            help='Flag to indicate if the skip button will be shown.',
            )
    u_split_on_drop_off_picked = fields.Boolean('Split on drop off picked')
    u_suggest_qty = fields.Boolean(
        string='Suggest Qty',
        default=True,
        help='If True, suggest quantity on mobile if there is an expected quantity.',
    )
    u_over_receive = fields.Boolean(
        string='Over Receive',
        default=True,
        help='If True, allow additional items not in the ASN, or over the expected quantity, '
             'to be added at goods in.',
    )
    u_enforce_location_dest_id = fields.Boolean(
        string='Enforce Destination Location',
        default=False,
        help='Flag to indicate if the destination location of operations should '
             'be forced to be a child_of the picking location_dest_id.',)
    u_confirm_location_dest_id = fields.Boolean(
        string='Confirm Destination Location',
        default=True,
        help='Flag to indicate whether we need to scan the Destination Location of operations, '
             'or if it is automatically confirmed as the preset Destination Location.',)
    u_display_summary = fields.Boolean(
        string='Display Summary',
        default=False,
        help='When True, we display the Source Document '
             'and a summary of all Package Names associated with that Source Document number at Goods-Out.'
    )
    u_validate_real_time = fields.Boolean(
        string='Validate In Real Time',
        default=False,
        help='When True, operations are automatically validated in real time.'
    )
    u_target_storage_format = fields.Selection([
        ('pallet_products', 'Pallet of products'),
        ('pallet_packages', 'Pallet of packages'),
        ('package', 'Packages'),
        ('product', 'Products'),
    ],
        string='Target Storage Format',
    )
    u_user_scans = fields.Selection([
        ('pallet', 'Pallets'),
        ('package', 'Packages'),
        ('product', 'Products'),],
        string='What the User Scans',
        help='What the user scans when asked to '
        'scan something from pickings of this type')
    u_reserve_as_packages = fields.Boolean(
        string='Reserve entire packages',
        default=False,
        help="Flag to indicate reservations should be rounded up to entire packages."
    )
    u_confirm_serial_numbers = fields.Selection([
        ('no', 'No'),
        ('yes', 'Yes'),
        ('first_last', 'First/Last'),
    ],
        string='Confirm Serial Numbers',
    )

    u_handle_partials = fields.Boolean(
        string='Process Partial Transfers',
        default=True,
        help='Allow processing a transfer when the preceding transfers are not all completed.'
    )

    u_create_procurement_group = fields.Boolean(
        string='Create Procurement Group',
        default=False,
        help='Flag to indicate that a procurement group should be created on '
             'confirmation of the picking if one does not already exist.',
    )

    u_suggest_location = fields.Boolean(
        string='Suggest locations',
        default=False,
        help='Flag to indicate with if picking type should suggest locations '
             'to user'
    )

    def _prepare_info(self):
        """
            Prepares the following extra info of the picking_type in self:
            - u_allow_swapping_packages: boolean
            - u_skip_allowed: boolean
            - u_split_on_drop_off_picked: boolean
            - u_suggest_qty: boolean
            - u_over_receive: boolean
            - u_validate_real_time: boolean
            - u_target_storage_format: string
            - u_user_scans: string
            - u_enforce_location_dest_id: boolean
            - u_reserve_as_packages: boolean
            - u_confirm_serial_numbers: string
        """
        info = super(StockPickingType, self)._prepare_info()
        info.update({
            'u_allow_swapping_packages': self.u_allow_swapping_packages,
            'u_skip_allowed': self.u_skip_allowed,
            'u_split_on_drop_off_picked': self.u_split_on_drop_off_picked,
            'u_suggest_qty': self. u_suggest_qty,
            'u_over_receive': self.u_over_receive,
            'u_validate_real_time': self.u_validate_real_time,
            'u_target_storage_format': self.u_target_storage_format,
            'u_user_scans': self.u_user_scans,
            'u_enforce_location_dest_id': self.u_enforce_location_dest_id,
            'u_confirm_location_dest_id': self.u_confirm_location_dest_id,
            'u_display_summary': self.u_display_summary,
            'u_reserve_as_packages': self.u_reserve_as_packages,
            'u_handle_partials': self.u_handle_partials,
            'u_create_procurement_group': self.u_create_procurement_group,
            'u_confirm_serial_numbers': self.u_confirm_serial_numbers,
            'u_suggest_location': self.u_suggest_location,
            })
        return info
