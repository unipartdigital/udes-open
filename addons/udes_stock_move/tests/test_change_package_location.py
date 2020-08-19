# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from addons.udes_stock.tests import common


class TestChangePackageLocation(common.BaseUDES):
    """ Tests for the change_package_location wizard """

    @classmethod
    def setUpClass(cls):
        super(TestChangePackageLocation, cls).setUpClass()

        Package = cls.env["stock.quant.package"]

        cls.empty_package = Package.create({})
        cls.package_1 = cls.create_package_with_quants(cls.test_stock_location_01)
        cls.package_2 = cls.create_package_with_quants(cls.test_stock_location_01)
        cls.package_3 = cls.create_package_with_quants(cls.test_stock_location_01)
        cls.package_4 = cls.create_package_with_quants(cls.test_stock_location_02)
        cls.packages = cls.package_1 | cls.package_2 | cls.package_3 | cls.package_4

    @classmethod
    def create_package_with_quants(cls, location):
        """
        Create a package containing apples and bananas at the given location
        """
        package = cls.create_package()
        cls.create_quant(cls.apple.id, location.id, 10, package_id=package.id)
        cls.create_quant(cls.banana.id, location.id, 10, package_id=package.id)
        return package

    @classmethod
    def create_wizard(cls, packages):
        """ Creates a change_package_location wizard for the given packages """
        ChangePackageLocation = cls.env["udes_stock_move.change_package_location"]

        wizard = ChangePackageLocation.create({})
        wizard = wizard.with_context(active_ids=packages.ids)
        return wizard

    def test01_move_empty_package(self):
        """ Tests that moving an empty package fails """
        wizard = self.create_wizard(self.empty_package)

        with self.assertRaises(UserError) as e:
            wizard.create_picking()

        self.assertEqual(e.exception.name, "Nothing to check the availability for.")

    def test02_move_single_package(self):
        """ Tests moving a single package """
        Picking = self.env["stock.picking"]

        wizard = self.create_wizard(self.package_2)
        wizard.location_dest_id = self.test_stock_location_02

        picking = Picking.browse(wizard.create_picking()["res_id"])
        self.assertEqual(picking.picking_type_id, self.picking_type_internal)
        self.assertEqual(picking.origin, False)
        self.assertEqual(picking.location_id, self.test_stock_location_01)
        self.assertEqual(picking.location_dest_id, self.test_stock_location_02)
        self.assertEqual(picking.state, "assigned")
        self.assertEqual(picking.move_line_ids.package_id, self.package_2)
        self.complete_picking(picking)
        self.assertEqual(self.package_2.location_id, self.test_stock_location_02)

    def test03_move_multiple_packages(self):
        """ Tests moving multiple packages """
        Picking = self.env["stock.picking"]

        wizard = self.create_wizard(self.packages)
        wizard.location_dest_id = self.test_trailer_location_01

        picking = Picking.browse(wizard.create_picking()["res_id"])
        self.assertEqual(picking.picking_type_id, self.picking_type_internal)
        self.assertEqual(picking.origin, False)
        self.assertEqual(picking.location_id, self.stock_location)
        self.assertEqual(picking.location_dest_id, self.test_trailer_location_01)
        self.assertEqual(picking.state, "assigned")
        self.assertEqual(picking.move_line_ids.package_id, self.packages)
        self.complete_picking(picking)
        self.assertEqual(self.packages.location_id, self.test_trailer_location_01)

    def test04_move_with_reference(self):
        """ Tests moving a package with a reference """
        Picking = self.env["stock.picking"]

        wizard = self.create_wizard(self.package_2)
        wizard.reference = "PO99999"
        wizard.location_dest_id = self.test_stock_location_02

        picking = Picking.browse(wizard.create_picking()["res_id"])
        self.assertEqual(picking.origin, "PO99999")
        self.complete_picking(picking)
        self.assertEqual(self.package_2.location_id, self.test_stock_location_02)

    def test05_move_with_picking_type(self):
        """ Tests moving a package with a custom picking type """
        Picking = self.env["stock.picking"]

        wizard = self.create_wizard(self.package_2)
        wizard.picking_type_id = self.picking_type_goods_out
        wizard.location_dest_id = self.test_trailer_location_01

        picking = Picking.browse(wizard.create_picking()["res_id"])
        self.assertEqual(picking.picking_type_id, self.picking_type_goods_out)
        self.complete_picking(picking)
        self.assertEqual(self.package_2.location_id, self.test_trailer_location_01)

    def test06_move_reserved_packages(self):
        """ Tests that moving packages with reserved contents fails """
        wizard = self.create_wizard(self.packages)

        self.package_2._get_contained_quants()[0].reserved_quantity = 1
        self.package_3._get_contained_quants()[0].reserved_quantity = 1
        with self.assertRaises(ValidationError) as e:
            wizard.create_picking()

        self.assertTrue(self.package_2.name)
        self.assertTrue(self.package_3.name)
        self.assertEqual(
            e.exception.name,
            "Cannot move packages with reserved contents. "
            "Please speak to a team leader to resolve the issue.\n"
            "Affected packages: %s, %s" % (self.package_2.name, self.package_3.name),
        )
