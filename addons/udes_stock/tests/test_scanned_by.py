from .common import BaseUDES
from odoo.api import Environment


class TestScannedBy(BaseUDES):
    @classmethod
    def setUpClass(cls):
        """Setup a picking to test user scanned by is correct"""
        super().setUpClass()
        # Setup user
        cls.test_company = cls.create_company("test_company")
        cls.test_user = cls.create_user(
            "test_user",
            "test_user_login",
            company_id=cls.test_company.id,
            company_ids=[(6, 0, cls.test_company.ids)],
        )

        cls.other_user = cls.create_user(
            "other_user",
            "other_user_login",
            company_id=cls.test_company.id,
            company_ids=[(6, 0, cls.test_company.ids)],
        )

        test_user_env = Environment(cls.env.cr, uid=cls.test_user.id, context=cls.env.context)

        # Setup picking
        cls.create_quant(cls.apple.id, cls.test_stock_location_01.id, 10)
        cls.create_quant(cls.banana.id, cls.test_stock_location_02.id, 20)
        picking = cls.create_picking(cls.picking_type_internal)
        move = cls.create_single_move(cls.apple, 10, picking)
        move = cls.create_single_move(cls.banana, 20, picking)
        picking.action_confirm()
        picking.action_assign()

        cls.picking = picking.with_env(test_user_env)

    # TODO: Does this need enabling even with real_uid removed now?

    # def test_records_real_id_on_move_line_update(self):
    #     """The original user should be in u_done_by so that when sudo is required for
    #     permission access the correct user and be reported on
    #     """
    #     sudo_picking = self.picking.sudo()  # Switch to admin to get around any access rights
    #     move_line = sudo_picking.move_line_ids[0]
    #     move_line.write({"qty_done": move_line.product_uom_qty})
    #     self.assertEqual(move_line.u_done_by.id, self.test_user.id)

    def test_multiple_users_move_line_update(self):
        """Check that when two users act on the same picking that they are recorded seperately"""
        sudo_picking = self.picking.sudo()  # Switch to admin to get around any access rights
        apple_move_line = sudo_picking.move_line_ids.filtered(
            lambda ml: ml.product_id == self.apple
        )
        apple_move_line.write({"qty_done": apple_move_line.product_uom_qty})
        self.assertEqual(apple_move_line.u_done_by_id.id, self.test_user.id)

        other_user_env = Environment(self.env.cr, uid=self.other_user.id, context=self.env.context)
        other_user_picking = self.picking.with_env(other_user_env).sudo()

        banana_move_line = other_user_picking.move_line_ids.filtered(
            lambda ml: ml.product_id == self.banana
        )
        banana_move_line.write({"qty_done": banana_move_line.product_uom_qty})
        self.assertEqual(banana_move_line.u_done_by_id.id, self.other_user.id)
