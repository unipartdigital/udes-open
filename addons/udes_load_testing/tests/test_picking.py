# -*- coding: utf-8 -*-

from .common import LoadRunner, parameterized


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
