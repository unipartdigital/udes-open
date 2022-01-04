"""Tests for the Package model."""

from odoo.exceptions import ValidationError
from psycopg2.errors import UniqueViolation

from odoo.addons.udes_stock.tests.common import BaseUDES


class PackageCreationTestCase(BaseUDES):
    """Tests for package creation."""

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures."""
        super().setUpClass()

        cls.package = cls.env["stock.quant.package"]

    def test_creates_package_with_valid_name(self):
        """We should be able to create a package if we provide a valid name."""
        name = "1001"

        package = self.package.create({"name": name})
        self.assertEqual(package.name, name)

    def test_creates_pallet_with_valid_name(self):
        """The system should create a package with a valid pallet name if provided."""
        name = "UDES001"

        package = self.package.create({"name": name})
        self.assertEqual(package.name, name)

    def test_creates_pallet_when_parent_id_is_false(self):
        """The system should create a package if the parent id is `False`."""
        name = "UDES001"

        package = self.package.create({"name": name, "parent_id": False})
        self.assertEqual(package.name, name)

    def test_creates_package_with_valid_name_automatically(self):
        """The system should create a package with a valid name if we don't provide one."""
        package = self.package.create({})
        prefix = package.name[:4]
        sequence = package.name[4:]

        self.assertEqual(prefix, "UDES")
        self.assertTrue(sequence.isnumeric())

    def test_rejects_package_with_invalid_name(self):
        """The system must reject an invalid package name."""
        # Bad names: no digits, bad prefix, non-ASCII digits
        invalid_names = ["UDES_ONE", "FOO001", "UDES᠐᠐᠑"]

        for name in invalid_names:
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    self.package.create({"name": name})

    def test_rejects_rename_to_invalid_package_name(self):
        """The system must prevent changing the package name to an invalid name."""
        package = self.package.create({})
        with self.assertRaises(ValidationError):
            package.name = "WRONG001"

    def test_rejects_duplicate_names(self):
        """The system must reject a duplicate name."""
        name = "UDES00001"
        self.package.create({"name": name})
        # Odoo converts the UniqueViolation to a ValidationError, but this
        # hasn't happened "yet" see how PGERROR_TO_OE is handled in
        # BaseModel.load.
        with self.assertRaises(UniqueViolation):
            self.package.create({"name": name})

    def test_prevents_using_package_as_pallet(self):
        """The system must reject attempts to use a package as a pallet."""
        package = self.package.create({"name": "1001"})
        with self.assertRaises(ValidationError):
            self.package.create({"parent_id": package.id})

    def test_permits_using_pallet_as_pallet(self):
        """The system will accept pallets as package parents."""
        name = "UDES001"
        pallet = self.package.create({"name": name})
        package = self.package.create({"parent_id": pallet.id})

        self.assertEqual(package.parent_id.name, name)

    def test_prevents_changing_pallet_to_package(self):
        """The system must not permit changing a package's pallet to a package."""
        original_pallet = self.package.create({"name": "UDES001"})
        package = self.package.create({"name": "1001", "parent_id": original_pallet.id})
        other_package = self.package.create({"name": "1002"})

        with self.assertRaises(ValidationError):
            package.parent_id = other_package

    def test_permits_changing_pallet_to_another_pallet(self):
        """The system must permit changing a package's pallet to another pallet."""
        original_pallet = self.package.create({"name": "UDES001"})
        package = self.package.create({"name": "1001", "parent_id": original_pallet.id})
        other_pallet = self.package.create({"name": "UDES002"})
        package.parent_id = other_pallet

        self.assertEqual(package.parent_id, other_pallet)

    def test_prevents_changing_loaded_pallet_name_to_package(self):
        """The system must not permit changing a pallet name to a package name if it is loaded."""
        pallet = self.package.create({"name": "UDES001"})
        self.package.create({"name": "1001", "parent_id": pallet.id})

        with self.assertRaises(ValidationError):
            pallet.name = "1002"

    def test_prevents_adding_pallets_to_a_pallet(self):
        """The system will not permit adding a pallet to a pallet."""
        pallet = self.package.create({"name": "UDES001"})
        package = self.package.create({"name": "1001"})
        other_pallet = self.package.create({"name": "UDES002"})
        children = package | other_pallet

        with self.assertRaises(ValidationError):
            pallet.children_ids = children.ids

    def test_prevents_adding_pallets_to_a_pallet_via_write(self):
        """The system will not permit adding a pallet to a pallet using write."""
        pallet = self.package.create({"name": "UDES001"})
        package = self.package.create({"name": "1001"})
        other_pallet = self.package.create({"name": "UDES002"})
        children = package | other_pallet

        with self.assertRaises(ValidationError):
            pallet.write({"children_ids": [(6, 0, children.ids)]})

    def test_can_add_packages_to_pallet(self):
        """The system must permit adding packages to a pallet."""
        pallet = self.package.create({"name": "UDES001"})
        package1 = self.package.create({"name": "1001"})
        package2 = self.package.create({"name": "1002"})
        packages = package1 | package2

        pallet.children_ids = packages.ids

        self.assertEqual(pallet.children_ids, packages)

    def test_can_add_packages_to_pallet_via_write(self):
        """The system must permit adding packages to a pallet using write."""
        pallet = self.package.create({"name": "UDES001"})
        package1 = self.package.create({"name": "1001"})
        package2 = self.package.create({"name": "1002"})
        packages = package1 | package2

        pallet.write({"children_ids": [(6, 0, packages.ids)]})

        self.assertEqual(pallet.children_ids, packages)

    def test_prevents_adding_packages_to_package(self):
        """The system must prevent adding package to a package."""
        parent_package = self.package.create({"name": "1001"})
        child_package = self.package.create({"name": "1002"})

        with self.assertRaises(ValidationError):
            parent_package.children_ids = child_package.ids

    def test_prevents_adding_packages_to_package_via_write(self):
        """The system must prevent adding package to a package using write."""
        parent_package = self.package.create({"name": "1001"})
        child_package = self.package.create({"name": "1002"})

        with self.assertRaises(ValidationError):
            parent_package.write({"children_ids": [(6, 0, child_package.ids)]})
