from odoo.addons.udes_stock.tests import common
from odoo.exceptions import ValidationError
from datetime import datetime

class TestStockPicking(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestStockPicking, cls).setUpClass()
        cls._set_up_some_pickings()
        cls.StockPicking = cls.env["stock.picking"]

    @classmethod
    def _set_up_some_pickings(cls):
        """
        Create all pickings with same scheduled_date.
        """
        Picking = cls.env["stock.picking"]
        cls.picks = Picking.browse()
        datetime_now = datetime.now()
        for i in range(5):
            cls.picks |= cls._create_quant_and_picking(
                cls.apple,
                cls.test_stock_location_01.id,
                scheduled_date=datetime_now,
                sequence=10,
            )

    @classmethod
    def _create_quant_and_picking(cls, product, location_id, **kwargs):
        cls.create_quant(product.id, location_id, 1)
        picking = cls.create_picking(
            cls.picking_type_pick,
            products_info=[{"product": product, "qty": 1}],
            confirm=True,
            assign=True,
            **kwargs
        )
        return picking

    def test_search_for_pickings_not_custom_order_pickings(self):
        """
        If order pickings variable is not passed when searching for pickings, it will order by stock picking
        _order attribute.
        """
        order = self.StockPicking._order
        earlier_date = datetime.now().replace(hour=0, minute=0, second=0)
        self.picks[2].scheduled_date = earlier_date
        # Checking that scheduled date is in _order attribute of picking, all picks have same priority
        self.assertIn("scheduled_date asc", order)
        picking = self.StockPicking.search_for_pickings(self.picking_type_pick.id, picking_priorities=None)
        self.assertEqual(picking.scheduled_date, min(self.picks.mapped("scheduled_date")))
        self.assertEqual(picking.scheduled_date, earlier_date)

    def test_search_for_pickings_custom_order_pickings(self):
        """
        If order pickings variable is passed when searching for pickings, it will order by order_pickings variable passed.
        """
        kwargs = {
            "order_pickings": "sequence desc, id desc"
        }
        self.picks[2].sequence = 100
        picking = self.StockPicking.search_for_pickings(self.picking_type_pick.id, picking_priorities=None, **kwargs)
        self.assertEqual(picking.sequence, max(self.picks.mapped("sequence")))
        self.assertEqual(picking.sequence, 100)


class TestBatchToUser(common.BaseUDES):
    @classmethod
    def setUpClass(cls):
        super(TestBatchToUser, cls).setUpClass()

        cls.stock_user = cls.create_user(
            "stock user",
            "stock user",
            groups_id=[(6, 0, [cls.env.ref("stock.group_stock_user").id])],
        )

    def test_picking_has_batch_and_batch_already_assigned_to_desired_user(self):
        batch = self.create_batch(self.stock_user)

        picking = self._create_apple_quant_and_picking(batch)

        self.assertEqual(picking.batch_to_user(self.stock_user), True)

    def test_picking_has_batch_and_batch_not_assigned_to_a_user(self):
        batch = self.create_batch(None)
        batch.write({"user_id": False})

        picking = self._create_apple_quant_and_picking(batch)

        with self.assertRaises(ValidationError) as cm:
            picking.batch_to_user(self.stock_user)
            self.assertEqual(
                str(cm.exception), f"Picking {picking.name} is already in an unassigned batch"
            )

    def test_picking_has_batch_and_batch_assigned_to_different_user(self):
        batch = self.create_batch(self.env.user)

        picking = self._create_apple_quant_and_picking(batch)

        with self.assertRaises(ValidationError) as cm:
            picking.batch_to_user(self.stock_user)
            self.assertEqual(
                str(cm.exception),
                f"Picking {self.name} is in a batch owned by another user: {self.batch_id.user_id.name}",
            )

    def test_picking_has_no_batch_and_user_has_batches(self):
        batch = self.create_batch(self.stock_user)
        self._create_apple_quant_and_picking(batch)
        batch.write({"state": "in_progress"})

        picking = self._create_apple_quant_and_picking()

        with self.assertRaises(ValidationError) as cm:
            picking.batch_to_user(self.stock_user)
            self.assertEqual(
                str(cm.exception),
                f"You ({self.stock_user.name}) already have a batch in progess",
            )

    def test_picking_has_no_batch_and_user_has_no_batches(self):
        PickingBatch = self.env["stock.picking.batch"]

        picking = self._create_apple_quant_and_picking()

        picking.batch_to_user(self.stock_user)

        batches = PickingBatch.sudo().search(
            [("user_id", "=", self.stock_user.id), ("state", "=", "in_progress")]
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
