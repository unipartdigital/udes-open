from odoo import api, models, _


class ProcurementGroup(models.Model):
    _name = "procurement.group"
    # Add mixin stock model
    _inherit = ["procurement.group", "mixin.stock.model"]

    # Allow groups to be created
    MSM_CREATE = True
