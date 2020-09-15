# -*- coding: utf-8 -*-
from odoo.tests import common


import logging

_logger = logging.getLogger(__name__)


@common.at_install(False)
@common.post_install(True)
class BaseUDES(common.SavepointCase):
    @classmethod
    def setUpClass(cls):
        super(BaseUDES, cls).setUpClass()

        # Products
        ## Untracked
        cls.apple = cls.create_product("Apple")
        cls.banana = cls.create_product("Banana")
        cls.cherry = cls.create_product("Cherry")
        cls.damson = cls.create_product("Damson")
        cls.elderberry = cls.create_product("Elderberry")
        cls.fig = cls.create_product("Fig")
        cls.grape = cls.create_product("Grape")

        ## Serial/Lot tracking
        cls.strawberry = cls.create_product("Strawberry", tracking="serial")
        cls.tangerine = cls.create_product("Tangerine", tracking="lot")
        cls.setup_default_warehouse()

    @classmethod
    def setup_default_warehouse(cls):
        """ Sets a warehouse with:
            * test locations
                test_input_01, test_stock_01, test_stock_02, test_output_01
            * all picking types as a copy of the default with TEST_ prepended
            * a simple inbound route goods_in->putaway
            * a simple outbound route pick->goods_out
        """
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.company = cls.warehouse.company_id
        cls._setup_picking_types()
        cls._setup_locations()
        cls._setup_routes()

    @classmethod
    def _setup_picking_types(cls):
        """ Additional test picking types - prepended with TEST """
        cls._set_test_picking_type("in", "goods_in")
        cls._set_test_picking_type("pick")
        # this order is important as int is overwritten
        cls._set_test_picking_type("int", "putaway")
        cls._set_test_picking_type("int", "internal")
        cls._set_test_picking_type("out", "goods_out")
        cls._set_test_picking_type("out", "trailer_dispatch")

    @classmethod
    def _set_test_picking_type(cls, ptype, name=None):
        if name is None:
            name = ptype

        copy_vals = {"name": "TEST_{}".format(name.upper()), "active": True}
        wh_attr = getattr(cls.warehouse, "{}_type_id".format(ptype))
        new_pt = wh_attr.copy(copy_vals)
        setattr(cls, "picking_type_{}".format(name), new_pt)
        setattr(cls.warehouse, "{}_type_id".format(ptype), new_pt)

    @classmethod
    def create_product(cls, name, **kwargs):
        """ Create and return a product """
        Product = cls.env["product.product"]
        vals = {
            "name": "Test product {}".format(name),
            "barcode": "product{}".format(name),
            "default_code": "product{}".format(name),
            "type": "product",
        }
        vals.update(kwargs)
        return Product.create(vals)

    @classmethod
    def create_quant(cls, product_id, location_id, qty, lot_name=None, **kwargs):
        """ Create and return a quant of a product at location """
        Quant = cls.env["stock.quant"]
        vals = {
            "product_id": product_id,
            "location_id": location_id,
            "quantity": qty,
        }
        if lot_name:
            lot = cls.create_lot(product_id, lot_name)
            vals["lot_id"] = lot.id
        vals.update(kwargs)
        return Quant.create(vals)

    @classmethod
    def create_lot(cls, product_id, lot_name, **kwargs):
        Lot = cls.env["stock.production.lot"]

        vals = {
            "name": lot_name,
            "product_id": product_id,
        }
        if "company_id" not in kwargs:
            vals["company_id"] = cls.company.id
        vals.update(kwargs)
        return Lot.create(vals)

    @classmethod
    def create_package(self, **kwargs):
        """ Create and return a new package """
        Package = self.env["stock.quant.package"]
        vals = {}
        vals.update(kwargs)
        return Package.create(vals)

    @classmethod
    def _setup_locations(cls):
        """ Test Locations """
        Location = cls.env["stock.location"]

        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        # Make it non-view to ease default routes
        cls.stock_location.write({"usage": "internal"})
        cls.received_location = cls.stock_location.copy({"name": "TEST_INPUT"})
        cls.test_received_locations = Location.create(
            [
                {
                    "name": "Test received location 01",
                    "barcode": "LRTEST01",
                    "location_id": cls.received_location.id,
                },
                {
                    "name": "Test received location 02",
                    "barcode": "LRTEST02",
                    "location_id": cls.received_location.id,
                },
            ]
        )
        cls.test_received_location_01, cls.test_received_location_02 = cls.test_received_locations

        cls.test_stock_locations = Location.create(
            [
                {
                    "name": "Test stock location 01",
                    "barcode": "LSTEST01",
                    "location_id": cls.stock_location.id,
                },
                {
                    "name": "Test stock location 02",
                    "barcode": "LSTEST02",
                    "location_id": cls.stock_location.id,
                },
            ]
        )
        cls.test_stock_location_01, cls.test_stock_location_02 = cls.test_stock_locations

        cls.warehouse_location = Location.create({"name": "Warehouse"})

        cls.out_location = cls.stock_location.copy({"name": "TEST_GOODS_OUT"})
        cls.test_goodsout_locations = Location.create(
            [
                {
                    "name": "Test Goods Out location 01",
                    "barcode": "LGOTEST01",
                    "location_id": cls.out_location.id,
                },
                {
                    "name": "Test Goods Out location 02",
                    "barcode": "LGOTEST02",
                    "location_id": cls.out_location.id,
                },
            ]
        )
        cls.test_goodsout_location_01, cls.test_goodsout_location_02 = cls.test_goodsout_locations

        cls.trailer_location = cls.picking_type_goods_out.default_location_dest_id.copy(
            {"name": "TEST_OUT_TRAILER", "active": True, "location_id": cls.warehouse_location.id,}
        )
        cls.test_trailer_locations = Location.create(
            [
                {
                    "name": "Test trailer location 01",
                    "barcode": "LTTEST01",
                    "location_id": cls.trailer_location.id,
                },
                {
                    "name": "Test trailer location 02",
                    "barcode": "LTTEST02",
                    "location_id": cls.trailer_location.id,
                },
            ]
        )
        cls.test_trailer_location_01, cls.test_trailer_location_02 = cls.test_trailer_locations

        cls.test_out_locations = (
            cls.test_goodsout_location_01
            + cls.test_trailer_location_01
            + cls.test_goodsout_location_02
            + cls.test_trailer_location_02
        )

    @classmethod
    def _setup_routes(cls):
        """ Default source and dest for picking types """
        cls.picking_type_goods_in.write(
            {
                "default_location_src_id": cls.env.ref("stock.stock_location_suppliers").id,
                "default_location_dest_id": cls.received_location.id,
            }
        )

        cls.picking_type_putaway.write(
            {
                "default_location_src_id": cls.received_location.id,
                "default_location_dest_id": cls.stock_location.id,
            }
        )

        cls.picking_type_internal.write(
            {
                "default_location_src_id": cls.stock_location.id,
                "default_location_dest_id": cls.stock_location.id,
            }
        )

        cls.picking_type_pick.write(
            {
                "default_location_src_id": cls.stock_location.id,
                "default_location_dest_id": cls.out_location.id,
            }
        )

        cls.picking_type_goods_out.write(
            {
                "default_location_src_id": cls.out_location.id,
                "default_location_dest_id": cls.trailer_location.id,
            }
        )

        cls.picking_type_trailer_dispatch.write(
            {
                "default_location_src_id": cls.trailer_location.id,
                "default_location_dest_id": cls.env.ref("stock.stock_location_customers").id,
            }
        )

        cls.create_simple_inbound_route(cls.picking_type_goods_in, cls.picking_type_putaway)
        cls.create_simple_outbound_route(
            cls.picking_type_pick, cls.picking_type_goods_out, cls.picking_type_trailer_dispatch
        )

    @classmethod
    def create_simple_inbound_route(cls, picking_type_in, picking_type_internal):
        Route = cls.env["stock.location.route"]
        Sequence = cls.env["ir.sequence"]
        Rule = cls.env["stock.rule"]

        route_vals = {
            "name": "TestPutaway",
            "sequence": 10,
            "product_selectable": False,
            "warehouse_selectable": True,
            "warehouse_ids": [(6, 0, [picking_type_internal.warehouse_id.id])],
        }
        cls.route_in = Route.create(route_vals)

        # PUTAWAY
        sequence_putaway = Sequence.create(
            {"name": "TestPutaway", "prefix": "TESTPUT", "padding": 5}
        )
        picking_type_internal.write({"sequence_id": sequence_putaway.id, "sequence": 13})

        location_path_vals = {
            "name": "TestPutaway",
            "route_id": cls.route_in.id,
            "sequence": 20,
            "action": "push",
            "location_id": picking_type_in.default_location_dest_id.id,
            "location_src_id": picking_type_internal.default_location_dest_id.id,
            "picking_type_id": picking_type_internal.id,
        }
        cls.push_putaway = Rule.create(location_path_vals)

    @classmethod
    def create_simple_outbound_route(
        cls, picking_type_pick, picking_type_out, picking_type_trailer
    ):
        Route = cls.env["stock.location.route"]
        Sequence = cls.env["ir.sequence"]
        Location = cls.env["stock.location"]
        Rule = cls.env["stock.rule"]

        route_vals = {
            "name": "TestGoodsOut",
            "sequence": 10,
            "product_selectable": False,
            "warehouse_selectable": True,
            "warehouse_ids": [(6, 0, [picking_type_out.warehouse_id.id])],
        }
        cls.route_out = Route.create(route_vals)

        # Goods out
        sequence_vals = {
            "name": "TestGoodsOut",
            "prefix": "TESTGOODSOUT",
            "padding": 5,
        }
        sequence_goodsout = Sequence.create(sequence_vals)

        out_vals = {
            "sequence_id": sequence_goodsout.id,
            "sequence": 13,
        }
        picking_type_out.write(out_vals)

        # set goods-out source location = pick dest location
        picking_type_out.default_location_src_id = picking_type_pick.default_location_dest_id
        if not picking_type_out.default_location_dest_id:
            picking_type_out.default_location_dest_id = Location.search(
                [("name", "=", "Customers")]
            )[0]

        location_path_vals = {
            "name": "TestGoodsOut",
            "route_id": cls.route_out.id,
            "sequence": 20,
            "location_src_id": picking_type_pick.default_location_dest_id.id,
            "location_id": picking_type_out.default_location_dest_id.id,
            "picking_type_id": picking_type_out.id,
            "action": "pull_push",
        }
        path_out_goodsout = Rule.create(location_path_vals)

        cls.rule_pick = Rule.create(
            {
                "name": "TestPick",
                "route_id": cls.route_out.id,
                "picking_type_id": picking_type_pick.id,
                "location_id": picking_type_pick.default_location_dest_id.id,
                "location_src_id": picking_type_out.default_location_dest_id.id,
                "action": "pull",
                "procure_method": "make_to_stock",
            }
        )
        cls.rule_out = Rule.create(
            {
                "name": "TestOut",
                "route_id": cls.route_out.id,
                "picking_type_id": picking_type_out.id,
                "location_id": picking_type_out.default_location_dest_id.id,
                "location_src_id": picking_type_out.default_location_src_id.id,
                "action": "pull",
                "procure_method": "make_to_order",
            }
        )

    @classmethod
    def _setup_check_location(cls):
        Location = cls.env["stock.location"]
        cls.check_location = cls.picking_type_pick.default_location_dest_id.copy(
            {"name": "TEST_CHECK", "active": True,}
        )
        cls.test_check_location_01 = Location.create(
            {
                "name": "Test check location 01",
                "barcode": "LTESCHECK01",
                "location_id": cls.check_location.id,
            }
        )

    @classmethod
    def create_picking(
        cls,
        picking_type,
        products_info=None,
        confirm=False,
        assign=False,
        create_batch=False,
        **kwargs
    ):
        """ Create and return a picking for the given picking_type """
        Picking = cls.env["stock.picking"]
        return Picking.create_picking(
            picking_type,
            products_info=products_info,
            confirm=confirm,
            assign=assign,
            create_batch=create_batch,
            **kwargs
        )

    @classmethod
    def create_move(cls, pickings, products_info, **kwargs):
        """
        Create and return move(s) for the given pickings and products using
        _prepare_move and _create_move helper methods from stock.picking
        """
        Picking = cls.env["stock.picking"]

        if not all(isinstance(el, list) for el in products_info):
            # Convert the products_info to a list of lists
            products_info = [products_info]

        move_values = Picking._prepare_move(pickings, products_info, **kwargs)
        moves = Picking._create_move(move_values)
        return moves

    @classmethod
    def create_move_line(cls, move, qty, **kwargs):
        """
        Create and return a single move line for the given move and quantity using
        _prepare_move_line and _create_move_line helper methods from stock.move
        """
        Move = cls.env["stock.move"]

        move_line_values = Move._prepare_move_line(move, qty, **kwargs)
        move_line = Move._create_move_line(move_line_values)
        return move_line

    @classmethod
    def create_move_lines(cls, moves_info, **kwargs):
        """
        Create and return move line(s) for the given moves_info using
        _prepare_move_lines and _create_move_line helper methods from stock.move
        """
        Move = cls.env["stock.move"]

        move_line_values = Move._prepare_move_lines(moves_info, **kwargs)
        move_lines = Move._create_move_line(move_line_values)
        return move_lines

    @classmethod
    def create_company(cls, name, **kwargs):
        """ Create and return a company """
        Company = cls.env["res.company"]
        vals = {"name": name}
        vals.update(kwargs)
        return Company.create(vals)

    @classmethod
    def create_user(cls, name, login, **kwargs):
        """ Create and return a user """
        User = cls.env["res.users"]
        # Creating user without company
        # takes company from current user
        vals = {
            "name": name,
            "login": login,
        }
        vals.update(kwargs)
        user = User.create(vals)

        # some action require email setup even if the email is not really sent
        user.partner_id.email = login

        return user

    @classmethod
    def update_move(cls, move, qty_done, **kwargs):
        """ Update a move with qty done
        """
        vals = {
            "quantity_done": qty_done + move["quantity_done"],
        }
        vals.update(kwargs)
        return move.update(vals)

    @classmethod
    def create_batch(cls, user=None, **kwargs):
        Batch = cls.env["stock.picking.batch"]

        vals = {}
        if user is not False:
            if user is None:
                user = cls.env.user
            vals = {"user_id": user.id}

        vals.update(kwargs)
        return Batch.create(vals)

    @classmethod
    def create_partner(cls, name, **kwargs):
        Partner = cls.env['res.partner']
        vals = {'name': name}
        vals.update(kwargs)
        return Partner.create(vals)

    @classmethod
    def complete_picking(cls, picking, validate=True):
        """ Marks a picking and all its moves as done """
        for move_line in picking.move_line_ids:
            if move_line.state == "assigned":
                move_line.qty_done = move_line.product_uom_qty
        if validate:
            picking.action_done()

    @classmethod
    def get_picking_names(cls, pickings):
        """
        Takes the names of the supplied pickings and returns
        a string with all names comma seperated
        """
        names = pickings.mapped("name")
        return ", ".join(map(str, names))
