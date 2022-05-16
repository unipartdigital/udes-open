import logging

from odoo import fields, models, _, api

_logger = logging.getLogger(__name__)

TARGET_STORAGE_FORMAT_OPTIONS = [
    ("pallet_products", "Pallet of products"),
    ("pallet_packages", "Pallet of packages"),
    ("package", "Packages"),
    ("product", "Products"),
]


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    # Overwrite sequence_code as it is only needed for old Odoo prefixes.
    sequence_code = fields.Char("Sequence_code", required=False)

    u_user_scans = fields.Selection(
        [("pallet", "Pallets"), ("package", "Packages"), ("product", "Products")],
        string="What the User Scans",
        help="What the user scans when asked to scan something from pickings of this type",
    )
    u_target_storage_format = fields.Selection(
        TARGET_STORAGE_FORMAT_OPTIONS, string="Target Storage Format"
    )
    u_under_receive = fields.Boolean(
        string="Under Receive",
        default=False,
        help="If True, allow less items than the expected quantity in a move line.",
    )
    u_over_receive = fields.Boolean(
        string="Over Receive",
        default=True,
        help="If True, allow more items than the expected quantity in a move line.",
    )
    u_scan_parent_package_end = fields.Boolean(
        string="Scan Parent Package at the End",
        default=False,
        help="If True, the user is asked to scan parent package on drop off.",
    )
    u_auto_unlink_empty = fields.Boolean(
        string="Auto Unlink Empty",
        default=True,
        help="""
        Flag to indicate whether to unlink empty pickings when searching for any empty picking in
        the system.
        """,
    )
    # Enable multi users processing same picking simultaneously
    u_multi_users_enabled = fields.Boolean(
        string="Multi Users Enabled",
        help="Flag to enable multiple users to work on a picking simultaneously."
        "On validation of a picking only the moves done by the specific user will be confirmed unless all moves have already been picked by other users",
        default=False,
    )
    u_enable_unpickable_items = fields.Boolean(
        string="Enable Unpickable Items",
        default=False,
        help="Flag to indicate if the current picking type should support handling of unpickable items.",
    )

    def get_action_picking_tree_draft(self):
        return self._get_action("udes_stock.action_picking_tree_draft")

    def can_handle_multiple_users(self):
        """Check if a picking type can handle multiple users.
        Placing into a method in order to be able to inherit and change behaviour if needed for
        specific customers
        """
        self.ensure_one()
        return self.u_multi_users_enabled

    def write(self, vals):
        """
        Purpose: This will remove the sequence code from the list of values to be updated. This is to prevent the sequences
        for each picking type from being updated with hardcoded values. sequence_code is only relevant to the old odoo prefixes
        and not the UDES ones, hence a warning message is also displayed.
        """
        if "sequence_code" in vals:
            _logger.warning(
                _(
                    "The 'sequence code' field, which has value: (%s), is no longer being used in UDES, this field has been removed from the values to update and will not be updated.",
                    vals["sequence_code"],
                )
            )
            del vals["sequence_code"]
        return super(StockPickingType, self).write(vals)

        
    @api.model
    def create(self, vals):
        """
        Purpose: If picking_type is to be full copy, then set the sequence_id on the record else set the sequence_code to the name 
        """
        Stockpickingtype = self.env["stock.picking.type"]
        stock_picking_type_record = Stockpickingtype.search([("name","=",vals["name"])])
        if len(stock_picking_type_record) != 0: 
            vals["sequence_id"] = stock_picking_type_record[0].sequence_id.id
        else:
            vals["sequence_code"] = vals["name"]
        return super(StockPickingType, self).create(vals)
