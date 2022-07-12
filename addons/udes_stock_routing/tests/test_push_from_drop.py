from odoo.addons.udes_stock.tests.common import BaseUDES


class PushFromDropBase(BaseUDES):
    @classmethod
    def setUpClass(cls):
        """Setup branching Inbound flow
        Goods In: Customers to Input
        Putaway: Input to Stock

        Putaway Push: Input/Received to Stock
        Damaged Push: Input/Damaged to QC

        Putaway Push and Damaged Push both push from drop.
        """
        super(PushFromDropBase, cls).setUpClass()

        Location = cls.env["stock.location"]
        Push = cls.env["stock.rule"]

        input_zone = cls.env.ref("stock.stock_location_company")
        input_zone.usage = "view"
        cls.picking_type_goods_in.default_location_dest_id = input_zone.id
        cls.picking_type_putaway.default_location_src_id = input_zone.id

        cls.received_location.location_id = input_zone
        cls.received_damaged_location = Location.create(
            {
                "name": "TEST_RECEIVEDDAMAGED",
                "barcode": "LTESTRECEIVEDDAMAGED",
                "location_id": input_zone.id,
            }
        )

        cls.location_qc_zone = Location.create(
            {
                "name": "QC Stock",
                "usage": "view",
            }
        )
        cls.location_qc_01 = Location.create(
            {
                "name": "QC Stock 01",
                "barcode": "LTESTQC01",
                "location_id": cls.location_qc_zone.id,
            }
        )

        # Update path_in_putaway to use correct location:
        cls.push_putaway.write(
            {
                "location_src_id": cls.received_location.id,
                "u_push_on_drop": True,
            }
        )

        cls.push_damaged_putaway = Push.create(
            {
                "name": "TestDamagedPutaway",
                "route_id": cls.route_in.id,
                "sequence": 30,
                "location_src_id": cls.received_damaged_location.id,
                "location_id": cls.location_qc_zone.id,
                "picking_type_id": cls.picking_type_putaway.id,
                "u_push_on_drop": True,
                "action": "push",
            }
        )

    def setUp(self):
        """
        Ensure all tests start with push_from_drop set to True
        """
        super(PushFromDropBase, self).setUp()
        self.push_putaway.u_push_on_drop = True
        self.push_damaged_putaway.u_push_on_drop = True


class TestGetPathFromLocation(PushFromDropBase):
    """Tests for the stock.rule.get_path_from_location method in
    isolation"""

    def test_no_route(self):
        """Test that get_path_from_location returns an empty recordset when no
        matching path is found"""
        Push = self.env["stock.rule"]
        self.push_damaged_putaway.unlink()
        move = Push.get_path_from_location(self.received_damaged_location)
        self.assertFalse(move)

    def test_one_route(self):
        """Test that get_path_from_location returns a single matching path when
        one exists"""
        Push = self.env["stock.rule"]
        move = Push.get_path_from_location(self.received_damaged_location)
        self.assertEqual(move, self.push_damaged_putaway)

    def test_many_routes(self):
        """Test that get_path_from_location returns a single matching path when
        more than one possible match exists, and the returned value is the one
        for the closest parent of the search location.
        """
        Push = self.env["stock.rule"]
        input_zone = self.env.ref("stock.stock_location_company")

        # create new push from the Input zone.
        Push.create(
            {
                "name": "TestPushMultiRoute",
                "route_id": self.route_in.id,
                "sequence": 40,
                "location_src_id": input_zone.id,
                "location_id": self.location_qc_zone.id,
                "picking_type_id": self.picking_type_putaway.id,
                "u_push_on_drop": True,
                "action": "push",
            }
        )
        # Damaged route found correctly
        move = Push.get_path_from_location(self.received_damaged_location)
        self.assertEqual(move, self.push_damaged_putaway)

        # Non-damaged route found correctly
        move = Push.get_path_from_location(self.received_location)
        self.assertEqual(move, self.push_putaway)


class TestCreateMovesForPush(PushFromDropBase):
    """Tests for the stock.move._create_moves_for_push method in
    isolation"""

    def setUp(self):
        """Create a picking to work with for tests"""
        super(TestCreateMovesForPush, self).setUp()
        products_info = [
            {"product": self.apple, "uom_qty": 10},
            {"product": self.banana, "uom_qty": 99},
        ]
        self.goods_in = self.create_picking(
            self.picking_type_goods_in, products_info=products_info, confirm=True, assign=True
        )
        self.move_lines = self.goods_in.move_line_ids
        for ml in self.move_lines:
            ml.write({"qty_done": ml.product_uom_qty})

    def test_correct_move_qty(self):
        """Test that created moves have the correct quantity"""
        Move = self.env["stock.move"]
        moves = Move._create_moves_for_push(self.push_damaged_putaway, self.move_lines)
        self.assertEqual(len(moves), 2)
        new_apple_move = moves.filtered(lambda m: m.product_id.id == self.apple.id)
        new_banana_move = moves.filtered(lambda m: m.product_id.id == self.banana.id)

        self.assertEqual(new_apple_move.product_uom_qty, 10)
        self.assertEqual(new_banana_move.product_uom_qty, 99)

    def test_correct_move_locations(self):
        """Test that created moves have the correct src and dest locations"""
        Move = self.env["stock.move"]
        moves = Move._create_moves_for_push(self.push_damaged_putaway, self.move_lines)

        self.assertEqual(len(moves), 2)
        for record in moves:
            with self.subTest(record=record):
                self.assertEqual(record.location_id, self.received_damaged_location)
                self.assertEqual(record.location_dest_id, self.location_qc_zone)

    def test_correct_move_orig_info(self):
        """Test that created moves set move_orig_ids correctly"""
        Move = self.env["stock.move"]

        moves = self.goods_in.move_lines
        apple_move = moves.filtered(lambda m: m.product_id.id == self.apple.id)
        banana_move = moves.filtered(lambda m: m.product_id.id == self.banana.id)
        self.assertFalse(apple_move.move_dest_ids)
        self.assertFalse(banana_move.move_dest_ids)

        moves = Move._create_moves_for_push(self.push_damaged_putaway, self.move_lines)

        self.assertEqual(len(moves), 2)
        new_apple_move = moves.filtered(lambda m: m.product_id.id == self.apple.id)
        new_banana_move = moves.filtered(lambda m: m.product_id.id == self.banana.id)
        self.assertEqual(new_apple_move.move_orig_ids, apple_move)
        self.assertEqual(new_banana_move.move_orig_ids, banana_move)


class TestPushFromDrop(PushFromDropBase):
    """Tests for the full push from drop functionality"""

    def setUp(self):
        """Create a picking to work with for tests"""
        super(TestPushFromDrop, self).setUp()
        products_info = [
            {"product": self.apple, "uom_qty": 10},
            {"product": self.banana, "uom_qty": 99},
        ]
        self.goods_in = self.create_picking(
            self.picking_type_goods_in, products_info=products_info, confirm=True, assign=True
        )

        self.move_lines = self.goods_in.move_line_ids
        for ml in self.move_lines:
            ml.write({"qty_done": ml.product_uom_qty})

    def test_picking_has_correct_src_and_dest(self):
        """Test that pickings created by push from drop have the src and dest
        location of the rule that created them."""
        for ml in self.move_lines:
            ml.write({"location_dest_id": self.received_damaged_location.id})
        putaway = self._complete_picking_and_return_next_picking_id()
        self.assertEqual(len(putaway), 1)
        self.assertEqual(putaway.location_id, self.received_damaged_location)
        self.assertEqual(putaway.location_dest_id, self.location_qc_zone)

    def test_no_push_rule(self):
        """Test that when no push rule exists nothing is created"""
        (self.push_damaged_putaway + self.push_putaway).unlink()
        putaway = self._complete_picking_and_return_next_picking_id()
        self.assertEqual(len(putaway), 0)

    def test_stock_is_reserved(self):
        """Test that when a push occurs, stock is reserved and available to move
        further."""
        putaway = self._complete_picking_and_return_next_picking_id()
        self.assertEqual(len(putaway), 1)
        self.assertEqual(putaway.state, "assigned")

    def test_picking_can_be_completed(self):
        """Test that when a picking is created by push_from_drop it can be
        validated."""
        putaway = self._complete_picking_and_return_next_picking_id()
        self.assertEqual(len(putaway), 1)
        self.assertEqual(putaway.state, "assigned")
        for ml in putaway.move_line_ids:
            ml.write({"qty_done": ml.product_uom_qty, "location_dest_id": self.location_qc_01.id})
        putaway._action_done()
        self.assertEqual(putaway.state, "done")

    def test_picking_info_propagated(self):
        """Test that when a picking is created by push_from_drop it contains
        the origin and partner of the source picking."""
        new_partner = self.create_partner("Test partner")
        self.goods_in.partner_id = new_partner
        new_origin = "Test origin"
        self.goods_in.origin = new_origin
        putaway = self._complete_picking_and_return_next_picking_id()
        self.assertEqual(putaway.origin, new_origin)
        self.assertEqual(putaway.partner_id, new_partner)

    def _complete_picking_and_return_next_picking_id(self):
        for ml in self.move_lines:
            ml.write({"location_dest_id": self.received_damaged_location.id})
        self.goods_in._action_done()
        return self.goods_in.u_next_picking_ids


class InitialDemandTestCase(PushFromDropBase):
    """Unit tests for initial demand behaviour."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        products_info = [{"product": cls.apple, "uom_qty": 20}]
        cls.goods_in_picking = cls.create_picking(
            picking_type=cls.picking_type_goods_in,
            products_info=products_info,
            confirm=True,
            assign=True,
        )

    def test_sets_initial_demand_on_push_move_to_quantity_done_of_previous_move(self):
        """Set the initial demand of a push move to the quantity done of the preceding move."""
        for ml in self.goods_in_picking.move_line_ids:
            ml.write(
                {"qty_done": ml.product_uom_qty, "location_dest_id": self.received_location.id}
            )
        self.goods_in_picking._action_done()
        putaway_move = self.goods_in_picking.u_next_picking_ids.move_lines

        self.assertEqual(putaway_move.u_uom_initial_demand, 20.0)

    def test_sets_initial_demand_on_push_move_to_quantity_done_of_previous_partially_completed_move(
        self,
    ):
        """Set the initial demand of a push move to the quantity done of the partially completed preceding move."""
        for ml in self.goods_in_picking.move_line_ids:
            ml.write({"qty_done": 10.0, "location_dest_id": self.received_location.id})
        self.goods_in_picking._action_done()
        putaway_move = self.goods_in_picking.u_next_picking_ids.move_lines

        self.assertEqual(putaway_move.u_uom_initial_demand, 10.0)
