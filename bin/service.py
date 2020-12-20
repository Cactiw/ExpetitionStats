
from resources.globals import moscow_tz

import datetime


def get_current_datetime():
    return datetime.datetime.now(tz=moscow_tz).replace(tzinfo=None)


def pretty_time_format(dt: datetime.datetime):
    return "{}".format(dt.strftime("%H:%M"))


def pretty_datetime_format(dt: datetime.datetime):
    return "{}".format(dt.strftime("%d/%m/%y %H:%M:%S"))
