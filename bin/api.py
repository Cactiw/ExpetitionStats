
from typing import Dict, List

from resources.globals import SessionMaker

from libs.api import ExpeditionAPI
from libs.models.Location import Location
from libs.models.Player import Player
from libs.models.Ship import Ship

from bin.service import get_current_datetime, pretty_time_format

import re
import logging
import datetime
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
            if location.is_space:
                if not player.location.is_space:
                    # Игрок только что вылетел
                    ships = player.location.outgoing_ships
                    player.possible_ships = list(filter(lambda ship: ship.departed_now, ships))
                    session.add(player)
                    session.commit()

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
            if ship.status in {"preparing", "launching"}:
                if "underway" in status:
                    ship.departed_date = get_current_datetime()
            ship.name = name
            ship.code = code
            ship.type = ship_type
            ship.status = status
            ship.determine_locations(session)
        session.close()
        logging.info("Ships updated")


def spy(bot, update):
    try:
        user_name = update.message.text.split()[1]
    except (TypeError, IndexError):
        return
    session = SessionMaker()
    player = session.query(Player).filter(Player.username.ilike("{}%".format(user_name))).first()
    if player is None:
        bot.send_message(chat_id=update.message.chat_id, text="Игрок не найден.")
        return
    response = "<b>{}</b>\n#{} 🏅{}\n".format(player.username, player.rank, player.lvl)
    if player.location.is_space:
        response += "<b>В пути</b> "
        if not player.possible_ships:
            response += "(Неизвестно)\n"
        elif len(player.possible_ships) == 1:
            ship = player.possible_ships[0]
            response += "({})\n".format(ship.format_short())
        else:
            response += "(возможны все варианты):\n{}".format(
                "    " + "\n    ".join(map(lambda possible_ship: possible_ship.format_short(), player.possible_ships))
            ) + "\n"
    else:
        response += "<b>{}</b>\n".format(player.location.name)
    response += "\nИстория перемещений: /pl_history_{}".format(player.id)
    bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode='HTML')
    session.close()


def player_history(bot, update):
    parse = re.match("/pl_history_(\\d+)( (\\d+))?", update.message.text)
    if parse is None:
        bot.send_message(chat_id=update.message.chat_id, text="Неверный синтаксис.")
        return
    session = SessionMaker()
    player: Player = session.query(Player).get(int(parse.group(1)))
    if player is None:
        bot.send_message(chat_id=update.message.chat_id, text="Игрок не найден.")
        return
    days = int(parse.group(3) or 1)
    response = "Перемещения <b>{}</b> за {} дней:\n".format(player.username, days)

    changes = list(filter(lambda change: change.date - get_current_datetime() <= datetime.timedelta(days=days) and
                                         not change.location.is_space,
                   player.location_changes))
    for current, previous in zip(changes, changes[1:]):
        response += "{} -> {} ({} -> {})\n".format(current.location.name, previous.location.name,
                                                   pretty_time_format(current.date), pretty_time_format(previous.date))

    bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode='HTML')
    session.close()


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

