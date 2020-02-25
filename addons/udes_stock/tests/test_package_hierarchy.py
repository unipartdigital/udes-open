from . import common
from odoo.exceptions import ValidationError


class TestPackageHierarchy(common.BaseUDES):

    def test1_max_package_depth_violation(self):
        """Test Non-Branching Maximum Package Depth Top Insertion"""
        pack_child = self.create_package()
        pack_parent = self.create_package()
        pack_grandparent = self.create_package()
        pack_child.package_id = pack_parent.id
        with self.assertRaises(ValidationError) as e:
            pack_parent.package_id = pack_grandparent.id
            self.assertEqual(e.exception.name, 'Maximum package depth exceeded.')

    def test2_max_package_depth_violation_tail(self):
        """Test Non-Branching Maximum Package Depth Tail Insertion"""
        pack_child = self.create_package()
        pack_parent = self.create_package()
        pack_grandparent = self.create_package()
        pack_child.package_id = pack_parent.id
        with self.assertRaises(ValidationError) as e:
            pack_grandparent.package_id = pack_child.id
            self.assertEqual(e.exception.name, 'Maximum package depth exceeded.')

    def test3_max_package_depth_violation_middle(self):
        """Test Non-Branching Maximum Package Depth Middle Insertion"""
        wh = self.env.user.get_user_warehouse()
        wh.u_max_package_depth = 3
        # Set up 3 level package
        pack_child_a = self.create_package()
        pack_child_b = self.create_package()
        pack_parent = self.create_package()
        pack_child_a.package_id = pack_child_b.id
        pack_child_b.package_id = pack_parent.id

        # Set up 2 level inner child
        pack_middle_child = self.create_package()
        pack_child_c = self.create_package()
        pack_child_c.package_id = pack_middle_child.id

        # Increase length of middle child to create 4 level package
        with self.assertRaises(ValidationError) as e:
            pack_middle_child.package_id = pack_child_b.id
            self.assertEqual(e.exception.name, 'Maximum package depth exceeded.')

    def test4_max_package_depth_violation_branch_top(self):
        """Test Branching Maximum Package Depth Top Insertion"""
        wh = self.env.user.get_user_warehouse()
        wh.u_max_package_depth = 4

        # Set up 4 level package
        pack_child_1_a = self.create_package()
        pack_child_1_b = self.create_package()
        pack_child_1_c = self.create_package()

        pack_parent_1 = self.create_package()
        pack_child_1_a.package_id = pack_child_1_b.id
        pack_child_1_b.package_id = pack_child_1_c.id
        pack_child_1_c.package_id = pack_parent_1.id 

        # Set up grandparent package - 2 levels
        pack_parent_2 = self.create_package()
        pack_grandparent = self.create_package()
        pack_parent_2.package_id = pack_grandparent.id

        # Add a 4 level package to grandparent
        with self.assertRaises(ValidationError) as e:
            pack_parent_1.package_id = pack_grandparent.id
            self.assertEqual(e.exception.name, 'Maximum package depth exceeded.')

    def test5_max_package_depth_violation_branch_tail(self):
        """Test Branching Maximum Package Depth Tail Insertion"""
        wh = self.env.user.get_user_warehouse()
        wh.u_max_package_depth = 4

        # Set up 3 level package
        pack_child_1_a = self.create_package()
        pack_child_1_b = self.create_package()
        pack_parent_1 = self.create_package()
        pack_child_1_a.package_id = pack_child_1_b.id
        pack_child_1_b.package_id = pack_parent_1.id

        # Set up 2 level package
        pack_parent_2 = self.create_package()

        # Set up grandparent package - 2 levels
        pack_grandparent = self.create_package()
        pack_parent_2.package_id = pack_grandparent.id
        self.assertEqual(pack_grandparent.u_package_depth, 2)

        # Add 4 level package to grandparent - 4 levels
        pack_parent_1.package_id = pack_grandparent.id
        self.assertEqual(pack_grandparent.u_package_depth, 4)

        # Create inner child
        pack_child_1_c = self.create_package()

        # Add a 5th level to grandparent as inner child
        with self.assertRaises(ValidationError) as e:
            pack_child_1_c.package_id = pack_child_1_a.id
            self.assertEqual(e.exception.name, 'Maximum package depth exceeded.')

    def test6_max_package_depth_violation_branch_middle(self):
        """Test Branching Maximum Package Depth Middle Insertion"""
        wh = self.env.user.get_user_warehouse()
        wh.u_max_package_depth = 4

        # Set up 3 level package
        pack_child_1_a = self.create_package()
        pack_child_1_b = self.create_package()
        pack_parent_1 = self.create_package()
        pack_child_1_a.package_id = pack_child_1_b.id
        pack_child_1_b.package_id = pack_parent_1.id

        # Set up grandparent package - 3 levels
        pack_parent_2 = self.create_package()
        pack_child_2 = self.create_package()
        pack_child_2.package_id = pack_parent_2.id
        pack_grandparent = self.create_package()
        pack_parent_2.package_id = pack_grandparent.id
        self.assertEqual(pack_grandparent.u_package_depth, 3)

        # Add 3 level package to grandparent
        pack_parent_1.package_id = pack_grandparent.id
        self.assertEqual(pack_grandparent.u_package_depth, 4)

        # Set up 2 level inner child
        pack_middle_child_a = self.create_package()
        pack_middle_child_b = self.create_package()
        pack_middle_child_a.package_id = pack_middle_child_b.id
        self.assertEqual(pack_middle_child_b.u_package_depth, 2)

        # Increase length of shorter chain middle child to create 5 level package
        with self.assertRaises(ValidationError) as e:
            pack_middle_child_b.package_id = pack_child_2.id
            self.assertEqual(e.exception.name, 'Maximum package depth exceeded.')

    def test7_max_package_depth_violation_branch_middle(self):
        """Test Adding Child Package To Parent Already Possessing Multiple Children"""
        wh = self.env.user.get_user_warehouse()
        wh.u_max_package_depth = 4

        # Set up 3 level package
        pack_child_1_a = self.create_package()
        pack_child_1_b = self.create_package()
        pack_parent_1 = self.create_package()
        pack_child_1_a.package_id = pack_child_1_b.id
        pack_child_1_b.package_id = pack_parent_1.id
        self.assertEqual(pack_parent_1.u_package_depth, 3)

        # Set up 4 level package
        pack_child_2_a = self.create_package()
        pack_child_2_b = self.create_package()
        pack_child_2_c = self.create_package()
        pack_parent_2 = self.create_package()
        pack_child_2_a.package_id = pack_child_2_b.id
        pack_child_2_b.package_id = pack_child_2_c.id
        pack_child_2_c.package_id = pack_parent_2.id
        self.assertEqual(pack_parent_2.u_package_depth, 4)

        # Set up grandparent package - 2 level grandparent
        pack_parent_3 = self.create_package()
        pack_grandparent = self.create_package()
        pack_parent_3.package_id = pack_grandparent.id
        self.assertEqual(pack_grandparent.u_package_depth, 2)

        # Add 3 level package to grandparent - 4 level grandparent
        pack_parent_1.package_id = pack_grandparent.id
        self.assertEqual(pack_grandparent.u_package_depth, 4)

        # Add 4 level package to grandparent - 5 level grandparent
        with self.assertRaises(ValidationError) as e:
            pack_parent_2.package_id = pack_grandparent.id
            self.assertEqual(e.exception.name, 'Maximum package depth exceeded.')
