import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.report import Report
from app.schemas.report import ReportGenerateRequest, ReportOut
from app.services.report_service import export_docx, export_pdf, generate_report

router = APIRouter()


@router.post("/generate", response_model=ReportOut)
async def create_report(
    request: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    report = await generate_report(db, request)
    return report


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/export")
async def export_report(
    report_id: int,
    format: str = Query(default="pdf", pattern="^(pdf|docx)$"),
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if format == "pdf":
        pdf_bytes = export_pdf(report.content_html or report.content_markdown)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="report_{report_id}.pdf"'},
        )
    else:
        docx_bytes = export_docx(report.content_markdown)
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="report_{report_id}.docx"'},
        )
