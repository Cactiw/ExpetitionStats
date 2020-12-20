
from typing import Dict, List

from resources.globals import SessionMaker

from libs.api import ExpeditionAPI
from libs.models.Location import Location
from libs.models.Player import Player
from libs.models.Ship import Ship

import logging
import traceback


TOPS_INTERVAL = 1  # minutes


def update_all(*args, **kwargs):
    try:
        update_ships()
    except Exception:
        logging.error("Error in updating ships: {}".format(traceback.format_exc()))

    try:
        update_tops()
    except Exception:
        logging.error("Error in updating users: {}".format(traceback.format_exc()))


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


def update_ships(*args, **kwargs):
    try:
        ships: Dict = ExpeditionAPI.get_ships()
    except RuntimeError:
        pass
    else:
        session = SessionMaker()
        logging.info("Updating ships")
        for ship in ships.get("ships"):
            ship_id, code, name, ship_type, status = ship.get("shipId"), ship.get("numberPlate"), ship.get("shipName"),\
                                                     ship.get("shipType"), ship.get("shipStatus")
            ship = Ship.get_create_ship(ship_id, session)
            ship.name = name
            ship.code = code
            ship.type = ship_type
            ship.status = status
            ship.determine_locations(session)
        session.close()
        logging.info("Ships updated")


def spy(bot, update):
    pass


def view_players(bot, update):
    try:
        location_name = update.message.text.split()[1]
    except (TypeError, IndexError):
        return
    session = SessionMaker()
    location = session.query(Location).filter(Location.name.ilike("{}%".format(location_name))).first()
    if location is None:
        bot.send_message(chat_id=update.message.chat_id, text="Локация не найдена.")
        return
    players = session.query(Player).filter_by(location=location).limit(50).all()
    response = "Игроки в <b>{}</b>:\n".format(location.name)
    for player in sorted(players, key=lambda player: (player.lvl, player.exp), reverse=True):
        response += player.short_format()
    bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode="HTML")

    session.close()

