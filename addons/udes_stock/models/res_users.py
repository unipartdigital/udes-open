# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import ValidationError


class ResUser(models.Model):
    _inherit = "res.users"

    @api.model
    def get_user_warehouse(self, aux_domain=None):
        """Get the warehouse(s) of the user by chain of the company
        :kwargs:
            - aux_domain:
                If specified must return a single warehouse, if want a subset
                of warehouses then don't specify the aux_domain and filter result
        :returns: Warehouse(s), or a singular warehouse if aux_domain not None
        """
        Warehouse = self.env["stock.warehouse"]

        user = self.env.user

        if user.id != SUPERUSER_ID:
            user = self.search([("id", "=", user.id)])
            if not user:
                raise ValidationError(_("Cannot find user"))

        domain = [("company_id", "=", user.company_id.id)]
        if aux_domain is not None:
            domain += aux_domain
        warehouse = Warehouse.search(domain)
        if not warehouse:
            raise ValidationError(_("Cannot find a warehouse for user"))
        if len(warehouse) > 1 and aux_domain is not None:
            raise ValidationError(
                _(
                    "Found multiple warehouses for user, "
                    + "the aux_domain is specifying multiple warehouses or cannot be correct!"
                )
            )
        return warehouse
