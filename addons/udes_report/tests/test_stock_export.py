# -*- coding: utf-8 -*-

import datetime
from unittest import mock

from odoo.addons.udes_stock.tests.common import BaseUDES
from odoo.exceptions import UserError


class TestStockExport(BaseUDES):
    def setUp(self, *args, **kwargs):
        super(TestStockExport, self).setUp()
        Package = self.env["stock.quant.package"]
        Users = self.env["res.users"].with_context(
            {"no_reset_password": True, "mail_create_nosubscribe": True}
        )
        self.test_user = Users.create(
            {
                "name": "Curt Kirkwood",
                "login": "ckirkwood",
                "email": "c.k@example.com",
                "notification_type": "inbox",
                "groups_id": [(6, 0, [self.env.ref("stock.group_stock_user").id])],
            }
        )
        self.StockExportObj = self.env["udes_report.stock_export"].sudo(self.test_user)
        self.stock_export = self.StockExportObj.create({})
        self.LocationObj = self.env["stock.location"]

        # Create some stock
        self.cherry_quant = self.create_quant(
            product_id=self.cherry.id, location_id=self.test_location_01.id, qty=10,
        )
        self.apple_package = Package.get_package("apple_package", create=True)
        self.apple_quant = self.create_quant(
            product_id=self.apple.id,
            location_id=self.test_location_02.id,
            package_id=self.apple_package.id,
            qty=5,
        )

    #
    ## Stock
    #

    def test_stock_no_locations(self):
        """ Stock - should error in case no locations are specified """
        empty_locations = self.LocationObj
        self.stock_export.included_locations = empty_locations
        self.stock_export.excluded_locations = empty_locations

        with self.assertRaises(UserError) as err:
            self.stock_export.run_stock_file_export()

        self.assertIn("The specified list", str(err.exception), "Wrong error message")

    def test_stock_all_excluded_locations(self):
        """ Stock - should error in case all locations are excluded """
        self.stock_export.included_locations = self.stock_location
        self.stock_export.excluded_locations = self.stock_location

        with self.assertRaises(UserError) as err:
            self.stock_export.run_stock_file_export()

        self.assertIn("The specified list", str(err.exception), "Wrong error message")

    def test_stock_success(self):
        """ Stock - should call the write method when locations are given """
        self.stock_export.included_locations = self.stock_location

        # Empty record set
        self.stock_export.excluded_locations = self.LocationObj

        with mock.patch.object(self.stock_export, "_write_workbook", autospec=True):
            self.stock_export.run_stock_file_export()
            self.assertEqual(
                self.stock_export._write_workbook.call_count,
                1,
                "The function that writes the " "workbook was not invoked",
            )

            _timestr = datetime.datetime.today().strftime("%Y-%m-%d %H:%M")
            self.assertIn(
                "warehouse_stock_{}".format(_timestr),
                self.stock_export._write_workbook.call_args[0][0],
            )

    def test_generate_stock_file_data(self):
        """Test that stock file data is correctly generated."""
        self.stock_export.included_locations = self.stock_location

        expected_column_titles_stock_file = [
            "Part Number",
            "Location",
            "Package",
            "Lot/Serial Number",
            "Quantity",
        ]
        expected_rows_stock_file = [
            {
                "Part Number": self.apple_quant.product_id.default_code,
                "Location": self.apple_quant.location_id.display_name,
                "Package": self.apple_quant.package_id.display_name,
                "Quantity": self.apple_quant.quantity,
                "Lot/Serial Number": "",
            },
            {
                "Part Number": self.cherry_quant.product_id.default_code,
                "Location": self.cherry_quant.location_id.display_name,
                "Package": "",
                "Quantity": self.cherry_quant.quantity,
                "Lot/Serial Number": "",
            },
        ]
        expected_column_titles_stock_summary = ["Part Number", "Package Count", "Quantity"]
        expected_rows_stock_summary = [
            {
                "Part Number": self.apple_quant.product_id.default_code,
                "Package Count": 1,
                "Quantity": self.apple_quant.quantity,
            },
            {
                "Part Number": self.cherry_quant.product_id.default_code,
                "Package Count": 0,
                "Quantity": self.cherry_quant.quantity,
            },
        ]

        data = self.stock_export._generate_stock_file_data()

        self.assertEqual(data[0]["name"], "Stock File")
        self.assertEqual(data[0]["column_titles"], expected_column_titles_stock_file)
        self.assertEqual(data[0]["rows"], expected_rows_stock_file)

        self.assertEqual(data[1]["name"], "Stock Summary")
        self.assertEqual(data[1]["column_titles"], expected_column_titles_stock_summary)
        self.assertEqual(data[1]["rows"], expected_rows_stock_summary)

    def test_stock_file_tracking(self):
        """"Check that the data for the stock file correctly displays
        tracking numbers if required.
        """
        Product = self.env["product.product"]

        self.stock_export.included_locations = self.stock_location
        # Assert tracking column is present even when not in stock.
        data = self.stock_export._generate_stock_file_data()
        self.assertTrue("Lot/Serial Number" in data[0]["column_titles"])
        self.assertFalse(any(row["Lot/Serial Number"] for row in data[0]["rows"]))

        # Test that tracking info is not displayed if no products are lot/serial tracked
        tracked_products = Product.search([("tracking", "!=", "none")])
        for product in tracked_products:
            product.tracking = "none"
        data = self.stock_export._generate_stock_file_data()
        self.assertFalse("Lot/Serial Number" in data[0]["column_titles"])

        # Test that a lots are correctly shown if one is present
        self.tangerine.tracking = "lot"
        self.create_quant(
            product_id=self.tangerine.id,
            location_id=self.test_location_02.id,
            qty=5,
            serial_number="TESTLOT001",
        )
        data = self.stock_export._generate_stock_file_data()
        self.assertTrue("Lot/Serial Number" in data[0]["column_titles"])
        self.assertTrue(
            all(
                row["Lot/Serial Number"] == "TESTLOT001"
                for row in data[0]["rows"]
                if row["Part Number"] == self.tangerine.default_code
            )
        )
        self.assertFalse(
            any(
                row["Lot/Serial Number"]
                for row in data[0]["rows"]
                if row["Part Number"] != self.tangerine.default_code
            )
        )

    #
    ## Movement
    #

    def test_move_no_date(self):
        """ Movement - should error in case no date is specified """
        self.stock_export.date = None

        with self.assertRaises(UserError) as err:
            self.stock_export.run_movement_file_export()

        self.assertEqual("Date not specified.", str(err.exception.name), "Wrong error message")

    def test_move_success(self):
        """ Movement - should call the write method """

        # create a picking to have some move lines
        out_pick_type = self.test_user.get_user_warehouse().out_type_id
        out_pick_type.default_location_dest_id = self.env.ref("stock.stock_location_customers")
        out_picking = self.create_picking(
            out_pick_type, [{"product": self.cherry, "qty": 10}], assign=True
        )

        out_picking.move_lines.write({"state": "done"})

        self.stock_export.date = datetime.date.today()
        with mock.patch.object(self.stock_export, "_write_workbook", autospec=True):
            self.stock_export.run_movement_file_export()
            self.assertEqual(
                self.stock_export._write_workbook.call_count,
                1,
                "The function that writes the " "workbook was not invoked",
            )

            _timestr = datetime.datetime.today().strftime("%Y-%m-%d %H:%M")
            self.assertIn(
                "warehouse_movement_{}".format(_timestr),
                self.stock_export._write_workbook.call_args[0][0],
            )

    def test_check_message(self):
        """Check that message is sent"""
        Message = self.env["mail.message"]

        self.stock_export.included_locations = self.stock_location
        # Empty record set
        self.stock_export.excluded_locations = self.LocationObj

        old_msg = Message.search([("partner_ids", "in", self.test_user.partner_id.id)])

        self.stock_export.run_stock_file_export(send_file_via="user")

        new_msg = Message.search([("partner_ids", "in", self.test_user.partner_id.id)])
        new_msg -= old_msg

        self.assertEqual(len(new_msg), 1)
        self.assertIn(".xls Stock File is attached", new_msg.body)

    def test_check_email(self):
        """Check that email is sent"""
        msg_template = self.env.ref("udes_report.automated_stock_email_template")
        msg_template.email_to = self.test_user.email

        # Make a stock export which has an admin user
        # as normal users are not allowed to send emails
        stock_export = self.env["udes_report.stock_export"].create({})

        stock_export.included_locations = self.stock_location
        # Empty record set
        stock_export.excluded_locations = self.LocationObj
        # Send email (Note: Odoo will not actually send the email in test mode)
        stock_export.send_automated_stock_file()
