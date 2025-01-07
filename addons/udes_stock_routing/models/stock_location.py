from odoo import models, fields


class StockLocation(models.Model):
    _inherit = "stock.location"

    u_requires_two_stage_when_stock_reserved = fields.Boolean(
        string="Requires Two stage?",
        help="Whether outbound stock reserved on this location or children of this location will trigger a two stage process. "
        "A two stage process involves splitting the stock reserved in this location into a new picking which will first move the stock to an intermediate location.",
    )

    # This field will be dynamically required in the client, if u_requires_two_stage_when_stock_reserved is True.
    u_two_stage_intermediate_location = fields.Many2one(
        "stock.location",
        string="Two stage intermediate location",
        help="The intermediate location for the two stage process "
        "(i.e the destination location of the first picking, and the source location of the second picking.) "
        "This would typically be set to a view location to restrict where the first stage can have stock moved to.",
    )

    # We want the flexibility to configure this as something different to the destination location of the original picking.
    # Users can leave this field blank in the client.
    u_two_stage_intermediate_dest_location = fields.Many2one(
        "stock.location",
        string="Two stage intermediate to location",
        help="Optional. The destination location of the 2nd stage. "
        "If not specified, the original destination location from the picking which the two stage process was started from will be used.",
    )

    # We want the flexibility to configure this as something different to the operation type of the original picking.
    # Users can leave this field blank in the client.
    u_two_stage_intermediate_operation_type = fields.Many2one(
        "stock.picking.type",
        string="Two stage intermediate Operation Type",
        help="Optional. The Operation Type of the 1st stage. "
        "If not specified, the original Operation Type from the picking which the two stage process was started from will be used. "
        "This is configurable to ensure that source -> target storage formats don't get violated by repeating the same operation type "
        "after transforming stocks storage formats.",
    )
