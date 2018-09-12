# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    show_operations = fields.Boolean(default=True)

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
    u_display_summary = fields.Selection([
        ('none', 'None'),
        ('list', 'List'),
        ('list_contents', 'List with Contents'),
    ],
        string='Display Summary',
        default='none'
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

    u_auto_batch_pallet = fields.Boolean(
        string='Auto batch pallet',
        default=False,
        help='Flag to indicate whether picking type will automatically '
             'create batches when the user scans the pallet'
    )

    u_move_line_key_format = fields.Char(
        'Move Line Grouping Key',
        help="""A field name on stock.move.line that is used to group move
        lines post-reservation."""
    )

    u_check_work_available = fields.Boolean(
        string='Check for more work',
        default=False,
        help='Flag to indicate with if picking type should display if there is'
             'picks of this type which are not in a batch'
    )

    def _prepare_info(self):
        """
            Prepares the following info of the picking_type in self:
            - id: int
            - code: string
            - count_picking_ready: int
            - display_name: string
            - name: string
            - sequence: int
            - default_location_dest_id: int
            - default_location_src_id: int
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
            - u_auto_batch_pallet: boolean
            - u_check_work_available: boolean
        """
        self.ensure_one()

        return {'id': self.id,
                'code': self.code,
                'count_picking_ready': self.count_picking_ready,
                'display_name': self.display_name,
                'name': self.name,
                'sequence': self.sequence,
                'default_location_dest_id': self.default_location_dest_id.id,
                'default_location_src_id': self.default_location_src_id.id,
                'u_allow_swapping_packages': self.u_allow_swapping_packages,
                'u_skip_allowed': self.u_skip_allowed,
                'u_split_on_drop_off_picked': self.u_split_on_drop_off_picked,
                'u_suggest_qty': self.u_suggest_qty,
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
                'u_auto_batch_pallet': self.u_auto_batch_pallet,
                'u_check_work_available': self.u_check_work_available,
                }

    def get_info(self):
        """ Return a list with the information of each picking_type in self.
        """
        res = []
        for picking_type in self:
            res.append(picking_type._prepare_info())

        return res

    def get_picking_type(self, picking_type_id):
        """ Get picking_type from id
        """
        picking_type = self.browse(picking_type_id)
        if not picking_type.exists():
            raise ValidationError(
                    _('Cannot find picking type with id %s') %
                    picking_type_id)
        return picking_type
