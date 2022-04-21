from odoo import models, fields


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_auto_assign_batch_pick = fields.Boolean(
        string="Auto Assign Running Batch Picks",
        help="Reserve automatically stock to picks when added to a running batch",
        default=False,
    )
    u_remove_unready_batch = fields.Boolean(
        string="Auto Remove Running Batch Unready Picks",
        help="Remove automatically unready picks from a running batch when batch assigned or pick state changed",
        default=True,
    )
    u_use_location_categories = fields.Boolean(
        string="Use Location Categories",
        default=False,
        help="Flag to indicate whether to ask the user to select location "
        "categories when starting the pick process. Location categories "
        "are used to decide which pickings are suitable to the users.",
    )
    u_batch_dest_loc_not_allowed = fields.Boolean(
        string="No Blocked Dest. Location Pickings",
        default=False,
        help="When batch chooses picking it filter out pickings which has block destination "
        "location. By default, block locations are allowed",
    )
    u_reserve_pallet_per_picking = fields.Boolean(
        string="Reserve one pallet per picking",
        default=False,
        help="If enabled, each picking in a batch will be associated with an individual pallet",
    )
    u_max_reservable_pallets = fields.Integer(
        string="Maximum pallets that may be simultaneously reserved in a batch.",
        default=10,
        help="This setting is only applied when u_reserve_pallet_per_picking is True",
    )
    u_allow_swapping_packages = fields.Boolean("Allow swapping packages")
    u_return_to_skipped = fields.Boolean(
        string="Return to Skipped Items",
        default=False,
        help="Flag to indicate if the skipped items will be returned to in the same batch.",
    )
    u_drop_criterion = fields.Selection(
        [
            ("all", "Drop off everything in one location"),
            ("by_products", "Group items by product"),
            ("by_orders", "Group items by order"),
            ("by_packages", "Drop off everything by package"),
        ],
        default="all",
        string="Drop Off Criterion",
        help="How to group items when dropping off.",
    )
