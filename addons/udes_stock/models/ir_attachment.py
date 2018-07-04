# -*- coding: utf-8 -*-
from odoo import api, models

class IrAttachment(models.Model):

    _inherit = 'ir.attachment'

    # Default to using file name as the attachment name
    @api.onchange('datas_fname')
    def _onchange_datas_fname(self):
        for attachment in self:
            if attachment.datas_fname and not attachment.name:
                attachment.name = attachment.datas_fname
