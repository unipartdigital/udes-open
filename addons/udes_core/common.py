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


def check_if_partial_quant(quants):
    """
    Don't allow partial quants of a package to move (i.e. if a package contains
    more than one quant, we either move ALL of them, or nothing - up to the user
    to select all of them).
    """
    quant_ids = quants.mapped('id')
    packages = quants.mapped('package_id')
    for p in packages:
        if not set(quant_ids) >= set(p.quant_ids.mapped('id')):
            raise ValidationError(_('Not all quants of the package %s have '
                                    'been taken') % (p.id))


def group_qty_by_product(recordsets):
    """
    Group quantity by product
    :param recordsets: recordsets having a product_id attribute
    :return: {'product_A': qty_of_product_A, ...}
    """
    products = {}
    for recordset in recordsets:
        products.setdefault(recordset.product_id.id, 0)
        products[recordset.product_id.id] = products[recordset.product_id.id] + recordset.qty
    return products


def check_if_quants_not_in_blocked_location(quants):
    """
    Don't allow quants to be moved if they are in a blocked location.
    """
    quant_ids = quants.filtered(lambda q: q.location_id.x_blocked)

    if quant_ids:
        quant_ids.mapped('location_id').check_blocked('Wrong location at operation.')
