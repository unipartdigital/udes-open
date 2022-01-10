# -*- coding: utf-8 -*-
from odoo import fields, models 

import logging
_logger = logging.getLogger(__name__)

CORE_LIFECYCLE_ACTIONS = [
    ("group_by_move_line_key", "Group by Move Line Key"),
    ("group_by_move_key", "Group by Move Key"),
]

POST_ASSIGN_ACTIONS = CORE_LIFECYCLE_ACTIONS + [
    ("by_maximum_quantity", "Maximum Quantity")
]

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'
   
    u_num_reservable_pickings = fields.Integer(
        string='Number of pickings to reserve',
        default=-1,
        help='The number of pickings in the queue to reserve stock for. '
             'If batch reservation is enabled, entire picking batches are '
             'reserved in the order of their earliest picking in the queue '
             'until at least this number of pickings are reserved. '
             '0 indicates no pickings should be reserved. '
             '-1 indicates all pickings should be reserved.'
    )  

    u_reserve_batches = fields.Boolean(
        string="Reserve picking batches atomically",
        default=False,
        help="Flag to indicate whether to reserve pickings by batches. "
        "This is ignored if the number of pickings to reserve is 0.",
    )

    u_handle_partials = fields.Boolean(
        string="Process Partial Transfers",
        default=False,
        help="Allow processing a transfer when the preceding transfers are not all completed.",
    ) 

    u_handle_partial_lines = fields.Boolean(
        string="Handle Partial Move Lines",
        default=False,
        help="Allow handling partial move lines. "
        "Only applicable if handling partial transfers is enabled.",
    )

    u_drop_location_policy = fields.Selection(
        [
            ("exactly_match_move_line", "Exactly Match The Move Line Destination Location",),
            ("by_products", "By Products"),
            ("by_product_lot", "By Product and Lot Number"),
            ("by_packages", "By Products in Packages"),
            ("by_height_speed", "By Height and Speed Category"),
            ("by_orderpoint", "By Order Point"),
            ("empty_location", "Only Empty Locations"),
        ],
        string="Suggest Locations Policy",
        default="exactly_match_move_line",
        help="Indicate the policy for suggesting drop locations.",
    )

    u_drop_location_preprocess = fields.Boolean(
        string="Add destination location on pick assignment",
        default=False,
        help="Flag to indicate if picking assignment should select destination locations",
    )

    u_reserve_as_packages = fields.Boolean(
        string="Reserve entire packages",
        default=False,
        help="Flag to indicate reservations should be rounded up to entire packages.",
    )

    u_post_confirm_action = fields.Selection(
        selection=[
            ("group_by_move_key", "Group by Move Key"),
            ("batch_pickings_by_date", "Batch pickings by date"),
            ("batch_pickings_by_date_priority", "Batch pickings by date and priority"),
        ],
        string="Post Confirm Action",
        help="Choose the action to be taken after confirming a picking.",
    )

    u_post_assign_action = fields.Selection(
        selection=POST_ASSIGN_ACTIONS,
        string="Post Assign Action",
        help="Choose the action to be taken after reserving a picking.",
    )

    u_post_validate_action = fields.Selection(
        selection=CORE_LIFECYCLE_ACTIONS,
        string="Post Validate Action",
        help="Choose the action to be taken after validating a picking.",
    )