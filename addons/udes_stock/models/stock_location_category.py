# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockLocationCategory(models.Model):
    _name = 'stock.location.category'
    _description = "Stock Location Category"
    _parent_name = "parent_id"
    _rec_name = 'complete_name'
    _order = 'parent_id, id'

    name = fields.Char('Name', index=True, required=True, translate=True)
    complete_name = fields.Char(
        'Complete Name', compute='_compute_complete_name',
        store=True)
    parent_id = fields.Many2one('stock.location.category', 'Parent Category',
                                index=True, ondelete='cascade')
    child_ids = fields.One2many('stock.location.category', 'parent_id',
                                'Child Categories', readonly=True)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            parent = category.parent_id
            if parent:
                category.complete_name = '%s / %s' % (parent.complete_name,
                                                      category.name)
            else:
                category.complete_name = category.name

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(
                _('Error ! You cannot create recursive categories.'))
        return True

    @api.model
    def name_create(self, name):
        """ Override name_create to use field name instead of _rec_name since it
            is pointing to complete_name that is a computed field.
        """
        return self.create({'name': name}).name_get()[0]

    def _prepare_info(self):
        """
            Prepares the following info of the location category in self:
            - id: int
            - name: string
        """
        self.ensure_one()

        return {"id": self.id,
                "name": self.name,
                "complete_name": self.complete_name}

    def get_info(self, **kwargs):
        """ Return a list with the information of each location category in self.
        """
        res = []
        for cat in self:
            res.append(cat._prepare_info(**kwargs))

        return res
