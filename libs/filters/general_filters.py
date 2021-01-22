
from telegram import Update
from telegram.ext import BaseFilter
from functools import wraps


def update_filter(func):
    @wraps(func)
    def wrapper(self, message):
        if isinstance(message, Update):
            message = message.message
        return func(self, message)
    return wrapper


class FilterIsPM(BaseFilter):
    def filter(self, message):
        if isinstance(message, Update):
            message = message.message
        if message.from_user is None:
            return False
        return message.chat_id == message.from_user.id


filter_is_pm = FilterIsPM()
filter_is_pm.update_filter = True
