from . import common
from odoo.exceptions import ValidationError

class TestLocationPolicy(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestLocationPolicy, cls).setUpClass()
        Location = cls.env['stock.location']

        cls.test_location_parent_stock = Location.create({
                'name': "Test location parent stock",
                'barcode': "LTESTP",
                'location_id': cls.stock_location.id,
                'usage': 'view'
            })
        cls.test_location_first_child_stock = Location.create({
                'name': "Test location middle child stock",
                'barcode': "LTESTF",
                'location_id': cls.test_location_parent_stock.id,
            })
        cls.test_location_middle_child_stock = Location.create({
                'name': "Test location middle child stock",
                'barcode': "LTESTM",
                'location_id': cls.test_location_first_child_stock.id,
            })
        cls.test_location_last_child_stock = Location.create({
                'name': "Test location last child stock",
                'barcode': "LTESTL",
                'location_id': cls.test_location_middle_child_stock.id,
            })

    def test01_set_location_policy(self):
        self.test_location_last_child_stock.u_quant_policy = 'single_product_id'
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)

        with self.assertRaisesRegex(ValidationError,
                        'Pick locations cannot contain more than one product.'):
            self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)

    def test02_set_grandparent_location_policy(self):
        self.test_location_parent_stock.u_quant_policy = 'single_product_id'
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)

        with self.assertRaisesRegex(ValidationError,
                        'Pick locations cannot contain more than one product.'):
            self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)
    
    def test03_set_direct_parent_location_policy(self):
        self.test_location_middle_child_stock.u_quant_policy = 'single_product_id'
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)

        with self.assertRaisesRegex(ValidationError,
                        'Pick locations cannot contain more than one product.'):
            self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)

    def test04_grandparent_parent_different_location_policy(self):
        self.test_location_middle_child_stock.u_quant_policy = 'all'
        self.test_location_parent_stock.u_quant_policy = 'single_product_id'
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)

    def test05_switch_to_parent_with_different_location_policy(self):
        self.test_location_middle_child_stock.u_quant_policy = 'all'
        self.test_location_parent_stock.u_quant_policy = 'single_product_id'
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)

        with self.assertRaisesRegex(ValidationError,
                        'Pick locations cannot contain more than one product.'):
            self.test_location_last_child_stock.location_id = \
                                    self.test_location_parent_stock.id

    def test06_change_location_policy(self):
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)
        with self.assertRaisesRegex(ValidationError,
                        'Pick locations cannot contain more than one product.'):
            self.test_location_last_child_stock.u_quant_policy = \
                                                             'single_product_id'

    def test07_change_grandparent_location_policy(self):
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)
        with self.assertRaisesRegex(ValidationError,
                        'Pick locations cannot contain more than one product.'):
            self.test_location_parent_stock.u_quant_policy = 'single_product_id'
    
    def test08_change_direct_parent_location_policy(self):
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)
        with self.assertRaisesRegex(ValidationError,
                        'Pick locations cannot contain more than one product.'):
            self.test_location_middle_child_stock.u_quant_policy =\
                                                             'single_product_id'
    
    def test09_change_middle_child_grandparent_location_policy(self):
        self.create_quant(self.apple.id, self.test_location_middle_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_middle_child_stock.id,
        10)
        with self.assertRaisesRegex(ValidationError,
                        'Pick locations cannot contain more than one product.'):
            self.test_location_parent_stock.u_quant_policy = 'single_product_id'

    def test10_change_middle_child_direct_parent_location_policy(self):
        self.create_quant(self.apple.id, self.test_location_middle_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_middle_child_stock.id,
        10)
        with self.assertRaisesRegex(ValidationError,
                        'Pick locations cannot contain more than one product.'):
            self.test_location_first_child_stock.u_quant_policy =\
                                                             'single_product_id'
