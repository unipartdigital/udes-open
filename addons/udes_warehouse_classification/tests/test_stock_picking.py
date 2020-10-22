from .common import Base


class TestWarehouseClassificationPicking(Base):
    """
        # Products for pickings types defining test cases:
        # 1. picking in - damson,
        # 2. picking in with non-inbound classification product - grape
        # 3. picking out with an additional non-outbound classification product - grape+banana,
        # 4. picking in - 2 alerts on one product - elderberry,
        # 5. picking in - 2 products with alert classifications on 1 picking - banana+damson,
        # 6. picking in and out - fig
        # 7. picking in - reordering of 2 alert classifications on one product - elderberry
        # 8. picking with no alerts - apple
    """

    @classmethod
    def create_picking_in(cls, products_info):
        return cls.create_picking(
            cls.picking_type_in,
            origin="test_picking_in",
            products_info=products_info,
            confirm=True,
        )

    @classmethod
    def create_picking_out(cls, products_info):
        return cls.create_picking(
            cls.picking_type_out,
            origin="test_picking_out",
            products_info=products_info,
            confirm=True,
        )

    def test01_basic_in_alert(self):
        test_picking_in = self.create_picking_in(products_info=[{"product": self.damson, "qty": 1}])
        messages = test_picking_in._get_classification_messages_for_product_picking()
        test_messages = {"productDamson": [{"message": "Inbound Alert"}]}
        self.assertEqual(messages, test_messages)

    def test02_non_in_alert(self):
        test_picking_in = self.create_picking_in(products_info=[{"product": self.grape, "qty": 2},])
        messages = test_picking_in._get_classification_messages_for_product_picking()
        test_messages = {"productGrape": []}
        self.assertEqual(messages, test_messages)

    def test03_out_and_non_out_alerts(self):
        test_picking_out = self.create_picking_out(
            products_info=[{"product": self.banana, "qty": 1}, {"product": self.grape, "qty": 2},]
        )
        messages = test_picking_out._get_classification_messages_for_product_picking()
        test_messages = {"productBanana": [], "productGrape": [{"message": "Outbound Alert"}]}
        self.assertEqual(messages, test_messages)

    def test04_in_two_alerts_one_product(self):
        test_picking_in = self.create_picking_in(
            products_info=[{"product": self.elderberry, "qty": 1}]
        )
        messages = test_picking_in._get_classification_messages_for_product_picking()
        test_messages = {
            "productElderberry": [
                {"message": "Inbound Alert"},
                {"message": "Inbound, Report a, Alert"},
            ]
        }
        self.assertEqual(messages, test_messages)

    def test05_in_two_products_with_alerts(self):
        test_picking_in = self.create_picking_in(
            products_info=[{"product": self.banana, "qty": 1}, {"product": self.damson, "qty": 2},]
        )
        messages = test_picking_in._get_classification_messages_for_product_picking()
        test_messages = {
            "productBanana": [{"message": "Inbound, Report a, Alert"}],
            "productDamson": [{"message": "Inbound Alert"}],
        }
        self.assertEqual(messages, test_messages)

    def test06_in_and_out(self):
        test_picking_in = self.create_picking_in(products_info=[{"product": self.fig, "qty": 1}])
        test_picking_out = self.create_picking_out(products_info=[{"product": self.fig, "qty": 1}])
        messages_in = test_picking_in._get_classification_messages_for_product_picking()
        messages_out = test_picking_out._get_classification_messages_for_product_picking()
        test_messages_in = {"productFig": [{"message": "Inbound Alert"}]}
        test_messages_out = {"productFig": [{"message": "Outbound Alert"}]}
        self.assertEqual(messages_in, test_messages_in)
        self.assertEqual(messages_out, test_messages_out)

    def test07_reordered_messages(self):
        test_picking_in = self.create_picking_in(
            products_info=[{"product": self.elderberry, "qty": 1}]
        )
        Classification = self.env["product.warehouse.classification"]
        inbound_alert = Classification.search([("name", "=", "inbound_alert")])
        inbound_alert.sequence = 2
        messages = test_picking_in._get_classification_messages_for_product_picking()
        test_messages = {
            "productElderberry": [
                {"message": "Inbound, Report a, Alert"},
                {"message": "Inbound Alert"},
            ]
        }
        self.assertEqual(messages, test_messages)

    def test08_no_classifications(self):
        test_picking_in = self.create_picking_in(products_info=[{"product": self.apple, "qty": 1}])
        messages = test_picking_in._get_classification_messages_for_product_picking()
        test_messages = {"productApple": []}
        self.assertEqual(messages, test_messages)
