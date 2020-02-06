from odoo import fields, api, models


class EmailTemplate(models.Model):

    _inherit = "mail.template"

    is_edi_template = fields.Boolean(
        string="EDI Notifier Template",
        default=False,
        help="This is an EDI notifier model",
    )
