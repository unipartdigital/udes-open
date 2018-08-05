# -*- coding: utf-8 -*-

from . import common
from odoo.exceptions import UserError
from odoo.tests.common import at_install, post_install
from functools import wraps
import unittest
import time
from collections import defaultdict
import re

_HAS_PARAMETERIZED = True
try:
    from parameterized import parameterized
except ImportError:
    _HAS_PARAMETERIZED = False

    # Gets around dependacies not being there during eval
    class _dummy_parameterized(object):

        @staticmethod
        def expand(*args, **kwargs):
            def dummy_wrapper(func):
                return func
            return dummy_wrapper

    parameterized = _dummy_parameterized()

_HAS_GRAPH = True
try:
    from ascii_graph import Pyasciigraph, colors
except ImportError:
    _HAS_GRAPH = False

REQUIRED_MODULES = ", ".join(
    name for name, installed in (
        ('parameterized', _HAS_PARAMETERIZED),
        ('ascii_graph', _HAS_GRAPH),
    ) if not installed
)


def time_func(func):
    # attach an attribute to method
    if not hasattr(func, 'duration'):
        func.__dict__.update({'duration': [None]})

    @wraps(func)
    def _wrapper(self, *args, **kwargs):
        start = time.time()
        result = func(self, *args, **kwargs)
        func.duration[0] = (time.time() - start)
        return result
    return _wrapper


@unittest.skipIf(REQUIRED_MODULES,
                 'Please install modules %s to run load tests' % REQUIRED_MODULES)
@at_install(False)
@post_install(False)
class LoadRunner(common.BaseUDES):

    results = defaultdict(lambda: defaultdict(list))
    _N = 1000
    _fw = None

    def __getattribute__(self, attr_name):
        attr = super(LoadRunner, self).__getattribute__(attr_name)
        if "time_" in attr_name and not hasattr(attr, '__wrapped__'):
            # if it isnt wrapped wrap it
            # then set attr as the wrapped version
            attr = time_func(attr)
            setattr(self, attr_name, attr)

        return attr

    @classmethod
    def setUpClass(cls):
        super(LoadRunner, cls).setUpClass()
        if 'Test' not in cls.__name__:
            return None

        # This is used to create the dummy background data
        cls._dummy_picking_type = cls.picking_type_pick

        # Setup file
        filename = '%s_times.txt' % cls.__name__.lstrip('Test')
        try:
            cls._fw = open(filename, 'a')
        except IOError:
            cls._fw = open(filename, 'w')

    def tearDown(self):
        super(LoadRunner, self).tearDown()
        if self._fw:
            self._fw.flush()

    @classmethod
    def tearDownClass(cls):
        super(LoadRunner, cls).tearDownClass()
        if cls._fw:
            cls._fw.close()

    def write_line(self, *args):
        self._fw.write('\t'.join(map(str, args))+'\n')

    def _process_results(self, n, *funcs):
        """ Process the durations of the functions into results"""
        total = 0
        for i, f in enumerate(funcs):
            func_name = f.__name__.lstrip('time_')
            self.results[(i, func_name)][n].append(f.duration[0])
            self.write_line(func_name, n, f.duration[0])
            total += f.duration[0]

        self.write_line('total', n, total)
        self.results[(len(funcs), 'total')][n].append(total)

    def test_report(self):
        """Make some nice ascii graphs"""
        graph = Pyasciigraph(
            min_graph_length=80,
            human_readable='si',
        )
        for func_name, res in sorted(self.results.items()):
            means = []
            for vals in sorted(res.values()):
                means.append(sum(vals)/len(vals))

            # Multiply by 1000 to stop truncation for quick calls
            lines = graph.graph(' %s/ms' % func_name[1],
                                [('Mean', m * 1000) for m in means])
            for line in lines:
                print(line)

    @classmethod
    def _dummy_background_data(cls):
        """Create some dummy background data"""
        Location = cls.env['stock.location']
        Package = cls.env['stock.quant.package']
        Picking = cls.env['stock.picking']

        full_location = Location.create({
            'name': 'TEST DUMMY LOCATION',
            'barcode': 'LTESTDUMMY',
        })

        child_locations = Location.browse()
        pickings = Picking.browse()

        for i in range(cls._N):
            loc = Location.create({
                'name': 'TEST DUMMY LOCATION %0.4i' % i,
                'barcode': 'LTESTDUMMY%0.4i' % i,
            })
            child_locations |= loc

            prod = cls.create_product('DUMMY%0.4i' % i)

            pack = Package.get_package(
                'TEST_DUMMY_%0.4i' % i, create=True
            )

            cls.create_quant(
                product_id=prod.id,
                location_id=loc.id,
                qty=100,
                package_id=pack.id
            )

            pick = cls.create_picking(
                picking_type=cls._dummy_picking_type,
                origin="TEST_DUMMY_origin_%0.4i" % i,
                products_info=[{'product': prod, 'qty': 100}],
            )
            pickings |= pick

        child_locations.write({'location_id': full_location.id})
        full_location.write({'location_id': cls.stock_location.id})
        pickings.action_assign()


class TestPickLines(LoadRunner):

    def time_setup(self, n):
        Package = self.env['stock.quant.package']
        packages = []

        for i in range(n):
            packages.append(
                Package.get_package(
                    "test_package_%i" % i, create=True)
            )

            self.create_quant(
                product_id=self.apple.id,
                location_id=self.test_location_01.id,
                qty=100,
                package_id=packages[-1].id
            )

        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            origin="test_pick_origin_%i" % i,
            products_info=[{'product': self.apple, 'qty': 100*n}],
        )
        return pick, packages

    def time_assign(self, pick):
        pick.action_assign()

    def time_confirm(self, pick):
        pick.action_confirm()

    def time_validate_lines(self, pick, packages):
        for package in packages:
            pick.update_picking(
                package_name=package.name,
                location_dest_id=self.test_location_02.id
            )

    def time_validate_pick(self, pick):
        pick.update_picking(validate=True)

    # Printed things dont come out when using parameterized hence test_report
    @parameterized.expand(sorted([(100,), (500,), (1000,), (1200,),
                                  (1400,), (1500,)] * 5))
    def test_load_test_picking(self, n):
        """ Runs each of the timed steps then passes them to a result
        processing function along with the identifying parameters
        """

        pick, packages = self.time_setup(n)
        self.time_confirm(pick)
        self.time_assign(pick)
        self.time_validate_lines(pick, packages)
        self.time_validate_pick(pick)

        self._process_results(
            n,
            self.time_setup,
            self.time_confirm,
            self.time_assign,
            self.time_validate_lines,
            self.time_validate_pick,
        )


class TestPickMoves(TestPickLines):

    def time_setup(self, n):
        Package = self.env['stock.quant.package']
        packages = []
        product_info = []

        for i in range(n):
            packages.append(
                Package.get_package(
                    "test_package_%i" % i, create=True)
            )

            new_prod = self.apple.copy()

            self.create_quant(
                product_id=new_prod.id,
                location_id=self.test_location_01.id,
                qty=100,
                package_id=packages[-1].id
            )

            product_info.append({'product': new_prod, 'qty': 100})

        pick = self.create_picking(
            picking_type=self.picking_type_pick,
            origin="test_pick_origin_%i" % i,
            products_info=product_info,
        )
        return pick, packages


class TestPickLinesBackGroundData(TestPickLines):

    @classmethod
    def setUpClass(cls):
        super(TestPickLinesBackGroundData, cls).setUpClass()
        cls._dummy_background_data()


class TestPickMovesBackGroundData(TestPickMoves):

    @classmethod
    def setUpClass(cls):
        super(TestPickMovesBackGroundData, cls).setUpClass()
        cls._dummy_background_data()
