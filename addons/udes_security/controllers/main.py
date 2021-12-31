# -*- coding: utf-8 -*-

import json
import logging

from datetime import datetime

from odoo import http, SUPERUSER_ID, _
from odoo.http import request

from odoo.addons.web.controllers.main import Binary, serialize_exception

_logger = logging.getLogger(__name__)


class BinaryExtension(Binary):
    def _get_file_type(self, filename):
        """Get file type from supplied filename"""
        file_type = ""
        if "." in filename:
            file_type = filename.split(".")[-1].lower()
        return file_type

    def _get_file_type_allowed(self, file_type):
        """Return true if the file type is allowed, otherwise false"""
        AllowedFileType = request.env["udes.allowed_file_type"].sudo()

        search_args = [("name", "=", file_type)]
        allowed_file_type_count = AllowedFileType.search_count(search_args)

        return bool(allowed_file_type_count)

    def _get_file_type_blocked_error_message(self, action, file_type):
        """Return an error message stating that the file type has been blocked"""
        message = ""

        if file_type:
            message = _("File type '%s' has been blocked by the system administrator.") % file_type
        else:
            message = _("Cannot %s a file without a file type.") % action

        return message

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
            "/web/content/<int:id>-<string:unique>/<path:extra>/<string:filename>",
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
        filename_field="name",
        unique=None,
        mimetype=None,
        download=None,
        data=None,
        token=None,
        access_token=None,
        **kw,
    ):
        """Extended to prevent non-system users from downloading blocked file types"""
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

                if not file_type:
                    file_type_allowed = False
                else:
                    file_type_allowed = self._get_file_type_allowed(file_type)

                # If the user is trying to download a blocked file type then
                # prevent download and return an error message
                if not file_type_allowed:
                    self._log_user_file_action_blocked("download", record_filename, user_id)

                    download_error = {
                        "message": "Unable to download file: File type blocked",
                        "data": {
                            "debug": self._get_file_type_blocked_error_message(
                                "download", file_type
                            )
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
    def upload_attachment(self, model, id, ufile, callback=None):
        """
        Extended to prevent non-system users from uploading blocked file types.

        If the file type is blocked, a UI notification is returned and the file is not uploaded.
        """
        user_id = request.session.uid
        files = request.httprequest.files.getlist("ufile")

        if user_id != SUPERUSER_ID:
            for upload_file in files:
                filename = upload_file.filename

                if upload_file and filename:
                    file_type = self._get_file_type(filename)
                    file_type_allowed = self._get_file_type_allowed(file_type)

                    # If the user is trying to upload a blocked file type then
                    # prevent upload and generate a notification
                    if not file_type_allowed:
                        self._log_user_file_action_blocked("upload", filename, user_id)

                        out = """<script language="javascript" type="text/javascript">
                                    var odoo = window.top.odoo;
                                    odoo.define("udes_security.%s", function (require) {
                                        "use strict";

                                        var Notification = require("web.NotificationService");
                                        var notification = new Notification();

                                        var params = {
                                            type: "danger",
                                            title: "File Upload",
                                            message: "%s"
                                        };

                                        notification.start();
                                        notification.notify(params);
                                    });
                                </script>"""

                        # Need to create a unique callback ref incase the user re-attempts
                        # to upload a blocked file type
                        blocked_file_callback = (
                            f"o_FileUploader_fileupload{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                        )
                        res = out % (
                            blocked_file_callback,
                            self._get_file_type_blocked_error_message("upload", file_type),
                        )

                        return res

        return super(BinaryExtension, self).upload_attachment(model, id, ufile, callback=callback)
