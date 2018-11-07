# -*- coding: utf-8 -*-
from datetime import time

from psycopg2 import IntegrityError

from odoo.tests import common
from odoo.tools import mute_logger


@common.at_install(False)
@common.post_install(True)
class TestDeliverySlot(common.SavepointCase):

    def test01_constraint(self):
        """Check constraints are enforced"""
        Slot = self.env['udes.delivery.slot']
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            Slot.create({'ref': '001', 'start_time': -1.0, 'end_time': 10.5})

    def test02_constraint(self):
        """Check constraints are enforced"""
        Slot = self.env['udes.delivery.slot']
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            Slot.create({'ref': '002', 'start_time': 10.0, 'end_time': 1.0})

    def test03_constraint(self):
        """Check constraints are enforced"""
        Slot = self.env['udes.delivery.slot']
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            Slot.create({'ref': '003', 'start_time': 12.0, 'end_time': 24.3})

    def test04_constraint(self):
        """Check constraints are enforced"""
        Slot = self.env['udes.delivery.slot']
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            Slot.create({'ref': '004', 'start_time': 24.0, 'end_time': 36.5})

    def test05_as_time(self):
        """Check the as_time() method returns correct times"""
        Slot = self.env['udes.delivery.slot']
        slot1 = Slot.create({'ref': '001', 'start_time': 09.50, 'end_time': 13.00})
        slot2 = Slot.create({'ref': '002', 'start_time': 0.00, 'end_time': 24.00})
        self.assertEqual(slot1.as_time(), (time(9, 30, 0, 0), time(13, 0, 0, 0)))
        self.assertEqual(slot2.as_time(), (time(0, 0, 0, 0), time.max))
