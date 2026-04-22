from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    federal_district: Mapped[str | None] = mapped_column(String(100))

    municipalities = relationship("Municipality", back_populates="region")
