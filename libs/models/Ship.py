
from sqlalchemy import Column, ForeignKey, INT, VARCHAR, BOOLEAN, TIMESTAMP, FLOAT, Table
from sqlalchemy.orm import relationship, Session

from resources.globals import Base

from libs.models.Location import Location

from bin.service import get_current_datetime, pretty_time_format

import re
import logging
import datetime


suitable_ships_table = Table(
    'suitable_ships', Base.metadata,
    Column("player_id", INT, ForeignKey("players.id")),
    Column("ship_id", INT, ForeignKey("ships.id")),
)

crashed_ships_table = Table(
    'crashed_ships', Base.metadata,
    Column("player_id", INT, ForeignKey("players.id")),
    Column("ship_id", INT, ForeignKey("ships.id")),
)

subscribed_ships_table = Table(
    'subscribed_ships', Base.metadata,
    Column("player_id", INT, ForeignKey("players.id")),
    Column("ship_id", INT, ForeignKey("ships.id")),
)


class Ship(Base):
    __tablename__ = "ships"
    id = Column(INT, primary_key=True)
    ship_id = Column(VARCHAR, unique=True)
    name = Column(VARCHAR)
    code = Column(VARCHAR)
    type = Column(VARCHAR)
    status = Column(VARCHAR)
    origin_id = Column(INT, ForeignKey("locations.id"))
    destination_id = Column(INT, ForeignKey("locations.id"))
    progress = Column(FLOAT)
    departed_date = Column(TIMESTAMP)

    origin = relationship("Location", foreign_keys=[origin_id], back_populates="outgoing_ships")
    destination = relationship("Location", foreign_keys=[destination_id], back_populates="incoming_ships")

    possible_players = relationship("Player", secondary=suitable_ships_table, back_populates="possible_ships")
    crashed_players = relationship("Player", secondary=crashed_ships_table, back_populates="crashed_ships")
    subscribed_players = relationship("Player", secondary=subscribed_ships_table, back_populates="subscribed_ships")

    _status_to_emoji = {
        "preparing": "💤",
        "starting": "🔜",
        "underway": "🚀",
        "crashed": "💥"
    }

    @property
    def status_emoji(self) -> str:
        emoji = self._status_to_emoji.get(self.status, "")
        if self.crashed:
            emoji += self._status_to_emoji.get("crashed")
        return emoji

    @property
    def crashed(self) -> bool:
        return bool(self.crashed_players)

    def format_line(self, outgoing=True):
        return "{}<code>{}</code> {} <code>{:<8}</code> {} /sh_{}\n".format(
            self.status_emoji, self.code, "→" if outgoing else "←",
            self.destination.name if outgoing else self.origin.name,
            "({}% {})".format(int(self.progress),
                              pretty_time_format(self.departed_date) if self.departed_date else "")
            if self.progress is not None else "<code>         </code>", self.id)

    @classmethod
    def get_create_ship(cls, ship_id: str, session: Session) -> 'Ship':
        ship = session.query(Ship).filter_by(ship_id=ship_id).first()
        if ship is None:
            ship = Ship(ship_id=ship_id)
            session.add(ship)
            session.commit()
        return ship

    @property
    def departed_now(self):
        return self.departed_date is not None and \
               get_current_datetime() - self.departed_date <= datetime.timedelta(minutes=1)

    def calculate_arrival(self):
        if self.departed_date and self.progress:
            return self.departed_date + (get_current_datetime() - self.departed_date) / self.progress * 100

    def format_short(self, show_link=True):
        return "{} -> {} {}%{}".format(self.origin.name, self.destination.name, self.progress,
                                        " /sh_{}".format(self.id) if show_link else "")

    def determine_locations(self, session: Session):
        parse = re.match("(.+)\n(\\w+) -\u003e(\\w+)", self.status)
        if parse is None:
            logging.error("Can not parse status: {}".format(self.status))
            return
        status, origin_code, destination_code = parse.groups()
        self.progress = None
        if "underway" in status:
            status = re.match("underway (\\d+\\.\\d+)%", status)
            self.progress = float(status.group(1))
            status = "underway"
        elif "underway" in self.status:
            # Долетел корабль
            if self.crashed:
                self.crashed_players.clear()
        self.origin, self.destination = \
            Location.get_location_by_code(origin_code, session), \
            Location.get_location_by_code(destination_code, session)
        self.status = status
        session.add(self)
        session.commit()


