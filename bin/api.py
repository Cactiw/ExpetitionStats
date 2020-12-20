
from typing import Dict, List

from resources.globals import SessionMaker

from libs.api import ExpeditionAPI
from libs.models.Location import Location
from libs.models.Player import Player

import logging


TOPS_INTERVAL = 1  # minutes


def update_tops(*args, **kwargs):
    try:
        users: Dict = ExpeditionAPI.get_users()
    except RuntimeError:
        pass
    else:
        session = SessionMaker()
        logging.info("Updating players")
        for user in users.get("users"):
            rank, user_id, user_name, exp, lvl, faction, location_name = \
                user.get("rank"), user.get("userId"), user.get("userName"), user.get("exp"), user.get("lvl"), \
                user.get("faction"), user.get("location")
            location = Location.get_create_location(location_name, session)
            player = Player.get_create_player(game_id=user_id, session=session)
            player.check_update_data(exp, lvl, rank, location, faction, user_name, session)
        session.close()
        logging.info("Players updated")

