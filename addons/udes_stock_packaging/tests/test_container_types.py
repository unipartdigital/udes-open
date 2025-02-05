"""Tests for container types."""

from odoo.exceptions import ValidationError
from psycopg2.errors import UniqueViolation
from odoo.tools.misc import mute_logger
from odoo.addons.udes_stock.tests import common


class ContainerTypeTestCase(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ContainerType = cls.env["container.type"]
        cls.base_attrs = {"length": 1.09, "width": 2.12, "height": 3.03, "weight": 0.3}

    def test_container_type_unique_name_create(self):
        """
        Ensure users can not create a container type with a non-unique name.
        """
        c1_vals = {"name": "C1"}
        self.ContainerType.create(self.base_attrs | c1_vals)
        # Can't create with duplicate name
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            self.ContainerType.create(self.base_attrs | c1_vals)

    def test_can_not_input_negative_physical_attributes(self):
        """
        Ensure any physical attributes can not be entered as negative values
        """
        for non_negative_fieldname in self.base_attrs.keys():
            with self.subTest(non_negative_fieldname=non_negative_fieldname):
                with self.assertRaises(ValidationError) as single_write_exception:
                    # Use the field name to get a unique name, so we don't hit the unique name constraint.
                    # Create a container with a negative value for each of the physical attributes
                    # in self.base_attrs
                    self.ContainerType.create(
                        self.base_attrs
                        | {"name": non_negative_fieldname, non_negative_fieldname: -0.01}
                    )
                self.assertEqual(
                    "Dimensions and weight must be positive values. %s have physical attributes which are less than 0."
                    % non_negative_fieldname,
                    single_write_exception.exception.args[0],
                )
        # Ensure writing to multiple at the same time raises too
        c1 = self.ContainerType.create(self.base_attrs | {"name": "C1"})
        c2 = self.ContainerType.create(self.base_attrs | {"name": "C2"})
        with self.assertRaises(ValidationError) as multi_write_exception:
            (c1 | c2).write({"length": -0.01})
        self.assertEqual(
            "Dimensions and weight must be positive values. C1, C2 have physical attributes which are less than 0.",
            multi_write_exception.exception.args[0],
        )

    def test_container_type_get_info(self):
        c1 = self.ContainerType.create(self.base_attrs | {"name": "C1"})
        get_info_result = c1.get_info()
        expected_get_info = [
            {
                "length": 1.09,
                "width": 2.12,
                "height": 3.03,
                "weight": 0.3,
                "display_name": "C1",
                "name": "C1",
                "id": c1.id,
            }
        ]
        self.assertEqual(get_info_result, expected_get_info)
