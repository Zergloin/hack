from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    scope_municipality_id: Mapped[int | None] = mapped_column(ForeignKey("municipalities.id"))
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
