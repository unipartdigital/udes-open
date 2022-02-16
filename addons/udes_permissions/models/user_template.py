import pdb
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class UserTemplate(models.Model):
    """
    UserTemplate Model.

    Allows users to configure a hierarchy of User Templates which have res.groups associated with them.
    Parents inherit their descendants groups (and thus, ACLs) via non stored computes.

    Has one magic field `template_group_id` which will automatically create/delete
    a user group with the template which allows for easy tuning of ACLs for users using this template.
    Name changes back / forth of this template should propagate between the group and template

    If you are utilizing this model, you should only need to use the following functions;
    - def get_template_groups()
    - def get_template_descendants()
    instead of directly access the fields on here.
    """

    _name = "user.template"
    _description = "User Template"
    _rec_name = "complete_name"
    _parent_name = "parent_id"
    _parent_store = True
    _sql_constraints = [
        ("name_unique", "unique(name)", "A User Template already exists with this name!"),
        (
            "template_group_id",
            "unique(template_group_id)",
            "A User Template already exists with this Template Group!",
        ),
    ]

    # Determines what auto-generated groups for User Templates get prefixed with.
    # Be wary if changing this if we have existing data, as data will not migrate with it
    TEMPLATE_GROUP_PREFIX = "User Template Group: "

    # Actual columns the user can configure
    name = fields.Char(
        string="Template Name",
        required=True,
        help="""The name of the User Template,
        typically something like Administrator, Stock Manager, etc..""",
    )
    complete_name = fields.Char("Complete Name", compute="_compute_complete_name", store=True)
    group_ids = fields.Many2many(
        "res.groups",
        string="Groups",
        required=True,
        help="""The Groups for this User Template,
        groups here, along with all child templates groups will
        be considered in get_template_groups()""",
    )
    # NB: We don't cascade on parent as it won't call the unlink() hook where cascaded
    parent_id = fields.Many2one(
        "user.template",
        index=True,
        string="Parent",
        help="""The Parent Template of this User Template.
        Allows for a hierarchy of templates to be created.
        A User Template can have multiple child templates (forks in the tree)""",
    )
    # Magic column updated as _parent_store is set to True
    parent_path = fields.Char(index=True)

    # Inverse to parent_id
    child_ids = fields.One2many(
        "user.template",
        "parent_id",
        string="Children",
        readonly=True,
        help="""User Templates which have directly have this template set as their parent.
        All templates groups in the family (excluding parents) will be considered
        when the User Template is applied to a user (via the family_group_ids column)""",
    )

    # Magic column that gets written to by the system on create. cascade only removes the
    # template if we delete the group, so we need an additional hook in unlink() on user.template
    template_group_id = fields.Many2one(
        "res.groups",
        ondelete="cascade",
        readonly=True,
        required=True,
        help="""A new group is created and attached to a User Template on template creation
        which allows for configuring specific ACLs for a template without too much hassle,
        with the downside of not being able to revoke specific ACLs from that group from a user.
        This can be used as an interim until more granular groups are available.
        The group set here will be bundled in with all other groups as part of get_template_groups()""",
    )

    # The three following computes all use the same method to save searching child_of
    # on three separate occasions, as they all hinge off the same initial 'family'
    family_descendant_ids = fields.Many2many(
        "user.template",
        compute="_compute_family_column_ids",
        store=False,  # We cannot store as function won't recompute if indirect descendants groups change
        string="All Child Templates",
        readonly=True,
        help="""Computed list of User Template records,
        which are descendants of this User Template record""",
    )
    family_group_ids = fields.Many2many(
        "res.groups",
        compute="_compute_family_column_ids",
        store=False,  # We cannot store as function won't recompute if indirect descendants groups change
        string="All Child Groups",
        readonly=True,
        help="""Computed list of user groups,
        based on this templates family (including its own groups)""",
    )
    family_acl_ids = fields.Many2many(
        "ir.model.access",
        compute="_compute_family_column_ids",
        store=False,  # We cannot store as function won't recompute if indirect descendants groups change
        string="All Child ACLs",
        readonly=True,
        help="""Computed list of ACLs,
        based on this templates family (including its own groups)
        This is really only used for easy visibility on the UI of what ACLs a template will inherit,
        """,
    )

    # Count columns used to display counts on the smart buttons
    family_descendant_count = fields.Integer(
        compute="_compute_family_counts",
        help="The number of templates which are descendants of this template",
    )
    family_group_count = fields.Integer(
        compute="_compute_family_counts",
        help="The number of groups associated with this templates family (including its own groups)",
    )
    family_acl_count = fields.Integer(
        compute="_compute_family_counts",
        help="The number of ACLs associated with this template family (including its own groups)",
    )

    def get_template_groups(self):
        """
        Get the usergroups associated with a template family
        along with the usergroup set under `template_group_id`.

        :return: res.groups(x,)
        """
        self.ensure_one()
        return self.family_group_ids | self.template_group_id

    def get_template_descendants(self):
        """
        Get the template along with all of its descendants

        :return: user.template(x,)
        """
        self.ensure_one()
        return self | self.family_descendant_ids

    @api.model
    def create(self, vals):
        """Extend create:
        Create a res.group for the template and link it to template_group_id
        """
        template_group = self._create_group_for_template(vals.get("name"))
        vals["template_group_id"] = template_group.id
        return super().create(vals)

    def write(self, vals):
        """Extend write:
        If we modify `name` - propagate that change to the `template_group_id.name`
        """
        res = super().write(vals)
        if (
            "name" in vals
            and vals.get("name")
            and not self.env.context.get("bypass_name_propagation_to_group")
        ):
            self.template_group_id.with_context(
                dict(bypass_name_propagation_to_template=True)
            ).name = self._get_user_template_group_name(vals.get("name"))
        return res

    def copy(self, default=None):
        """Extend copy:"""
        self.ensure_one()
        if default is None:
            default = {}

        if not default.get("name"):
            default["name"] = f"{self.name} (copy)"

        return super().copy(default)

    def unlink(self):
        """Extend unlink:
        If we delete the template, delete its respective template_group_id
        """
        self.template_group_id.unlink()
        return super().unlink()

    def _get_user_template_group_name(self, base_name):
        """
        Generate the full user template group name, with prefix
        :param: basename: str() of the template name
        """
        return f"{self.TEMPLATE_GROUP_PREFIX}{base_name}"

    def _set_user_template_name(self, group_name):
        """
        Given a group name which includes the prefix,
        update the name of the template by removing the prefix from group name,
        passing additional context to prevent recursion
        :param: group_name: str() of the group name
                           i.e return value of _get_user_template_group_name()
        """
        if group_name.startswith(self.TEMPLATE_GROUP_PREFIX):
            self.with_context(dict(bypass_name_propagation_to_group=True)).name = group_name[
                len(self.TEMPLATE_GROUP_PREFIX) :
            ]
        else:
            # We don't really care if it fails as it is only a name, but log warn it anyway
            _logger.warning(
                f"""Could not determine User Template name from Group name '{group_name}'
                using prefix '{self.TEMPLATE_GROUP_PREFIX}'.
                Not propagating change to User Template '{self.name}' (id: {self.id})"""
            )

    def _create_group_for_template(self, group_name):
        """
        Create goup and generate values for the group which will be linked to only one template
        :param: group_name: str() of the template name
        :return: res.groups(x) to then be passed into .create()
        """
        ResGroups = self.env["res.groups"]
        template_group = ResGroups.create(
            {
                "name": self._get_user_template_group_name(group_name),
                "category_id": self.env.ref("udes_permissions.module_category_user_templates").id,
            },
        )
        return template_group

    @api.depends("group_ids.model_access", "child_ids")
    def _compute_family_column_ids(self):
        """
        Find all descendants of self and replace the records in the Many2many columns:
        :family_descendant_ids : descendants
        :family_group_ids      : descendants.group_ids + descendants.template_group_id + self.group_ids
        :family_acl_ids        : family_group_ids.model_access
        """
        UserTemplate = self.env["user.template"]
        for usertemplate in self:
            groups = usertemplate.group_ids
            template_children = UserTemplate.browse()

            if usertemplate.id:  # Prevent invalid leaf if we have no id yet
                template_children = UserTemplate.search([("id", "child_of", usertemplate.ids)])
                groups |= template_children.mapped("group_ids")
                # Also include descendants template_group_id.
                groups |= template_children.mapped("template_group_id")
            usertemplate.family_descendant_ids = [[6, 0, (template_children - usertemplate).ids]]
            usertemplate.family_group_ids = [[6, 0, groups.ids]]
            usertemplate.family_acl_ids = [[6, 0, groups.mapped("model_access").ids]]

    @api.depends(
        "family_descendant_ids",
        "family_group_ids",
        "family_acl_ids",
    )
    def _compute_family_counts(self):
        """Set the count columns to the len() of their respective Many2many columns"""
        for usertemplate in self:
            usertemplate.family_descendant_count = len(usertemplate.family_descendant_ids)
            usertemplate.family_group_count = len(usertemplate.get_template_groups())
            usertemplate.family_acl_count = len(usertemplate.family_acl_ids)

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for usertemplate in self:
            if usertemplate.parent_id:
                usertemplate.complete_name = "%s / %s" % (
                    usertemplate.parent_id.complete_name,
                    usertemplate.name,
                )
            else:
                usertemplate.complete_name = usertemplate.name

    def action_view_child_templates(self):
        """Action called via the smart button on the form
        for viewing User Templates which are descendants of this template"""
        self.ensure_one()
        action = self.env.ref("udes_permissions.user_template_action").read()[0]
        action["domain"] = [("id", "in", self.family_descendant_ids.ids)]
        if self.id:
            # If users create from this action, autofill the parent to the record they came from
            action["context"] = "{'default_parent_id': %s}" % self.id

        return action

    def action_view_child_groups(self):
        """Action called via the smart button on the form
        for viewing groups which are associated with this template and its descendants"""
        self.ensure_one()
        action = self.env.ref("base.action_res_groups").read()[0]
        action["domain"] = [("id", "in", self.get_template_groups().ids)]
        return action

    def action_view_child_acls(self):
        """Action called via the smart button on the form
        for viewing ACLs which are associated with this template and its descendants"""
        self.ensure_one()
        action = self.env.ref("base.ir_access_act").read()[0]
        action["domain"] = [("id", "in", self.family_acl_ids.ids)]
        return action
