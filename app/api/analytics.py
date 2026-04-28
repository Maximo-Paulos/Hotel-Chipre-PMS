from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.analytics import AnalyticsResponseEnvelopeRead, AnalyticsStarterSummaryRead
from app.schemas.analytics_api import (
    AnalyticsAIConfigRead,
    AnalyticsAIConfigUpdate,
    AnalyticsExportJobRead,
    AnalyticsExportRequest,
    AnalyticsAlertSettingsRead,
    AnalyticsAlertSettingsUpdate,
    AnalyticsAlertSnoozeCreate,
    AnalyticsAlertSnoozeRead,
)
from app.schemas.analytics_insights import AnalyticsAIChatRead, AnalyticsAIChatRequest, AnalyticsInsightRead, AnalyticsInsightRequest, AnalyticsInsightStatusRead
from app.services.analytics_service import (
    build_category_detail_payload,
    build_channels_payload,
    build_home_payload,
    get_company_fact_detail,
    build_operations_payload,
    build_room_detail_payload,
    build_rooms_overview_payload,
    build_segments_payload,
    build_starter_summary_payload,
    get_ai_config,
    get_alert_settings,
    patch_ai_config,
    patch_alert_settings,
    require_analytics_plan,
    snooze_alert,
    unsnooze_alert,
    _analytics_window,
)
from app.services.analytics_exports import (
    create_xlsx_export_job,
    expire_export_job_if_needed,
    generate_xlsx_export_job,
    get_export_job_or_404,
    get_export_job_read,
    list_export_jobs,
    render_export_csv,
    render_export_png,
)
from app.services.analytics_insights import (
    build_anomalies_insight,
    build_analytics_chat_answer,
    build_home_insight,
    build_pricing_insight,
    get_analytics_ai_status,
)
from app.models.analytics import AnalyticsExportStatusEnum


router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def _common_filters(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    currency_display: str = Query(default="ARS"),
    compare_previous: bool = Query(default=True),
    compare_yoy: bool = Query(default=False),
):
    return {
        "date_from": date_from,
        "date_to": date_to,
        "currency_display": currency_display,
        "compare_previous": compare_previous,
        "compare_yoy": compare_yoy,
    }


@router.get("/starter-summary", response_model=AnalyticsStarterSummaryRead)
def starter_summary(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "starter")
    return build_starter_summary_payload(db, hotel_id=context.hotel_id, date_from=date_from, date_to=date_to)


@router.get("/home", response_model=AnalyticsResponseEnvelopeRead)
def analytics_home(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    currency_display: str = Query(default="ARS"),
    compare_previous: bool = Query(default=True),
    compare_yoy: bool = Query(default=False),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return build_home_payload(
        db,
        hotel_id=context.hotel_id,
        date_from=date_from,
        date_to=date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
        currency_display=currency_display,
    )


@router.get("/rooms", response_model=AnalyticsResponseEnvelopeRead)
def analytics_rooms(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    currency_display: str = Query(default="ARS"),
    compare_previous: bool = Query(default=True),
    compare_yoy: bool = Query(default=False),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return build_rooms_overview_payload(
        db,
        hotel_id=context.hotel_id,
        date_from=date_from,
        date_to=date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
        currency_display=currency_display,
    )


@router.get("/rooms/{room_id}", response_model=AnalyticsResponseEnvelopeRead)
def analytics_room_detail(
    room_id: int,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    currency_display: str = Query(default="ARS"),
    compare_previous: bool = Query(default=True),
    compare_yoy: bool = Query(default=False),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return build_room_detail_payload(
        db,
        hotel_id=context.hotel_id,
        room_id=room_id,
        date_from=date_from,
        date_to=date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
        currency_display=currency_display,
    )


@router.get("/categories/{category_id}", response_model=AnalyticsResponseEnvelopeRead)
def analytics_category_detail(
    category_id: int,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    currency_display: str = Query(default="ARS"),
    compare_previous: bool = Query(default=True),
    compare_yoy: bool = Query(default=False),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return build_category_detail_payload(
        db,
        hotel_id=context.hotel_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
        currency_display=currency_display,
    )


@router.get("/segments", response_model=AnalyticsResponseEnvelopeRead)
def analytics_segments(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    currency_display: str = Query(default="ARS"),
    compare_previous: bool = Query(default=True),
    compare_yoy: bool = Query(default=False),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return build_segments_payload(
        db,
        hotel_id=context.hotel_id,
        date_from=date_from,
        date_to=date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
        currency_display=currency_display,
    )


@router.get("/companies/{company_id}", response_model=AnalyticsResponseEnvelopeRead)
def analytics_company_detail(
    company_id: int,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    currency_display: str = Query(default="ARS"),
    compare_previous: bool = Query(default=True),
    compare_yoy: bool = Query(default=False),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    window = _analytics_window(
        db,
        context.hotel_id,
        date_from=date_from,
        date_to=date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
    )
    payload = get_company_fact_detail(
        db,
        hotel_id=context.hotel_id,
        company_id=company_id,
        date_from=window.date_from,
        date_to=window.date_to,
    )
    return {
        "hotel_id": context.hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "currency_display": currency_display,
        "comparison": window.comparison,
        "data": payload,
        "generated_at": datetime.now(timezone.utc),
    }


@router.get("/channels", response_model=AnalyticsResponseEnvelopeRead)
def analytics_channels(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    currency_display: str = Query(default="ARS"),
    compare_previous: bool = Query(default=True),
    compare_yoy: bool = Query(default=False),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return build_channels_payload(
        db,
        hotel_id=context.hotel_id,
        date_from=date_from,
        date_to=date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
        currency_display=currency_display,
    )


@router.get("/operations", response_model=AnalyticsResponseEnvelopeRead)
def analytics_operations(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    currency_display: str = Query(default="ARS"),
    compare_previous: bool = Query(default=True),
    compare_yoy: bool = Query(default=False),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return build_operations_payload(
        db,
        hotel_id=context.hotel_id,
        date_from=date_from,
        date_to=date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
        currency_display=currency_display,
    )


@router.post("/exports/png")
def export_analytics_png(
    payload: AnalyticsExportRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    content = render_export_png(db, hotel_id=context.hotel_id, request=payload)
    filename = f"analytics-{context.hotel_id}-{payload.entity_code}.png"
    return Response(
        content=content,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/exports/csv")
def export_analytics_csv(
    payload: AnalyticsExportRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    content = render_export_csv(db, hotel_id=context.hotel_id, request=payload)
    filename = f"analytics-{context.hotel_id}-{payload.entity_code}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/exports/xlsx", response_model=AnalyticsExportJobRead, status_code=201)
def export_analytics_xlsx(
    payload: AnalyticsExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    job = create_xlsx_export_job(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, request=payload)
    db.commit()
    background_tasks.add_task(generate_xlsx_export_job, job.id)
    return get_export_job_read(db, hotel_id=context.hotel_id, job_id=job.id)


@router.get("/exports", response_model=list[AnalyticsExportJobRead])
def list_analytics_exports(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    return list_export_jobs(db, hotel_id=context.hotel_id)


@router.get("/exports/{job_id}", response_model=AnalyticsExportJobRead)
def get_analytics_export(
    job_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    return get_export_job_read(db, hotel_id=context.hotel_id, job_id=job_id)


@router.get("/exports/{job_id}/download")
def download_analytics_export(
    job_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    job = get_export_job_or_404(db, hotel_id=context.hotel_id, job_id=job_id)
    if expire_export_job_if_needed(db, job):
        db.commit()
        raise HTTPException(status_code=410, detail="Export vencido")
    if job.status != AnalyticsExportStatusEnum.COMPLETED:
        raise HTTPException(status_code=409, detail="Export no finalizado")
    if not job.file_path:
        raise HTTPException(status_code=404, detail="Archivo de export no encontrado")
    return FileResponse(
        path=job.file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(job.file_path).name,
    )


@router.get("/alert-settings", response_model=AnalyticsAlertSettingsRead)
def analytics_alert_settings(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    result = get_alert_settings(db, hotel_id=context.hotel_id, user_id=context.user_id or 0)
    db.commit()
    return result


@router.patch("/alert-settings", response_model=AnalyticsAlertSettingsRead)
def patch_analytics_alert_settings(
    payload: AnalyticsAlertSettingsUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    result = patch_alert_settings(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, payload=payload)
    db.commit()
    return result


@router.post("/alerts/{alert_code}/snooze", response_model=AnalyticsAlertSnoozeRead)
def snooze_analytics_alert(
    alert_code: str,
    payload: AnalyticsAlertSnoozeCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    result = snooze_alert(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, alert_code=alert_code, payload=payload)
    db.commit()
    return result


@router.delete("/alerts/{alert_code}/snooze")
def unsnooze_analytics_alert(
    alert_code: str,
    scope_key: str = Query(default="global", min_length=1, max_length=120),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    result = unsnooze_alert(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, alert_code=alert_code, scope_key=scope_key)
    db.commit()
    return result


@router.get("/ai-config", response_model=AnalyticsAIConfigRead)
def analytics_ai_config(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    return get_ai_config(db, context.hotel_id)


@router.patch("/ai-config", response_model=AnalyticsAIConfigRead)
def patch_analytics_ai_config(
    payload: AnalyticsAIConfigUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    result = patch_ai_config(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, payload=payload)
    db.commit()
    return result


@router.get("/insights/status", response_model=AnalyticsInsightStatusRead)
def analytics_insights_status(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    result = get_analytics_ai_status(db, hotel_id=context.hotel_id)
    db.commit()
    return result


@router.post("/ai-chat", response_model=AnalyticsAIChatRead)
def analytics_ai_chat(
    payload: AnalyticsAIChatRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    result = build_analytics_chat_answer(db, hotel_id=context.hotel_id, payload=payload)
    db.commit()
    return result


@router.post("/insights/home", response_model=AnalyticsInsightRead)
def analytics_insights_home(
    payload: AnalyticsInsightRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    result = build_home_insight(db, hotel_id=context.hotel_id, payload=payload)
    db.commit()
    return result


@router.post("/insights/anomalies", response_model=AnalyticsInsightRead)
def analytics_insights_anomalies(
    payload: AnalyticsInsightRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    result = build_anomalies_insight(db, hotel_id=context.hotel_id, payload=payload)
    db.commit()
    return result


@router.post("/insights/pricing", response_model=AnalyticsInsightRead)
def analytics_insights_pricing(
    payload: AnalyticsInsightRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "ultra")
    result = build_pricing_insight(db, hotel_id=context.hotel_id, payload=payload)
    db.commit()
    return result
