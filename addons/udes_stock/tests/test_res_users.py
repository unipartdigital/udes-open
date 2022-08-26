from odoo.exceptions import ValidationError
from . import common


class TestGetUserWarehouse(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestGetUserWarehouse, cls).setUpClass()
        Warehouse = cls.env["stock.warehouse"]
        cls.User = cls.env["res.users"]
        # Create new company so there is more than one warehouse
        cls.test_company = cls.create_company("test_company")
        cls.test_warehouse = Warehouse.search([("company_id", "=", cls.test_company.id)])
        cls.test_user = cls.create_user(
            "test_user",
            "test_user_login",
            company_id=cls.test_company.id,
            company_ids=[(6, 0, cls.test_company.ids)],
        )

    def test_get_user_warehouse_no_user(self):
        """Checking that when no user is found the correct error is raised"""
        # Make it so user isn't found in search
        self.test_user.active = False
        with self.assertRaises(ValidationError) as e:
            self.User.with_user(self.test_user).get_user_warehouse()
        self.assertEqual(e.exception.args[0], "Cannot find user")

    def test_get_user_warehouse_no_warehouse(self):
        """Checking that when a user has no warehouse the correct error is raised"""
        # Make it so warehouse isn't found in search
        self.test_warehouse.active = False
        with self.assertRaises(ValidationError) as e:
            self.User.with_user(self.test_user).get_user_warehouse()
        self.assertEqual(e.exception.args[0], "Cannot find a warehouse for user")

    def test_get_user_warehouse_multiple_warehouse(self):
        """Checking that when a user has multiple warehouses that all the warehouse are returned"""
        # Create new warehouse by copying current one and changing
        # the required fields
        warehouse2 = self.test_warehouse.copy({"name": "test_company_2", "code": "123"})
        warehouses = self.test_warehouse | warehouse2
        whs = self.User.with_user(self.test_user).get_user_warehouse()
        self.assertEqual(whs, warehouses)

    def test_get_user_warehouse_single_warehouse(self):
        """Checking that when a user has a single warehouse that the warehouse is returned"""
        whs = self.User.with_user(self.test_user).get_user_warehouse()
        self.assertEqual(whs, self.test_warehouse)

    def test_get_user_warehouse_single_from_multiple_warehouses(self):
        """Checking that when a user has multiple warehouses that a warehouse is returned if an
        additional domain is used
        """
        # Create new warehouse by copying current one and changing
        # the required fields
        warehouse2 = self.test_warehouse.copy({"name": "test_company_2", "code": "123"})
        whs = self.User.with_user(self.test_user).get_user_warehouse(
            aux_domain=[("name", "=", "test_company_2")]
        )
        self.assertEqual(whs, warehouse2)

    def test_get_user_warehouse_subset_from_multiple_warehouses(self):
        """Checking that when a user has multiple warehouses they cannot use aux_domain to return
        a subset"""
        # Create new warehouse by copying current one and changing
        # the required fields
        self.test_warehouse.copy({"name": "test_company_2", "code": "123"})
        self.test_warehouse.copy({"name": "test_company_3", "code": "321"})
        with self.assertRaises(ValidationError) as e:
            self.User.with_user(self.test_user).get_user_warehouse(
                aux_domain=[("name", "in", ["test_company_2", "test_company_3"])]
            )
        self.assertEqual(
            e.exception.args[0],
            "Found multiple warehouses for user, "
            + "the aux_domain is specifying multiple warehouses or cannot be correct!",
        )
