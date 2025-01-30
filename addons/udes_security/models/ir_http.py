"""Ir Http model."""

import inspect
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    """
    Monkeypatching stub.

    The purpose of this model extension is to allow us to monkeypatch a
    third-party model with a signature that is no longer valid.
    """

    _inherit = "ir.http"

    @api.model_cr
    def _register_hook(self):
        res = super()._register_hook()
        cls = type(self)

        # Find classes with the wrong method signature. Assume that there is at
        # most one (this is currently true, and unlikely to change).
        selected = None
        for klass in iter(cls.__bases__):
            if "_authenticate" in klass.__dict__:
                sig = inspect.getfullargspec(klass._authenticate)
                if sig.args[1] == "auth_method":
                    selected = klass
                    break

        if selected:
            from odoo.http import request

            def _authenticate(cls, endpoint):
                res = super(selected, cls)._authenticate(endpoint)
                if request and request.env and request.env.user:
                    request.env.user._auth_timeout_check()
                return res

            selected._authenticate = classmethod(_authenticate)
            _logger.info(_("Method '_authenticate' of %r has been patched."), selected)
        return res
