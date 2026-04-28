from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from fastapi import HTTPException, status
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session_factory
from app.models.analytics import AnalyticsExportFormatEnum, AnalyticsExportJob, AnalyticsExportStatusEnum
from app.schemas.analytics_api import AnalyticsExportJobRead, AnalyticsExportRequest
from app.services.analytics_service import (
    _analytics_window,
    build_category_detail_payload,
    build_channels_payload,
    build_home_payload,
    build_operations_payload,
    build_room_detail_payload,
    build_rooms_overview_payload,
    build_segments_payload,
    get_company_fact_detail,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_export_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    data = normalized.get("data")
    if isinstance(data, dict):
        cards = data.get("cards")
        if isinstance(cards, list):
            filtered_cards = []
            for card in cards:
                if isinstance(card, dict):
                    filtered_cards.append(dict(card))
            data = dict(data)
            data["cards"] = filtered_cards
        normalized["data"] = data
    return normalized


def _normalize_export_filename_segment(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip().lower())
    return cleaned.strip("-") or "export"


def _format_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _flatten_payload_rows(payload: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = [["section", "key", "value"]]
    for key in ("hotel_id", "date_from", "date_to", "currency_display", "generated_at"):
        if key in payload:
            rows.append(["meta", key, _format_scalar(payload.get(key))])

    comparison = payload.get("comparison")
    if isinstance(comparison, dict):
        for phase in ("previous", "yoy"):
            comparison_row = comparison.get(phase)
            if isinstance(comparison_row, dict):
                for sub_key, sub_value in comparison_row.items():
                    rows.append([f"comparison.{phase}", sub_key, _format_scalar(sub_value)])

    data = payload.get("data")
    if not isinstance(data, dict):
        return rows

    cards = data.get("cards")
    if isinstance(cards, list):
        for idx, card in enumerate(cards):
            if not isinstance(card, dict):
                continue
            for field, value in card.items():
                rows.append([f"cards[{idx}]", field, _format_scalar(value)])

    for section_name, section_value in data.items():
        if section_name == "cards":
            continue
        if isinstance(section_value, list):
            for idx, item in enumerate(section_value):
                if isinstance(item, dict):
                    for field, value in item.items():
                        rows.append([f"{section_name}[{idx}]", field, _format_scalar(value)])
                else:
                    rows.append([f"{section_name}[{idx}]", "value", _format_scalar(item)])
        elif isinstance(section_value, dict):
            for field, value in section_value.items():
                if isinstance(value, (list, dict)):
                    rows.append([section_name, field, json.dumps(value, ensure_ascii=False, default=_format_scalar)])
                else:
                    rows.append([section_name, field, _format_scalar(value)])
        else:
            rows.append([section_name, "value", _format_scalar(section_value)])
    return rows


def _rows_to_csv_bytes(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _png_from_rows(rows: list[list[str]], title: str) -> bytes:
    font = ImageFont.load_default()
    lines = [title, ""]
    for row in rows[1:]:
        lines.append(" | ".join(row))
    max_line_length = max((len(line) for line in lines), default=0)
    width = min(max(720, max_line_length * 7 + 40), 2200)
    line_height = 14
    height = max(180, (len(lines) + 2) * line_height + 24)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    y = 16
    draw.text((18, y), title, fill="black", font=font)
    y += 24
    for line in lines[2:]:
        draw.text((18, y), line[:300], fill="black", font=font)
        y += line_height
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _sheet_xml_from_table(rows: list[list[str]]) -> str:
    def col_name(index: int) -> str:
        result = ""
        while index:
            index, rem = divmod(index - 1, 26)
            result = chr(65 + rem) + result
        return result

    sheet_rows: list[str] = []
    for row_number, row in enumerate(rows, start=1):
        cells: list[str] = []
        for col_index, value in enumerate(row, start=1):
            ref = f"{col_name(col_index)}{row_number}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{xml_escape(str(value))}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        + "".join(sheet_rows)
        + "</sheetData></worksheet>"
    )


def _sheet_name(value: str, used: set[str]) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {" ", "-", "_"} else "_" for ch in value).strip()
    cleaned = cleaned[:31] or "Sheet"
    candidate = cleaned
    suffix = 2
    while candidate in used:
        base = cleaned[: max(1, 31 - len(str(suffix)) - 1)]
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _build_xlsx_bytes(sheets: list[tuple[str, list[list[str]]]]) -> bytes:
    workbook_rels = []
    workbook_sheets = []
    used_names: set[str] = set()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for index in range(1, len(sheets) + 1)
            )
            + "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/styles.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
            '<borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            "</styleSheet>",
        )

        for index, (name, rows) in enumerate(sheets, start=1):
            sheet_name = _sheet_name(name, used_names)
            zf.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml_from_table(rows))
            workbook_rels.append(
                f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            )
            workbook_sheets.append(f'<sheet name="{xml_escape(sheet_name)}" sheetId="{index}" r:id="rId{index}"/>')

        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{"".join(workbook_sheets)}</sheets>'
            "</workbook>",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(workbook_rels)
            + "</Relationships>",
        )
    return output.getvalue()


def _build_payload_for_request(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> dict[str, Any]:
    if request.entity_code == "home":
        return _normalize_export_payload(
            build_home_payload(
                db,
                hotel_id=hotel_id,
                date_from=request.date_from,
                date_to=request.date_to,
                compare_previous=request.compare_previous,
                compare_yoy=request.compare_yoy,
                currency_display=request.currency_display,
            )
        )
    if request.entity_code == "rooms":
        return _normalize_export_payload(
            build_rooms_overview_payload(
                db,
                hotel_id=hotel_id,
                date_from=request.date_from,
                date_to=request.date_to,
                compare_previous=request.compare_previous,
                compare_yoy=request.compare_yoy,
                currency_display=request.currency_display,
            )
        )
    if request.entity_code == "room":
        if request.room_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="room_id es requerido para entity_code=room")
        return _normalize_export_payload(
            build_room_detail_payload(
                db,
                hotel_id=hotel_id,
                room_id=request.room_id,
                date_from=request.date_from,
                date_to=request.date_to,
                compare_previous=request.compare_previous,
                compare_yoy=request.compare_yoy,
                currency_display=request.currency_display,
            )
        )
    if request.entity_code == "category":
        if request.category_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="category_id es requerido para entity_code=category")
        return _normalize_export_payload(
            build_category_detail_payload(
                db,
                hotel_id=hotel_id,
                category_id=request.category_id,
                date_from=request.date_from,
                date_to=request.date_to,
                compare_previous=request.compare_previous,
                compare_yoy=request.compare_yoy,
                currency_display=request.currency_display,
            )
        )
    if request.entity_code == "segments":
        return _normalize_export_payload(
            build_segments_payload(
                db,
                hotel_id=hotel_id,
                date_from=request.date_from,
                date_to=request.date_to,
                compare_previous=request.compare_previous,
                compare_yoy=request.compare_yoy,
                currency_display=request.currency_display,
            )
        )
    if request.entity_code == "company":
        if request.company_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="company_id es requerido para entity_code=company")
        window = _analytics_window(
            db,
            hotel_id,
            date_from=request.date_from,
            date_to=request.date_to,
            compare_previous=request.compare_previous,
            compare_yoy=request.compare_yoy,
        )
        return {
            "hotel_id": hotel_id,
            "date_from": window.date_from,
            "date_to": window.date_to,
            "currency_display": request.currency_display,
            "comparison": window.comparison,
            "data": get_company_fact_detail(
                db,
                hotel_id=hotel_id,
                company_id=request.company_id,
                date_from=window.date_from,
                date_to=window.date_to,
            ),
            "generated_at": _now(),
        }
    if request.entity_code == "channels":
        return _normalize_export_payload(
            build_channels_payload(
                db,
                hotel_id=hotel_id,
                date_from=request.date_from,
                date_to=request.date_to,
                compare_previous=request.compare_previous,
                compare_yoy=request.compare_yoy,
                currency_display=request.currency_display,
            )
        )
    if request.entity_code == "operations":
        return _normalize_export_payload(
            build_operations_payload(
                db,
                hotel_id=hotel_id,
                date_from=request.date_from,
                date_to=request.date_to,
                compare_previous=request.compare_previous,
                compare_yoy=request.compare_yoy,
                currency_display=request.currency_display,
            )
        )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entity_code inválido")


def build_export_payload(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> dict[str, Any]:
    return _build_payload_for_request(db, hotel_id=hotel_id, request=request)


def render_export_csv(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> bytes:
    payload = build_export_payload(db, hotel_id=hotel_id, request=request)
    return _rows_to_csv_bytes(_flatten_payload_rows(payload))


def render_export_png(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> bytes:
    payload = build_export_payload(db, hotel_id=hotel_id, request=request)
    return _png_from_rows(_flatten_payload_rows(payload), title=f"Analytics export - {request.entity_code}")


def render_export_xlsx(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> bytes:
    payload = build_export_payload(db, hotel_id=hotel_id, request=request)
    sheets: list[tuple[str, list[list[str]]]] = []
    rows = _flatten_payload_rows(payload)
    sheets.append(("Summary", rows))

    data = payload.get("data")
    if isinstance(data, dict):
        cards = data.get("cards")
        if isinstance(cards, list) and cards:
            card_rows: list[list[str]] = [["card_code", "label", "value_count", "value_pct", "value_ars", "value_usd"]]
            for card in cards:
                if not isinstance(card, dict):
                    continue
                card_rows.append(
                    [
                        _format_scalar(card.get("card_code")),
                        _format_scalar(card.get("label")),
                        _format_scalar(card.get("value_count")),
                        _format_scalar(card.get("value_pct")),
                        _format_scalar(card.get("value_ars")),
                        _format_scalar(card.get("value_usd")),
                    ]
                )
            sheets.append(("Cards", card_rows))

        for section_name, section_value in data.items():
            if section_name == "cards":
                continue
            if isinstance(section_value, list) and section_value:
                headers: list[str] = []
                for item in section_value:
                    if isinstance(item, dict):
                        for key in item.keys():
                            if key not in headers:
                                headers.append(key)
                if headers:
                    section_rows: list[list[str]] = [headers]
                    for item in section_value:
                        if isinstance(item, dict):
                            section_rows.append([_format_scalar(item.get(header)) for header in headers])
                        else:
                            section_rows.append([_format_scalar(item)])
                    sheets.append((section_name[:31], section_rows))
            elif isinstance(section_value, dict) and section_value:
                section_rows = [["key", "value"]]
                for key, value in section_value.items():
                    section_rows.append([key, _format_scalar(value)])
                sheets.append((section_name[:31], section_rows))
    return _build_xlsx_bytes(sheets)


def create_xlsx_export_job(db: Session, *, hotel_id: int, user_id: int, request: AnalyticsExportRequest) -> AnalyticsExportJob:
    job = AnalyticsExportJob(
        hotel_id=hotel_id,
        user_id=user_id,
        entity_code=request.entity_code,
        card_code=request.card_code,
        format=AnalyticsExportFormatEnum.XLSX,
        currency_display=request.currency_display,
        date_from=request.date_from or _now().date(),
        date_to=request.date_to or _now().date(),
        compare_previous=request.compare_previous,
        compare_yoy=request.compare_yoy,
        filters_json=request.model_dump_json(exclude_none=True),
        status=AnalyticsExportStatusEnum.PENDING,
        expires_at=_now() + timedelta(hours=24),
    )
    db.add(job)
    db.flush()
    return job


def _export_job_path(job: AnalyticsExportJob) -> Path:
    settings = get_settings()
    created_at = job.created_at or _now()
    return Path(settings.ANALYTICS_EXPORTS_DIR) / str(job.hotel_id) / f"{created_at.year:04d}" / f"{created_at.month:02d}" / f"{job.id}.xlsx"


def _persist_export_file(job: AnalyticsExportJob, file_bytes: bytes) -> None:
    path = _export_job_path(job)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(file_bytes)
    job.file_path = str(path)
    job.file_size_bytes = len(file_bytes)
    job.sha256_hex = hashlib.sha256(file_bytes).hexdigest()


def generate_xlsx_export_job(job_id: int) -> None:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        job = db.get(AnalyticsExportJob, job_id)
        if not job:
            return
        if job.status == AnalyticsExportStatusEnum.EXPIRED:
            return
        request = AnalyticsExportRequest.model_validate(json.loads(job.filters_json))
        job.status = AnalyticsExportStatusEnum.RUNNING
        job.started_at = _now()
        db.flush()
        file_bytes = render_export_xlsx(db, hotel_id=job.hotel_id, request=request)
        _persist_export_file(job, file_bytes)
        job.status = AnalyticsExportStatusEnum.COMPLETED
        job.completed_at = _now()
        job.error_code = None
        job.error_message = None
        db.commit()
    except Exception as exc:  # pragma: no cover - exercised through API tests if generation fails
        db.rollback()
        job = db.get(AnalyticsExportJob, job_id)
        if job:
            job.status = AnalyticsExportStatusEnum.FAILED
            job.error_code = exc.__class__.__name__
            job.error_message = str(exc)[:500]
            job.completed_at = _now()
            try:
                db.commit()
            except Exception:  # pragma: no cover - defensive secondary failure path
                db.rollback()
        raise
    finally:
        db.close()


def list_export_jobs(db: Session, *, hotel_id: int) -> list[AnalyticsExportJobRead]:
    rows = (
        db.query(AnalyticsExportJob)
        .filter(AnalyticsExportJob.hotel_id == hotel_id)
        .order_by(AnalyticsExportJob.created_at.desc(), AnalyticsExportJob.id.desc())
        .all()
    )
    return [AnalyticsExportJobRead.model_validate(row) for row in rows]


def get_export_job_or_404(db: Session, *, hotel_id: int, job_id: int) -> AnalyticsExportJob:
    job = db.get(AnalyticsExportJob, job_id)
    if not job or job.hotel_id != hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job no encontrado")
    return job


def get_export_job_read(db: Session, *, hotel_id: int, job_id: int) -> AnalyticsExportJobRead:
    return AnalyticsExportJobRead.model_validate(get_export_job_or_404(db, hotel_id=hotel_id, job_id=job_id))


def get_export_download_path(job: AnalyticsExportJob) -> Path:
    if not job.file_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export job no finalizado")
    return Path(job.file_path)


def expire_export_job_if_needed(db: Session, job: AnalyticsExportJob) -> bool:
    if job.status == AnalyticsExportStatusEnum.EXPIRED:
        return True
    expires_at = _ensure_utc(job.expires_at)
    if expires_at and expires_at <= _now():
        job.status = AnalyticsExportStatusEnum.EXPIRED
        db.flush()
        return True
    return False
