
import pytz
import tzlocal
import psycopg2
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLSession
from sqlalchemy.ext.declarative import declarative_base

from libs.bot import AsyncBot
from libs.updater import AsyncUpdater
from libs.database import Conn

from config import TOKEN, request_kwargs, psql_credentials

bot = AsyncBot(token=TOKEN, workers=16, request_kwargs=request_kwargs)
updater = AsyncUpdater(bot=bot)

dispatcher = updater.dispatcher
job_queue = updater.job_queue

bot.dispatcher = dispatcher

engine = create_engine(f'postgresql+psycopg2://{psql_credentials["user"]}:{psql_credentials["pass"]}@'
                       f'{psql_credentials["host"]}:{psql_credentials["port"]}/{psql_credentials["dbname"]}',
                       echo=False)

SessionMaker = sessionmaker(bind=engine, autoflush=False)
session: SQLSession = SessionMaker()
Base = declarative_base()


moscow_tz = pytz.timezone('Europe/Moscow')
try:
    local_tz = tzlocal.get_localzone()
except pytz.UnknownTimeZoneError:
    local_tz = pytz.timezone('Europe/Andorra')
utc = pytz.utc
