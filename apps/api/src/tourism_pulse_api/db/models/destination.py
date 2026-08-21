from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tourism_pulse_api.db.base import Base

if TYPE_CHECKING:
    from tourism_pulse_api.db.models.place import Place


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    places: Mapped[list["Place"]] = relationship(
        back_populates="destination",
        cascade="all, delete-orphan",
    )