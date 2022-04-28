from datetime import datetime, date, time
from odoo import fields


DATE_LENGTH = fields.DATE_LENGTH
DATETIME_FORMAT = fields.DATETIME_FORMAT + ".%f"
DATETIME_LENGTH = len(datetime.now().strftime(DATETIME_FORMAT))


class PreciseDatetime(fields.Datetime):
    """Store microsecond-precision timestamps."""

    type = "datetime"
    column_type = ("timestamp", "timestamp")
    column_cast_from = ("date",)

    @staticmethod
    def now(*args):
        """ Return the current day and time in the format expected by the ORM.
            This function may be used to compute default values.
        """
        return datetime.now().strftime(DATETIME_FORMAT)

    @staticmethod
    def to_datetime(value):
        """ Convert an ORM ``value`` into a :class:`datetime` value. """
        if not value:
            return None
        if isinstance(value, date):
            if isinstance(value, datetime):
                if value.tzinfo:
                    raise ValueError("Datetime field expects a naive datetime: %s" % value)
                return value
            return datetime.combine(value, time.min)

        value = value[:DATETIME_LENGTH]
        if len(value) == DATE_LENGTH:
            value += " 00:00:00.000000"
        return datetime.strptime(value, DATETIME_FORMAT)

    @staticmethod
    def to_string(value):
        """ Convert a :class:`datetime` value into the format expected by the ORM. """
        return value.strftime(DATETIME_FORMAT) if value else False

    def convert_to_column(self, value, record, values=None):
        return super(PreciseDatetime, self).convert_to_column(value or None, record, values)

    def convert_to_display_name(self, value, record):
        assert record, "Record expected"
        return PreciseDatetime.to_string(
            PreciseDatetime.context_timestamp(record, PreciseDatetime.from_string(value))
        )
