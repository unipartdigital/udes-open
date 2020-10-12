from odoo import fields
from odoo.exceptions import ValidationError

__all__ = ("validate_dates", "date_diff")


def validate_dates(start_date, end_date, error_msg):
    if start_date and end_date and (start_date > end_date):
        raise ValidationError(error_msg)


def date_diff(start_date, end_date):
    """ Calculate date difference between two dates and returns hours

    Args:
        start_date (datetime): fields.Datetime type
        end_date (datetime): fields.Datetime type
    Returns:
        float: returns hours in decimal value
    """
    date_diff = fields.Datetime.from_string(end_date) - fields.Datetime.from_string(start_date)
    # Convert to hours
    return date_diff.total_seconds() / 3600
