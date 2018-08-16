# -*- coding: utf-8 -*-

import re
import time
import unittest
from ascii_graph import Pyasciigraph, colors
from collections import defaultdict
from functools import wraps
from parameterized import parameterized
from odoo.addons.udes_stock.tests import common
from odoo.exceptions import UserError
from odoo.tests.common import at_install, post_install


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


@at_install(False)
@post_install(True)
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

    def _report(self):
        """Make some nice ascii graphs"""
        graph = Pyasciigraph(
            min_graph_length=80,
            human_readable='si',
        )
        for func_name, res in sorted(self.results.items()):
            plot_data = []
            for key, vals in sorted(res.items()):
                plot_data.append((key ,sum(vals)/len(vals)))

            # Multiply by 1000 to stop truncation for quick calls
            lines = graph.graph(' %s/ms' % func_name[1],
                                [('Mean (N=%i)' % k, m * 1000)
                                for k, m in plot_data])
            for line in lines:
                print(line)



class BackgroundDataRunner(LoadRunner):
    _N = int(1e5)
    _dummy_picking_type = None

    @classmethod
    def setUpClass(cls):
        super(BackgroundDataRunner, cls).setUpClass()
        cls._dummy_picking_type = cls.picking_type_pick
        cls._dummy_background_data()

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
            print('Setting up background data (%0.2f' \
                  % (100*(i+1)/cls._N) + '%)', end='\r')

        child_locations.write({'location_id': full_location.id})
        full_location.write({'location_id': cls.stock_location.id})
        print('Assigning picks')
        pickings.action_assign()
        print('Complete')
