# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from .main import UdesApi


class WarehouseStock(UdesApi):

    @http.route('/api/stock-warehouse/', type='json', methods=['GET'], auth='user')
    def read_stock_warehouse_config(self):
        """
        Read the stock_warehouse records on the endpoint /api/stock-warhouse/
        :return: the main warehouse configuration + stock picking types values in a json format
        """
        Users = request.env['res.users']
        PickingType = request.env['stock.picking.type']

        res = {}
        # get the user's warehouse
        warehouse = Users.get_user_warehouse()
        # get warehouse info
        res['stock_warehouse'] = warehouse.get_info()[0]
        # get info of the picking types of the warehouse
        res['picking_types'] = warehouse.get_picking_types().get_info()

        return res 
