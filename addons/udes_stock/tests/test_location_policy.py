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
                        'Location %s cannot contain more than one product.'
                                % self.test_location_last_child_stock.name):
            self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)

    def test02_set_grandparent_location_policy(self):
        self.test_location_parent_stock.u_quant_policy = 'single_product_id'
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)

        with self.assertRaisesRegex(ValidationError,
                        'Location %s cannot contain more than one product.'
                                % self.test_location_last_child_stock.name):
            self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)
    
    def test03_set_direct_parent_location_policy(self):
        self.test_location_middle_child_stock.u_quant_policy = 'single_product_id'
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)

        with self.assertRaisesRegex(ValidationError,
                        'Location %s cannot contain more than one product.'
                                % self.test_location_last_child_stock.name):
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
                        'Location %s cannot contain more than one product.'
                                % self.test_location_last_child_stock.name):
            self.test_location_last_child_stock.location_id = \
                                    self.test_location_parent_stock.id

    def test06_change_location_policy(self):
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)
        with self.assertRaisesRegex(ValidationError,
                        'Location %s cannot contain more than one product.'
                                % self.test_location_last_child_stock.name):
            self.test_location_last_child_stock.u_quant_policy = \
                                                             'single_product_id'

    def test07_change_grandparent_location_policy(self):
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)
        with self.assertRaisesRegex(ValidationError,
                        'Location %s cannot contain more than one product.'
                                % self.test_location_last_child_stock.name):
            self.test_location_parent_stock.u_quant_policy = 'single_product_id'
    
    def test08_change_direct_parent_location_policy(self):
        self.create_quant(self.apple.id, self.test_location_last_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_last_child_stock.id,
        10)
        with self.assertRaisesRegex(ValidationError,
                        'Location %s cannot contain more than one product.'
                                % self.test_location_last_child_stock.name):
            self.test_location_middle_child_stock.u_quant_policy =\
                                                             'single_product_id'
    
    def test09_change_middle_child_grandparent_location_policy(self):
        self.create_quant(self.apple.id, self.test_location_middle_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_middle_child_stock.id,
        10)
        with self.assertRaisesRegex(ValidationError,
                        'Location %s cannot contain more than one product.'
                                % self.test_location_middle_child_stock.name):
            self.test_location_parent_stock.u_quant_policy = 'single_product_id'

    def test10_change_middle_child_direct_parent_location_policy(self):
        self.create_quant(self.apple.id, self.test_location_middle_child_stock.id,
        10)
        self.create_quant(self.fig.id, self.test_location_middle_child_stock.id,
        10)
        with self.assertRaisesRegex(ValidationError,
                        'Location %s cannot contain more than one product.'
                                % self.test_location_middle_child_stock.name):
            self.test_location_first_child_stock.u_quant_policy =\
                                                             'single_product_id'


class TestLocationPolicySingleLotAndProductPerPackage(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestLocationPolicySingleLotAndProductPerPackage, cls).setUpClass()
        Location = cls.env['stock.location']
        Package = cls.env['stock.quant.package']

        cls.test_location = Location.create({
                'name': "Test location",
                'barcode': "LTESTLOCATION",
                'location_id': cls.stock_location.id,
                'u_quant_policy': 'single_lot_id_single_product_id_per_package'
            })
        cls.test_package = Package.create({})

    def _create_lot_quant_in_package(self, product_id, lot_name=None):
        self.create_quant(
            product_id, self.test_location.id, 10,
            serial_number=lot_name, package_id=self.test_package.id)

    def test01_error_multiple_lots_in_package(self):
        self._create_lot_quant_in_package(self.tangerine.id, "TLOT01")
        with self.assertRaisesRegex(ValidationError,
                        'Package %s cannot contain more than one lot or product'
                                % self.test_package.name):
            self._create_lot_quant_in_package(self.tangerine.id, "TLOT02")

    def test012error_multiple_products_in_package(self):
        self._create_lot_quant_in_package(self.tangerine.id, "TLOT01")
        with self.assertRaisesRegex(ValidationError,
                        'Package %s cannot contain more than one lot or product'
                                % self.test_package.name):
            self._create_lot_quant_in_package(self.apple.id)
