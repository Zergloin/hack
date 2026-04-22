from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint("municipality_id", "forecast_year", "model_name"),
        Index("idx_forecast_muni", "municipality_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    municipality_id: Mapped[int] = mapped_column(ForeignKey("municipalities.id", ondelete="CASCADE"))
    forecast_year: Mapped[int] = mapped_column(nullable=False)
    predicted_population: Mapped[int] = mapped_column(nullable=False)
    confidence_lower: Mapped[int | None] = mapped_column()
    confidence_upper: Mapped[int | None] = mapped_column()
    model_name: Mapped[str] = mapped_column(String(100), default="linear_regression")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    municipality = relationship("Municipality", back_populates="forecasts")
