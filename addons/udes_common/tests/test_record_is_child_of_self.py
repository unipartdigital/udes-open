"""Tests for `record_is_child_of_self`"""

from .common import CommonBase


class TestRecordIsChildOfSelf(CommonBase):
    """Tests for `record_is_child_of_self` method on BaseModel"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_partner_categories()
        cls._setup_partners()

    @classmethod
    def _setup_partner_categories(cls):
        """Create hierarchy of categories"""
        cls.category_a = cls.create_partner_category("A")
        cls.category_a1 = cls.create_partner_category("A1", parent_id=cls.category_a.id)
        cls.category_a1x = cls.create_partner_category("A1-X", parent_id=cls.category_a1.id)

        cls.category_b = cls.create_partner_category("B")
        cls.category_b1 = cls.create_partner_category("B1", parent_id=cls.category_b.id)
        cls.category_b2 = cls.create_partner_category("B2", parent_id=cls.category_b.id)

    @classmethod
    def _setup_partners(cls):
        """Create partner records"""
        cls.partner_a = cls.create_partner("Test Partner A", category_id=cls.category_a)
        cls.partner_b = cls.create_partner("Test Partner B", category_id=cls.category_b)

    def _assert_record_is_child(self, parent, child):
        """Assert that the supplied `parent` is an ancestor of the supplied `child` record"""
        parent.ensure_one()
        child.ensure_one()
        self.assertTrue(
            parent.record_is_child_of_self(child),
            f"{child.name} should be considered a child of {parent.name}",
        )

    def _assert_record_is_not_child(self, parent, child):
        """Assert that the supplied `parent` is not an ancestor of the supplied `child` record"""
        parent.ensure_one()
        child.ensure_one()
        self.assertFalse(
            parent.record_is_child_of_self(child),
            f"{child.name} should be not considered a child of {parent.name}",
        )

    def test_check_record_is_child_against_itself(self):
        """Assert that a record is considered a child of itself"""
        self._assert_record_is_child(self.category_a, self.category_a)

    def test_check_record_is_considered_child_against_parent(self):
        """Assert that record is considered a child of its direct parent"""
        self._assert_record_is_child(self.category_a, self.category_a1)

    def test_check_record_is_considered_child_against_top_ancestor(self):
        """Assert that record is considered a child of its top ancestor"""
        self._assert_record_is_child(self.category_a, self.category_a1x)

    def test_check_record_is_not_considered_child_against_different_hierarchy(self):
        """Assert that any category in the "B" is not considered a child of category A"""
        b_categories = self.category_b | self.category_b1 | self.category_b2
        for category in b_categories:
            with self.subTest(category=category):
                self._assert_record_is_not_child(self.category_a, category)

    def test_records_of_different_models_cannot_be_checked(self):
        """
        Assert that a TypeError is raised if a record is checked to be the child
        of a record from a different model
        """
        with self.assertRaises(TypeError) as e:
            self._assert_record_is_child(self.category_a, self.partner_a)
        self.assertEqual(
            e.exception.args[0],
            f"Unable to check if {self.partner_a} is child of {self.category_a}."
            " Records are from different models.",
        )

    def test_records_without_parent_path_cannot_be_checked(self):
        """
        Assert that a ValueError is raised if a record is checked to be the child of another record
        when their model doesn't have the parent_path field.
        """
        with self.assertRaises(ValueError) as e:
            self._assert_record_is_child(self.partner_a, self.partner_b)
        self.assertEqual(
            e.exception.args[0],
            f"Unable to check if {self.partner_b} is child of {self.partner_a}."
            " Model 'res.partner' doesn't have a parent/child hierarchy.",
        )
