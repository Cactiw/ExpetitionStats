
from typing import Dict, List

from sqlalchemy import or_, func

from resources.globals import SessionMaker, dispatcher, factions

from libs.api import ExpeditionAPI
from libs.models.Location import Location
from libs.models.Player import Player, provide_player
from libs.models.Ship import Ship
from libs.models.Guild import Guild

from bin.service import get_current_datetime, pretty_time_format, pretty_datetime_format_short, provide_session, \
    make_progressbar
from bin.string_service import translate_number_to_emoji

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

    list(map(lambda guild_id: update_guild_stats(dispatcher.bot, guild_id), Guild.GUILD_IDS))


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
                if player.location and not player.location.is_space:
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
                elif ship.status == "preparing" and "launching" in status:
                    # Корабль начал отправляться
                    ship.crashed_players.clear()
                    for player in ship.subscribed_players:
                        if player.telegram_id:
                            dispatcher.bot.send_message(
                                chat_id=player.telegram_id,
                                text="🚀<b>{} {}</b> скоро отправится к <b>{}</b>".format(
                                    ship.code, ship.name, ship.destination.name),
                                parse_mode='HTML'
                            )
                    ship.subscribed_players.clear()
            ship.name = name
            ship.code = code
            ship.type = ship_type
            ship.status = status
            ship.determine_locations(session)
        session.close()
        logging.info("Ships updated")


@provide_session
def spy(bot, update, session):
    try:
        user_name = update.message.text.split()[1]
    except (TypeError, IndexError):
        return
    player = session.query(Player).filter(Player.username.ilike("{}%".format(user_name))).first()
    if player is None:
        bot.send_message(chat_id=update.message.chat_id, text="Игрок не найден.")
        return
    response = "[{}] <b>{}</b>\n#{} 🏅{}\n".format(player.faction, player.username, player.rank, player.lvl)
    if player.location.is_space:
        response += "<b>🚀В пути</b> "
        if not player.possible_ships:
            response += "(Неизвестно)\n"
        elif len(player.possible_ships) == 1:
            ship = player.possible_ships[0]
            response += "({})\n".format(ship.format_short(show_link=False))
            response += "<b>{} {}</b> /sh_{}\n".format(ship.code, ship.name, ship.id)
        else:
            response += "(возможны все варианты):\n{}".format(
                "    " + "\n    ".join(map(lambda possible_ship: possible_ship.format_short(), player.possible_ships))
            ) + "\n"
    else:
        response += "<b>{}</b>\n".format(player.location.name)
    response += "\nИстория перемещений: /pl_history_{}".format(player.id)
    bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode='HTML')


@provide_session
def player_history(bot, update, session):
    parse = re.match("/pl_history_(\\d+)( (\\d+))?", update.message.text)
    if parse is None:
        bot.send_message(chat_id=update.message.chat_id, text="Неверный синтаксис.")
        return
    player: Player = session.query(Player).get(int(parse.group(1)))
    if player is None:
        bot.send_message(chat_id=update.message.chat_id, text="Игрок не найден.")
        return
    days = int(parse.group(3) or 1)
    response = "Перемещения <b>{}</b> за {} дней:\n".format(player.username, days)

    changes = list(sorted(filter(lambda change: get_current_datetime() - change.date <= datetime.timedelta(days=days),
                   player.location_changes), key=lambda change: change.date, reverse=False))
    if changes and changes[0].location.is_space:
        changes = changes[1:]
    for current, space, previous in zip(changes[::2], changes[1::2], changes[2::2]):
        if not space.location.is_space:
            continue
        response += "{} -> {} ({} -> {})\n".format(current.location.name, previous.location.name,
                                                   pretty_time_format(space.date), pretty_time_format(previous.date))

    bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode='HTML')


@provide_session
def view_players(bot, update, session):
    location, faction = None, None
    try:
        location_name = update.message.text.split()[1]
        if location_name.lower() in factions:
            faction = location_name.lower()
            players = session.query(Player).filter(func.lower(Player.faction) == faction).all()
        else:
            location = Location.search_location(location_name, session)
            if location is None:
                bot.send_message(chat_id=update.message.chat_id, text="Локация не найдена.")
                return
            players = session.query(Player).filter_by(location=location).limit(50).all()
    except (TypeError, IndexError):
        players = session.query(Player).limit(100).all()
    response = "Игроки {}на <b>{}</b>:\n".format("{} ".format(faction.upper()) if faction else "",
                                                 location.name if location else "сервере")
    for player in sorted(players, key=lambda player: (player.lvl, player.exp), reverse=True):
        response += player.short_format()
    bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode="HTML")


@provide_session
def update_guild_stats(bot, guild_id: int, session):
    ships = []
    guild = session.query(Guild).get(guild_id)
    if guild is None or not guild.chat_id:
        return
    if guild.is_faction:
        players = session.query(Player).filter_by(faction=guild.name).order_by(Player.lvl.desc()).\
            order_by(Player.exp.desc()).all()
    else:
        players = session.query(Player).filter_by(guild=guild).order_by(Player.lvl.desc()).\
            order_by(Player.exp.desc()).all()
    response = ""
    for player in players:
        index = None
        if player.location.is_space and player.possible_ships:
            ship = player.possible_ships[0]
            if ship in ships:
                index = ships.index(ship) + 1
            else:
                ships.append(ship)
                index = len(ships)
        response += "🏅{} <code>{:11}</code> {}\n".format(
            player.lvl, player.username,
            ("🪐{}".format(player.location.name)) if not player.location.is_space else (
                "🚀{}{}".format(translate_number_to_emoji(index) if index else "", "{} -> {} ({}%)".format(
                    player.possible_ships[0].origin.name, player.possible_ships[0].destination.name,
                    player.possible_ships[0].progress) if player.possible_ships else ""
        )))
    if ships:
        response += "\nShips:\n"
        for i, ship in enumerate(ships, start=1):
            response += "{} {} -> {} ({}% - {})\n".format(
                translate_number_to_emoji(i), ship.origin.name, ship.destination.name, ship.progress,
                pretty_datetime_format_short(ship.calculate_arrival()))
    response += "\nUpdated on {}\n".format(pretty_time_format(get_current_datetime()))
    if guild.stats_message_id:
        bot.editMessageText(chat_id=guild.chat_id, message_id=guild.stats_message_id, text=response, parse_mode='HTML')
    else:
        message = bot.sync_send_message(chat_id=guild.chat_id, text=response, parse_mode='HTML')
        guild.stats_message_id = message.message_id
        session.add(guild)
        session.commit()


@provide_session
def view_ships(bot, update, session):
    location = None
    try:
        location_name = update.message.text.split()[1]
        location = Location.search_location(location_name, session)
        if location is None:
            bot.send_message(chat_id=update.message.chat_id, text="Локация не найдена.")
            return
        ships = session.query(Ship).filter(or_(
            Ship.origin_id == location.id, Ship.destination_id == location.id)
        ).order_by(Ship.destination_id).order_by(Ship.origin_id).order_by(Ship.status).all()
    except (TypeError, IndexError):
        ships = session.query(Ship).order_by(Ship.origin_id).order_by(Ship.destination_id).all()

    if location:
        response = format_location_ships(location, ships)
    else:
        response = format_all_ships(ships)
    bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode='HTML')


def format_all_ships(ships):
    response = "Все корабли в игре:"
    origin_id = None
    for ship in ships:
        if ship.origin_id != origin_id:
            origin_id = ship.origin_id
            response += "\n"

        response += "{}<code>{}</code> {} -> {} {} /sh_{}\n".format(
            ship.status_emoji, ship.code, ship.origin.name, ship.destination.name,
            "({}% {})".format(int(ship.progress),
                              pretty_time_format(ship.departed_date) if ship.departed_date else "")
            if ship.progress is not None else "", ship.id
        )
    return response


def format_location_ships(location, ships) -> str:
    response = "Корабли в {}:\n".format(location.name)
    outgoing = list(filter(lambda ship: ship.origin_id == location.id, ships))
    incoming = list(filter(lambda ship: ship.destination_id == location.id, ships))

    if outgoing:
        response += "🛫Отбытие\n"
        for ship in outgoing:
            response += ship.format_line()
        response += "\n"

    if incoming:
        response += "🛫Прибытие\n"
        for ship in incoming:
            response += ship.format_line(outgoing=False)
    return response


@provide_session
def view_ship(bot, update, session):
    parse = re.match("/sh_(\\d+)", update.message.text)
    if parse is None:
        try:
            code = update.message.text.split()[1]
            ship = session.query(Ship).filter(Ship.code.ilike("{}%".format(code))).first()
            if ship is None:
                raise ValueError
        except (TypeError, ValueError):
            bot.send_message(chat_id=update.message.chat_id, text="Карабль не найден.")
            return
    else:
        ship_id = int(parse.group(1))
        ship = session.query(Ship).get(ship_id)
    if ship is None:
        bot.send_message(chat_id=update.message.chat_id, text="Корабль не найден.")
        return

    response = "<b>{} {}</b>\n".format(ship.code, ship.name)
    response += "{} -> {}\n".format(ship.origin.name, ship.destination.name)
    response += "{}{}\n".format(
        ship.status_emoji, ship.status if not ship.crashed_players else ship.status + " ( 💥crashed? )")
    if ship.progress:
        response += "{}\n".format(make_progressbar(ship.progress))
        response += "{}% {}\n".format(ship.progress, "- departed {}".format(
            pretty_datetime_format_short(ship.departed_date)) if ship.departed_date else ""
        )
        if ship.departed_date:
            response += "Прибытие: {}\n".format(
                pretty_datetime_format_short(
                    ship.calculate_arrival(),
                )
            )
    if ship.possible_players:
        response += "\nПассажиры:\n"
        for player in ship.possible_players:
            response += "{}".format(player.short_format())

    for player in ship.crashed_players:
        response += "💥{}".format(player.short_format())

    bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode='HTML')


def start(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text="Привет!\nДоступные команды:\n/spy username - Отобразить статус игрока\n"
             "/ships location - Отобразить корабли на локации\n"
             "/players location or faction - Отобразить игроков на локации или конкретной фракции\n"
             "/register nickname - Зарегистрироваться как игрок с ником nickname (нужно для команды /sub)\n"
             "/sub location - Подпишется на уведомление о подготовке к отправке корабля "
             "(то есть о начале отсчёта 10 минут) от вашей текущей локации к location\n"
    )


@provide_session
def register(bot, update, session, args):
    if not args:
        bot.send_message(chat_id=update.message.chat_id, text="Неверный синтаксис.\nПример: /register vamik76")
        return
    players = session.query(Player).filter(Player.username.ilike("{}%".format(" ".join(args)))).all()
    if players is None:
        bot.send_message(chat_id=update.message.chat_id, text="Игрок не найден.")
        return
    response = "Найденные игроки:\n{}".format("\n".join(map(lambda player: "{} /register_{}".format(player.username, player.id), players)))
    bot.send_message(chat_id=update.message.chat_id, text=response, parse_mode='HTML')


@provide_session
def register_id(bot, update, session):
    player_id = re.search("_(\\d+)", update.message.text)
    if player_id is None:
        bot.send_message(chat_id=update.message.chat_id, text="Неверный синтаксис.")
        return
    player_id = int(player_id.group(1))
    player = session.query(Player).get(player_id)
    if player is None:
        bot.send_message(chat_id=update.message.chat_id, text="Игрок не найден.")
        return
    player.telegram_id = update.message.from_user.id
    session.add(player)
    session.commit()
    bot.send_message(chat_id=update.message.chat_id,
                     text="Я тебя запомнил, <b>{}</b>!\n<em>Регистрация успешна.</em>".format(player.username),
                     parse_mode='HTML')


@provide_session
@provide_player
def sub(bot, update, session, player, args):
    if not args:
        bot.send_message(chat_id=update.message.chat_id, text="Неверный синтаксис.\nПример: /sub luna")
        return
    if not player:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Команда доступна только зарегистрированным пользователям.\nУкажите свой ник в игре "
                              "(пример: /register vamik76)")
        return
    location = Location.search_location(args[0], session)
    if not location or location.is_space:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Локация не найдена.")
        return
    if not player.location:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Местоположения игрока не определено.\n(Неизвестная ошибка)")
        return
    if player.location.is_space:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Команду можно использовать только находясь на планете (не в космосе)")
        return
    ships: List = session.query(Ship).filter_by(origin=player.location).filter_by(status="preparing").\
        filter_by(destination=location).all()
    if not ships:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Ожидающие корабли по маршруту <b>{}</b> -> <b>{}</b> не найдены.".format(
                             player.location.name, location.name))
        return
    if len(ships) == 1:
        ship = ships[0]
        if ship not in player.subscribed_ships:
            player.subscribed_ships.append(ship)
        session.add(player)
        session.commit()
        bot.send_message(chat_id=update.message.chat_id,
                         text="Вы подписаны на изменение статуса корабля <b>{} {}</b>.".format(ship.code, ship.name),
                         parse_mode='HTML')
    else:
        ships.sort(key=lambda sh: sh.type)
        bot.send_message(chat_id=update.message.chat_id, text="Выберите корабль ({} -> {}):\n{}".format(
            player.location.name, location.name,
            "\n".join(
                map(lambda ship: "{} {} {}".format(ship.code, ship.name, "/sub_{}".format(ship.id)), ships)))
        )


@provide_session
@provide_player
def sub_id(bot, update, session, player):
    ship_id = re.search("_(\\d+)", update.message.text)
    if ship_id is None:
        bot.send_message(chat_id=update.message.chat_id, text="Неверный синтаксис.")
        return
    ship_id = int(ship_id.group(1))
    ship = session.query(Ship).get(ship_id)
    if ship is None:
        bot.send_message(chat_id=update.message.chat_id, text="Корабль не найден.")
        return
    if ship not in player.subscribed_ships:
        player.subscribed_ships.append(ship)
    session.add(player)
    session.commit()
    bot.send_message(chat_id=update.message.chat_id,
                     text="Вы подписаны на изменение статуса корабля <b>{} {}</b>.".format(ship.code, ship.name),
                     parse_mode='HTML')


