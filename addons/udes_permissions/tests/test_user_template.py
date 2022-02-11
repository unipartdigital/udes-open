from odoo.tests import common
from psycopg2.errors import UniqueViolation
from odoo.tools import mute_logger


class TestUserTemplate(common.SavepointCase):
    @classmethod
    def setUpClass(cls):
        """
        Make a hierarchy of templates with [groups] that look something like this
        (not using example from readme as it would require module dependencies);
        | - Admin [Administration/Settings]
        | -- L2 User [Multi Companies, Technical Features]
        | --- L3 User A [Public]
        | --- L3 User B [Public, Internal User]
        | - Outlier [Technical Features]
        """
        super().setUpClass()

        # All the usergroups we will need
        cls.usergroup_admin_settings = cls.env.ref("base.group_system")
        cls.usergroup_multi_company = cls.env.ref("base.group_multi_company")
        cls.usergroup_tech_features = cls.env.ref("base.group_no_one")
        cls.usergroup_public = cls.env.ref("base.group_public")
        cls.usergroup_internal = cls.env.ref("base.group_user")

        cls.admin_template = cls._create_user_template(
            name="Admin",
            groups=cls.usergroup_admin_settings,
        )
        cls.l2_user_template = cls._create_user_template(
            name="L2 User",
            groups=cls.usergroup_multi_company | cls.usergroup_tech_features,
            parent=cls.admin_template,
        )
        cls.l3a_user_template = cls._create_user_template(
            name="L3 User A",
            groups=cls.usergroup_public,
            parent=cls.l2_user_template,
        )
        cls.l3b_user_template = cls._create_user_template(
            name="L3 User B",
            groups=cls.usergroup_public | cls.usergroup_internal,
            parent=cls.l2_user_template,
        )
        cls.outlier_user_template = cls._create_user_template(
            name="Outlier",
            groups=cls.usergroup_tech_features,
        )
        cls.all_user_templates = [
            cls.admin_template,
            cls.l2_user_template,
            cls.l3a_user_template,
            cls.l3b_user_template,
            cls.outlier_user_template,
        ]

    @classmethod
    def _create_user_template(cls, name="", groups=None, parent=None):
        """
        Helper method to create a user.template record.
        :param: name: str() name you wish to give to the template
        :param: group_names: res.group(x,) recordsets you wish to associate with the template
        :param: parent_id: user.template(x,) recordset of parent

        :return: user.template(x,) recordset
        """
        UserTemplate = cls.env["user.template"]
        return UserTemplate.create(
            dict(
                name=name,
                group_ids=[[6, 0, groups.ids if groups else []]],
                parent_id=parent.id if parent else False,
            )
        )

    def assert_generated_template_group_id(self, template):
        """
        Assert that a template has a group generated for it.
        Assert that the group name follows the prefix convention set on UserTemplate
        :param: template: user.template(x,) recordset
        """
        self.assertTrue(template.template_group_id.id)
        self.assertEqual(
            f"{template.TEMPLATE_GROUP_PREFIX}{template.name}",
            template.template_group_id.name,
        )

    def assert_template_group_id_name_propagation(self, template):
        """
        Assert that if user writes to the `name` column of the group
        or the template, the name propagates correctly to the other model
        :param: template: user.template(x,) recordset
        """
        group = template.template_group_id
        template.name = f"{template.name} Cowabunga"
        # We can just call this as it asserts propagation one way
        self.assert_generated_template_group_id(template)
        # Test propgagation the other way.
        group.name = f"{group.name} dude!"
        self.assert_generated_template_group_id(template)
        # Now test removing the prefix from the group.
        # This should result in no propagation and a warn as it is invalid
        # (but we surpress the warn here)
        template_name_before_invalid_group_name_change = template.name
        # Surpress warnings when doing this as the warnings are expected
        with mute_logger("odoo.addons.udes_permissions.models.user_template"):
            group.name = group.name.replace(template.TEMPLATE_GROUP_PREFIX, "")
        self.assertEqual(template_name_before_invalid_group_name_change, template.name)

    def test_generated_template_group_id(self):
        """Ensure a group is generated following the naming scheme (for all of our templates)"""
        for template in self.all_user_templates:
            with self.subTest(template=template):
                self.assert_generated_template_group_id(template)

    def test_template_group_id_name_propagation(self):
        """Ensure when we write to the `name` column on the group or template
        which are linked, that it propagates (for all of our templates)"""
        for template in self.all_user_templates:
            with self.subTest(template=template):
                self.assert_template_group_id_name_propagation(template)

    def test_user_template_constraints(self):
        """Ensure we cannot have a duplicate name or linked template_group_id"""
        with self.assertRaises(UniqueViolation), mute_logger("odoo.sql_db"):
            self._create_user_template(name="Admin")
            self.admin_template.template_group_id = self.l2_user_template.template_group_id

    def assert_template_does_not_exist(self, template):
        """Ensure the user.template record does not exist anymore.
        Needed as cache gets in the way.
        :param: template: user.template(x,)
        """
        UserTemplate = self.env["user.template"]
        self.assertEqual(template.exists(), UserTemplate)

    def assert_group_does_not_exist(self, group):
        """Ensure the res.groups record does not exist anymore.
        Needed as cache gets in the way.
        :param: group: res.groups(x,)
        """
        ResGroups = self.env["res.groups"]
        self.assertEqual(group.exists(), ResGroups)

    def test_unlink(self):
        """Ensure when the template is unlinked, the corresponding template_group_id is also removed."""
        for template in self.all_user_templates:
            with self.subTest(template=template):
                corresponding_group = template.template_group_id
                template.unlink()
                self.assert_template_does_not_exist(template)
                self.assert_group_does_not_exist(corresponding_group)

    def test_unlink2(self):
        """Ensure when the template_group_id is unlinked, the corresponding user template is also removed."""
        for template in self.all_user_templates:
            with self.subTest(template=template):
                corresponding_group = template.template_group_id
                corresponding_group.unlink()
                self.assert_template_does_not_exist(template)
                self.assert_group_does_not_exist(corresponding_group)

    def test_smart_button_counts(self):
        """Ensure the smart buttons on the User Template form
        use expected counts"""
        for template in self.all_user_templates:
            with self.subTest(template=template):
                self.assertEqual(
                    template.family_descendant_count, len(template.family_descendant_ids)
                )
                self.assertEqual(template.family_group_count, len(template.get_template_groups()))
                self.assertEqual(template.family_acl_count, len(template.family_acl_ids))

    def test_smart_button_actions(self):
        """Ensure the smart buttons on the User Template form
        return an action using the correct domain (ids)"""
        UserTemplate = self.env["user.template"]
        ResGroups = self.env["res.groups"]
        IrModelAccess = self.env["ir.model.access"]

        for template in self.all_user_templates:
            with self.subTest(template=template):
                template_action_domain = template.action_view_child_templates().get("domain")
                group_action_domain = template.action_view_child_groups().get("domain")
                acl_action_domain = template.action_view_child_acls().get("domain")
                # Ensure action domains return the same records as we expect
                self.assertEqual(
                    UserTemplate.search(template_action_domain), template.family_descendant_ids
                )
                self.assertEqual(
                    ResGroups.search(group_action_domain), template.get_template_groups()
                )
                self.assertEqual(IrModelAccess.search(acl_action_domain), template.family_acl_ids)

    def test_api_endpoint_get_template_groups(self):
        """Ensure get_template_groups() gives us the expected results"""
        self.assertEqual(
            self.admin_template.get_template_groups(),
            (
                self.usergroup_admin_settings
                | self.usergroup_multi_company
                | self.usergroup_tech_features
                | self.usergroup_public
                | self.usergroup_internal
                | self.admin_template.template_group_id
                | self.l2_user_template.template_group_id
                | self.l3a_user_template.template_group_id
                | self.l3b_user_template.template_group_id
            ),
        )
        self.assertEqual(
            self.l2_user_template.get_template_groups(),
            (
                self.usergroup_multi_company
                | self.usergroup_tech_features
                | self.usergroup_public
                | self.usergroup_internal
                | self.l2_user_template.template_group_id
                | self.l3a_user_template.template_group_id
                | self.l3b_user_template.template_group_id
            ),
        )
        self.assertEqual(
            self.l3a_user_template.get_template_groups(),
            (self.usergroup_public | self.l3a_user_template.template_group_id),
        )
        self.assertEqual(
            self.l3b_user_template.get_template_groups(),
            (
                self.usergroup_public
                | self.usergroup_internal
                | self.l3b_user_template.template_group_id
            ),
        )
        self.assertEqual(
            self.outlier_user_template.get_template_groups(),
            (self.usergroup_tech_features | self.outlier_user_template.template_group_id),
        )

    def test_api_endpoint_get_template_descendants(self):
        """Ensure get_template_descendants() gives us the expected results"""
        self.assertEqual(
            self.admin_template.get_template_descendants(),
            (
                self.admin_template
                | self.l2_user_template
                | self.l3a_user_template
                | self.l3b_user_template
            ),
        )
        self.assertEqual(
            self.l2_user_template.get_template_descendants(),
            (self.l2_user_template | self.l3a_user_template | self.l3b_user_template),
        )
        self.assertEqual(self.l3a_user_template.get_template_descendants(), self.l3a_user_template)
        self.assertEqual(self.l3b_user_template.get_template_descendants(), self.l3b_user_template)
        self.assertEqual(
            self.outlier_user_template.get_template_descendants(), self.outlier_user_template
        )
