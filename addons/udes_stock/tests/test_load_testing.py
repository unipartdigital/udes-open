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


def merge_lines(lines, actions,
                graphsymbol='█',
                col_close='\x1b[0m',
                colour_regex='\\x1b\[\d?;?\d?\dm'):
    """Merges lines of the ascii graph
    for better presentation

    Lines will be merged in the order provided

    Actions: An iterable of values of len(lines)
        allowed values are:
        None: do nothing with the line
        'keep': the line whos ending you wish to keep
        'g': removes all but the last char of the line
        any other char: same as 'g' but replaces symbol
    """
    if not any('keep' in a for a in actions if a is not None):
        raise IndexError('Keep must be specifed in actions')

    if len(actions) < len(lines):
        raise ValueError('length of actions can not be less '
                         'than the lenght of lines')

    new_line = ''
    ending = ''
    replace_vals = []
    symbols = [graphsymbol, ' ']
    col_re = re.compile(colour_regex)

    def clean(dirty_line):
        """Remove colour tags from string"""
        return col_re.sub('', dirty_line)

    lenght = len(clean(lines[0])) # the expected length of the line

    for line, action in zip(lines, actions):
        reminant, _ending = line.split(maxsplit=1)
        if action is not None:
            if 'keep' in action:
                ending = _ending
                action = action.replace('keep', '')

            if len(action) > 0:
                if action == 'g':
                    action = graphsymbol

                replace_index = len(clean(reminant).strip())
                cols = col_re.findall(reminant)[:2]
                replace_vals.append((replace_index, action, cols))
                symbols.append(action)
                continue

        if len(new_line) == 0:
            new_line = reminant
            continue

        big_line = new_line
        small_line = reminant

        if len(clean(reminant)) > len(clean(new_line)):
            big_line = reminant
            small_line = new_line

        lenght_diff = len(clean(big_line)) - len(clean(small_line))
        # check if there are colours before removal
        cols = col_re.findall(big_line)[:2]
        big_line = clean(big_line)[:lenght_diff]
        if cols:
            big_line = cols[0] + big_line + cols[1]

        new_line = small_line + big_line

    # Add the ending we want to keep on the end
    lenght_diff = lenght - (len(clean(new_line)) + len(clean(ending)))
    new_line += (' ' * lenght_diff) + ending

    # Finds the index of the n apearance of a char
    # doing this to update replace index for added colours
    # spaces are there incase its longer than the bar
    for index, symbol, cols in replace_vals:
        real_index = [
            n for n, c in enumerate(new_line) if c in symbols
        ][index]

        if cols:
            pre_cols = col_re.findall(new_line[:real_index])

            if not len(pre_cols) % 2 == 0:
                symbol = col_close + cols[0] + symbol + cols[1] \
                    + pre_cols[-1]
            else:
                symbol = cols[0] + symbol + cols[1]

        new_line = new_line[:real_index-1] + symbol + new_line[real_index:]
    return new_line


def chunker(iterable, chunk_size=3):
    for i in range(0, len(iterable)//chunk_size):
        yield iterable[i*chunk_size: (i+1)*chunk_size]


def time_func(func):
    # attach an attribute to method
    if not hasattr(func, 'duration'):
        func.__dict__.update({'duration': [None]})

    @wraps(func)
    def _wrapper(self, *args, **kwargs):
        start = time.time()
        result = func(self, *args, **kwargs)
        func.duration[0] = (time.time() - start) * 1000
        return result
    return _wrapper


if not REQUIRED_MODULES: # Gets around dependacies not being there

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

            # Lets setup the warehouse required
            User = cls.env['res.users']
            user_warehouse = User.get_user_warehouse()

            # Get goods in type
            cls.picking_type_pick = user_warehouse.pick_type_id
            cls.picking_type_pick.active = True

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
            """ Process the durations of the functions
                into results
            """
            total = 0
            for i, f in enumerate(funcs):
                func_name = f.__name__.lstrip('time_')
                self.results[(i, func_name)][n].append(f.duration[0])
                self.write_line(func_name, n, f.duration[0])
                total += f.duration[0]

            self.write_line('total', n, total)
            self.results[(len(funcs), 'total')][n].append(total)
            self.write_line('=' * 80)

        def test_report(self):
            """Make some nice ascii graphs"""
            graph = Pyasciigraph(
                min_graph_length=80,
                human_readable='si',
            )
            for func_name, res in sorted(self.results.items()):
                stats = []
                for key, vals in sorted(res.items()):
                    _mean = sum(vals)/len(vals)
                    _min = min(vals)
                    _max = max(vals)

                    stats.append(('N=%i (min)' % key, _min))
                    stats.append(('N=%i (mean)' % key, _mean))
                    stats.append(('N=%i (max)' % key, _max))

                lines = graph.graph(' %s/ms' % func_name[1], stats)

                for line in lines[:2]:
                    print(line)

                for chunk in chunker(lines[2:], 3):
                    print(merge_lines(chunk, ('>', 'x', 'keep<')))

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


    @unittest.skipIf(REQUIRED_MODULES,
        'Please install modules %s to run load tests' % REQUIRED_MODULES)
    @at_install(False)
    @post_install(False)
    class TestPickLines(LoadRunner):

        @classmethod
        def setUpClass(cls):
            super(TestPickLines, cls).setUpClass()

            # Lets setup the warehouse required
            User = cls.env['res.users']
            user_warehouse = User.get_user_warehouse()

            cls.picking_type_pick.default_location_src_id = \
                cls.test_location_01.id

            cls.create_simple_outbound_route(
                cls.picking_type_pick, user_warehouse.out_type_id)

            # This is used to create the dummy background data
            cls._dummy_picking_type = cls.picking_type_pick

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

        # Printed things dont come out when using parameterized
        # hense test_report
        @parameterized.expand(sorted([(10,), (50,), (100,), (200,), (400,),
                                      (600,), (800,), (1000,), (1500,)] * 5))
        def test_load_test_picking(self, n):

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

    @unittest.skipIf(REQUIRED_MODULES,
        'Please install modules %s to run load tests' % REQUIRED_MODULES)
    @at_install(False)
    @post_install(False)
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


    # @unittest.skipIf(REQUIRED_MODULES,
    #     'Please install modules %s to run load tests' % REQUIRED_MODULES)
    # @at_install(False)
    # @post_install(False)
    # class TestPickLinesBackGroundData(TestPickLines):

    #     @classmethod
    #     def setUpClass(cls):
    #         super(TestPickLinesBackGroundData, cls).setUpClass()
    #         cls._dummy_background_data()


    # @unittest.skipIf(REQUIRED_MODULES,
    #     'Please install modules %s to run load tests' % REQUIRED_MODULES)
    # @at_install(False)
    # @post_install(False)
    # class TestPickMovesBackGroundData(TestPickMoves):

    #     @classmethod
    #     def setUpClass(cls):
    #         super(TestPickMovesBackGroundData, cls).setUpClass()
    #         cls._dummy_background_data()
