# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


def check_many2one_validity(field, obj, id_):
    """
    Raise an error if id of the field for the object does not exist
    :param field: (str) field name
    :param obj: (recordset)
    :param id_: (int) id of the record referenced by the field
    :return:
    """
    if not obj.search([('id', '=', id_)]):
        raise ValidationError(_('The %s supplied (%s) is not valid, '
                                'it does not exist.') % (field, id_))
