from odoo import models, fields


class UdesCarrier(models.Model):
    _name = "udes.carrier"
    _description = "Carrier"

    name = fields.Char(string="Carrier Name")
