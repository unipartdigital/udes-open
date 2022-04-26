from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class MixinStockModel(models.AbstractModel):
    _name = "mixin.stock.model"
    _description = "Inherited Model"

    # Whether the model is allowed to create a record when using get_or_create
    MSM_CREATE = False
    # Default fields to search with a str on get_or_create
    MSM_STR_DOMAIN = ("name",)

    def _get_msm_domain(self, identifier):
        """Return a domain based on MSM_STR_DOMAIN attribute
           (which can be changed on the model which this model is mixed in to)
        :args:
            - identifier: str or int
                The identifier to search by
        :returns:
            List of tuples (Odoo style domain)
        """
        if isinstance(identifier, str):
            domain = expression.OR([[(field, "=", identifier)] for field in self.MSM_STR_DOMAIN])
        elif isinstance(identifier, int):
            domain = [("id", "=", identifier)]
        else:
            raise TypeError(_("Identifier must be either int or str, not %s") % (type(identifier)))

        return domain

    def get_or_create(self, identifier, create=False, aux_domain=None, return_empty=False):
        """Gets an object of the model from the identifier. In case that no results
            are found, creates a new object of the model depending on the create
            parameter and the MSM_CREATE setting.
        :args:
            - identifier: str or int
                The identifier to search by
        :kwargs:
            - create: Boolean
                If true, and MSM_CREATE is true, a new object is created if needed
            - aux_domain: list
                An additional domain to add to the search
            - return_empty: Boolean
                Allow empty/False results to be returned without raising an exception
        :returns:
            Object of the model queried
        """
        IrModel = self.env["ir.model"]

        model = self._name
        model_name = IrModel.search([("model", "=", self._name)]).name
        # Prepare domain for search
        domain = self._get_msm_domain(identifier)
        if aux_domain:
            if not isinstance(aux_domain, list):
                raise ValidationError(_("Aux domain for get_or_create() should be a list."))

            domain.extend(aux_domain)
        # Search overriding order for performance
        results = self.search(domain, order="id")

        if not results:
            if self.MSM_CREATE and create and isinstance(identifier, str):
                results = self.create({"name": identifier})
            elif self.MSM_CREATE and create:
                raise ValidationError(
                    _(f"Cannot create a new {model_name} for %s with identifier of type %s")
                    % (model, type(identifier))
                )
            elif create:
                raise ValidationError(_(f"Cannot create a new {model_name} for %s") % model)
            else:
                if not return_empty:
                    raise ValidationError(_(f"{model_name} not found for identifier %s") % identifier)
        elif len(results) > 1:
            raise ValidationError(
                _(f"Too many {model_name}s found for identifier %s in %s") % (identifier, model)
            )
        return results
