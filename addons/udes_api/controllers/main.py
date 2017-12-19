# -*- coding: utf-8 -*-

from odoo import http

class UdesApi(http.Controller):

    def transform_id_fields(self, input_dict, fields):
        for field in fields:
            if field in input_dict and input_dict[field]:
                input_dict[field]=input_dict[field][0]

        return input_dict

