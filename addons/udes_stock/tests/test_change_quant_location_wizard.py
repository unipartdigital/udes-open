from . import common
from odoo.exceptions import ValidationError


class TestChangeQuantLocationWizard(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        """Setup basic data"""
        super(TestChangeQuantLocationWizard, cls).setUpClass()
        Picking = cls.env["stock.picking"]
        cls.change_quant_location = cls.env["change_quant_location"].sudo(cls.outbound_user)

        cls.package1 = cls.create_package()
        cls.product_quantity = 10

        cls.quant1 = cls.create_quant(
            cls.apple.id,
            cls.test_location_01.id,
            cls.product_quantity,
            package_id=cls.package1.id
        )

        cls.products_info = [{"product": cls.apple, "qty": cls.product_quantity}]

    def assert_cannot_create_reserved_permission(self, cql):
        """Assert we get a validation error when we try to move a reserved package
        due to permissions/settings"""
        with self.assertRaises(ValidationError) as e:
            cql.create_picking()
        self.assertTrue(e.exception.name.startswith(
            "Items are reserved and cannot be moved. "
            "Please speak to a team leader to resolve the issue."
        ))

    def assert_cannot_create_partially_reserved(self, cql):
        """Assert we get a validation error when we try to move a reserved package
        as it is partially reserved"""
        with self.assertRaises(ValidationError) as e:
            cql.create_picking()
        self.assertTrue(e.exception.name.startswith(
            "Packages/Pallets must be either entirely reserved or unreserved."
        ))

    def give_permission_to_move_reserved(self, user):
        """Setup the user and their warehouse to allow them to move reserved packages"""
        warehouse = user.get_user_warehouse()
        warehouse.u_allow_create_picking_reserved_package = True
        group_manage_reserved_packages = self.env.ref("udes_stock.group_manage_reserved_packages")
        user.write({"groups_id": [(4, group_manage_reserved_packages.id)]})

    def test_create_picking(self):
        """Check that we can create a picking for a package"""
        self.assertFalse(self.quant1.reserved_quantity)

        cql = self.change_quant_location.with_context(
            active_ids=[self.package1.id]
        ).create({"picking_type_id": self.picking_type_pick.id})
        cql.create_picking()

        new_picking = self.package1.move_line_ids.picking_id
        self.assertEqual(new_picking.picking_type_id, self.picking_type_pick)
        self.assertEqual(self.quant1.quantity, self.quant1.reserved_quantity)

    def test_create_picking_multiple_packages(self):
        """Check that we can create a picking for multiple packages"""
        package2 = self.create_package()
        quant2 = self.create_quant(
            self.apple.id,
            self.test_location_01.id,
            self.product_quantity,
            package_id=package2.id
        )

        self.assertFalse(self.quant1.reserved_quantity)
        self.assertFalse(quant2.reserved_quantity)

        cql = self.change_quant_location.with_context(
            active_ids=[self.package1.id, package2.id]
        ).create({"picking_type_id": self.picking_type_pick.id})
        cql.create_picking()

        package1_picking = self.package1.move_line_ids.picking_id
        package2_picking = package2.move_line_ids.picking_id
        self.assertEqual(package1_picking, package2_picking)
        self.assertEqual(package1_picking.picking_type_id, self.picking_type_pick)
        self.assertEqual(self.quant1.quantity, self.quant1.reserved_quantity)
        self.assertEqual(quant2.quantity, quant2.reserved_quantity)

    def test_create_picking_reserved_permissions(self):
        """Check that a picking for a reserved package can only be created
        with the correct settings and permissions."""
        warehouse = self.outbound_user.get_user_warehouse()
        test_picking = self.create_picking(
            self.picking_type_pick,
            origin="test_picking_origin",
            products_info=self.products_info,
            confirm=True,
        )
        test_picking.action_assign()
        self.assertEqual(self.quant1.quantity, self.quant1.reserved_quantity)

        cql = self.change_quant_location.with_context(
            active_ids=[self.package1.id]
        ).create({"picking_type_id": self.picking_type_out.id})

        # We cannot create a picking without user permission for either value
        # of u_allow_create_picking_reserved_package
        for value in [False, True]:
            warehouse.u_allow_create_picking_reserved_package = value
            self.assert_cannot_create_reserved_permission(cql)

        warehouse.u_allow_create_picking_reserved_package = False
        # We cannot create a picking without the warehouse setting despite having user permission
        group_manage_reserved_packages = self.env.ref("udes_stock.group_manage_reserved_packages")
        self.outbound_user.write({"groups_id": [(4, group_manage_reserved_packages.id)]})
        self.assert_cannot_create_reserved_permission(cql)

        # Finally we can create a picking when we have both user permission and
        # warehouse setting
        warehouse.u_allow_create_picking_reserved_package = True
        cql.create_picking()

        new_picking = self.package1.move_line_ids.picking_id
        self.assertEqual(new_picking.picking_type_id, self.picking_type_out)
        self.assertEqual(self.quant1.quantity, self.quant1.reserved_quantity)

    def test_create_picking_partially_reserved(self):
        """Test that we are not allowed to create a picking for a package
        if it is paritally reserved
        """
        # Give user permission to create pickings for reserved packages
        self.give_permission_to_move_reserved(self.outbound_user)
        self.quant1.reserved_quantity = 1

        cql = self.change_quant_location.with_context(
            active_ids=[self.package1.id]
        ).create({"picking_type_id": self.picking_type_pick.id})

        self.assert_cannot_create_partially_reserved(cql)

    def test_create_picking_partially_reserved_multi_package(self):
        """Test that that we cannot create pickings for partially reserved
        packages.
        """
        # Give user permission to create pickings for reserved packages
        self.give_permission_to_move_reserved(self.outbound_user)
        # Reserve first package
        test_picking = self.create_picking(
            self.picking_type_pick,
            origin="test_picking_origin",
            products_info=self.products_info,
            confirm=True,
        )
        test_picking.action_assign()
        # Create second package
        package2 = self.create_package()
        quant2 = self.create_quant(
            self.apple.id,
            self.test_location_01.id,
            self.product_quantity,
            package_id=package2.id
        )

        cql = self.change_quant_location.with_context(
            active_ids=[self.package1.id, package2.id]
        ).create({"picking_type_id": self.picking_type_pick.id})

        # Check we cannot create picking for both packages
        self.assert_cannot_create_partially_reserved(cql)

        # Reserve second package
        test_picking2 = self.create_picking(
            self.picking_type_pick,
            origin="test_picking_origin",
            products_info=self.products_info,
            confirm=True,
        )
        test_picking2.action_assign()

        # Check we can create a picking when both are reserved
        cql.create_picking()

        package1_picking = self.package1.move_line_ids.picking_id
        package2_picking = package2.move_line_ids.picking_id
        self.assertEqual(package1_picking, package2_picking)
        self.assertEqual(package1_picking.picking_type_id, self.picking_type_pick)
        self.assertEqual(self.quant1.quantity, self.quant1.reserved_quantity)
        self.assertEqual(quant2.quantity, quant2.reserved_quantity)

    def test_create_picking_partially_complete(self):
        """Test that we are not allowed to create a picking for a package
        if it has partially complete movelines.
        """
        # Give user permission to create pickings for reserved packages
        self.give_permission_to_move_reserved(self.outbound_user)

        # Reserve package
        test_picking = self.create_picking(
            self.picking_type_pick,
            origin="test_picking_origin",
            products_info=self.products_info,
            confirm=True,
        )
        test_picking.action_assign()
        # Partially complete the move/moveline for the package
        test_picking.move_line_ids.qty_done = 1
        test_picking.move_lines.quantity_done = 1

        # Check that it errors when we try to create a picking for the package
        cql = self.change_quant_location.with_context(active_ids=[self.package1.id]).create(
            {"picking_type_id": self.picking_type_pick.id}
        )
        with self.assertRaises(ValidationError) as e:
            cql.create_picking()
        self.assertTrue(
            e.exception.name.startswith(
                "Pickings cannot be created when movelines are partially complete."
            )
        )
