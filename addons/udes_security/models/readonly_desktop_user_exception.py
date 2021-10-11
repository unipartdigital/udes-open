from odoo import fields, models, api


class ReadonlyDesktopUserException(models.Model):
    """
    Model names that are exempt from the Readonly Desktop User setting
    """

    _name = "udes.readonly_desktop_user_model_exception"
    _description = "Readonly Desktop User Model Exception"

    _sql_constraints = [
        ("name_uniq", "unique (name)", "Exception for this model has already been added")
    ]

    name = fields.Char("Model Name", required=True, index=True)

    @api.model
    def is_exempt(self, model_name):
        """Return True if the supplied model name is exempt, otherwise False"""
        return bool(self.search_count([("name", "=", model_name)]))
