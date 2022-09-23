from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class MixinStockModel(models.AbstractModel):
    _name = "mixin.stock.model"
    _description = "Inherited Model"

    # Whether the model is allowed to create a record when using get_or_create
    MSM_CREATE = False
    # Whether the model is allowed to create as sudo when using get_or_create
    MSM_CREATE_SUDO = False
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

    def get_or_create(
        self, identifier, create=False, create_sudo=False, aux_domain=None, return_empty=False
    ):
        """Gets an object of the model from the identifier. In case that no results
            are found, creates a new object of the model depending on the create
            parameter and the MSM_CREATE setting.
        :args:
            - identifier: str or int
                The identifier to search by
        :kwargs:
            - create: Boolean
                If true, and MSM_CREATE is true, a new object is created if needed
            - create_sudo: Boolean
                If true, and MSM_CREATE_SUDO is true, if a new object is created it will be
                created with sudo to avoid potential permissions exception
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
                model_instance = self
                if self.MSM_CREATE_SUDO and create_sudo:
                    model_instance = model_instance.sudo()
                results = model_instance.create({"name": identifier})
            elif self.MSM_CREATE and create:
                raise ValidationError(
                    _("Cannot create a new %s for %s with identifier of type %s")
                    % (model_name, model, type(identifier))
                )
            elif create:
                raise ValidationError(_("Cannot create a new %s for %s") % (model_name, model))
            else:
                if not return_empty:
                    raise ValidationError(
                        _("%s not found for identifier %s") % (model_name, identifier)
                    )
        elif len(results) > 1:
            raise ValidationError(
                _("Too many %ss found for identifier %s in %s") % (model_name, identifier, model)
            )
        return results
