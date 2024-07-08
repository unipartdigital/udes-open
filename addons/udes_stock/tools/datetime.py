from dateutil.parser import parse
import dateutil.tz
from datetime import datetime


def format_iso_datetime(dt):
    """
    Converts date strings returned by Odoo, or a datetime object, to 
    ISO 8601 date strings with the timezone included.

    eg. '2020-01-07 18:01:01' gets turned into '2020-01-07T18:01:01+00:00'
    """
    if not isinstance(dt, datetime):
        dt = parse(dt)
    dt = dt.replace(tzinfo=dateutil.tz.tzutc())
    return dt.isoformat(timespec="microseconds")
