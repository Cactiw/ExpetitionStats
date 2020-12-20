
from sqlalchemy import Column, ForeignKey, INT, VARCHAR, BOOLEAN, TIMESTAMP, FLOAT
from sqlalchemy.orm import relationship, Session

from resources.globals import Base

from libs.models.Location import Location

import re
import logging


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

    origin = relationship("Location", foreign_keys=[origin_id])
    destination = relationship("Location", foreign_keys=[destination_id])

    @classmethod
    def get_create_ship(cls, ship_id: str, session: Session) -> 'Ship':
        ship = session.query(Ship).filter_by(ship_id=ship_id).first()
        if ship is None:
            ship = Ship(ship_id=ship_id)
            session.add(ship)
            session.commit()
        return ship

    def determine_locations(self, session: Session):
        parse = re.match("(.+)\n(\\w+) -\u003e(\\w+)", self.status)
        if parse is None:
            logging.error("Can not parse status: {}".format(self.status))
            return
        status, origin_code, destination_code = parse.groups()
        if "underway" in status:
            status = re.match("underway (\\d+\\.\\d+)%", status)
            self.progress = float(status.group(1))
            status = "underway"
        self.origin, self.destination = \
            Location.get_location_by_code(origin_code, session), \
            Location.get_location_by_code(destination_code, session)
        self.status = status
        session.add(self)
        session.commit()


