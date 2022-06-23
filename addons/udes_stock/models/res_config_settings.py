from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):

    _inherit = "res.config.settings"

    @api.model
    def get_values(self):
        """
        Getting config settings values
        """
        IrConfigParameterSudo = self.env["ir.config_parameter"].sudo()
        res = super(ResConfigSettings, self).get_values()

        stock_move_sms_validation = IrConfigParameterSudo.get_param(
            "stock_sms.stock_move_sms_validation", default=False
        )
        res.update(stock_move_sms_validation=stock_move_sms_validation)
        return res

    def set_values(self):
        """
        Setting config settings values
        """
        IrConfigParameterSudo = self.env["ir.config_parameter"].sudo()
        ret_vals = super(ResConfigSettings, self).set_values()

        IrConfigParameterSudo.set_param(
            "stock_sms.stock_move_sms_validation", self.stock_move_sms_validation
        )
        return ret_vals
