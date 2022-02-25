from odoo import models, fields, api, _


class Location(models.Model):

    _inherit = "stock.location"
    _get_info_field_names = {
        "barcode",
        "complete_name",
        "posx",
        "posy",
        "posz",
        "scrap_location",
        "return_location",
    }
