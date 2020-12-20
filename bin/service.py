
from resources.globals import moscow_tz

import datetime


def get_current_datetime():
    return datetime.datetime.now(tz=moscow_tz).replace(tzinfo=None)

