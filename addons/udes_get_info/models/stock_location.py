# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class Location(models.Model):

    _inherit = "stock.location"
    _get_info_field_names = {
        "id",
        "name",
        "display_name",
        "complete_name",
        "barcode",
        "posx",
        "posy",
        "posz",
        "scrap_location",
        "return_location",
    }
