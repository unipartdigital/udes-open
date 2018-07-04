# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from . import common

class TestGetUserWarehouse(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestGetUserWarehouse, cls).setUpClass()
        Warehouse = cls.env['stock.warehouse']
        # Create new company so there is more than one warehouse
        cls.test_company = cls.create_company('test_company')
        cls.test_warehouse = Warehouse.search([('company_id', '=', cls.test_company.id)])
        cls.test_user = cls.create_user('test_user',
                                        'test_user_login',
                                        company_id=cls.test_company.id,
                                        company_ids=[(6, 0, cls.test_company.ids)])


    def test01_get_user_warehouse_no_user(self):
        """Checking that when no user is found
           the correct error is raised
        """
        User = self.env['res.users']
        # Make it so user isn't found in search
        self.test_user.active = False
        with self.assertRaises(ValidationError) as e:
            User.sudo(self.test_user).get_user_warehouse()
        self.assertEqual(e.exception.name, 'Cannot find user to get warehouse.')

    def test02_get_user_warehouse_no_warehouse(self):
        """Checking that when a user has no warehouse 
           the correct error is raised
        """
        User = self.env['res.users']
        # Make it so warehouse isn't found in search
        self.test_warehouse.active = False
        with self.assertRaises(ValidationError) as e:
            User.sudo(self.test_user).get_user_warehouse()
        self.assertEqual(e.exception.name, 'Cannot find a warehouse for user')

    def test03_get_user_warehouse_multiple_warehouses(self):
        """Checking that when a user has mutiple warehouses 
           the correct error is raised
        """
        User = self.env['res.users']
        # Create new warehouse by copying current one and changing
        # the required feilds
        warehouse2 = self.test_warehouse.copy({'name': '123',
                                               'code': '123'})
        with self.assertRaises(ValidationError) as e:
            User.sudo(self.test_user).get_user_warehouse()
        self.assertEqual(e.exception.name, 'Found multiple warehouses for user')

    def test04_get_user_warehouse_success(self):
        """Checks that the correct warehouse is returned"""
        User = self.env['res.users']
        returned_warehouse = User.sudo(self.test_user).get_user_warehouse()
        self.assertEqual(returned_warehouse.id, self.test_warehouse.id)
