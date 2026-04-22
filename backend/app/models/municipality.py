from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Municipality(Base):
    __tablename__ = "municipalities"
    __table_args__ = (
        Index("idx_municipalities_region", "region_id"),
        Index("idx_municipalities_oktmo", "oktmo_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    oktmo_code: Mapped[str | None] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    municipality_type: Mapped[str] = mapped_column(String(50), nullable=False)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"))
    latitude: Mapped[float | None] = mapped_column()
    longitude: Mapped[float | None] = mapped_column()
    area_sq_km: Mapped[float | None] = mapped_column()

    region = relationship("Region", back_populates="municipalities")
    population_records = relationship("PopulationRecord", back_populates="municipality")
    demographic_indicators = relationship("DemographicIndicator", back_populates="municipality")
    forecasts = relationship("Forecast", back_populates="municipality")
