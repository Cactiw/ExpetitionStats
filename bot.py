
from telegram.ext import CommandHandler, MessageHandler, Filters

from libs.filters.general_filters import filter_is_pm

from resources.globals import updater, dispatcher, job_queue, engine, Base, SessionMaker

from bin.api import update_all, TOPS_INTERVAL, view_players, view_ship, view_ships, spy, player_history, start, \
    register, register_id, sub, sub_id

from libs.models.Location import Location
from libs.models.Guild import Guild

import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

dispatcher.add_handler(CommandHandler('players', view_players))
dispatcher.add_handler(CommandHandler('start', start, filters=filter_is_pm))
dispatcher.add_handler(CommandHandler('help', start, filters=filter_is_pm))
dispatcher.add_handler(CommandHandler('ships', view_ships))
dispatcher.add_handler(CommandHandler('register', register, filters=filter_is_pm, pass_args=True))
dispatcher.add_handler(MessageHandler(Filters.command & Filters.regex("/register_\\d+") & filter_is_pm, register_id))
dispatcher.add_handler(CommandHandler('sub', sub, filters=filter_is_pm, pass_args=True))
dispatcher.add_handler(MessageHandler(Filters.command & Filters.regex("/sub_\\d+") & filter_is_pm, sub_id))
dispatcher.add_handler(MessageHandler(Filters.command & Filters.regex("/sh[_ ].+"), view_ship))
dispatcher.add_handler(CommandHandler('spy', spy))
dispatcher.add_handler(MessageHandler(Filters.command & Filters.regex("/pl_history_\\d+.*"), player_history))

job_queue.run_repeating(update_all, TOPS_INTERVAL * 60, first=5)


def init_database():
    Base.metadata.create_all(engine)

    session = SessionMaker()
    Location.init_database(session)
    Guild.init_database(session)
    session.close()


if __name__ == "__main__":
    init_database()

    updater.start_polling()
    updater.idle()

    SessionMaker.close_all()
