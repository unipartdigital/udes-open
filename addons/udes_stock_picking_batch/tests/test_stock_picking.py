from odoo.addons.udes_stock.tests import common
from odoo.exceptions import ValidationError


class TestStockPicking(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockPicking, cls).setUpClass()


class TestBatchToUser(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestBatchToUser, cls).setUpClass()
        User = cls.env["res.users"]

        cls.outbound_user = User.create({"name": "Outbound User", "login": "out_log"})

    def test_picking_has_batch_and_batch_already_assigned_to_desired_user(self):
        batch = self.create_batch(self.outbound_user)

        picking = self._create_apple_quant_and_picking(batch)

        self.assertEqual(picking.batch_to_user(self.outbound_user), True)

    def test_picking_has_batch_and_batch_not_assigned_to_a_user(self):
        batch = self.create_batch(None)
        batch.write({"user_id": False})

        picking = self._create_apple_quant_and_picking(batch)

        with self.assertRaises(ValidationError) as cm:
            picking.batch_to_user(self.outbound_user)
            self.assertEqual(
                str(cm.exception),
                f"Picking {picking.name} is already in an unassigned batch",
            )

    def test_picking_has_batch_and_batch_assigned_to_different_user(self):
        batch = self.create_batch(self.env.user)

        picking = self._create_apple_quant_and_picking(batch)

        with self.assertRaises(ValidationError) as cm:
            picking.batch_to_user(self.outbound_user)
            self.assertEqual(
                str(cm.exception),
                f"Picking {self.name} is in a batch owned by another user: {self.batch_id.user_id.name}",
            )

    def test_picking_has_no_batch_and_user_has_batches(self):
        batch = self.create_batch(self.outbound_user)
        self._create_apple_quant_and_picking(batch)
        batch.write({"state":"in_progress"})

        picking = self._create_apple_quant_and_picking()

        with self.assertRaises(ValidationError) as cm:
            picking.batch_to_user(self.outbound_user)
            self.assertEqual(
                str(cm.exception),
                f"You ({self.outbound_user.name}) already have a batch in progess",
            )

    def test_picking_has_no_batch_and_user_has_no_batches(self):
        PickingBatch = self.env["stock.picking.batch"]

        picking = self._create_apple_quant_and_picking()

        picking.batch_to_user(self.outbound_user)

        batches = PickingBatch.sudo().search(
            [("user_id", "=", self.outbound_user.id), ("state", "=", "in_progress")]
        )

        self.assertEqual(batches.picking_ids.id, picking.id)

    def _create_apple_quant_and_picking(self, batch=False):
        self.create_quant(self.apple.id, self.test_stock_location_01.id, 10)
        picking = self.create_picking(
            self.picking_type_pick,
            products_info=[{"product": self.apple, "qty": 10}],
            confirm=True,
            assign=True,
            batch_id=batch.id if batch else False,
        )
        return picking
