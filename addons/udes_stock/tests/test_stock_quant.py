# -*- coding: utf-8 -*-

from . import common
from datetime import datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class TestStockQuant(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockQuant, cls).setUpClass()
        # Based on the tests in Odoo core
        # Default config is FIFO
        cls.Quant = cls.env["stock.quant"]

        # Create packages
        cls.pack1 = cls.create_package(name="test_package_one")
        cls.pack2 = cls.create_package(name="test_package_two")
        cls.pack3 = cls.create_package(name="test_package_three")

        # Create three quants in the same location
        cls.quant1 = cls.create_quant(cls.apple.id, cls.test_location_01.id, 1.0)
        cls.quant2 = cls.create_quant(cls.apple.id, cls.test_location_01.id, 1.0)
        cls.quant3 = cls.create_quant(cls.apple.id, cls.test_location_01.id, 1.0)

    def test_fifo_without_nones(self):
        """Check that the FIFO strategies are correctly applied"""
        # Give each quant a package_id and in_date
        oldest_time = datetime.now() - timedelta(days=5)
        self.quant1.write({"package_id": self.pack1.id, "in_date": datetime.now()})
        self.quant2.write({"package_id": self.pack2.id, "in_date": oldest_time})
        self.quant3.write({"package_id": self.pack3.id, "in_date": oldest_time})

        # Reserve quantity - one apple
        reserved_quants = self.Quant._update_reserved_quantity(self.apple, self.test_location_01, 1)
        reserved_quant = reserved_quants[0][0]

        # Should choose between quant2 and quant3 based on `in_date`
        # Choose quant2 as it has a package_id
        self.assertEqual(
            reserved_quant.in_date, oldest_time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        )
        self.assertEqual(reserved_quant.package_id, self.pack2)
        self.assertEqual(reserved_quant, self.quant2)

    def test_in_date_ordered_first_in_fifo(self):
        """Check that the FIFO strategies correctly applies when you have populated `in_date` fields
        and None for `package_id` fields.
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
        reserved_quants = self.Quant._update_reserved_quantity(self.apple, self.test_location_01, 1)
        reserved_quant = reserved_quants[0][0]

        self.assertEqual(
            reserved_quant.in_date, oldest_time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        )
        self.assertEqual(reserved_quant.package_id, self.pack2)
        self.assertEqual(reserved_quant, self.quant2)

    def test_fifo_with_nones(self):
        """Check that the FIFO strategies correctly applies when you have unpopulated `in_date` 
        and `package_id` fields.

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
        reserved_quants = self.Quant._update_reserved_quantity(self.apple, self.test_location_01, 1)
        reserved_quant = reserved_quants[0][0]

        self.assertFalse(reserved_quant.in_date)
        self.assertFalse(reserved_quant.package_id)
        self.assertEqual(reserved_quant, self.quant2)
