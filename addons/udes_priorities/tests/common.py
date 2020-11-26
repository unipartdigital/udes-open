# -*- coding: utf-8 -*-

from odoo.addons.udes_stock.tests import common


class BasePriorities(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Priorities = cls.env["udes_priorities.priority"]
        (Priorities.search([]) - cls.env.ref("udes_priorities.normal")).write({"active": False})

        cls.urgent = Priorities.create(
            {
                "name": "urgent",
                "reference": "test_urgent",
                "sequence": 0,
                "description": "A priority which is urgent",
                "picking_type_ids": [(6, 0, cls.picking_type_pick.ids)],
            }
        )
        cls.normal = Priorities.create(
            {
                "name": "normal",
                "reference": "test_normal",
                "sequence": 1,
                "description": "A priority which is normal",
                "picking_type_ids": [(6, 0, cls.picking_type_internal.ids)],
            }
        )
        cls.not_urgent = Priorities.create(
            {
                "name": "not urgent",
                "reference": "test_not_urgent",
                "sequence": 2,
                "description": "A priority which is not urgent",
            }
        )

        cls.test_priorities = cls.urgent | cls.normal | cls.not_urgent
