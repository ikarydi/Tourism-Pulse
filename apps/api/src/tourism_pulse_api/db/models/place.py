from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)

    destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    place_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )