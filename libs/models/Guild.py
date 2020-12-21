
from sqlalchemy import Column, ForeignKey, INT, VARCHAR, BOOLEAN, TIMESTAMP, Table, BIGINT
from sqlalchemy.orm import relationship, Session

from resources.globals import Base


class Guild(Base):
    __tablename__ = "guilds"
    id = Column(INT, primary_key=True)
    name = Column(VARCHAR)
    chat_id = Column(BIGINT)
    stats_message_id = Column(BIGINT)

    players = relationship("Player")


