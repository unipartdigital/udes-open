from odoo.addons.udes_stock.tests import common
from odoo.addons.udes_stock import utils
from odoo import tools
from PIL import Image


class TestUtils(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestUtils, cls).setUpClass()

    def test_product_quantity_label(self):
        """
        In this test the product_quantity_label function is copied and tested,
        this is to ensure that any change made to it is intentional
        """

        product_label = utils.product_quantity_label(self.apple, 5)
        test_product_label = "{name} x {quantity}".format(name=self.apple.display_name, quantity=5)

        self.assertEqual(product_label, test_product_label)

    def test_package_product_quantity_label(self):
        """
        In this test the package_product_quantity_label function is copied and tested,
        this is to ensure that any change made to it is intentional
        """

        package_kwargs = {"name": "PACK001"}
        self.package1 = self.create_package(**package_kwargs)

        package_label = utils.package_product_quantity_label(self.package1, self.apple, 5)
        test_package_label = "{package} {product_quantity}".format(
            package=self.package1.name,
            product_quantity="{name} x {quantity}".format(name=self.apple.display_name, quantity=5),
        )

        self.assertEqual(package_label, test_package_label)

    def test_format_picking_data_for_display_list_component(self):
        """
        In this test the format_picking_data_for_display_list_component function
        is copied and tested, this is to ensure that any change made to it is intentional
        """
        Picking = self.env["stock.picking"]

        package_kwargs = {"name": "PACK001"}
        self.package1 = self.create_package(**package_kwargs)
        product_kwargs = {"package_id": self.package1.id}
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 50, **product_kwargs)
        self.create_quant(self.banana.id, self.test_stock_location_01.id, 50, **product_kwargs)
        pick = Picking.create_picking(
            picking_type=self.picking_type_pick,
            products_info=[
                {"product": self.apple, "uom_qty": 2},
                {"product": self.banana, "uom_qty": 4},
            ],
            assign=True,
        )

        order = True

        picking_details = utils.format_picking_data_for_display_list_component(pick)
        test_picking_details = []
        for package, package_lines in pick.move_line_ids.groupby("package_id", order):
            for product, product_lines in package_lines.groupby("product_id", order):
                test_picking_details.append(
                    utils.package_product_quantity_label(
                        package, product, int(sum(product_lines.mapped("product_uom_qty")))
                    )
                )

        self.assertEqual(picking_details, test_picking_details)

    def test_md_format_label_value(self):
        """
        Test md_format_label_value function returns a string with the correct value.
        This test is simple and is made to ensure that any change made to it is intentional
        """

        label = "quantity"
        value = "5"
        separator = ":"

        result = utils.md_format_label_value(label, value)
        test_result = f"**{label}{separator}** {value}\n"
        self.assertEqual(result, test_result)

        result = utils.md_format_label_value(label)
        test_result = f"**{label}**\n"
        self.assertEqual(result, test_result)

        result = utils.md_format_label_value("", value)
        test_result = f"{value}\n"
        self.assertEqual(result, test_result)

    def test_md_format_list_of_label_value(self):
        """
        Test md_format_list_of_label_value function returns a string with the correct value.
        This test is simple and is made to ensure that any change made to it is intentional
        """

        label = "quantity"
        value = "5"
        separator = ":"
        input_list = [{"label": label, "value": value}]

        result = utils.md_format_list_of_label_value(input_list)
        test_result = f"**{label}{separator}** {value}\n"

        self.assertEqual(result, test_result)

    def test_format_dict_for_display_list_component(self):
        """
        Test format_dict_for_display_list_component function returns a list with the correct values.
        This test is simple and is made to ensure that any change made to it is intentional
        """

        label = "quantity"
        value = "5"
        input_dict = {"label": label, "value": value}

        result = utils.format_dict_for_display_list_component(input_dict)
        test_result = ["**label**: " + label, "**value**: " + str(value)]
        self.assertEqual(result, test_result)

        input_dict = {"label": label, "value": False}

        result = utils.format_dict_for_display_list_component(input_dict)
        test_result = ["**label**: " + label, "**value**: None"]
        self.assertEqual(result, test_result)

    def test_product_image_uris(self):
        """Assert product_image_uris util function returns the expected results"""
        product = self.strawberry

        # Ensure result is False when no image is on the product
        result = utils.product_image_uris(product)
        self.assertFalse(result)

        # Make the product have an image
        base64_1920x1080_jpeg = tools.image_to_base64(Image.new("RGB", (1920, 1080)), "JPEG")
        self.strawberry.image_1920 = base64_1920x1080_jpeg

        # Ensure result is as expected
        result = utils.product_image_uris(product)
        self.assertTrue(result)
        self.assertEqual(result.get("small"), tools.image.image_data_uri(self.strawberry.image_128))
        self.assertEqual(
            result.get("medium"), tools.image.image_data_uri(self.strawberry.image_512)
        )
        self.assertEqual(
            result.get("large"), tools.image.image_data_uri(self.strawberry.image_1920)
        )
