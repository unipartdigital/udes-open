from .common import BaseUDES
from odoo.exceptions import ValidationError
from unittest.mock import patch


class TestMixinModel(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestMixinModel, cls).setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Group = cls.env["procurement.group"]
        cls.Package = cls.env["stock.quant.package"]

    def test_incorrect_identifier_type(self):
        """Error raised when incorrect identifier type is passed"""
        identifier = ["Test product Apple"]
        with self.assertRaises(TypeError) as e:
            self.Product._get_msm_domain(identifier)
        self.assertEqual(
            e.exception.args[0], f"Identifier must be either int or str, not {type(identifier)}"
        )

    def test_correct_identifier_type(self):
        """Get domain with correct identifier type"""
        identifier = "Test product Apple"
        domain = self.Product._get_msm_domain(identifier)
        self.assertEqual(domain, ["|", ("name", "=", identifier), ("barcode", "=", identifier)])

    def test_get_existing_product_by_name(self):
        """Get a product by name"""
        prod = self.Product.get_or_create("Test product Apple")
        self.assertEqual(prod, self.apple)

    def test_get_existing_product_by_barcode(self):
        """Get product by barcode"""
        prod = self.Product.get_or_create("productApple")
        self.assertEqual(prod, self.apple)

    def test_get_existing_product_by_id(self):
        """Get a product by id"""
        # First get the product via the name (tested above)
        prod = self.Product.get_or_create("Test product Apple")
        id = prod.id
        prod_id = self.Product.get_or_create(id)
        self.assertEqual(prod_id, prod)

    def test_error_on_product_not_found(self):
        """Error raised when product not found"""
        with self.assertRaises(ValidationError) as e:
            self.Product.get_or_create("Invisible Apple")
        self.assertEqual(e.exception.args[0], "Product not found for identifier Invisible Apple")

    def test_error_on_create_product(self):
        """Cannot create a new product"""
        with self.assertRaises(ValidationError) as e:
            self.Product.get_or_create("Invisible Apple", create=True)
        self.assertEqual(e.exception.args[0], "Cannot create a new Product for product.product")

    def test_create_and_get_group(self):
        """Create a group and then get it by name and id"""
        # Check cannot get group to begin with and there are no groups
        self.assertEqual(len(self.Group.search([])), 0)
        with self.assertRaises(ValidationError) as e:
            self.Group.get_or_create("TESTGROUP01")
        self.assertEqual(
            e.exception.args[0], "Procurement Group not found for identifier TESTGROUP01"
        )
        # Create group
        group = self.Group.get_or_create("TESTGROUP01", create=True)
        self.assertEqual(group, self.Group.search([]))
        # Check get group by name
        self.assertEqual(self.Group.get_or_create("TESTGROUP01"), group)
        # Check get group by id
        self.assertEqual(self.Group.get_or_create(group.id), group)

    def test_do_not_create_group_with_same_name(self):
        """Create a group and then get it with create enabled, returns the same group"""
        # Check cannot get group to begin with
        with self.assertRaises(ValidationError) as e:
            self.Group.get_or_create("TESTGROUP01")
        self.assertEqual(
            e.exception.args[0], "Procurement Group not found for identifier TESTGROUP01"
        )
        group = self.Group.get_or_create("TESTGROUP01", create=True)
        self.assertEqual(group, self.Group.search([]))
        # Check cannot create a new group with the same name
        new_group = self.Group.get_or_create("TESTGROUP01", create=True)
        self.assertEqual(new_group, group)

    def test_cannot_create_group_by_id(self):
        """Error raised when try to create group by id"""
        id = 100000000
        # Check cannot get group to begin with
        with self.assertRaises(ValidationError) as e:
            self.Group.get_or_create(id)
        self.assertEqual(e.exception.args[0], f"Procurement Group not found for identifier {id}")
        with self.assertRaises(ValidationError) as e:
            self.Group.get_or_create(id, create=True)
        self.assertEqual(
            e.exception.args[0],
            f"Cannot create a new Procurement Group for procurement.group with identifier of type {type(id)}",
        )

    def test_get_product_by_multiple_domains(self):
        """Test that the way the domain is formatted is correct, by extending what product can
        look for, as in the future we may want to search by more than two domains.
        It's done for three string domains in product, the rest is true by induction.
        """
        with patch.object(
            type(self.Product), "MSM_STR_DOMAIN", ("name", "default_code", "barcode")
        ):
            prod = self.Product.get_or_create("productApple")

            self.assertEqual(self.Product.get_or_create(prod.default_code), prod)
            self.assertEqual(self.Product.get_or_create(prod.name), prod)
            self.assertEqual(self.Product.get_or_create(prod.barcode), prod)

    def test_create_then_get_new_package_success_by_name(self):
        """Create a new Package and then get it by name"""
        test_package = self.Package.get_or_create("Test Pack 1", create=True)
        get_package = self.Package.get_or_create("Test Pack 1")
        self.assertEqual(test_package, get_package)

    def test_create_then_get_new_package_success_by_id(self):
        """Create a new Package and then get it by id"""
        test_package = self.Package.get_or_create("Test Pack 2", create=True)
        get_package = self.Package.get_or_create(test_package.id)
        self.assertEqual(test_package.name, get_package.name)

    def test_cannot_create_package_with_id(self):
        """Cannot create a package with id"""
        # Check id does not exist
        id = 1001
        with self.assertRaises(ValidationError) as e:
            self.Package.get_or_create(id)
        self.assertEqual(e.exception.args[0], f"Package not found for identifier {id}")
        # Try to create package
        with self.assertRaises(ValidationError) as e:
            self.Package.get_or_create(id, create=True)
        self.assertEqual(
            e.exception.args[0],
            f"Cannot create a new Package for stock.quant.package with identifier of type {type(id)}",
        )

    def test_error_on_multiple_instances_group(self):
        """Error raised when existing multiple instances of the same id"""
        # Create initial group using get_or_create
        group = self.Group.get_or_create("TESTGROUP01", create=True)
        # Create repeated group
        new_group = self.Group.create({"name": "TESTGROUP01"})
        self.assertNotEqual(group.id, new_group.id)
        # Get error when trying to get the group
        with self.assertRaises(ValidationError) as e:
            self.Group.get_or_create("TESTGROUP01")
        self.assertEqual(
            e.exception.args[0],
            "Too many Procurement Groups found for identifier TESTGROUP01 in procurement.group",
        )
