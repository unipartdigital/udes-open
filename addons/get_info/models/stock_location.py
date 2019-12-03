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

    # Notes this is how you can add values too _get_info_field_names
    #
    # def _setup_complete(self):
    #     """Use setup complete call to add field"""
    #     super()._setup_complete()
    #     self.__class__._get_info_field_names.add("company_id")
