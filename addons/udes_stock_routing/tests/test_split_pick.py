from odoo.addons.udes_stock.tests.common import BaseUDES
from ..models.stock_rule import RULE_RESERVATION_TYPE_WHOLE_PALLET

from datetime import datetime, timedelta


class SplitPickBase(BaseUDES):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Rule = cls.env["stock.rule"]
        PickingType = cls.env["stock.picking.type"]
        # We are making an example 'pure' configuration. Disable anything which could conflict
        # with the test. We don't use data xml for the picking types for the same reason.
        # We want the simplest possible configuration to use as an example, but this
        # configuration of the extra rules can basically be applied to any system.
        Rule.search([]).write({"active": False})
        PickingType.search([]).write({"active": False})
        cls.Picking = cls.env["stock.picking"]
        cls.customer_location = cls.env.ref("stock.stock_location_customers")

        cls.bulk_location = cls.create_location(
            "Bulk", location_id=cls.stock_location.id, usage="view"
        )
        cls.bulk_location_01 = cls.create_location("Bulk 01", location_id=cls.bulk_location.id)
        cls.standard_location = cls.create_location(
            "Standard", location_id=cls.stock_location.id, usage="view"
        )
        cls.standard_location_01 = cls.create_location(
            "Standard 01", location_id=cls.standard_location.id
        )
        cls.output_location = cls.create_location(
            "Output", location_id=cls.stock_location.id, usage="view"
        )
        cls.output_location_01 = cls.create_location(
            "Output 01", location_id=cls.output_location.id
        )
        # These two operation types represent the 'normal' ones, which will likely already
        # exist on a UDES implementation.
        # The stock flow of this test is from WH/Stock/* --> WH/Stock/Output --> Partner Locations/Customers.
        cls.pick_operation_type = PickingType.create(
            {
                "name": "TEST PICK",
                "code": "internal",
                "default_location_src_id": cls.stock_location.id,
                "default_location_dest_id": cls.output_location.id,
                "warehouse_id": cls.warehouse.id,
                # "u_target_storage_format": "pallet_products",
                # "u_user_scans": "product",
            }
        )
        cls.goodsout_operation_type = PickingType.create(
            {
                "name": "TEST GOODSOUT",
                "code": "internal",
                "default_location_src_id": cls.output_location.id,
                "default_location_dest_id": cls.customer_location.id,
                "warehouse_id": cls.warehouse.id,
            }
        )
        # These two operation types represent the ones which 'Pick' can be split into,
        # depending on the rule configuration. They go from sublocations of stock to the same
        # destination location as pick. The source location actually used is determined by the rule
        # however, so the default_location_src_id doesn't really matter here for the split pick
        # rule functionality, it only matters for manual creations. It is also worth noting
        # that the location _doesn't_ have to be a subset of the source location of 'Pick'
        # because the new rule(s) will determine where quants are gathered from,
        # and split the move lines into the new operation type.
        cls.bulk_operation_type = PickingType.create(
            {
                "name": "TEST BULK",
                "code": "internal",
                "default_location_src_id": cls.bulk_location.id,
                "default_location_dest_id": cls.output_location.id,
                "warehouse_id": cls.warehouse.id,
            }
        )
        cls.standard_operation_type = PickingType.create(
            {
                "name": "TEST STANDARD",
                "code": "internal",
                "default_location_src_id": cls.standard_location.id,
                "default_location_dest_id": cls.output_location.id,
                "warehouse_id": cls.warehouse.id,
            }
        )
        # When need occurs in Customers, TEST GOODSOUT are created from Output to fulfill the need.
        # A need is created in Output and a rule will be triggered to fulfill it.
        Rule.create(
            {
                "name": "TEST Output -> Customers",
                "action": "pull",
                "picking_type_id": cls.goodsout_operation_type.id,
                "location_src_id": cls.output_location.id,
                "location_id": cls.customer_location.id,
                "procure_method": "make_to_order",
                "route_id": cls.route_out.id,
                "warehouse_id": cls.warehouse.id,
            }
        )
        # When need occurs in Output, TEST PICK are created from Stock to fulfill the need.
        Rule.create(
            {
                "name": "TEST Stock -> Output",
                "action": "pull",
                "picking_type_id": cls.pick_operation_type.id,
                "location_src_id": cls.stock_location.id,
                "location_id": cls.output_location.id,
                "procure_method": "make_to_stock",
                "route_id": cls.route_out.id,
                "warehouse_id": cls.warehouse.id,
            }
        )
        # This uses the new flag u_run_on_assign, which prevents the rule from being run
        # under normal circumstances. Instead, the rule is used when a pick is assigned.
        # This is controlled with the u_run_on_assign flag and u_run_on_assign_applicable_to.
        # The reservation type controls whether we enforce whole pallet reservation or whether
        # any stock is considered.
        # Finally, the sequence of rules which are applicable to the same picking type (if there are multiple)
        # determines the order in which stock is considered. So this pair of rules will consider
        # whole pallets in the Bulk location first, and _any_ stock in the Standard location second.
        # We are not limited to using different picking types on these rules however.
        cls.bulk_rule = Rule.create(
            {
                "name": "TEST Bulk -> Output",
                "action": "pull",
                "picking_type_id": cls.bulk_operation_type.id,
                "location_src_id": cls.bulk_location.id,
                "location_id": cls.output_location.id,
                "procure_method": "make_to_stock",
                "route_id": cls.route_out.id,
                "warehouse_id": cls.warehouse.id,
                "u_run_on_assign": True,
                "u_run_on_assign_applicable_to": cls.pick_operation_type.id,
                "u_run_on_assign_reservation_type": RULE_RESERVATION_TYPE_WHOLE_PALLET,
                "sequence": 10,
            }
        )
        cls.standard_rule = Rule.create(
            {
                "name": "TEST Standard -> Output",
                "action": "pull",
                "picking_type_id": cls.standard_operation_type.id,
                "location_src_id": cls.standard_location.id,
                "location_id": cls.output_location.id,
                "procure_method": "make_to_stock",
                "route_id": cls.route_out.id,
                "warehouse_id": cls.warehouse.id,
                "u_run_on_assign": True,
                "u_run_on_assign_applicable_to": cls.pick_operation_type.id,
                "u_run_on_assign_reservation_type": False,
                "sequence": 20,
            }
        )

    def procure_products(self, products_data):
        """Helper to generate a Customer location need for the products passed in"""
        ProcurementGroup = self.env["procurement.group"]
        # This logic is ripped off what happens when a sale is confirmed from sale_stock module.
        group = ProcurementGroup.create({"name": "test"})
        procurements = []
        for product_data in products_data:
            product = product_data.get("product")
            qty = product_data.get("qty")
            values = {
                "group_id": group,
                "company_id": self.company,
                "warehouse_id": self.warehouse,
            }

            procurements.append(
                ProcurementGroup.Procurement(
                    product_id=product,
                    product_qty=qty,
                    product_uom=product.uom_id,
                    location_id=self.customer_location,
                    name="TEST",
                    origin="TEST",
                    company_id=self.company,
                    values=values,
                )
            )
        if procurements:
            ProcurementGroup.run(procurements)


class TestSplitPick(SplitPickBase):
    def test_split_does_not_occur_when_procurements_are_run(self):
        """
        Despite having our rules set up, we want to ensure that when the products are procured
        in the customer location (i.e the sale is confirmed) that they are ignored.
        We should just have a normal Pick --> Goods Out for 99 apples.
        This is also to ensure the procure_products helper is working as intended.
        """
        self.procure_products([{"product": self.apple, "qty": 99}])
        all_picks = self.Picking.search([])
        self.assertEqual(len(all_picks), 2)
        pick_pick = all_picks.filtered(lambda p: p.picking_type_id == self.pick_operation_type)
        self.assertEqual(len(pick_pick), 1)
        goods_out_pick = all_picks - pick_pick
        self.assertEqual(len(goods_out_pick), 1)
        for pick in [pick_pick, goods_out_pick]:
            self.assertEqual(len(pick.move_lines), 1)
            self.assertEqual(pick.move_lines.product_id, self.apple)
            self.assertEqual(pick.move_lines.product_uom_qty, 99)
            self.assertEqual(len(pick.move_line_ids), 0)

    def test_split_whole_pallet_rule_ignored(self):
        """
        Ensure that when a rule is set up to use whole pallets, that partial stock is not reserved
        off a pallet, and instead the loose stock is used.
        """
        # Set up 200 apples on 2 pallets in bulk, 100 apples loose in standard.
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(self.apple.id, self.standard_location_01.id, 100)
        # Need for 199 apples. The first sequenced rule of whole pallets should find only one suitable quant
        # as the palletised apples are of a qty of 100 and the rule has RULE_RESERVATION_TYPE_WHOLE_PALLET set.
        # The second sequence rule which has no defined u_run_on_assign_reservation_type will
        # look up any remaining stock in the standard location.
        self.procure_products([{"product": self.apple, "qty": 199}])
        all_picks = self.Picking.search([])
        pick_pick = all_picks.filtered(lambda p: p.picking_type_id == self.pick_operation_type)
        pick_pick.action_assign()
        # The split pick rule should have just run, and ripped off the moves to the Standard picking type.
        self.assertEqual(len(pick_pick.move_lines), 0)
        all_picks = self.Picking.search([])
        standard_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.standard_operation_type
        )
        bulk_pick = all_picks.filtered(lambda p: p.picking_type_id == self.bulk_operation_type)
        # Ensure only one whole pallet was reserved
        self.assertEqual(len(bulk_pick), 1)
        self.assertEqual(len(bulk_pick.move_lines), 1)
        self.assertEqual(bulk_pick.move_lines.product_uom_qty, 100)
        self.assertEqual(bulk_pick.move_line_ids.product_uom_qty, 100)

        # Assert the standard pick contains the remaining qty.
        self.assertEqual(len(standard_pick), 1)
        self.assertEqual(len(standard_pick.move_lines), 1)
        self.assertEqual(len(standard_pick.move_line_ids), 1)
        self.assertEqual(standard_pick.move_lines.product_uom_qty, 99)
        self.assertEqual(standard_pick.move_line_ids.product_uom_qty, 99)

        goodsout_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.goodsout_operation_type
        )
        self.assertEqual(standard_pick.move_lines.move_dest_ids, goodsout_pick.move_lines)
        self.assertEqual(len(standard_pick.move_lines.move_orig_ids), 0)

    def test_split_whole_pallet_rule_used(self):
        """
        Ensure that when a rule is set up to use whole pallets, that the whole pallet is reserved
        if it can be fully utilised to fulfill part or all of the quantity.
        """
        # Set up 100 apples on a pallet in bulk, 100 apples loose in standard.
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(self.apple.id, self.standard_location_01.id, 100)
        # Need for 100 apples. The first sequenced rule of whole pallets should find a suitable quant.
        self.procure_products([{"product": self.apple, "qty": 100}])
        all_picks = self.Picking.search([])
        pick_pick = all_picks.filtered(lambda p: p.picking_type_id == self.pick_operation_type)
        pick_pick.action_assign()
        # The split pick rule should have just run, and ripped off the moves to the Bulk picking type.
        self.assertEqual(len(pick_pick.move_lines), 0)
        all_picks = self.Picking.search([])
        bulk_pick = all_picks.filtered(lambda p: p.picking_type_id == self.bulk_operation_type)
        self.assertEqual(len(bulk_pick), 1)
        goodsout_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.goodsout_operation_type
        )
        self.assertEqual(len(bulk_pick.move_lines), 1)
        self.assertEqual(len(bulk_pick.move_line_ids), 1)
        self.assertEqual(bulk_pick.move_lines.move_dest_ids, goodsout_pick.move_lines)
        self.assertEqual(len(bulk_pick.move_lines.move_orig_ids), 0)
        self.assertEqual(bulk_pick.move_lines.product_uom_qty, 100)
        self.assertEqual(bulk_pick.move_line_ids.product_uom_qty, 100)
        # No standard pick should have been created.
        standard_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.standard_operation_type
        )
        self.assertEqual(len(standard_pick), 0)

    def test_split_whole_pallet_rule_used_for_multiple_pallets(self):
        """
        Ensure that when a rule is set up to use whole pallets, that multiple whole pallets are reserved
        if they can be fully utilised to fulfill part or all of the quantity.
        """
        # Set up 200 apples on 2 pallets in bulk, 100 apples loose in standard.
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(self.apple.id, self.standard_location_01.id, 100)
        # Need for 200 apples. The first sequenced rule of whole pallets should find multiple suitable quants.
        self.procure_products([{"product": self.apple, "qty": 200}])
        all_picks = self.Picking.search([])
        pick_pick = all_picks.filtered(lambda p: p.picking_type_id == self.pick_operation_type)
        pick_pick.action_assign()
        # The split pick rule should have just run, and ripped off the moves to the Bulk picking type.
        self.assertEqual(len(pick_pick.move_lines), 0)
        all_picks = self.Picking.search([])
        bulk_pick = all_picks.filtered(lambda p: p.picking_type_id == self.bulk_operation_type)
        self.assertEqual(len(bulk_pick), 1)
        goodsout_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.goodsout_operation_type
        )
        self.assertEqual(len(bulk_pick.move_lines), 1)
        self.assertEqual(len(bulk_pick.move_line_ids), 2)
        self.assertEqual(bulk_pick.move_lines.move_dest_ids, goodsout_pick.move_lines)
        self.assertEqual(len(bulk_pick.move_lines.move_orig_ids), 0)
        self.assertEqual(sum(bulk_pick.move_lines.mapped("product_uom_qty")), 200)
        self.assertEqual(sum(bulk_pick.move_line_ids.mapped("product_uom_qty")), 200)
        # No standard pick should have been created.
        standard_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.standard_operation_type
        )
        self.assertEqual(len(standard_pick), 0)

    def test_split_both_rules_used(self):
        """
        Ensure that if two rules are configured and the first rule is set up to do whole pallets while
        the second rule is configured to use any, that the whole pallet rule runs first and the second
        rule runs to fulfill any remaining quantity which the first rule could not fulfill.
        """
        # Set up 200 apples on multiple pallets in bulk, 100 apples loose in standard.
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(self.apple.id, self.standard_location_01.id, 100)
        # Need for 199 apples. The first sequenced rule of whole pallets should find one suitable quant.
        # The second rule should find one suitable quant also.
        self.procure_products([{"product": self.apple, "qty": 299}])
        all_picks = self.Picking.search([])
        pick_pick = all_picks.filtered(lambda p: p.picking_type_id == self.pick_operation_type)
        pick_pick.action_assign()
        # The split pick rule should have just run, and ripped off the moves to the Bulk and Standard picking types.
        self.assertEqual(len(pick_pick.move_lines), 0)
        all_picks = self.Picking.search([])
        bulk_pick = all_picks.filtered(lambda p: p.picking_type_id == self.bulk_operation_type)
        self.assertEqual(len(bulk_pick), 1)
        goodsout_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.goodsout_operation_type
        )
        self.assertEqual(len(bulk_pick.move_lines), 1)
        self.assertEqual(len(bulk_pick.move_line_ids), 2)
        self.assertEqual(bulk_pick.move_lines.move_dest_ids, goodsout_pick.move_lines)
        self.assertEqual(len(bulk_pick.move_lines.move_orig_ids), 0)
        self.assertEqual(sum(bulk_pick.move_lines.mapped("product_uom_qty")), 200)
        self.assertEqual(sum(bulk_pick.move_line_ids.mapped("product_uom_qty")), 200)
        # No standard pick should have been created.
        standard_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.standard_operation_type
        )
        self.assertEqual(len(standard_pick), 1)
        self.assertEqual(len(standard_pick.move_lines), 1)
        self.assertEqual(len(standard_pick.move_line_ids), 1)
        self.assertEqual(standard_pick.move_lines.move_dest_ids, goodsout_pick.move_lines)
        self.assertEqual(len(standard_pick.move_lines.move_orig_ids), 0)
        self.assertEqual(standard_pick.move_lines.product_uom_qty, 99)
        self.assertEqual(standard_pick.move_line_ids.product_uom_qty, 99)

    def test_inactive_rules_ignored(self):
        """
        Ensure that when the new rules are disabled, original functionality is restored.
        """
        self.bulk_rule.active = False
        self.standard_rule.active = False
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(self.apple.id, self.standard_location_01.id, 100)
        # Need for 199 apples. As the rules are disabled, we should have just two move lines on the original pick.
        self.procure_products([{"product": self.apple, "qty": 199}])
        all_picks = self.Picking.search([])
        pick_pick = all_picks.filtered(lambda p: p.picking_type_id == self.pick_operation_type)
        pick_pick.action_assign()
        self.assertEqual(len(pick_pick.move_line_ids), 2)
        # No new picks should have been created.
        all_picks = self.Picking.search([])
        bulk_pick = all_picks.filtered(lambda p: p.picking_type_id == self.bulk_operation_type)
        self.assertEqual(len(bulk_pick), 0)
        standard_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.standard_operation_type
        )
        self.assertEqual(len(standard_pick), 0)

    def test_removal_strategy_preserved(self):
        """
        Ensure the removal strategy e.g FIFO is preserved whilst using split pick rules on whole pallets
        """
        q1 = self.create_quant(
            self.apple.id, self.bulk_location_01.id, 10, package_id=self.create_package().id
        )
        q2 = self.create_quant(
            self.apple.id, self.bulk_location_01.id, 10, package_id=self.create_package().id
        )
        q3 = self.create_quant(
            self.apple.id, self.bulk_location_01.id, 10, package_id=self.create_package().id
        )
        now = datetime.now()
        oldest_time = now - timedelta(days=5)
        q1.in_date = now
        q2.in_date = oldest_time
        q3.in_date = now - timedelta(days=3)
        # q2 and q3 should be ripped off onto the new pick when assigned.
        self.procure_products([{"product": self.apple, "qty": 20}])
        all_picks = self.Picking.search([])
        pick_pick = all_picks.filtered(lambda p: p.picking_type_id == self.pick_operation_type)
        pick_pick.action_assign()
        self.assertEqual(q1.available_quantity, 10)
        self.assertEqual(q2.available_quantity, 0)
        self.assertEqual(q3.available_quantity, 0)

    def test_split_pick_partial(self):
        """
        Ensure the pick is split based on what stock could be reserved, and the remaining qty is left on the original picking.
        """
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(self.apple.id, self.standard_location_01.id, 20)
        self.procure_products([{"product": self.apple, "qty": 150}])
        all_picks = self.Picking.search([])
        pick_pick = all_picks.filtered(lambda p: p.picking_type_id == self.pick_operation_type)
        pick_pick.action_assign()
        self.assertEqual(len(pick_pick.move_lines), 1)
        all_picks = self.Picking.search([])
        bulk_pick = all_picks.filtered(lambda p: p.picking_type_id == self.bulk_operation_type)
        standard_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.standard_operation_type
        )
        self.assertEqual(len(bulk_pick), 1)
        self.assertEqual(len(standard_pick), 1)
        self.assertEqual(bulk_pick.move_line_ids.product_uom_qty, 100)
        self.assertEqual(standard_pick.move_line_ids.product_uom_qty, 20)
        self.assertEqual(pick_pick.move_lines.product_uom_qty, 30)
        self.assertEqual(bulk_pick.state, "assigned")
        self.assertEqual(standard_pick.state, "assigned")
        self.assertEqual(pick_pick.state, "confirmed")

    def test_split_pick_multiple_products_complex(self):
        """
        Ensure more complex move groupings end up in the correct pickings with their moves grouped back together.
        """
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(self.apple.id, self.standard_location_01.id, 20)

        self.create_quant(
            self.banana.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(self.banana.id, self.standard_location_01.id, 20)

        # A whole pallet and 10 of the loose stock should be utilised for apples. Bananas however
        # can not be fulfilled with a whole pallet, so the fallback rule of loose stock should be used.
        self.procure_products(
            [{"product": self.apple, "qty": 110}, {"product": self.banana, "qty": 15}]
        )
        all_picks = self.Picking.search([])
        pick_pick = all_picks.filtered(lambda p: p.picking_type_id == self.pick_operation_type)
        pick_pick.action_assign()
        # All stock ripped off as it could be fulfilled.
        self.assertEqual(len(pick_pick.move_lines), 0)
        all_picks = self.Picking.search([])
        bulk_pick = all_picks.filtered(lambda p: p.picking_type_id == self.bulk_operation_type)
        standard_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.standard_operation_type
        )
        self.assertEqual(len(bulk_pick), 1)
        self.assertEqual(bulk_pick.move_line_ids.product_uom_qty, 100)
        self.assertTrue(bulk_pick.move_line_ids.package_id)
        self.assertEqual(bulk_pick.state, "assigned")

        # Depending on the modules installed pick_pick could have been deleted because after split
        # there weren't any moves and u_is_empty is set to True.
        if pick_pick.exists():
            self.assertTrue(pick_pick.u_is_empty)
            self.assertFalse(pick_pick.move_lines)

        self.assertEqual(len(standard_pick), 1)
        standard_move_lines = standard_pick.move_line_ids
        standard_apple_line = standard_move_lines.filtered(lambda ml: ml.product_id == self.apple)
        standard_banana_line = standard_move_lines.filtered(lambda ml: ml.product_id == self.banana)
        self.assertEqual(standard_apple_line.product_uom_qty, 10)
        self.assertEqual(standard_banana_line.product_uom_qty, 15)
        self.assertEqual(standard_apple_line.state, "assigned")
        self.assertEqual(standard_banana_line.state, "assigned")

    def test_other_route_rules_ignored(self):
        """Ensure even though another loose product rule exists in another route, whole pallet rule
        is still used.
        This test borrows test_split_whole_pallet_rule_used structure, only difference is a new
        route and rule with more priority are added just before calling action assign.
        """

        # Set up 100 apples on a pallet in bulk, 100 apples loose in standard.
        self.create_quant(
            self.apple.id, self.bulk_location_01.id, 100, package_id=self.create_package().id
        )
        self.create_quant(self.apple.id, self.standard_location_01.id, 100)
        # Need for 100 apples. The first sequenced rule of whole pallets should find a suitable quant.
        self.procure_products([{"product": self.apple, "qty": 100}])
        all_picks = self.Picking.search([])
        pick_pick = all_picks.filtered(lambda p: p.picking_type_id == self.pick_operation_type)
        # Create new route and a new rule in it with more priority than bulk_rule
        route_out_new = self.route_out.copy({"name": f"{self.route_out.name} NEW"})
        standard_rule_new = self.standard_rule.copy({
            "name": f"{self.standard_rule.name} NEW",
            "sequence": self.bulk_rule.sequence-1,
            "route_id": route_out_new.id,
        })
        # After calling action_assign all checks should still pass, since new rule is ignored
        pick_pick.action_assign()
        # The split pick rule should have just run, and ripped off the moves to the Bulk picking type.
        self.assertEqual(len(pick_pick.move_lines), 0)
        all_picks = self.Picking.search([])
        bulk_pick = all_picks.filtered(lambda p: p.picking_type_id == self.bulk_operation_type)
        self.assertEqual(len(bulk_pick), 1)
        goodsout_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.goodsout_operation_type
        )
        self.assertEqual(len(bulk_pick.move_lines), 1)
        self.assertEqual(len(bulk_pick.move_line_ids), 1)
        self.assertEqual(bulk_pick.move_lines.move_dest_ids, goodsout_pick.move_lines)
        self.assertEqual(len(bulk_pick.move_lines.move_orig_ids), 0)
        self.assertEqual(bulk_pick.move_lines.product_uom_qty, 100)
        self.assertEqual(bulk_pick.move_line_ids.product_uom_qty, 100)
        # No standard pick should have been created.
        standard_pick = all_picks.filtered(
            lambda p: p.picking_type_id == self.standard_operation_type
        )
        self.assertEqual(len(standard_pick), 0)
