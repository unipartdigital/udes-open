# -*- coding: utf-8 -*-

from odoo.addons.udes_stock.tests.common import BaseUDES


class PickingZoneTestCase(BaseUDES):
    def create_location(self, name, **kwargs):
        Location = self.env["stock.location"]

        vals = {"name": name, "location_id": self.test_location_01.id}
        vals.update(kwargs)
        return Location.create(vals)

    def test_get_picking_zone_self_is_zone(self):
        """
        Test that a location that is a picking zone returns itself when
        get_picking_zone() is called.
        """
        loc = self.create_location("picking_zone_test_location", u_is_picking_zone=True)
        self.assertEqual(loc.get_picking_zone(), loc)

    def test_get_picking_zone_a_parent_is_zone(self):
        """
        Test that when a parent location is a picking zone it is returned
        correctly.
        """
        loc = self.create_location("picking_zone_test_location")
        self.test_location_01.u_is_picking_zone = True
        self.assertEqual(loc.get_picking_zone(), self.test_location_01)

    def test_get_picking_zone_no_zone(self):
        """
        Test that when no parent location is a picking zone, an empty recordset
        is returned.
        """
        loc = self.create_location("picking_zone_test_location")
        self.assertFalse(loc.get_picking_zone())
