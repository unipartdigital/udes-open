from odoo import models, fields, _


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    u_auto_assign_batch_pick = fields.Boolean(
        string=_("Auto Assign Running Batch Picks"),
        help=_("Reserve automatically stock to picks when added to a running batch"),
        default=False,
    )
    u_remove_unready_batch = fields.Boolean(
        string=_("Auto Remove Running Batch Unready Picks"),
        help=_(
            "Remove automatically unready picks from a running batch when batch assigned or pick state changed"
        ),
        default=True,
    )
    u_use_location_categories = fields.Boolean(
        string=_("Use Location Categories"),
        default=False,
        help=_(
            "Flag to indicate whether to ask the user to select location "
            "categories when starting the pick process. Location categories "
            "are used to decide which pickings are suitable to the users."
        ),
    )
    u_batch_dest_loc_not_allowed = fields.Boolean(
        string=_("No Blocked Dest. Location Pickings"),
        default=False,
        help=_(
            "When batch chooses picking it filter out pickings which has block destination "
            "location. By default, block locations are allowed"
        ),
    )
    u_reserve_pallet_per_picking = fields.Boolean(
        string=_("Reserve One Pallet per Picking"),
        default=False,
        help=_("If enabled, each picking in a batch will be associated with an individual pallet"),
    )
    u_max_reservable_pallets = fields.Integer(
        string=_("Maximum Pallets That May Be Simultaneously Reserved in a Batch"),
        default=10,
        help=_("This setting is only applied when u_reserve_pallet_per_picking is True"),
    )
    u_allow_swapping_packages = fields.Boolean(string="Allow Swapping Packages", default=False)
    u_return_to_skipped = fields.Boolean(
        string=_("Return to Skipped Items"),
        default=False,
        help=_("Flag to indicate if the skipped items will be returned to in the same batch."),
    )
    u_drop_criterion = fields.Selection(
        [
            ("all", _("Drop off everything in one location")),
            ("by_products", _("Group Items by Product")),
            ("by_orders", _("Group Items by Order")),
            ("by_packages", _("Drop Off Everything by Package")),
        ],
        default="all",
        string=_("Drop Off Criterion"),
        help=_("How to group items when dropping off."),
    )
    u_auto_batch_pallet = fields.Boolean(
        string=_("Auto Batch Pallet"),
        default=False,
        help=_(
            "Flag to indicate whether picking type will automatically "
            "create batches when the user scans the pallet"
        ),
    )
    u_create_batch_for_user = fields.Boolean(
        string=_("Create Batch for User"),
        default=True,
        help=_(
            "Flag to indicate whether to create a new batch and assign it to "
            "the user, if he does not have one already assigned."
        ),
    )
    u_assign_batch_to_user = fields.Boolean(
        string=_("Assign Batch to User"),
        default=False,
        help=_(
            'Flag to indicate whether to assign a "ready" batch to the '
            "user, if he does not have one already assigned."
        ),
    )
