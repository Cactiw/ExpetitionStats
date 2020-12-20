
from sqlalchemy import Column, ForeignKey, INT, VARCHAR, BOOLEAN, TIMESTAMP
from sqlalchemy.orm import Session

from resources.globals import Base


class Location(Base):
    __tablename__ = "locations"
    id = Column(INT, primary_key=True)
    name = Column(VARCHAR)

    @staticmethod
    def get_create_location(name: str, session: Session) -> 'Location':
        location = session.query(Location).filter_by(name=name).first()
        if location is None:
            location = Location(name=name)
            session.add(location)
            session.commit()
        return location

