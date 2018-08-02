# -*- coding: utf-8 -*-

from . import common
from odoo.exceptions import UserError


class TestCreateProcurementGroup(common.BaseUDES):

    def setUp(self):
        """
        Create stock.
        """
        super(TestCreateProcurementGroup, self).setUp()
        # create stock: 10 apple
        self.create_quant(self.apple.id, self.test_location_01.id, 10,
                          package_id=self.create_package().id)


    def test01_create_group_when_no_group_at_picking(self):
        """
            Create a pick picking without group, after
            action_confirm() it should have group
            when u_create_procurement_group is true.
        """
        self.picking_type_pick.u_create_procurement_group = True

        products = [{'product': self.apple, 'qty': 10}]
        pick_picking = self.create_picking(self.picking_type_pick,
                                           products_info=products)
        pick_picking = pick_picking.sudo(self.outbound_user)

        self.assertEqual(pick_picking.state, 'draft')
        self.assertEqual(len(pick_picking.group_id), 0)
        pick_picking.action_confirm()
        self.assertEqual(len(pick_picking.group_id), 1)

    def test02_dont_create_group_when_group_at_picking(self):
        """
            Create a pick picking with group, after
            action_confirm() it should have the same group.
        """
        Group = self.env['procurement.group']
        self.picking_type_pick.u_create_procurement_group = True

        group = Group.get_group("TESTGROUP99", create=True)
        products = [{'product': self.apple, 'qty': 10, 'group_id': group.id}]
        pick_picking = self.create_picking(self.picking_type_pick,
                                           products_info=products,
                                           group_id=group.id,
                                           confirm=True, assign=True)
        pick_picking = pick_picking.sudo(self.outbound_user)

        self.assertEqual(len(pick_picking.group_id), 1)
        pick_picking.action_confirm()
        self.assertEqual(len(pick_picking.group_id), 1)
        self.assertEqual(pick_picking.group_id, group)

    def test03_dont_create_group_when_flag_is_false(self):
        """
            Create a pick picking without group, after
            action_confirm() it shouldn't have group
            when u_create_procurement_group is false.
        """
        self.picking_type_pick.u_create_procurement_group = False

        products = [{'product': self.apple, 'qty': 10}]
        pick_picking = self.create_picking(self.picking_type_pick,
                                           products_info=products)
        pick_picking = pick_picking.sudo(self.outbound_user)

        self.assertEqual(pick_picking.state, 'draft')
        self.assertEqual(len(pick_picking.group_id), 0)
        pick_picking.action_confirm()
        self.assertEqual(len(pick_picking.group_id), 0)

    def test04_action_confirm_still_returns_result(self):
        """
            Create a pick picking without group, after
            action_confirm() it should have group
            when u_create_procurement_group is true.
        """
        self.picking_type_pick.u_create_procurement_group = True

        products = [{'product': self.apple, 'qty': 10}]
        pick_picking = self.create_picking(self.picking_type_pick,
                                           products_info=products)
        pick_picking = pick_picking.sudo(self.outbound_user)

        self.assertEqual(pick_picking.state, 'draft')
        result = pick_picking.action_confirm()
        # result can be True or a dict
        if result is not True:
            # res_id if of the result is the picking id
            self.assertEqual(result['res_id'], pick_picking.id,
                             "Unexpected result of action_confirm")
