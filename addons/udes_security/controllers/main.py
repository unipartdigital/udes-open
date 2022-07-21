import json
import logging

from odoo import http, SUPERUSER_ID, _
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.web.controllers.main import Binary, serialize_exception, Action

_logger = logging.getLogger(__name__)


class SecureAction(Action):
    @http.route()
    def load(self, action_id, additional_context=None):
        """
        Extend load to check menu level access rights before returning the super call,
        to prevent users without sufficient permission accessing pages via direct URL
        """
        group_no_one_id = request.env.ref("base.group_no_one").id
        group_debug_user_id = request.env.ref("udes_security.group_debug_user").id

        menu_path, action_group_ids = self._get_menu_info_from_action_id(action_id)
        user_group_ids = self._get_object_group_ids(
            request.session.uid, "res_groups_users_rel", "uid"
        )
        # Check if user has access to the menu, trigger AccessError and log a warning if not
        if not self._user_has_access_right(
            action_group_ids, menu_path, user_group_ids, group_no_one_id, group_debug_user_id
        ):
            _logger.warning(
                f"User id: {request.session.uid} had access blocked to action id: {action_id}"
            )
            raise AccessError(_("You do not have permission to access this action"))
        return super().load(action_id, additional_context=additional_context)

    def _get_object_group_ids(self, obj_id, relation_table, inverse_name):
        """
        Bypass the ORM to get groups associated with the object id

        :param: obj_id: int() res.users or ir.ui.menu id
        :param: relation_name: str() of rel table for object and groups
        :param: inverse_name: str() of inverse relation for rel table to object

        :return: list() res.group ids
        """
        query = f"SELECT ARRAY_AGG(gid) FROM {relation_table} WHERE {relation_table}.{inverse_name} IN (%s)"
        request.env.cr.execute(
            query,
            (obj_id,),
        )
        result = request.env.cr.fetchone()
        return result and result[0] or []

    def _get_menu_info_from_action_id(self, action_id):
        """
        Get the ir.ui.menu parent_path and actions group_ids from a given action_id
        `IrUiMenu.sudo().search([("action.id", "=", action_id)])`
        does not work as `action` is a Reference field. The other option would be to
        fetch all ir.ui.menu records and then `.filtered()`, but this is a little slow,
        so instead do a direct query to get only the relevant parts.

        All models on the `action` Reference field on `ir.ui.menu` have the same
        `_sequence` parameter, so there is no risk of colliding ids from separate models.

        They are stored in the db like "ir.actions.act_window,90" or "ir.actions.server,242"
        due to being a Reference field, so perform a fuzzy search on %,<id>% to get it

        Be extra safe and ensure `action_id` is an int, as if the user enters text in the URL
        for action= param, it will come through to here as a string

        :param: action_id: int() for an action (ir.actions.server, ir.actions.act_window, etc..)

        :return: parent_path_ids: list() of ids for all ir.ui.menu records in the hierarchy
                 action_group_ids:   list() of ids for res.groups for the action
        """
        IrUiMenu = request.env["ir.ui.menu"]

        action_group_ids = []
        parent_path_ids = []

        if not isinstance(action_id, int):
            raise ValidationError("Invalid action ID specified.")
        query = """
            SELECT
                menu.id AS menu_id,
                field.relation_table AS relation_table,
                field.column1 AS inverse,
                SPLIT_PART(menu.action, ',', '2') AS action_id
            FROM
                ir_ui_menu menu
            LEFT JOIN ir_model model ON model.model = SPLIT_PART(menu.action, ',', '1')
            LEFT JOIN ir_model_fields field ON field.model_id = model.id AND field.name = 'groups_id'
            WHERE action LIKE '%%,%s'
        """
        request.env.cr.execute(query, (action_id,))
        result = request.env.cr.fetchone()
        if result:
            (menu_id, relation_table, inverse, action_id) = result
            # Get ids in order from parent --> child of the menus
            menu = IrUiMenu.browse(menu_id)
            while menu:
                parent_path_ids.insert(0, menu.id)
                menu = menu.parent_id
            if relation_table and inverse:  # Some ir.actions* models don't have groups_id column
                action_group_ids = self._get_object_group_ids(action_id, relation_table, inverse)
        else:
            # Certain actions don't have a menu, but we still need to determine the model
            # which the action_id is for to get its groups. This approach is slower.
            # This will happen rarely, so not concerned about optimising.
            models = [
                "ir.actions.act_window",
                "ir.actions.server",
                "ir.actions.client",
                "ir.actions.report",
                "ir.actions.act_url",
            ]
            for model in models:
                action = request.env[model].sudo().search([("id", "=", action_id)], order="id")
                if action and hasattr(action, "groups_id"):
                    action_group_ids = action.groups_id.ids
                    # Let _user_has_access_right() run at least once but give it
                    # a menu id which will resolve to no result in the query
                    parent_path_ids = [0]
                    break
        return parent_path_ids, action_group_ids

    def _user_has_access_right(
        self, action_group_ids, parent_path, user_group_ids, group_no_one_id, group_debug_user_id
    ):
        """
        Check user access rights against action, menu, and menu parent.

        Start at the end of the parent_path, and pop the last item,
        before recursively calling with the new parent_path until either:
        1.) The user has no groups which are specified against the action or menu (return False)
        2.) The user has groups specified against the action or menu, and no parent exists (return True)
        3.) There are no groups specified against the action or menu, and no parent exists (return True)

        This ensures that the user has access at least every menuitem in the chain of menuitems
        leading to the menu/action they are trying to access, following the same logic of the web UI.

        :param: action_group_ids: int() ids for res.groups
        :param: parent_path: list() of ids referring to ir.ui.menu hierarchy
        :param: user_group_ids: list() of res.group ids for the user
        :param: group_no_one_id: int() id for Extra Rights/Technical Features group
        :param: group_debug_user_id: int() id for Other Extra Rights/Debug User group

        :return: bool() whether or not the user should be granted access
        """
        # Can have actions defined in the system with no menu associated. These should be blocked.
        if not parent_path:
            return False
        menu_id = parent_path.pop()
        group_ids_for_access = action_group_ids + self._get_object_group_ids(
            menu_id, "ir_ui_menu_group_rel", "menu_id"
        )
        user_has_any_groups = any(g_id in user_group_ids for g_id in group_ids_for_access)
        # If Technical Features is a group we need for access, then it implies Debug User
        # is required (ANDed) to see the menu by enabling debug mode
        # (as all menus with Technical Features are hidden from normal UI)
        if group_no_one_id in group_ids_for_access:
            if group_debug_user_id not in user_group_ids:
                user_has_any_groups = False
        if group_ids_for_access and not user_has_any_groups:
            return False
        else:
            return (
                self._user_has_access_right(
                    action_group_ids,
                    parent_path,
                    user_group_ids,
                    group_no_one_id,
                    group_debug_user_id,
                )
                if parent_path
                else True
            )


class BinaryExtension(Binary):
    def _get_file_type(self, filename):
        """Extract the file type from the filename by returning value
        after the last '.' character"""
        return filename.split(".")[-1].lower()

    def _get_file_type_allowed(self, file_type):
        """Return true if the file type is allowed, otherwise false"""
        AllowedFileType = request.env["udes.allowed_file_type"].sudo()

        search_args = [("name", "=", file_type)]
        allowed_file_type_count = AllowedFileType.search_count(search_args)

        return bool(allowed_file_type_count)

    def _get_file_type_blocked_error_message(self, file_type):
        """Return an error message stating that the file type has been blocked"""
        return _("File type '%s' has been blocked by system administrator." % (file_type))

    def _log_user_file_action_blocked(self, action, filename, user_id):
        """Log a message when a user is blocked trying to upload/download a file"""
        ResUsers = request.env["res.users"].sudo()

        user = ResUsers.browse(user_id)

        message = "Blocked attempt to %s file '%s' by user '%s'" % (action, filename, user.login)
        _logger.info(message)

        return True

    @http.route(
        [
            "/web/content",
            "/web/content/<string:xmlid>",
            "/web/content/<string:xmlid>/<string:filename>",
            "/web/content/<int:id>",
            "/web/content/<int:id>/<string:filename>",
            "/web/content/<int:id>-<string:unique>",
            "/web/content/<int:id>-<string:unique>/<string:filename>",
            "/web/content/<string:model>/<int:id>/<string:field>",
            "/web/content/<string:model>/<int:id>/<string:field>/<string:filename>",
        ],
        type="http",
        auth="public",
    )
    def content_common(
        self,
        xmlid=None,
        model="ir.attachment",
        id=None,
        field="datas",
        filename=None,
        filename_field="datas_fname",
        unique=None,
        mimetype=None,
        download=None,
        data=None,
        token=None,
        access_token=None,
        **kw,
    ):
        """Override to prevent non-admin users from downloading blocked file types"""
        user_id = request.session.uid

        if user_id != SUPERUSER_ID:
            # Check if the file type is allowed
            if download:
                record_filename = ""

                if filename:
                    record_filename = filename
                elif id and model and filename_field:
                    RecordModel = request.env[model].sudo()
                    record = RecordModel.browse(id)
                    record_filename = record[filename_field]

                file_type = self._get_file_type(record_filename)
                file_type_allowed = self._get_file_type_allowed(file_type)

                # If the user is trying to download a blocked file type then
                # prevent download and return an error message
                if not file_type_allowed:
                    self._log_user_file_action_blocked("download", record_filename, user_id)

                    download_error = {
                        "message": "Unable to download file: File type blocked",
                        "data": {
                            "debug": self._get_file_type_blocked_error_message(file_type),
                        },
                    }

                    return request.make_response((json.dumps(download_error)))

        return super(BinaryExtension, self).content_common(
            xmlid,
            model,
            id,
            field,
            filename,
            filename_field,
            unique,
            mimetype,
            download,
            data,
            token,
            access_token,
            **kw,
        )

    @http.route("/web/binary/upload_attachment", type="http", auth="user")
    @serialize_exception
    def upload_attachment(self, callback, model, id, ufile):
        """Override to prevent non-admin users from uploading blocked file types"""
        user_id = request.session.uid
        files = request.httprequest.files.getlist("ufile")

        if user_id != SUPERUSER_ID:
            for upload_file in files:
                filename = upload_file.filename

                if upload_file and filename:
                    file_type = self._get_file_type(filename)
                    file_type_allowed = self._get_file_type_allowed(file_type)

                    # If the user is trying to upload a blocked file type then
                    # prevent upload and return an error message
                    if not file_type_allowed:
                        self._log_user_file_action_blocked("upload", filename, user_id)

                        out = """<script language="javascript" type="text/javascript">
                                    var win = window.top.window;
                                    win.jQuery(win).trigger(%s, %s);
                                </script>"""

                        args = [{"error": self._get_file_type_blocked_error_message(file_type)}]

                        return out % (json.dumps(callback), json.dumps(args))

        return super(BinaryExtension, self).upload_attachment(callback, model, id, ufile)
