# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import ValidationError
from odoo.tools.translate import _
from odoo.addons.web import controllers


class UdesApi(http.Controller):
    pass


class DataSet(controllers.main.DataSet):
    """Dataset controller"""

    @http.route()
    def resequence(self, model, ids, field='sequence', **kwargs):
        """Check that resequencing has resulted in expected record order

        The Odoo web UI does not correctly handle models for which the
        ``sequence`` field is not the highest precedence within the
        sort order.
        """
        result = super().resequence(model, ids, field=field, **kwargs)
        recs = http.request.env[model].browse(ids)
        if list(recs.sorted()) != list(recs.sorted(field)):
            raise ValidationError(
                _("Sequence is overridden by default sort ordering")
            )
        return result
