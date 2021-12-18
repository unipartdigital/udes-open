from odoo.tests import common
from odoo.exceptions import ValidationError


@common.at_install(False)
@common.post_install(True)
class TestResArchivingRestriction(common.SavepointCase):
    """
    Tests for res.archiving.restriction model for superuser and normal user
    Ensure backend writes to active field are blocked
    appropriately based on configured restrictions

    We do not unittest UI changes (removal of archive action, and smart buttons)
    based on configured restrictions
    """

    @classmethod
    def setUpClass(cls):
        super(TestResArchivingRestriction, cls).setUpClass()
        cls.ResArchivingRestriction = cls.env["res.archiving.restriction"]

        ProductProduct = cls.env["product.product"]
        ResUsers = cls.env["res.users"]
        ResPartner = cls.env["res.partner"]

        cls.product_a = ProductProduct.create(dict(name="Product A", default_code="code_a"))

        normal_user_partner = ResPartner.create(dict(name="Bob"))
        cls.normal_user = ResUsers.create(
            dict(login="bob", email="bob@bob.com", partner_id=normal_user_partner.id)
        )
        cls.product_model_id = cls.env.ref("product.model_product_product").id
        cls.group_employee_id = cls.env.ref("base.group_user").id
        cls.group_debug_id = cls.env.ref("udes_security.group_debug_user").id
        cls.group_inbound_id = cls.env.ref("udes_stock.group_inbound_user").id

    # -------------- SUPERUSER TESTS --------------
    def test_superuser_access_no_restriction(self):
        """
        Ensure superuser can access product.product archive functionality
        with no ResArchivingRestriction in place on product.product.
        """
        self.product_a.active = False
        self.assertEqual(self.product_a.active, False)

    def test_superuser_access_restriction_no_permitted_groups(self):
        """
        Ensure superuser can access product.product archive functionality
        after creating a ResArchivingRestriction with no permitted_group_ids.
        """
        self.ResArchivingRestriction.create(dict(model_id=self.product_model_id))
        self.product_a.active = False
        self.assertEqual(self.product_a.active, False)

    def test_superuser_access_restriction_has_permitted_groups(self):
        """
        Ensure superuser can access product.product archive functionality
        after adding one of their groups to permitted_group_ids (aswell as another group they do not have)
        """
        self.ResArchivingRestriction.create(
            dict(
                model_id=self.product_model_id,
                permitted_group_ids=[[6, 0, [self.group_debug_id, self.group_inbound_id]]],
            )
        )
        self.product_a.active = False
        self.assertEqual(self.product_a.active, False)

    # -------------- NORMAL USER TESTS --------------
    def test_normal_user_access_no_restriction(self):
        """
        Ensure newly created dummy user can access product.product archive functionality
        with no ResArchivingRestriction in place on product.product.
        """
        self.product_a.sudo(user=self.normal_user).active = False
        self.assertEqual(self.product_a.active, False)

    def test_normal_user_access_restriction_no_permitted_groups(self):
        """
        Ensure newly created dummy user can not access product.product archive functionality
        after creating a ResArchivingRestriction with no permitted_group_ids.
        """
        self.ResArchivingRestriction.create(dict(model_id=self.product_model_id))
        with self.assertRaises(ValidationError):
            self.product_a.sudo(user=self.normal_user).active = False
        self.assertEqual(self.product_a.active, True)

    def test_normal_user_access_restriction_has_permitted_groups(self):
        """
        Ensure newly created dummy user can access product.product archive functionality
        after adding one of their groups to permitted_group_ids (aswell as another group they do not have)
        """
        self.ResArchivingRestriction.create(
            dict(
                model_id=self.product_model_id,
                permitted_group_ids=[[6, 0, [self.group_employee_id, self.group_debug_id]]],
            )
        )
        self.product_a.sudo(user=self.normal_user).active = False
        self.assertEqual(self.product_a.active, False)
