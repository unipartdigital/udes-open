# -*- coding: utf-8 -*-
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


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

    def group_move_lines(self, move_lines):
        MoveLine = self.env['stock.move.line']
        return {k: MoveLine.browse([ml.id for ml in g])
                for k, g in
                groupby(sorted(move_lines, key=MoveLine.move_line_key),
                        key=MoveLine.move_line_key)}

    def post_reservation_split(self, moves):
        """
        group the move lines by the splitting criteria
        for each resulting group of stock.move.lines:
            create a new picking
            split any stock.move records that are only partially covered by the
                group of stock.move.lines
            attach the stock.moves and stock.move.lines to the new picking.
        """
        MoveLine = self.env['stock.move.line']
        if not self.u_move_line_key_format:
            return

        pickings = moves.mapped('picking_id')
        mls_by_key = self.group_move_lines(moves.mapped('move_line_ids'))

        for key, ml_group in mls_by_key.items():
            touched_moves = ml_group.mapped('move_id')
            group_moves = self.env['stock.move']
            for move in touched_moves:
                # Get all the mls in current group that are for current move
                move_mls = ml_group.filtered(lambda l: l.move_id == move)

                # See if all mls for the move are in the current group
                if move_mls != move.move_line_ids:
                    # The move iss not entirely contained by the move lines
                    # for this grouping. Need to split the move.
                    group_moves |= move.split_out_move_lines(move_mls)
                else:
                    group_moves |= move

            self.new_picking_for_group(key, ml_group, group_moves)

        empty_picks = pickings.filtered(lambda p: len(p.move_lines) == 0)
        if empty_picks:
            _logger.info(_("Cancelling empty picks after splitting."))
            # action_cancel does not cancel a picking with no moves.
            empty_picks.write({
                'state': 'cancel',
                'is_locked': True
            })

    def new_picking_for_group(self, group_key, move_lines, moves):
        Picking = self.env['stock.picking']
        Group = self.env['procurement.group']

        group = Group.get_group(group_identifier=group_key,
                                create=True)
        picking = Picking.search([
            ('picking_type_id', '=', self.id),
            ('group_id', '=', group.id),
            ('state', '=', 'assigned'),
        ])
        if not picking or len(picking) > 1:
            picking = Picking.create({
                'picking_type_id': self.id,
                'location_id': self.default_location_src_id.id,
                'location_dest_id': self.default_location_dest_id.id,
                'group_id': group.id
            })

        moves.write({
            'group_id': group.id,
            'picking_id': picking.id
        })
        move_lines.write({'picking_id': picking.id})

        return picking
