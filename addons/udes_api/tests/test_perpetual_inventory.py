# -*- coding: utf-8 -*-

import json
import os

import jsonschema

from odoo.addons.udes_core.tests import common
from odoo.exceptions import ValidationError


SCHEMA_FILE_REL_PATH = '../schemas/stock-location-pi-count.json'


class TestPerpetualInventoryRequest(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestPerpetualInventoryRequest, cls).setUpClass()

        tests_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.abspath(
            os.path.join(tests_dir, SCHEMA_FILE_REL_PATH))

        with open(schema_path, 'r') as f_r:
            cls.request_schema = json.loads(f_r.read())

        cls.validator = jsonschema.Draft4Validator(cls.request_schema)

    def test00_schema_is_good(self):
        """ Metatest for checking the schema """
        jsonschema.Draft4Validator.check_schema(self.request_schema)

    def test01_schema_validation_succeed(self):
        """ Can validate a good request """
        req = {
            'location_id': 1234,
            'pi_count_moves': [
                {
                    'quants_ids': [1, 2, 3],
                    'location_id': 1234,
                    'location_dest_id': 1236
                }
            ],
            'inventory_adjustments': [
                {'product_id': 8, 'package_name': 'spam', 'quantity': 5}
            ]
        }

        self.assertTrue(self.validator.is_valid(req))

    def test02_schema_validation_fails_no_location_id(self):
        """ Does not validate if there is no location_id """
        req = {
            'this should be the location_id': 1234,
            'pi_count_moves': [
                {
                    'quants_ids': [1, 2, 3],
                    'location_id': 1234,
                    'location_dest_id': 1236
                }
            ]
        }

        self.assertFalse(self.validator.is_valid(req))

    def test03_schema_validation_fails_only_location(self):
        """ Does not validate if the request is incomplete """
        req = {'location_id': 1234}

        self.assertFalse(self.validator.is_valid(req))

    def test04_schema_validation_fails_quants_and_package(self):
        """ Does not validate if move has both quant and package """
        req = {
            'location_id': 1234,
            'pi_count_moves': [
                {
                    'quants_ids': [1, 2, 3],
                    'package_id': 42,
                    'location_id': 1234,
                    'location_dest_id': 1236
                }
            ]
        }

        self.assertFalse(self.validator.is_valid(req))

    def test05_schema_validation_fails_quants_and_package(self):
        """ Does not validate if preceding adjustment no quantity """
        req = {
            'location_id': 1234,
            'inventory_adjustments': [
                {'product_id': 7, 'package_name': 'foo', 'quantity': 3}
            ],
            'preceding_inventory_adjustment': {
                'location_id': 1234,
                'inventory_adjustments': [
                    {'product_id': 7, 'package_name': 'foo'}
                ]
            }
        }

        self.assertFalse(self.validator.is_valid(req))
