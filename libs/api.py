
import requests
import logging


class ExpeditionAPI:
    BASE_URL = "https://api.extracoffee.pro/public/v1/"

    @classmethod
    def get_users(cls):
        result = requests.get(cls.BASE_URL + "users")
        if result.status_code // 100 != 2:
            logging.error("Error in GET /users: {}".format(result.text))
            raise RuntimeError
        return result.json()

    @classmethod
    def get_ships(cls):
        result = requests.get(cls.BASE_URL + "ships")
        if result.status_code // 100 != 2:
            logging.error("Error in GET /ships: {}".format(result.text))
            raise RuntimeError
        return result.json()
