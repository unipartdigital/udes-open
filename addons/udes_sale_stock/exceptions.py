"""Custom exceptions for the UDES Sale Stock addon."""


from odoo.exceptions import ValidationError


class CombinedException(ValidationError):
    """
    An exception which contains detals of other exceptions.

    We inherit from `ValidationError` because Odoo evaluates code provided through an
    action's `code` attribute with `odoo.tools.unsafe_eval`, which converts many exception
    types to `ValueErrors`.  This loses the extra information in
    `collected_exceptions`, which we would like to keep.
    """

    def __init__(self, msg, collected_exceptions, *args):
        super().__init__(msg, *args)
        self.collected_exceptions = collected_exceptions
