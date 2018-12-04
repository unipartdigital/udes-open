# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import ValidationError
from odoo.tools.translate import _
from odoo.addons.web import controllers
from odoo.http import request


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


class Session(controllers.main.Session):
    @http.route('/web/session/logout', type='http', auth="user")
    def logout(self, *args, **kwargs):
        PickingBatch = request.env['stock.picking.batch']
        Users = request.env['res.users']

        _batches = PickingBatch.unassign_user_batches()
        _res = Users.set_user_location_categories([])

        return super().logout(*args, **kwargs)
