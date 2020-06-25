# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    def get_package(self, package_identifier, create=False, no_results=False):
        """ Get package from a name (i.e., barcode) or id.

            @param create: Boolean
                When it is True and package_identifier is a name,
                a package will be created if it does not exist

            @param no_results: Boolean
                Allows to return empty recordset when the package is
                not found
        """
        name = None
        if isinstance(package_identifier, int):
            domain = [("id", "=", package_identifier)]
        elif isinstance(package_identifier, str):
            domain = [("name", "=", package_identifier)]
            name = package_identifier
        else:
            raise ValidationError(
                _("Unable to create domain for package search from identifier of type %s")
                % type(package_identifier)
            )

        results = self.search(domain)
        if not results and not no_results:
            if not create or name is None:
                raise ValidationError(
                    _("Package not found for identifier %s") % str(package_identifier)
                )
            results = self.create({"name": name})
        if len(results) > 1:
            raise ValidationError(
                _("Too many packages found for identifier %s") % str(package_identifier)
            )

        return results
