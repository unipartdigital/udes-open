import logging


from odoo import fields, models, _, SUPERUSER_ID
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResArchivingRestriction(models.Model):
    """
    Configurable access to _only_ record archiving & unarchiving

    If an Archiving Restriction is created for a model, the permitted_group_ids set will determine
    which groups have the facility to archive and unarchive records on the model.

    This includes backend writes to the `active` field, as well as hiding
    the Archive/Unarchive action from the model, and attempting to remove active
    fields & smart buttons from form views.
    """

    _name = "res.archiving.restriction"
    _description = "Record Archiving Restriction"
    _sql_constraints = [
        (
            "model_id_uniq",
            "unique(model_id)",
            _("An Archiving Restriction already exists for this model."),
        )
    ]

    model_id = fields.Many2one(
        "ir.model", string="Model", help="Model to apply restriction to", required=True, index=True
    )
    name = fields.Char(string="Model Name", related="model_id.model", readonly=True)
    permitted_group_ids = fields.Many2many(
        "res.groups",
        string="Permitted Groups",
        index=True,
        help="""
        Groups Permitted to Archive & Unarchive on the given model.

        If no groups are configured, ALL users will be prevented from archiving (except superuser)
        If the user is in any of the configured groups, they will be permitted access
        If no restriction on a model is intended, then do not create a restriction record for that model
        """,
    )

    def _get_can_archive(self, model_name):
        """
        Check against the model to see if active user is
        permitted to archive/unarchive the record.

        Can archive if user has _any_ groups defined on the restriction,
        or no restriction is defined

        :param: model_name: str() model _name i.e "stock.picking.type"
        :returns: bool()
        """
        ResArchivingRestriction = self.env["res.archiving.restriction"]

        if self.env.user.id == SUPERUSER_ID:
            return True
        if not model_name:
            return True
        model_restriction = ResArchivingRestriction.search([("model_id.model", "=", model_name)])
        if not model_restriction:
            return True
        user_group_ids = self.env.user.groups_id.ids
        groups_on_user_and_restriction = [
            gid for gid in user_group_ids if gid in model_restriction.permitted_group_ids.ids
        ]
        return bool(groups_on_user_and_restriction)

    def _check_can_archive(self, model_name):
        """Raises a warning if the logged in user does not meet
        the group requirements to archive/unarchive a record

        :param: model_name: str() model _name i.e "stock.picking.type"
        """
        if not self._get_can_archive(model_name):
            user = self.env.user
            _logger.warning(
                f"User '{user.name}', ID {user.id} blocked attempt at archiving on '{model_name}'."
            )
            raise ValidationError(_("You do not have permission to archive/unarchive this record."))
        return True
