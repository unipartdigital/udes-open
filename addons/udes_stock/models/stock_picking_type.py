# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

CORE_LIFECYCLE_ACTIONS = [
    ('group_by_move_line_key', 'Group by Move Line Key'),
    ('group_by_move_key', 'Group by Move Key'),
]


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    show_operations = fields.Boolean(default=True)

    # Pick workflow options

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

    u_under_receive = fields.Boolean(
        string='Under Receive',
        default=False,
        help='If True, allow less items than the expected quantity in a move line.',
    )

    u_over_receive = fields.Boolean(
        string='Over Receive',
        default=True,
        help='If True, allow additional items not in the ASN, or over the expected quantity, '
             'to be added at goods in.',
    )

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
        ('product', 'Products'),
    ],
        string='What the User Scans',
        help='What the user scans when asked to '
        'scan something from pickings of this type'
    )

    # TODO(ale): misleading, as this also depends on `u_user_scans` and
    # and `u_target_storage_format`; consider using an enumeration
    u_scan_parent_package_end = fields.Boolean(
        string='Scan parent package at the end',
        default=False,
        help='If True, the user is asked to scan parent package on drop off.',
    )

    u_reserve_as_packages = fields.Boolean(
        string='Reserve entire packages',
        default=False,
        help="Flag to indicate reservations should be rounded up to entire packages."
    )
    u_confirm_tracking = fields.Selection([
        ('no', 'No'),
        ('yes', 'Yes'),
        ('first_last', 'First/Last'),
    ],
        required=True,
        default='yes',
        string='Confirm Tracked Products',
        help='Confirm tracked products: yes; no; first and last serial number.',
    )

    u_confirm_expiry_date = fields.Boolean(
        string='Confirm Expiry Date',
        default=False,
        help='Request expiry date for tracked products.'
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

    u_auto_batch_pallet = fields.Boolean(
        string='Auto batch pallet',
        default=False,
        help='Flag to indicate whether picking type will automatically '
             'create batches when the user scans the pallet'
    )

    u_check_work_available = fields.Boolean(
        string='Check for more work',
        default=False,
        help='Flag to indicate whether to display the remaining picking '
             'operations to be done, that can be either batched or unassigned.'
    )

    u_use_product_packaging = fields.Boolean(
        string='Use Product Packaging',
        default=False,
        help='Flag to indicate if privacy wrapping information is relevant.',
    )

    u_assign_batch_to_user = fields.Boolean(
        string='Assign batch to user',
        default=False,
        help='Flag to indicate whether to assign a "ready" batch to the '
             'user, if he does not have one already assigned.',
    )

    u_create_batch_for_user = fields.Boolean(
        string='Create batch for user',
        default=True,
        help='Flag to indicate whether to create a new batch and assign it to '
             'the user, if he does not have one already assigned.',
    )

    u_check_picking_priorities = fields.Boolean(
        string='Check picking priorities',
        default=True,
        help='Flag to indicate whether to check picking priorities while '
             'processing the picking.',
    )

    u_use_location_categories = fields.Boolean(
        string='Use Location Categories',
        default=False,
        help='Flag to indicate whether to ask the user to select location '
             'categories when starting the pick process. Location categories '
             'are used to decide which pickings are suitable to the users.',
    )

    u_enable_unpickable_items = fields.Boolean(
        string='Enable Unpickable Items',
        default=False,
        help='Flag to indicate if the current picking type has unpickable '
             'items enabled.',
    )

    u_confirm_batch = fields.Boolean(
        string='Confirm Batch',
        default=False,
        help='Flag to indicate if user has to confirm the batch to work with.'
    )

    u_enable_confirmations = fields.Boolean(
        string='Enable Confirmations',
        default=False,
        help='Flag to indicate if user has to perform any confirmation after '
             'picking a product.'
    )

    # Drop location options

    u_drop_criterion = fields.Selection([
        ('all', 'Drop off everything in one location'),
        ('by_products', 'Group items by product'),
        ('by_orders', 'Group items by order')
    ],
        default='all',
        string='Drop Off Criterion',
        help='How to group items when dropping off.'
    )

    u_drop_location_constraint = fields.Selection([
        ('dont_scan', 'Do not scan'),
        ('scan', 'Scan'),
        ('suggest', 'Suggest'),
        ('enforce', 'Enforce'),
        ('enforce_with_empty', 'Enforce with empty locations'),
    ],
        default='scan',
        string='Suggest Locations Constraint',
        help='Whether drop locations should be scanned, suggested and, then, enforced.'
    )

    u_drop_location_policy = fields.Selection([
        ('exactly_match_move_line', 'Exactly Match The Move Line Destination Location'),
        ('by_products', 'By Products'),
        ('by_packages', 'By Products in Packages'),
        ('by_height_speed', 'By Height and Speed Catagory'),
    ],
        string='Suggest Locations Policy',
        default='exactly_match_move_line',
        help='Indicate the policy for suggesting drop locations.'
    )

    u_drop_location_preprocess = fields.Boolean(
        string='Add destination location on pick assignement',
        default=False,
        help='Flag to indicate if picking assignment should select '
             'destination locations'
    )

    # Picking lifecycle actions

    u_move_line_key_format = fields.Char(
        'Move Line Grouping Key',
        help="""A field name on stock.move.line that can be to group
        move lines."""
    )

    u_move_key_format = fields.Char(
        'Move Grouping Key',
        help="""A field name on stock.move that can be to group move."""
    )

    u_post_confirm_action = fields.Selection(
        selection=[
            ('group_by_move_key', 'Group by Move Key'),
        ],
        string='Post Confirm Action',
        help='Choose the action to be taken after confirming a picking.'
    )

    u_post_assign_action = fields.Selection(
        selection=CORE_LIFECYCLE_ACTIONS,
        string='Post Assign Action',
        help='Choose the action to be taken after reserving a picking.'
    )

    u_post_validate_action = fields.Selection(
        selection=CORE_LIFECYCLE_ACTIONS,
        string='Post Validate Action',
        help='Choose the action to be taken after validating a picking.'
    )

    u_new_package_policy = fields.Selection(
        selection=[
            ('default', 'Default Package Name'),
        ],
        string='Package Name Policy',
        help='Choose the package name policy to be applied for the picking type.'
    )

    u_continue_picking = fields.Boolean(
        string='Allow continue picking',
        default=False,
        help='Flag to indicate whether the user can request more work be added'
             'to current batch rather than going to drop off once current '
             'picking is done in the case that they have more capacity.'
    )

    u_num_reservable_pickings = fields.Integer(
        string='Number of pickings to reserve',
        default=0,
        help='The number of pickings in the queue to reserve stock for. '
             'If batch reservation is enabled, entire picking batches are '
             'reserved in the order of their earliest picking in the queue '
             'until at least this number of pickings are reserved. '
             '0 indicates no pickings should be reserved. '
             '-1 indicates all pickings should be reserved.'
    )

    u_reserve_batches = fields.Boolean(
        string='Reserve picking batches atomically',
        default=True,
        help='Flag to indicate whether to reserve pickings by batches. '
             'This is ignored if the number of pickings to reserve is 0.'
    )

    def do_refactor_action(self, action, moves):
        """Resolve and call the method to be executed on the moves.

           Methods doing a refactor are expected to take a single recordset of
           moves on which they will act, and to return the recordset of
           equivalent moves after they have been transformed.
           The output moves may be identical to the input, may contain none
           of the input moves, or anywhere in between.
           The output should contain a functionally similar set of moves.
        """
        Move = self.env['stock.move']
        if action == 'none':
            return moves

        # TODO: getattr(self will return a func bound to self, then just func()
        func = getattr(Move, 'refactor_action_' + action, None)
        if func is not None:
            return func(moves)
        return moves

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
            - u_under_receive: boolean
            - u_over_receive: boolean
            - u_validate_real_time: boolean
            - u_target_storage_format: string
            - u_user_scans: string
            - u_scan_parent_package_end: boolean
            - u_reserve_as_packages: boolean
            - u_auto_batch_pallet: boolean
            - u_continue_picking: boolean
            - u_check_work_available: boolean
            - u_use_product_packaging: boolean
            - u_assign_batch_to_user: boolean
            - u_create_batch_for_user: boolean
            - u_check_picking_priorities: boolean
            - u_use_location_categories: boolean
            - u_confirm_batch: boolean
            - u_enable_confirmations: boolean
            - u_drop_criterion: string
            - u_drop_location_constraint: string
            - u_drop_location_policy: string
            - u_new_package_policy: string
            - u_num_reservable_pickings: int
            - u_reserve_batches: boolean
        """
        self.ensure_one()
        Batch = self.env['stock.picking.batch']
        drop_off_instructions = \
            "" if self.u_drop_criterion == 'all' \
            else Batch.get_drop_off_instructions(self.u_drop_criterion)

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
                'u_under_receive': self.u_under_receive,
                'u_over_receive': self.u_over_receive,
                'u_validate_real_time': self.u_validate_real_time,
                'u_target_storage_format': self.u_target_storage_format,
                'u_user_scans': self.u_user_scans,
                'u_scan_parent_package_end': self.u_scan_parent_package_end,
                'u_display_summary': self.u_display_summary,
                'u_reserve_as_packages': self.u_reserve_as_packages,
                'u_handle_partials': self.u_handle_partials,
                'u_create_procurement_group': self.u_create_procurement_group,
                'u_confirm_tracking': self.u_confirm_tracking,
                'u_confirm_expiry_date': self.u_confirm_expiry_date,
                'u_drop_criterion': self.u_drop_criterion,
                'drop_criterion_instructions': drop_off_instructions,
                'u_drop_location_constraint': self.u_drop_location_constraint,
                'u_drop_location_policy': self.u_drop_location_policy,
                'u_new_package_policy': self.u_new_package_policy,
                'u_auto_batch_pallet': self.u_auto_batch_pallet,
                'u_continue_picking': self.u_continue_picking,
                'u_check_work_available': self.u_check_work_available,
                'u_use_product_packaging': self.u_use_product_packaging,
                'u_assign_batch_to_user': self.u_assign_batch_to_user,
                'u_create_batch_for_user': self.u_create_batch_for_user,
                'u_check_picking_priorities': self.u_check_picking_priorities,
                'u_use_location_categories': self.u_use_location_categories,
                'u_confirm_batch': self.u_confirm_batch,
                'u_enable_confirmations': self.u_enable_confirmations,
                'u_num_reservable_pickings': self.u_num_reservable_pickings,
                'u_reserve_batches': self.u_reserve_batches,
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

    def get_action_picking_tree_draft(self):
        return self._get_action('udes_stock.action_picking_tree_draft')
