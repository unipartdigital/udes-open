odoo.define('udes_security.basic_fields', function (require) {
    "use strict";

    var core = require('web.core');
    var _t = core._t;
    var rpc = require('web.rpc');

    var basicFields = require('web.basic_fields');
    var FieldBinaryFile = basicFields.FieldBinaryFile;
    var FieldBinaryImage = basicFields.FieldBinaryImage;

    var warningFTBlockedTitle = _t("File upload");
    var warningFTBlockedMessage = _t("The selected file type has been blocked by system administrator.");

    function getFileType(filename) {
        var fileTypeRegEx = /(?:\.([^.]+))?$/;
        var fileType = fileTypeRegEx.exec(filename)[1];

        return fileType;
    }

    function getAllowedFileTypeCount(fileType) {
        return new Promise(function (resolve, reject) {
            var checkFileType = fileType.toLowerCase();

            rpc.query({
                model: "udes.allowed_file_type",
                method: "search_count",
                args: [[["name", "=", checkFileType]]],
            }).then(function (allowedCount) {
                resolve(allowedCount);
            });
        });
    }

    FieldBinaryFile.include({
        on_file_change: function (e) {
            var self = this;
            var _super = this._super;
            var args = arguments;

            if (this.useFileAPI) {
                var file_node = e.target;
                var file = file_node.files[0];

                if (file.name) {
                    var fileType = getFileType(file.name);

                    if (fileType) {
                        getAllowedFileTypeCount(fileType).then(function (allowedCount) {
                            if (allowedCount == 0) {
                                self.do_warn(warningFTBlockedTitle, warningFTBlockedMessage);
                                return false;
                            }
                            else {
                                _super.apply(self, args);
                            }
                        });
                    }
                }
            }
            else {
                _super.apply(self, args);
            }
        },
    })

    FieldBinaryImage.include({
        on_file_change: function (e) {
            var self = this;
            var _super = this._super;
            var args = arguments;

            if (this.useFileAPI) {
                var file_node = e.target;
                var file = file_node.files[0];

                if (file.name) {
                    var fileType = getFileType(file.name);

                    if (fileType) {
                        getAllowedFileTypeCount(fileType).then(function (allowedCount) {
                            if (allowedCount == 0) {
                                self.do_warn(warningFTBlockedTitle, warningFTBlockedMessage);
                                return false;
                            }
                            else {
                                _super.apply(self, args);
                            }
                        });
                    }
                }
            }
            else {
                _super.apply(self, args);
            }
        },
    })

});
