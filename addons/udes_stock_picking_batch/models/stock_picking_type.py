from odoo import models, fields


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

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
        help="If enabled, each picking in a batch will be associated with an " "individual pallet",
    )
    u_max_reservable_pallets = fields.Integer(
        string="Maximum pallets that may be simultaneously reserved in a batch.",
        default=10,
        help="This setting is only applied when u_reserve_pallet_per_picking is True",
    )
