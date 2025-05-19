import json
import odoo.tools
from odoo.tests import common


class TestForceUpperCaseOnFieldsHttp(common.HttpCase):

    def setUp(self):
        super(TestForceUpperCaseOnFieldsHttp, self).setUp()
        self.u_force_upper_case_config = '{"product.product": "barcode,default_code"}'
        self.empty_u_force_upper_case_config = '{}'
        self.warehouse_id = self.env.ref("stock.warehouse0")
        self.params_create_product = {'model': 'product.template',
                                      'method': 'create',
                                      }
        self.params_write_product = {'model': 'product.product',
                                     'method': 'write',
                                     }

    @odoo.tools.mute_logger('odoo.http')
    def call_route_to_test(self, route, params, vals, record_to_update=False):
        self.authenticate("admin", "admin")
        data = json.dumps({"params": {
            'model': params.get('model'),
            'method': params.get('method'),
            'args': [record_to_update, vals] if record_to_update else [vals],
            'kwargs': {},
        }, })
        open_route = self.url_open(route, data=data, headers={"Content-Type": "application/json"})
        return open_route

    def test_product_creation_with_empty_u_force_upper_case_config_no(self):
        """If u_force_upper_case_config is empty no validation error should occur"""

        self.warehouse_id.u_force_upper_case_config = self.empty_u_force_upper_case_config
        vals = [{'name': "banana_no_exp",
                 'default_code': 'banana_no_exp',
                 'barcode': 'banana_no_exp',
                 },
                {'name': "banana_no_exp2",
                 'default_code': 'banana_no_exp2',
                 'barcode': 'banana_no_exp2',
                 }
                ]
        self.call_route_to_test('/web/dataset/call_kw', self.params_create_product,
                                vals)

    def test_product_creation_with_u_force_upper_case_config(self):
        """If u_force_upper_case_config is set and lower case value provide validation error should occur"""
        self.warehouse_id.u_force_upper_case_config = self.u_force_upper_case_config
        vals = [{'name': "banana1",
                 'default_code': 'abc1',
                 'barcode': 'abc1',
                 },
                {'name': "banana_no_exp2",
                 'default_code': 'banana_no_exp2',
                 'barcode': 'banana_no_exp2',
                 }]
        open_route = self.call_route_to_test('/web/dataset/call_kw', self.params_create_product, vals)
        validation_error = open_route.json()
        self.assertEqual(validation_error['error']['data']['name'], 'odoo.exceptions.ValidationError')

    def test_product_updation_with_empty_u_force_upper_case_config_no(self):
        """If u_force_upper_case_config is empty no validation error should occur"""

        self.warehouse_id.u_force_upper_case_config = self.empty_u_force_upper_case_config
        create_vals = {'name': "product_with_lower_case",
                       'default_code': '',
                       'barcode': '',
                       }
        create_route = self.call_route_to_test('/web/dataset/call_kw', self.params_create_product,
                                         create_vals)
        product_id_to_update = create_route.json()['result']
        write_vals = {'default_code': 'product_with_lower_case', 'barcode': '', }
        self.call_route_to_test('/web/dataset/call_kw', self.params_write_product,
                                write_vals, record_to_update=product_id_to_update)

    def test_product_updation_with_u_force_upper_case_config(self):
        """If u_force_upper_case_config is set and lower case value provide validation error should occur"""

        # create new product with empty_u_force_upper_case_config and lower case default_code and barcode
        self.warehouse_id.u_force_upper_case_config = self.empty_u_force_upper_case_config
        create_vals = {'name': "product_with_lower_case",
                       'default_code': 'product_with_lower_case',
                       'barcode': 'product_with_lower_case',
                       }
        create_route = self.call_route_to_test('/web/dataset/call_kw', self.params_create_product,
                                         create_vals)
        product_id_to_update = create_route.json()['result']
        # update created product with lower case again but with u_force_upper_case_config config
        write_vals = {'default_code': 'new_lower_case', 'barcode': '', }
        self.warehouse_id.u_force_upper_case_config = self.u_force_upper_case_config
        open_route = self.call_route_to_test('/web/dataset/call_kw', self.params_write_product,
                                             write_vals, record_to_update=product_id_to_update)
        # this should generate the validation error
        validation_error = open_route.json()
        self.assertEqual(validation_error['error']['data']['name'], 'odoo.exceptions.ValidationError')
