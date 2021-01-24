
from sqlalchemy import Column, ForeignKey, INT, VARCHAR, BOOLEAN, TIMESTAMP, Table, BIGINT
from sqlalchemy.orm import relationship, Session

from resources.globals import Base, factions


class Guild(Base):
    __tablename__ = "guilds"
    id = Column(INT, primary_key=True)
    name = Column(VARCHAR)
    chat_id = Column(BIGINT)
    stats_message_id = Column(BIGINT)

    players = relationship("Player")

    GUILD_IDS = []

    @property
    def is_faction(self):
        return self.name.lower() in factions

    @classmethod
    def init_database(cls, session):
        cls.GUILD_IDS = list(map(lambda guild: guild.id, session.query(Guild).all()))

