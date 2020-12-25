
from sqlalchemy import Column, ForeignKey, INT, VARCHAR, BOOLEAN, TIMESTAMP
from sqlalchemy.orm import Session, relationship

from first import first
from fuzzywuzzy import fuzz

from resources.globals import Base

import logging


class Location(Base):
    __tablename__ = "locations"
    id = Column(INT, primary_key=True)
    name = Column(VARCHAR)

    SPACE_ID: int = None  # Id of the 'SPACE' location in the database
    CODES = {
        "EMN": "Luna",
        "MRS": "Mars",
        "CRS": "Ceres",
        "VST": "Vesta",
        "TTN": "Titan",
        "GMD": "Ganymede",
    }
    LOCATION_NAMES = set()

    outgoing_ships = relationship("Ship", back_populates="origin", foreign_keys='Ship.origin_id')
    incoming_ships = relationship("Ship", back_populates="destination", foreign_keys='Ship.destination_id')

    @property
    def is_space(self) -> bool:
        return self.name == "Space"

    @classmethod
    def get_create_location(cls, name: str, session: Session) -> 'Location':
        location = session.query(Location).filter_by(name=name).first()
        if location is None:
            location = Location(name=name)
            session.add(location)
            session.commit()
            cls.init_database(session)

            # cls.LOCATION_NAMES.add(location.name)
        return location

    @classmethod
    def get_location_by_code(cls, code: str, session: Session) -> 'Location':
        name = cls.CODES.get(code)
        if name is None:
            name = max(cls.LOCATION_NAMES, key=lambda cur_name: fuzz.token_set_ratio(
                cur_name, code, force_ascii=False) if cur_name not in cls.LOCATION_NAMES else
                fuzz.token_set_ratio(cur_name, code, force_ascii=False) * 0.1)
            if name is None:
                logging.error("Can not find name corresponding to code {}".format(code))
                return None
            logging.warning("Can not find name corresponding to code {}, assuming it is {}".format(code, name))
            cls.CODES.update({code: name})
        location = cls.get_create_location(name, session)
        return location


    @classmethod
    def init_database(cls, session: Session):
        cls.LOCATION_NAMES.clear()
        locations = session.query(Location).all()
        list(map(lambda location: cls.LOCATION_NAMES.add(location.name),
                 filter(lambda location: not location.is_space, locations)))
        space_location = first(locations, key=lambda location: location.is_space)
        cls.SPACE_ID = space_location.id if space_location else None


