# -*- coding: utf-8 -*-

from .common import LoadRunner, parameterized
from .config import config


class OutboundLines(LoadRunner):

    xlabel = 'Number of MoveLines'

    @classmethod
    def _setup_3step_outbound_route(cls, pt_pick, pt_check):
        Route = cls.env['stock.location.route']
        Path = cls.env['stock.location.path']
        Sequence = cls.env['ir.sequence']

        # Check
        sequence_vals = {
            "name": "TestCheck",
            "prefix": "TESTCHECK",
            "padding": 9,
        }
        sequence_check = Sequence.create(sequence_vals)

        check_vals = {
            'sequence_id': sequence_check.id,
            'sequence': 12,
        }
        pt_check.write(check_vals)

        route = Route.search([
            ('name', '=', 'TestGoodsOut'),
        ])
        location_path_vals = {
            "name": "TestCheck",
            "route_id": route.id,
            "sequence": 10,
            "location_from_id": pt_pick.default_location_dest_id.id,
            "location_dest_id": pt_check.default_location_dest_id.id,
            "picking_type_id": pt_check.id,
        }
        path_out_check = Path.create(location_path_vals)

        #update check goods out path
        out_path = Path.search([
            ('name', '=', 'TestGoodsOut'),
        ])
        out_path.location_from_id = pt_check.default_location_dest_id

    @classmethod
    def setUpClass(cls):
        super(OutboundLines, cls).setUpClass()

        cls._setup_check_location()
        cls.picking_type_pick.default_location_dest_id = \
            cls.test_check_location_01

        cls.picking_type_check = cls.picking_type_pick.copy({
            'name': 'TEST_CHECK',
            'default_location_src_id':
                cls.picking_type_pick.default_location_dest_id.id,
            'default_location_dest_id':
                cls.picking_type_out.default_location_src_id.id,
        })

        cls._setup_3step_outbound_route(cls.picking_type_pick,
                                        cls.picking_type_check)

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

        return packages, [{'product': self.apple, 'qty': 100 * n}]

    def time_create_pick(self, products_info):
        return self.create_picking(
            picking_type=self.picking_type_pick,
            origin="test_pick_origin",
            products_info=products_info,
        )

    def _assign(self, pick):
        pick.action_assign()

    def _confirm(self, pick):
        pick.action_confirm()

    def _validate_lines(self, pick, packages):
        for package in packages:
            pick.update_picking(
                package_name=package.name,
                location_dest_id=self.test_location_02.id
            )

    def _validate_pick(self, pick):
        pick.update_picking(validate=True)

    def time_pick_assign(self, pick):
        self._assign(pick)

    def time_pick_confirm(self, pick):
        self._confirm(pick)

    def time_pick_validate_lines(self, pick, packages):
        self._validate_lines(pick, packages)

    def time_pick_validate_pick(self, pick):
        self._validate_pick(pick)

    def time_check_assign(self, pick):
        self._assign(pick)

    def time_check_confirm(self, pick):
        self._confirm(pick)

    def time_check_validate_lines(self, pick, packages):
        self._validate_lines(pick, packages)

    def time_check_validate_pick(self, pick):
        self._validate_pick(pick)


    def time_out_assign(self, pick):
        self._assign(pick)

    def time_out_confirm(self, pick):
        self._confirm(pick)

    def time_out_validate_lines(self, pick, packages):
        self._validate_lines(pick, packages)

    def time_out_validate_pick(self, pick):
        self._validate_pick(pick)

    def _outbound_pick(self, n):
        packages, products_info = self.time_setup(n)
        pick = self.time_create_pick(products_info)

        self.time_pick_confirm(pick)
        self.time_pick_assign(pick)

        check_pick = pick.u_next_picking_ids
        out_pick = check_pick.u_next_picking_ids

        self.time_pick_validate_lines(pick, packages)
        self.time_pick_validate_pick(pick)

        self.time_check_confirm(check_pick)
        self.time_check_assign(check_pick)
        self.time_check_validate_lines(check_pick, packages)
        self.time_check_validate_pick(check_pick)

        self.time_out_confirm(out_pick)
        self.time_out_assign(out_pick)
        self.time_out_validate_lines(out_pick, packages)
        self.time_out_validate_pick(out_pick)

        self._process_results(
            n,
            self.time_setup,
            self.time_create_pick,
            self.time_pick_confirm,
            self.time_pick_assign,
            self.time_pick_validate_lines,
            self.time_pick_validate_pick,
            self.time_check_confirm,
            self.time_check_assign,
            self.time_check_validate_lines,
            self.time_check_validate_pick,
            self.time_out_confirm,
            self.time_out_assign,
            self.time_out_validate_lines,
            self.time_out_validate_pick,
        )


class OutboundMoves(OutboundLines):

    xlabel = 'Number of Moves'

    def time_setup(self, n):
        Package = self.env['stock.quant.package']
        packages = []
        products_info = []

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

            products_info.append({'product': new_prod, 'qty': 100})

        return packages, products_info


class TestOutboundLines(OutboundLines):

    @parameterized.expand(config.TestOutboundLines or config.default)
    def test_outbound_pick(self, n):
        self._outbound_pick(n)

    def test_report(self):
        self._report()

class TestOutboundMoves(OutboundMoves):

    @parameterized.expand(config.TestOutboundMoves or config.default)
    def test_outbound_pick(self, n):
        self._outbound_pick(n)

    def test_report(self):
        self._report()
