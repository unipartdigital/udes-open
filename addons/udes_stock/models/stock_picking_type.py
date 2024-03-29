import logging

from odoo import fields, models, _, api

_logger = logging.getLogger(__name__)

TARGET_STORAGE_FORMAT_OPTIONS = [
    ("pallet_products", "Pallet of products"),
    ("pallet_packages", "Pallet of packages"),
    ("package", "Packages"),
    ("product", "Products"),
]

GROUP_RELATED_PICKINGS_CRITERIA = [
    ("original_picking", "Original Picking"),
    ("origin", "Origin"),
    ("nothing", "Nothing"),
]


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    # Disable translation to avoid issues with renaming
    name = fields.Char(translate=False)

    # Overwrite sequence_code as it is only needed for old Odoo prefixes.
    sequence_code = fields.Char(required=False)

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
    u_validate_real_time = fields.Boolean(
        string="Validate In Real Time",
        default=False,
        help="When True, operations are automatically validated in real time.",
    )

    u_handle_partials = fields.Boolean(
        string="Process Partial Transfers",
        default=True,
        help="Allow processing a transfer when the preceding transfers are not all completed.",
    )

    u_group_related_pickings_by = fields.Selection(
        selection=GROUP_RELATED_PICKINGS_CRITERIA,
        default="original_picking",
        string="Group Related Pickings By",
        copy=True,
        help="The criteria in which to group related pickings for kafka pick events \n"
        " * Batch: All pickings of the same picking type, which were a part of this pickings batch if it has one \n"
        " * Original Picking: All pickings of the same picking type, which stemmed from the first picking in the chain \n"
        " * Origin: All pickings of the same picking type, which share a source document \n"
        " * Nothing: No grouping is applied and each picking will be considered separately \n",
    )
    u_propagate_cancel = fields.Boolean(
        default=False,
        string="Propagate Move Cancellations",
        help="Whether or not to propagate move cancellations to the next picks moves. \n"
        "Odoo has a built in `propagate_cancel` field on the `stock.rule` which is only \n"
        "available on pull rules, and does not work for partial cancellations \n"
        "i.e if move grouping exists on pick type A but not pick type B, then \n"
        "pick type B's moves will be merged, and if a pick type A move is cancelled \n"
        "then the qty of the merged moves in pick type B will not be reduced. \n\n"
        "This toggle however, does support partial cancellations, and will propagate forward \n"
        "until it reaches a pick type with this setting turned off (or the move can not be found).\n\n"
        "For this reason, it is suggested to not use this feature on pick types whose rules are \n"
        "configured to propagate cancellations, to avoid any conflicting functionality.",
    )
    u_create_procurement_group = fields.Boolean(
        string="Create Procurement Group",
        default=False,
        help="Flag to indicate that a procurement group should be created on "
        "confirmation of the picking if one does not already exist.",
    )

    u_count_packages = fields.Boolean(
        default=False,
        string="Report Package Counts",
        help="Report package counts",
    )

    u_count_pallets = fields.Boolean(
        default=False,
        string="Report Pallet Counts",
        help="Report pallet counts",
    )
    u_allow_swapping_tracked_products = fields.Boolean(
        string="Allow Swapping Tracked Products",
        default=False,
        help="If enabled, tracked products that are not in the picking, but are more easily available to the warehouse user, can be swapped into the picking during scanning",
    )
    u_preserve_backorder_batch = fields.Boolean(
        string="Preserve Batch on Backorder",
        default=False,
        help="Flag to indicate whether to copy the batch_id on a picking of "
        "this type when a backorder is created",
    )
    u_pallet_barcode_regex = fields.Char(
        "Pallet Barcode Format",
        help="If is not set, pallet barcode regex will be retrieved from the warehouse"
    )
    u_package_barcode_regex = fields.Char(
        "Package Barcode Format",
        help="If is not set, package barcode regex will be retrieved from the warehouse"
    )

    def get_pallet_barcode_format(self):
        """Getting the pallet barcode regex which enforces pallets to be on a specific format"""
        self.ensure_one()
        return self.u_pallet_barcode_regex or self.warehouse_id.u_pallet_barcode_regex

    def get_package_barcode_format(self):
        """Getting the package barcode regex which enforces packages to be on a specific format"""
        self.ensure_one()
        return self.u_package_barcode_regex or self.warehouse_id.u_package_barcode_regex

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
        Purpose: When copying the picking type, the sequence id is not copied. This can lead to issues when trying to create the picking type.
        If the picking type is to be a direct copy then a search will be done for the original record and the sequence will be attached to the
        new record. If it isn't going to be a direct copy i.e. have a different name, then the sequence code should be set. This can happen when
        calling .copy(vals) on a record, where vals contains an updated name field. In this case the copied record will have the old Odoo style
        prefix.
        """
        Stockpickingtype = self.env["stock.picking.type"]
        stock_picking_type_record = Stockpickingtype.search(
            [("name", "=", vals["name"]), ("company_id", "=", vals.get("company_id"))]
        )
        if len(stock_picking_type_record) != 0 and not vals.get("sequence_id"):
            vals["sequence_id"] = stock_picking_type_record[0].sequence_id.id
        else:
            vals["sequence_code"] = vals["name"].upper().replace(" ", "_")
        return super(StockPickingType, self).create(vals)

    # TODO: Review
    def is_picking_type_check(self):
        """Place holder"""
        return False
