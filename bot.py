
from telegram.ext import CommandHandler, MessageHandler, Filters

from resources.globals import updater, dispatcher, job_queue, engine, Base, SessionMaker

from bin.api import update_all, TOPS_INTERVAL, view_players, view_ship, view_ships, spy, player_history

from libs.models.Location import Location

import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

dispatcher.add_handler(CommandHandler('players', view_players))
dispatcher.add_handler(CommandHandler('ships', view_ships))
dispatcher.add_handler(MessageHandler(Filters.command & Filters.regex("/sh[_ ].+"), view_ship))
dispatcher.add_handler(CommandHandler('spy', spy))
dispatcher.add_handler(MessageHandler(Filters.command & Filters.regex("/pl_history_\\d+.*"), player_history))

job_queue.run_repeating(update_all, TOPS_INTERVAL * 60, first=5)


def init_database():
    Base.metadata.create_all(engine)

    session = SessionMaker()
    Location.init_database(session)
    session.close()


if __name__ == "__main__":
    init_database()

    updater.start_polling()
    updater.idle()

    SessionMaker.close_all()
