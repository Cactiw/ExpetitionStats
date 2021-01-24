
from sqlalchemy import Column, ForeignKey, INT, VARCHAR, BOOLEAN, TIMESTAMP, Table, not_, BIGINT
from sqlalchemy.orm import relationship, Session

import datetime

from resources.globals import Base

from bin.service import get_current_datetime

from libs.models.Location import Location
from libs.models.Ship import Ship, suitable_ships_table, crashed_ships_table


class Player(Base):
    __tablename__ = "players"
    id = Column(INT, primary_key=True)
    game_id = Column(VARCHAR)
    username = Column(VARCHAR)
    lvl = Column(INT)
    exp = Column(INT)
    faction = Column(VARCHAR)
    location_id = Column(INT, ForeignKey("locations.id"))
    rank = Column(INT)

    guild_id = Column(INT, ForeignKey("guilds.id"))

    telegram_id = Column(BIGINT)

    exp_history = relationship("PlayerExpChanges")
    rank_history = relationship("PlayerRankChanges")
    location_history = relationship("PlayerLocationChanges")

    location = relationship("Location")
    guild = relationship("Guild")

    location_changes: list = relationship("PlayerLocationChanges")

    possible_ships = relationship("Ship", secondary=suitable_ships_table, back_populates="possible_players")
    crashed_ships = relationship("Ship", secondary=crashed_ships_table, back_populates="crashed_players")

    @property
    def current_ship(self):
        if self.location and self.location.is_space:
            if self.possible_ships:
                return self.possible_ships[0]

    @staticmethod
    def get_create_player(game_id: str, session: Session):
        player = session.query(Player).filter_by(game_id=game_id).first()
        if player is None:
            player = Player(game_id=game_id)
            session.add(player)
            session.commit()
        return player

    def short_format(self) -> str:
        return "#<code>{:<2} 🏅{:<1}</code> [{}] {}\n".format(self.rank, self.lvl, self.faction, self.username)

    def check_update_data(self, exp: int, lvl: int, rank: int, location: 'Location', faction: str, username: str,
                          session: Session):
        if exp != self.exp:
            self.update_exp(exp, session)
        if lvl != self.lvl:
            self.update_lvl(lvl, session)
        if rank != self.rank:
            self.update_rank(rank, session)
        if location != self.location:
            self.update_location(location, session)
        if faction != self.faction:
            self.update_faction(faction, session)
        if username != self.username:
            self.update_username(username, session)

        session.add(self)
        session.commit()

    def update_exp(self, exp: int, session: Session):
        change = PlayerExpChanges(player=self, new_value=exp, date=get_current_datetime())
        self.exp = exp
        session.add(change)

    def update_lvl(self, lvl: int, session: Session):
        change = PlayerLvlChanges(player=self, new_value=lvl, date=get_current_datetime())
        self.lvl = lvl
        session.add(change)

    def update_rank(self, rank: int, session: Session):
        change = PlayerRankChanges(player=self, new_value=rank, date=get_current_datetime())
        self.rank = rank
        session.add(change)

    def update_location(self, location: 'Location', session: Session):
        change = PlayerLocationChanges(player=self, location=location, date=get_current_datetime())
        if self.location and self.location.is_space and not location.is_space:
            last_location_change = session.query(PlayerLocationChanges).join(Player).\
                join(PlayerLocationChanges.location).filter(Player.id == self.id).\
                filter(not_(Location.is_space)).order_by(PlayerLocationChanges.date.desc()).first()
            if last_location_change and location.id == last_location_change.location.id:
                # Пацаны разбились
                if self.current_ship:
                    self.crashed_ships.append(self.current_ship)
            self.possible_ships.clear()
        self.location = location
        session.add(change)

    def update_faction(self, faction: str, session: Session):
        change = PlayerFactionChanges(player=self, new_value=faction, date=get_current_datetime())
        self.faction = faction
        session.add(change)

    def update_username(self, username: str, session: Session):
        change = PlayerUsernameChanges(player=self, new_value=username, date=get_current_datetime())
        self.username = username
        session.add(change)




class PlayerExpChanges(Base):
    __tablename__ = "exp_changes"
    id = Column(INT, primary_key=True)
    player_id: int = Column(INT, ForeignKey("players.id"))
    new_value: int = Column(INT)
    date: datetime.datetime = Column(TIMESTAMP)

    player = relationship("Player")


class PlayerLvlChanges(Base):
    __tablename__ = "lvl_changes"
    id = Column(INT, primary_key=True)
    player_id: int = Column(INT, ForeignKey("players.id"))
    new_value: int = Column(INT)
    date: datetime.datetime = Column(TIMESTAMP)

    player = relationship("Player")


class PlayerRankChanges(Base):
    __tablename__ = "rank_changes"
    id = Column(INT, primary_key=True)
    player_id: int = Column(INT, ForeignKey("players.id"))
    new_value: int = Column(INT)
    date: datetime.datetime = Column(TIMESTAMP)

    player = relationship("Player")


class PlayerFactionChanges(Base):
    __tablename__ = "faction_changes"
    id = Column(INT, primary_key=True)
    player_id: int = Column(INT, ForeignKey("players.id"))
    new_value: str = Column(VARCHAR)
    date: datetime.datetime = Column(TIMESTAMP)

    player = relationship("Player")


class PlayerUsernameChanges(Base):
    __tablename__ = "username_changes"
    id = Column(INT, primary_key=True)
    player_id: int = Column(INT, ForeignKey("players.id"))
    new_value: str = Column(VARCHAR)
    date: datetime.datetime = Column(TIMESTAMP)

    player = relationship("Player")


class PlayerLocationChanges(Base):
    __tablename__ = "location_changes"
    id = Column(INT, primary_key=True)
    player_id: int = Column(INT, ForeignKey("players.id"))
    new_location_id: int = Column(INT, ForeignKey("locations.id"))
    date: datetime.datetime = Column(TIMESTAMP)

    player = relationship("Player")
    location = relationship("Location")
