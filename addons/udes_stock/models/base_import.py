from odoo import fields, api, models, _
from odoo.exceptions import ValidationError
from . common import check_upper_case_validation

class BaseImportExtended(models.TransientModel):
    _inherit = "base_import.import"


    def do(self, fields, columns, options, dryrun=False):
        res = super().do(fields, columns, options, dryrun=dryrun)
        """
        Override base function to add a check for upper case validation
        in case of UDES'S default import feature.
        """
        active_model = self.res_model
        if active_model == "product.template":
            active_model = "product.product"
        check_upper_case_validation(active_model,'create_from_import',fields,self.env.user,
                                    ids = res['ids'],model_to_browse=self.res_model)
        return res