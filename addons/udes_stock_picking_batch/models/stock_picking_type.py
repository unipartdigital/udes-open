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
        string="Reserve One Pallet per Picking",
        default=False,
        help="If enabled, each picking in a batch will be associated with an individual pallet",
    )
    u_max_reservable_pallets = fields.Integer(
        string="Maximum Pallets That May Be Simultaneously Reserved in a Batch",
        default=10,
        help="This setting is only applied when u_reserve_pallet_per_picking is True",
    )
    u_allow_swapping_packages = fields.Boolean(string="Allow Swapping Packages", default=False)
    u_return_to_skipped = fields.Boolean(
        string="Return to Skipped Items",
        default=False,
        help="Flag to indicate if the skipped items will be returned to in the same batch.",
    )
    u_drop_criterion = fields.Selection(
        [
            ("all", "Drop off everything in one location"),
            ("by_products", "Group Items by Product"),
            ("by_orders", "Group Items by Order"),
            ("by_packages", "Drop Off Everything by Package"),
        ],
        default="all",
        string="Drop Off Criterion",
        help="How to group items when dropping off.",
    )
    u_auto_batch_pallet = fields.Boolean(
        string="Auto Batch Pallet",
        default=False,
        help="Flag to indicate whether picking type will automatically "
        "create batches when the user scans the pallet",
    )
    u_create_batch_for_user = fields.Boolean(
        string="Create Batch for User",
        default=True,
        help="Flag to indicate whether to create a new batch and assign it to "
        "the user, if he does not have one already assigned.",
    )
    u_assign_batch_to_user = fields.Boolean(
        string="Assign Batch to User",
        default=False,
        help='Flag to indicate whether to assign a "ready" batch to the '
        "user, if he does not have one already assigned.",
    )
    u_prioritise_matrix_small_items = fields.Boolean(
        string="Prioritise Matrix Pick Small Items",
        default=False,
        help="Flag to indicate that during matrix pick orders with small volume will be picked first after existing "
             "ordering applied like date and priority.",
    )
    u_small_orders_volume_threshold = fields.Float(
        "Threshold Volume (m3)",
        digits=(16, 6),
        help="When Prioritise Matrix Pick Small Items is enabled, pick threshold volume which will define small orders, "
             "and will be picked orders same or lower volume."
    )
    u_max_small_reservable_pallets = fields.Integer(
        string="Maximum Small Pallets That May Be Simultaneously Reserved in a Batch",
        default=20,
        help="This setting is only applied when u_prioritise_matrix_small_items is True",
    )
