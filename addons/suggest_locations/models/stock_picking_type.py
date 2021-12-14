# -*- coding: utf-8 -*-
from odoo import models, fields


class PickingType(models.Model):

    _inherit = "stock.picking.type"

    # The policy is fetched on implementation
    u_suggest_locations_policy = fields.Selection(
        selection=[],
        string="Suggest locations policy",
        help="The policy used to suggest locations",
    )

    # We could move the definition somewhere else and extend to add suggestion
    # based constraints
    u_drop_location_constraint = fields.Selection(
        [
            ("dont_scan", "Do not scan"),
            ("scan", "Scan"),
            ("suggest", "Suggest"),
            ("suggest_with_empty", "Suggest with empty locations"),
            ("enforce", "Enforce"),
            ("enforce_with_empty", "Enforce with empty locations"),
        ],
        default="scan",
        string="Suggest locations constraint",
        help="Whether drop locations should be scanned, suggested and, then, enforced.",
    )
