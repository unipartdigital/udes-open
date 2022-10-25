from . import common


class TestPickingPreventDateDone(common.BaseUDES):
    """
    Test that if date_done is set and not all moves are in done state an issue is
    created with the traceback as description.
    """

    @classmethod
    def setUpClass(cls):
        super(TestPickingPreventDateDone, cls).setUpClass()
        cls.prevent_name = "Open Pickings with Date Done"

    @classmethod
    def prepare_move_vals(cls, product, qty, picking_type, state="draft", **kwargs):
        vals = {
            "product_id": product.id,
            "name": product.name,
            "product_uom": product.uom_id.id,
            "product_uom_qty": qty,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
            "picking_type_id": picking_type.id,
            "state": state,
        }
        vals.update(kwargs)
        return vals

    def test_prevent_date_done_project_doesnt_exist(self):
        """
        Testing that at first the project is created and after using the same project
        for other issues.
        """
        Project = self.env["project.project"]
        prevent_project = Project.search([("name", "=", self.prevent_name)], limit=1)
        self.assertFalse(prevent_project, f"{self.prevent_name} shouldn't exist")

    def test_date_done_emptied(self):
        """
        Create a pick with date_done in vals and some moves where not all moves are done.
        Trying to replicate a possible issue on refactoring done moves.

        Testing that date_done is emptied and an issue is created in the specified project.
        Testing that if a second issue is created it will be added on the same project.
        """
        Project = self.env["project.project"]

        kwargs = {
            "date_done": "2022-10-19 01:12:13",
            "move_lines": [
                (
                    0,
                    0,
                    self.prepare_move_vals(self.apple, 5, self.picking_type_in, "done"),
                ),
                (
                    0,
                    0,
                    self.prepare_move_vals(
                        self.banana, 3, self.picking_type_in, "done"
                    ),
                ),
                (
                    0,
                    0,
                    self.prepare_move_vals(
                        self.cherry, 4, self.picking_type_in, "assigned"
                    ),
                ),
            ],
        }
        pick_a = self.create_picking(self.picking_type_in, **kwargs)
        self.assertFalse(
            pick_a.date_done, f"{pick_a.name} date_done field should be emptied"
        )
        prevent_project = Project.search([("name", "=", self.prevent_name)])
        self.assertEqual(len(prevent_project), 1)
        self.assertEqual(len(prevent_project.task_ids), 1)
        pick_b = self.create_picking(self.picking_type_in, **kwargs)
        self.assertFalse(
            pick_b.date_done, f"{pick_b.name} date_done field should be emptied"
        )
        prevent_project = Project.search([("name", "=", self.prevent_name)])
        self.assertEqual(len(prevent_project), 1)
        self.assertEqual(len(prevent_project.task_ids), 2)

    def test_date_done_not_emptied(self):
        """
        Testing that date done is not emptied in case that all moves are done
        """
        date_done = "2022-10-19 05:25:00"
        kwargs = {
            "date_done": date_done,
            "move_lines": [
                (
                    0,
                    0,
                    self.prepare_move_vals(self.apple, 5, self.picking_type_in, "done"),
                ),
                (
                    0,
                    0,
                    self.prepare_move_vals(
                        self.banana, 3, self.picking_type_in, "done"
                    ),
                ),
                (
                    0,
                    0,
                    self.prepare_move_vals(
                        self.cherry, 4, self.picking_type_in, "done"
                    ),
                ),
            ],
        }
        pick = self.create_picking(self.picking_type_in, **kwargs)
        self.assertEqual(pick.date_done, date_done)
