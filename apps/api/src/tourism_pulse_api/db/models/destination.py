from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tourism_pulse_api.db.base import Base


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)