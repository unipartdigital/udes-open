# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class StockLocationCategory(models.Model):
    _name = 'stock.location.category'
    _description = "Stock Location Category"
    _parent_name = "parent_id"
    # TODO: check this
    _parent_order = 'name'
    # TODO: check this
    _rec_name = 'complete_name'
    _order = 'parent_id, id'

    name = fields.Char('Name', index=True, required=True, translate=True)
    complete_name = fields.Char(
        'Complete Name', compute='_compute_complete_name',
        store=True)
    parent_id = fields.Many2one('stock.location.category', 'Parent Category',
                                index=True, ondelete='cascade')
    child_id = fields.One2many('stock.location.category', 'parent_id',
                               'Child Categories')
    # TODO: do we want this?
    # location_count = fields.Integer(
    #     '# Locations', compute='_compute_location_count',
    #     help="The number of locations under this category "
    #          "(Does not consider the children categories)")

    # TODO: picking types related to a category?

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name

    # def _compute_location_count(self):
    #     read_group_res = self.env['product.template'].read_group([('categ_id', 'child_of', self.ids)], ['categ_id'], ['categ_id'])
    #     group_data = dict((data['categ_id'][0], data['categ_id_count']) for data in read_group_res)
    #     for categ in self:
    #         product_count = 0
    #         for sub_categ_id in categ.search([('id', 'child_of', categ.id)]).ids:
    #             product_count += group_data.get(sub_categ_id, 0)
    #         categ.product_count = product_count

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('Error ! You cannot create recursive categories.'))
        return True

    # @api.model
    # def name_create(self, name):
    #     return self.create({'name': name}).name_get()[0]