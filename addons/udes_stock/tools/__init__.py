"""Tools and utilties for the udes_stock addon."""

from odoo.exceptions import ValidationError
from odoo.tools.translate import _


def get_printer_by_barcode(env, barcode):
    """Return the printer with the provided barcode."""
    Printer = env["print.printer"]

    if barcode:
        printer = Printer.search([("barcode", "=", barcode)])
        if not printer:
            raise ValidationError(_("Cannot find printer with barcode: %s") % barcode)
    else:
        printer = Printer.browse([])
    return printer
