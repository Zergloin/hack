from datetime import datetime

from pydantic import BaseModel


class ReportGenerateRequest(BaseModel):
    report_type: str = "comprehensive"
    region_id: int | None = None
    municipality_id: int | None = None
    year_from: int | None = None
    year_to: int | None = None


class ReportOut(BaseModel):
    id: int
    title: str
    report_type: str
    content_markdown: str
    content_html: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
