from . import common


class TestReplen(common.BaseUDES):

    @classmethod
    def setUpClass(cls):
        super(TestReplen, cls).setUpClass()
        # Create an orderpoint with values
        cls.stock = 100
        cls.op = cls.create_orderpoint(cls.apple, cls.test_output_location_01,
                                       5, 10)
        cls.quant = cls.create_quant(cls.apple.id, cls.test_location_01.id,
                                     cls.stock)
        cls.Picking = cls.env['stock.picking']
        cls.Procurement = cls.env['procurement.group']

    @classmethod
    def get_apples(cls):
        """ Get available quantity of apples in test_output_location_01 """
        Stock = cls.env['stock.quant']
        domain = [('product_id', '=', cls.apple.id),
                  ('location_id', 'child_of', cls.test_output_location_01.id)]
        quants = Stock.search(domain)
        return sum(quants.mapped('quantity')) -\
               sum(quants.mapped('reserved_quantity'))

    def test01_replen_full(self):
        """
        Tests full replen pick creation and completion
        """
        Procurement = self.Procurement
        Picking = self.Picking
        quant = self.quant

        # Run orderpoints
        Procurement._procure_orderpoint_confirm()

        # Verify there are is now a picking to refill max apples
        pickings = Picking.search([])
        self.assertEqual(len(pickings), 1)
        picking = pickings[0]
        move = pickings.mapped('move_lines')

        self.assertEqual(move.product_id, self.apple)
        self.assertEqual(move.product_uom_qty, self.op.product_max_qty)

        # Ensure that no more will be ordered if picking exists already
        Procurement._procure_orderpoint_confirm()
        self.assertEqual(len(Picking.search([])), 1)

        # Complete the picking
        picking.action_assign()
        for move in picking.move_lines:
            move.quantity_done = move.product_uom_qty
        picking.action_done()

        # Verify picking is done
        self.assertEqual(picking.state, 'done')

        # Verify new quantities are correct
        self.assertEqual(quant.quantity, self.stock-self.op.product_max_qty)
        self.assertEqual(self.get_apples(), self.op.product_max_qty)

        # Ensure that no more will be ordered once picking complete
        Procurement._procure_orderpoint_confirm()
        self.assertEqual(len(Picking.search([])), 1)

    def test02_create_replen_partial(self):
        """ Test quantity of partial replen is correct """
        Procurement = self.Procurement
        Picking = self.Picking

        # Create quantity of stock in pick location
        in_pick = 4
        self.create_quant(self.apple.id, self.test_output_location_01.id,
                          in_pick)

        # Run orderpoints
        Procurement._procure_orderpoint_confirm()

        # Verify picking exists
        pickings = Picking.search([])
        self.assertEqual(len(pickings), 1)

        # Verify the picking will top up the location to the max value
        move = pickings.mapped('move_lines')
        self.assertEqual(move.product_id, self.apple)
        self.assertEqual(move.product_uom_qty, self.op.product_max_qty-in_pick)
