# -*- coding: utf-8 -*-
from .common import BaseUDES
from datetime import datetime, timedelta


class TestStockQuantModel(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockQuantModel, cls).setUpClass()
        cls.Quant = cls.env["stock.quant"]
        cls.test_package = cls.create_package()
        cls.test_package2 = cls.create_package()
        cls.quantA = cls.create_quant(
            cls.apple.id, cls.test_stock_location_01.id, 10, package_id=cls.test_package.id
        )
        cls.create_quant(
            cls.apple.id, cls.test_stock_location_01.id, 5, package_id=cls.test_package.id
        )

        cls.create_quant(
            cls.apple.id, cls.test_stock_location_01.id, 1, package_id=cls.test_package.id
        )

        cls.create_quant(
            cls.banana.id, cls.test_stock_location_01.id, 10, package_id=cls.test_package.id
        )

        cls.create_quant(
            cls.banana.id, cls.test_stock_location_02.id, 10, package_id=cls.test_package2.id
        )
        # Total Apples = 11
        # reserved = 0
        # Total Bananas = 20
        # reserved = 0

    def test01_get_quantity(self):
        """ Test get_quantity """
        self.assertEqual(self.test_stock_location_01.quant_ids.get_quantity(), 26)

    def test02_get_quantities_by_key(self):
        """ Test get_quantities_by_key """
        self.assertEqual(
            {self.apple: 16, self.banana: 10},
            self.test_stock_location_01.quant_ids.get_quantities_by_key(),
        )
        # group by non-product_ids: test name
        self.assertEqual(
            {self.apple.name: 16, self.banana.name: 10},
            self.test_stock_location_01.quant_ids.get_quantities_by_key(
                get_key=lambda q: q.product_id.name
            ),
        )
        # Group by name, and only available (not-reserved) quantities
        # Still should return 16 and 10
        self.assertEqual(
            {self.apple.name: 16, self.banana.name: 10},
            self.test_stock_location_01.quant_ids.get_quantities_by_key(
                get_key=lambda q: q.product_id.name, only_available=True
            ),
        )
        # Reserve 5 apples
        self.quantA.reserved_quantity = 5
        # Group by name, and only available (not-reserved) quantities
        self.assertEqual(
            {self.apple.name: 11, self.banana.name: 10},
            self.test_stock_location_01.quant_ids.get_quantities_by_key(
                get_key=lambda q: q.product_id.name, only_available=True
            ),
        )

    def test03_gather_success(self):
        """ Test extended _gather function """
        gathered_items = self.Quant._gather(self.apple, self.test_stock_location_01)
        # Check the number of apple quants returned is correct
        self.assertEqual(len(gathered_items), 3)
        # Check that the products are all of expected type
        self.assertEqual(gathered_items.product_id, self.apple)

        # Unfold the returned quants
        _q1, second_quant, _q2 = gathered_items
        # Check when quant_ids is set in the context
        gathered_items_subset = self.Quant.with_context(quant_ids=[second_quant.id])._gather(
            self.apple, self.test_stock_location_01
        )
        self.assertEqual(len(gathered_items_subset), 1)
        self.assertEqual(gathered_items_subset.product_id, self.apple)
        self.assertEqual(gathered_items_subset, second_quant)

    def test04_gather_location_no_product(self):
        """ Test extended _gather function on a location without apples """
        gathered_items = self.Quant._gather(self.apple, self.test_stock_location_02)
        # Check the number of apple quants returned is correct
        self.assertFalse(len(gathered_items))


class TestCreatePicking(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestCreatePicking, cls).setUpClass()

        cls.quant_1 = cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)
        cls.quant_2 = cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 10)

        cls.test_user = cls.create_user("test_user", "test_user_login")

    def test01_single_quant(self):
        """ Create a picking from a single quant """
        pick = self.quant_1.create_picking(self.picking_type_pick)
        # Confirm made in state draft
        self.assertEqual(pick.state, "draft")
        # Confirm quant location used if non specified
        self.assertEqual(pick.location_id, self.test_stock_location_01)
        # Confirm default dest location used if non specified
        self.assertEqual(pick.location_dest_id, self.picking_type_pick.default_location_dest_id)
        # Confirm correct picking type id associated
        self.assertEqual(pick.picking_type_id, self.picking_type_pick)
        # Check default priority is 1 = 'Normal'
        self.assertEqual(pick.priority, "1")
        #  Check picking has correct products associated to it
        self.assertEqual(pick.product_id, self.apple)
        #  Check picking has correct quantities associated to it
        self.assertEqual(pick.move_lines.product_id, self.apple)
        self.assertEqual(pick.move_lines.product_qty, 10)

    def test02_single_quant_confirm(self):
        """ Create a picking from a single quant and confirm """
        pick = self.quant_1.create_picking(self.picking_type_pick, confirm=True)
        # Check it is confirmed
        self.assertEqual(pick.state, "confirmed")

    def test03_single_quant_assign(self):
        """ Create a picking from a single quant and assign to user """
        pick = self.quant_1.create_picking(
            self.picking_type_pick, assign=True, user_id=self.test_user.id
        )
        # Check it is in state assigned
        self.assertEqual(pick.state, "assigned")
        # Check user is assigned
        self.assertEqual(pick.user_id, self.test_user)
        # Check quant_1 is now reserved
        self.assertEqual(self.quant_1.reserved_quantity, 10)

    def test04_single_quant_assign_correct_quant(self):
        """ Test that create_picking uses the right quant when assigning
            the picking
        """
        Quant = self.env["stock.quant"]

        # Create a bunch of identical quants in the same location
        quants = Quant.browse()
        for i in range(5):
            quants |= self.create_quant(self.apple.id, self.test_stock_location_01.id, 10)
        self.assertEqual(len(quants), 5)

        quant = quants[2]
        pick = quant.create_picking(self.picking_type_pick, confirm=True, assign=True)
        self.assertEqual(pick.state, "assigned")
        self.assertEqual(quant.reserved_quantity, 10)

    def test05_single_quant_priority(self):
        """ Create a picking from a single quant
            Change the priority to Urgent
            Priorities: [('0', 'Not urgent'), ('1', 'Normal'), ('2', 'Urgent'), ('3', 'Very Urgent')]
        """
        pick = self.quant_1.create_picking(self.picking_type_pick, priority="2")
        # Check priority is 2 = 'Urgent'
        self.assertEqual(pick.priority, "2")

    def test06_single_quant_non_default_locations(self):
        """ Create a picking from a single quant
            - non-default location_id
            - non-default location_dest_id
        """
        pick = self.quant_1.create_picking(
            self.picking_type_pick,
            location_id=self.test_stock_location_01.id,
            location_dest_id=self.test_goodsout_location_02.id,
        )
        # Confirm default location used if non specified
        self.assertEqual(pick.location_id, self.test_stock_location_01)
        self.assertNotEqual(pick.location_id, self.picking_type_pick.default_location_src_id)
        # Confirm default dest location used if non specified
        self.assertEqual(pick.location_dest_id, self.test_goodsout_location_02)
        self.assertNotEqual(pick.location_id, self.picking_type_pick.default_location_dest_id)

    def test07_multiple_quants(self):
        """ Multiple quants for pick """
        # Get all quants in test package
        quants = self.quant_1 | self.quant_2
        pick = quants.create_picking(self.picking_type_pick)
        # Check picking has correct location
        self.assertEqual(pick.location_id, self.stock_location)
        #  Check picking has correct products and quantities associated to it
        self.assertEqual(pick.move_lines.product_id, quants.product_id)
        self.assertEqual(pick.move_lines.mapped("product_qty"), [10.0, 10.0])


class TestStockQuantFIFO(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockQuantFIFO, cls).setUpClass()
        # Based on the tests in Odoo core
        cls.Quant = cls.env["stock.quant"]

        # Create packages
        cls.pack1 = cls.create_package(name="test_package_one")
        cls.pack2 = cls.create_package(name="test_package_two")
        cls.pack3 = cls.create_package(name="test_package_three")

        # Create three quants in the same location
        cls.quant1 = cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 1.0)
        cls.quant2 = cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 1.0)
        cls.quant3 = cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 1.0)

    def test_fifo_without_nones(self):
        """Check that the FIFO strategies are correctly applied"""
        # Give each quant a package_id and in_date
        oldest_time = datetime.now() - timedelta(days=5)
        self.quant1.write({"package_id": self.pack1.id, "in_date": datetime.now()})
        self.quant2.write({"package_id": self.pack2.id, "in_date": oldest_time})
        self.quant3.write({"package_id": self.pack3.id, "in_date": oldest_time})

        # Reserve quantity - one apple
        reserved_quants = self.Quant._update_reserved_quantity(
            self.apple, self.test_stock_location_01, 1
        )
        reserved_quant = reserved_quants[0][0]

        # Should choose between quant2 and quant3 based on `in_date`
        # Choose quant2 as it has a package_id
        self.assertEqual(reserved_quant.in_date, oldest_time)
        self.assertEqual(reserved_quant.package_id, self.pack2)
        self.assertEqual(reserved_quant, self.quant2)

    def test_in_date_ordered_first_in_fifo(self):
        """Check that the FIFO strategies correctly applies when you have populated `in_date`
        fields and None for `package_id` fields.
        Setup:
               |   in_date  |  package_id |
        quant1 |    middle  |     None    |
        quant2 |    oldest  |   pack2.id  |
        quant3 |    recent  |     None    |

        It should order_by `in_date` first, then `package_id`, so the fact package_id's are None
        for both quant1 and quant3 should have no impact.
        """
        # Populate all `in_date` fields, with quant2 being the oldest
        # Set the `package_id` only for quant2
        oldest_time = datetime.now() - timedelta(days=5)
        self.quant1.write({"in_date": datetime.now()})
        self.quant2.write({"package_id": self.pack2.id, "in_date": oldest_time})
        self.quant3.write({"in_date": datetime.now() - timedelta(days=3)})

        # Reserve quantity - one apple
        reserved_quants = self.Quant._update_reserved_quantity(
            self.apple, self.test_stock_location_01, 1
        )
        reserved_quant = reserved_quants[0][0]

        self.assertEqual(reserved_quant.in_date, oldest_time)
        self.assertEqual(reserved_quant.package_id, self.pack2)
        self.assertEqual(reserved_quant, self.quant2)

    def test_fifo_with_nones(self):
        """Check that the FIFO strategies correctly applies when you have unpopulated `in_date`
        and `package_id` fields.
        Setup:
               |   in_date   |  package_id |
        quant1 |     None    |   pack1.id  |
        quant2 |     None    |      None   |
        quant3 |     Now()   |   pack3.id  |

        First, it should filter by `in_date` and return NULLS first => quant1 and quant2
        Should then filter by `package_id` and return NULLS first => quant2
        """
        # Leave quant1, quant 2 with `in_date: False`
        # Leave quant 2 with no package, set quant1 and quant2 packages.
        self.quant1.write({"package_id": self.pack1.id})
        self.quant3.write({"package_id": self.pack3.id, "in_date": datetime.now()})

        # Reserve quantity - one apple
        reserved_quants = self.Quant._update_reserved_quantity(
            self.apple, self.test_stock_location_01, 1
        )
        reserved_quant = reserved_quants[0][0]

        self.assertFalse(reserved_quant.in_date)
        self.assertFalse(reserved_quant.package_id)
        self.assertEqual(reserved_quant, self.quant2)
