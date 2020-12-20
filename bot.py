
from resources.globals import updater, dispatcher, job_queue, engine, Base, SessionMaker

from bin.api import update_tops, TOPS_INTERVAL

import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

job_queue.run_repeating(update_tops, TOPS_INTERVAL * 60, first=5)

if __name__ == "__main__":
    Base.metadata.create_all(engine)

    updater.start_polling()
    updater.idle()

    SessionMaker.close_all()
