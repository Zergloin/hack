from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class DemographicIndicator(Base):
    __tablename__ = "demographic_indicators"
    __table_args__ = (
        UniqueConstraint("municipality_id", "year"),
        Index("idx_demo_muni_year", "municipality_id", "year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    municipality_id: Mapped[int] = mapped_column(ForeignKey("municipalities.id", ondelete="CASCADE"))
    year: Mapped[int] = mapped_column(nullable=False)
    births: Mapped[int | None] = mapped_column()
    deaths: Mapped[int | None] = mapped_column()
    natural_growth: Mapped[int | None] = mapped_column()
    migration_in: Mapped[int | None] = mapped_column()
    migration_out: Mapped[int | None] = mapped_column()
    net_migration: Mapped[int | None] = mapped_column()
    birth_rate: Mapped[float | None] = mapped_column()
    death_rate: Mapped[float | None] = mapped_column()
    natural_growth_rate: Mapped[float | None] = mapped_column()
    net_migration_rate: Mapped[float | None] = mapped_column()

    municipality = relationship("Municipality", back_populates="demographic_indicators")
