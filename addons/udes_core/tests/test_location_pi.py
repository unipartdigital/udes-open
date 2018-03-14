# -*- coding: utf-8 -*-

from . import common

from odoo.exceptions import ValidationError


class TestLocationPI(common.BaseUDES):

    def test01_validate_pi_request_success(self):
        """ No error is raised for a good PI request """
        req = {
            'location_id': self.test_location_01.id,
            'pi_count_moves': [
                {
                    'quants_ids': [1, 2, 3],
                    'location_id': self.test_location_01.id,
                    'location_dest_id': self.test_location_02.id
                }
            ]
        }

        self.test_location_01._validate_perpetual_inventory_request(req)
        self.assertTrue(True)

    def test02_validate_pi_request_failure_unknown_location(self):
        """ Errors if the request contains unknown locations """
        req = {
            'location_id': self.test_location_01.id,
            'pi_count_moves': [
                {
                    'quants_ids': [1, 2, 3],
                    'location_id': self.test_location_01.id,
                    'location_dest_id': 123412341234
                }
            ]
        }

        with self.assertRaisesRegex(ValidationError,
                                    'The request has an unknown location'):
            self.test_location_01._validate_perpetual_inventory_request(req)

    def test03_validate_pi_request_failure_no_adj(self):
        """ Errors if the request contains unknown locations """
        req = {
            'location_id': self.test_location_01.id,
            'pi_count_moves': [
                {
                    'quants_ids': [1, 2, 3],
                    'location_id': self.test_location_01.id,
                    'location_dest_id': self.test_location_02.id
                }
            ],
            'preceding_inventory_adjustments': {
                'location_id': self.test_location_01.id,
                'inventory_adjustments': [
                    {'product_id': 7, 'package_name': 'foo', 'quantity': 0}
                ]
            }
        }

        with self.assertRaisesRegex(ValidationError,
                                    'You must specify inventory adjustments'):
            self.test_location_01._validate_perpetual_inventory_request(req)
