from odoo import models, _
from odoo.exceptions import ValidationError


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    def get_group(self, group_identifier, create=False):
        """
        Gets the group from the supplied group identifier - either the id
        or the group name
        :param group_identifier: The id or the name of the group we are
            getting or creating
        :param create: Boolean:  When True and group_identifier is a string
            will create a new group if it does not exist
        """
        name = None
        if isinstance(group_identifier, int):
            domain = [('id', '=', group_identifier)]
        elif isinstance(group_identifier, str):
            domain = [('name', '=', group_identifier)]
            name = group_identifier
        else:
            raise ValidationError(_(
                'Unable to create domain for group search from'
                ' identifier of type %s') % type(group_identifier))
        results = self.search(domain)
        if not results:
            if create and name is not None:
                results = self.create({'name': name})
            else:
                raise ValidationError(
                    _('Group not found for '
                      'identifier %s') % str(group_identifier))
        if len(results) > 1:
            raise ValidationError(
                _('Too many groups found for '
                  'identifier %s') % str(group_identifier))
        return results
