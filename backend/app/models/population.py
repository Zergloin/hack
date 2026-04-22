from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class PopulationRecord(Base):
    __tablename__ = "population_records"
    __table_args__ = (
        UniqueConstraint("municipality_id", "year"),
        Index("idx_pop_muni_year", "municipality_id", "year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    municipality_id: Mapped[int] = mapped_column(ForeignKey("municipalities.id", ondelete="CASCADE"))
    year: Mapped[int] = mapped_column(nullable=False)
    population: Mapped[int | None] = mapped_column()

    municipality = relationship("Municipality", back_populates="population_records")
