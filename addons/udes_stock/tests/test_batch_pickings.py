"""Tests for grouping picks in draft batches."""
import random

from ..models.common import PRIORITIES
from .common import BaseUDES


class TestByDatePriority(BaseUDES):
    """Tests for grouping by date and priority."""

    @classmethod
    def setUpClass(cls):
        """Setup for test class."""
        super().setUpClass()

        Picking = cls.env["stock.picking"]

        cls.today = "2019-07-11"
        cls.tomorrow = "2019-07-12"

        cls.picking_type_pick.u_post_confirm_action = "batch_pickings_by_date_priority"

        picks = [
            # Not urgent orders today.
            (cls.today, PRIORITIES[0], 1),
            (cls.today, PRIORITIES[0], 2),
            (cls.today, PRIORITIES[0], 3),
            # Normal orders today.
            (cls.today, PRIORITIES[1], 1),
            (cls.today, PRIORITIES[1], 2),
            (cls.today, PRIORITIES[1], 3),
            # Not urgent orders tomorrow.
            (cls.tomorrow, PRIORITIES[0], 1),
            (cls.tomorrow, PRIORITIES[0], 2),
            (cls.tomorrow, PRIORITIES[0], 3),
            # Normal orders tomorrow.
            (cls.tomorrow, PRIORITIES[1], 1),
            (cls.tomorrow, PRIORITIES[1], 2),
            (cls.tomorrow, PRIORITIES[1], 3),
        ]
        random.seed(42)
        random.shuffle(picks)

        cls.picks_by_key = {
            (date, priority, sequence): cls.create_picking(
                name="{}/{}/{}".format(date, priority[1], sequence),
                picking_type=cls.picking_type_pick,
                priority=priority[0],
                sequence=sequence,
                products_info=[
                    # Set the date here because cls.create_picking creates the picking
                    # without moves then adds the moves, overwriting the `scheduled_date`.
                    dict(product=product, qty=1, date_expected=date)
                    for product in [cls.apple, cls.banana]
                ],
            )
            for date, priority, sequence in picks
        }
        cls.picks = Picking.union(*(cls.picks_by_key.values()))
        for pick in cls.picks:
            pick.with_context(tracking_disable=True).action_confirm()

    def assertFactorised(self, wrong=False):  # pylint: disable=invalid-name
        """Assert that picks are [not] factorised as expected."""
        assertion = self.assertNotEqual if wrong else self.assertEqual
        picks_by_key = {
            key: pick
            for key, pick in self.picks_by_key.items()
            if pick.picking_type_id == self.picking_type_pick
        }
        batches_by_key = {
            (date, priority): picks.mapped("batch_id")
            for (date, priority, sequence), picks in picks_by_key.items()
        }
        assertion(
            set(batches_by_key[(self.today, PRIORITIES[0])].picking_ids),
            set(
                [
                    picks_by_key[(self.today, PRIORITIES[0], 3)],
                    picks_by_key[(self.today, PRIORITIES[0], 2)],
                    picks_by_key[(self.today, PRIORITIES[0], 1)],
                ]
            ),
        )
        assertion(
            set(batches_by_key[(self.today, PRIORITIES[1])].picking_ids),
            set(
                [
                    picks_by_key[(self.today, PRIORITIES[1], 3)],
                    picks_by_key[(self.today, PRIORITIES[1], 2)],
                    picks_by_key[(self.today, PRIORITIES[1], 1)],
                ]
            ),
        )
        assertion(
            set(batches_by_key[(self.tomorrow, PRIORITIES[0])].picking_ids),
            set(
                [
                    picks_by_key[(self.tomorrow, PRIORITIES[0], 3)],
                    picks_by_key[(self.tomorrow, PRIORITIES[0], 2)],
                    picks_by_key[(self.tomorrow, PRIORITIES[0], 1)],
                ]
            ),
        )
        assertion(
            set(batches_by_key[(self.tomorrow, PRIORITIES[1])].picking_ids),
            set(
                [
                    picks_by_key[(self.tomorrow, PRIORITIES[1], 3)],
                    picks_by_key[(self.tomorrow, PRIORITIES[1], 2)],
                    picks_by_key[(self.tomorrow, PRIORITIES[1], 1)],
                ]
            ),
        )

    def test01_setup(self):
        """Verify that setup is as expected."""
        self.assertEqual(len(self.picks), 12)
        for pick in self.picks_by_key.values():
            self.assertIn(pick, self.picks)
            self.assertEqual(pick.state, "confirmed")
            self.assertEqual(len(pick.move_lines), 2)
            self.assertTrue(pick.batch_id)
        self.assertFactorised()

    def test02_refactor(self):
        """Verify that refactoring leaves batches intact."""
        picks = self.picks.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        batches = picks.mapped("batch_id")
        picks.mapped("move_lines").action_refactor()
        self.assertFactorised()

        picks = self.picks.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        self.assertEqual(batches, picks.mapped("batch_id"))

    def test03_recreate(self):
        """Verify that batches can be recreated after deletion."""
        picks = self.picks.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        picks.mapped("batch_id").unlink()
        picks.mapped("move_lines").action_refactor()
        self.assertFactorised()

    def test04_fix(self):
        """Verify that batches can be fixed up."""
        PickingBatch = self.env["stock.picking.batch"]

        picks = self.picks.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        picks_by_key = {
            key: pick
            for key, pick in self.picks_by_key.items()
            if pick.picking_type_id == self.picking_type_pick
        }
        rogue = PickingBatch.create({"name": "Rogue batch"})
        picks_by_key[(self.today, PRIORITIES[1], 1)].batch_id = rogue
        picks_by_key[(self.tomorrow, PRIORITIES[1], 2)].batch_id = rogue
        picks_by_key[(self.today, PRIORITIES[0], 3)].batch_id = False
        picks_by_key[(self.tomorrow, PRIORITIES[0], 1)].batch_id.unlink()
        self.assertFactorised(wrong=True)

        picks.mapped("move_lines").action_refactor()
        self.assertFactorised()


class TestByDate(BaseUDES):
    """Tests for grouping by date."""

    @classmethod
    def setUpClass(cls):
        """Setup for test class."""
        super().setUpClass()

        Picking = cls.env["stock.picking"]

        cls.today = "2019-07-11"
        cls.tomorrow = "2019-07-12"

        cls.picking_type_pick.u_post_confirm_action = "batch_pickings_by_date"

        picks = [
            # Orders today.
            (cls.today, 1),
            (cls.today, 2),
            (cls.today, 3),
            # Orders tomorrow.
            (cls.tomorrow, 1),
            (cls.tomorrow, 2),
            (cls.tomorrow, 3),
        ]
        random.seed(42)
        random.shuffle(picks)

        cls.picks_by_key = {
            (date, sequence): cls.create_picking(
                name="{}/{}".format(date, sequence),
                picking_type=cls.picking_type_pick,
                sequence=sequence,
                products_info=[
                    # Set the date here because cls.create_picking creates the picking
                    # without moves then adds the moves, overwriting the `scheduled_date`.
                    dict(product=product, qty=1, date_expected=date)
                    for product in [cls.apple, cls.banana]
                ],
            )
            for date, sequence in picks
        }
        cls.picks = Picking.union(*(cls.picks_by_key.values()))
        for pick in cls.picks:
            pick.with_context(tracking_disable=True).action_confirm()

    def assertFactorised(self, wrong=False):  # pylint: disable=invalid-name
        """Assert that picks are [not] factorised as expected."""
        assertion = self.assertNotEqual if wrong else self.assertEqual
        picks_by_key = {
            key: pick
            for key, pick in self.picks_by_key.items()
            if pick.picking_type_id == self.picking_type_pick
        }
        batches_by_key = {
            (date,): picks.mapped("batch_id")
            for (date, sequence), picks in picks_by_key.items()
        }
        assertion(
            set(batches_by_key[(self.today,)].picking_ids),
            set(
                [
                    picks_by_key[(self.today, 3)],
                    picks_by_key[(self.today, 2)],
                    picks_by_key[(self.today, 1)],
                ]
            ),
        )
        assertion(
            set(batches_by_key[(self.today,)].picking_ids),
            set(
                [
                    picks_by_key[(self.today, 3)],
                    picks_by_key[(self.today, 2)],
                    picks_by_key[(self.today, 1)],
                ]
            ),
        )
        assertion(
            set(batches_by_key[(self.tomorrow,)].picking_ids),
            set(
                [
                    picks_by_key[(self.tomorrow, 3)],
                    picks_by_key[(self.tomorrow, 2)],
                    picks_by_key[(self.tomorrow, 1)],
                ]
            ),
        )
        assertion(
            set(batches_by_key[(self.tomorrow,)].picking_ids),
            set(
                [
                    picks_by_key[(self.tomorrow, 3)],
                    picks_by_key[(self.tomorrow, 2)],
                    picks_by_key[(self.tomorrow, 1)],
                ]
            ),
        )

    def test01_setup(self):
        """Verify that setup is as expected."""
        self.assertEqual(len(self.picks), 6)
        for pick in self.picks_by_key.values():
            self.assertIn(pick, self.picks)
            self.assertEqual(pick.state, "confirmed")
            self.assertEqual(len(pick.move_lines), 2)
            self.assertTrue(pick.batch_id)
        self.assertFactorised()

    def test02_refactor(self):
        """Verify that refactoring leaves batches intact."""
        picks = self.picks.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        batches = picks.mapped("batch_id")
        picks.mapped("move_lines").action_refactor()
        self.assertFactorised()

        picks = self.picks.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        self.assertEqual(batches, picks.mapped("batch_id"))

    def test03_recreate(self):
        """Verify that batches can be recreated after deletion."""
        picks = self.picks.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        picks.mapped("batch_id").unlink()
        picks.mapped("move_lines").action_refactor()
        self.assertFactorised()

    def test04_fix(self):
        """Verify that batches can be fixed up."""
        PickingBatch = self.env["stock.picking.batch"]

        picks = self.picks.filtered(
            lambda x: x.picking_type_id == self.picking_type_pick
        )
        picks_by_key = {
            key: pick
            for key, pick in self.picks_by_key.items()
            if pick.picking_type_id == self.picking_type_pick
        }
        rogue = PickingBatch.create({"name": "Rogue batch"})
        picks_by_key[(self.today, 1)].batch_id = rogue
        picks_by_key[(self.tomorrow, 2)].batch_id = rogue
        picks_by_key[(self.today, 3)].batch_id = False
        picks_by_key[(self.tomorrow, 1)].batch_id.unlink()
        self.assertFactorised(wrong=True)

        picks.mapped("move_lines").action_refactor()
        self.assertFactorised()
