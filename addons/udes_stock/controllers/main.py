from odoo import http, tools, _
from odoo.http import request
from odoo.addons.web.controllers.main import DataSet
from odoo.exceptions import ValidationError
from ..models.common import check_upper_case_validation

class DataSetExtended(DataSet):

    # methods to check determines in which methods we want to call our validation
    # As the route is dynamic we may want to ignore some models. In the case of
    # base_import.import(Default Import Feature) return types are different from
    # regular UDES object so we are handling it separately
    METHODS_TO_CHECK = ["create", "write"]
    MODELS_TO_IGNORE = ["base_import.import"]

    @http.route(['/web/dataset/call_kw', '/web/dataset/call_kw/<path:path>'], type='json', auth="user")
    def call_kw(self, model, method, args, kwargs, path=None):
        """
        Overriding this controller to dynamically determine which route is getting called.
        Idea hear is to check if upper case configuration is enabled in the warehouse.
        As we do not know which fields of which class will require this validation we
        are checking each create/write call.
        """
        res = super().call_kw(model, method, args, kwargs, path=path)
        if method in self.METHODS_TO_CHECK:
            user = request.env.user
            if model not in self.MODELS_TO_IGNORE:
                active_model = model
                #UDES may have product variant feature disabled.
                #UDES always create a product variant from template.
                #Condition is to make sure even though route return's
                #product.template create/write call we always deal with product variant.
                if active_model == 'product.template':
                    active_model = 'product.product'
                check_upper_case_validation(active_model, method, args, user)
        return res
