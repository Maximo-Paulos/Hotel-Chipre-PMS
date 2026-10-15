from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Iterable as IterableABC
from datetime import datetime, timedelta, timezone
from itertools import chain, islice
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, Iterable, Iterator
from xml.sax.saxutils import escape as xml_escape

from fastapi import HTTPException, status
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.database import get_session_factory
from app.models.analytics import AnalyticsExportFormatEnum, AnalyticsExportJob, AnalyticsExportStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.schemas.analytics_api import AnalyticsExportJobRead, AnalyticsExportRequest
from app.services.object_storage import ObjectStorageError, get_object_storage
from app.services.stored_object_service import register_uploaded_object, register_uploaded_object_file
from app.services.csv_export_safety import spreadsheet_safe_value
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
from app.services.tenant_context import set_tenant_hotel_context


PNG_EXPORT_PAGE_ROWS = 250
PNG_EXPORT_SPOOL_MEMORY_BYTES = 8 * 1024 * 1024
XLSX_EXPORT_SPOOL_MEMORY_BYTES = 8 * 1024 * 1024
XLSX_MAX_ROWS_PER_SHEET = 1_048_576


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


def _xml_10_text(value: str) -> str:
    """Drop code points forbidden in XML 1.0 before escaping cell text."""
    return "".join(
        character
        for character in value
        if character in "\t\n\r"
        or 0x20 <= ord(character) <= 0xD7FF
        or 0xE000 <= ord(character) <= 0xFFFD
        or 0x10000 <= ord(character) <= 0x10FFFF
    )


def _iter_export_payload_rows(payload: dict[str, Any]) -> Iterator[list[str]]:
    yield ["section", "key", "value"]
    for key in ("hotel_id", "date_from", "date_to", "currency_display", "generated_at"):
        if key in payload:
            yield ["meta", key, _format_scalar(payload.get(key))]

    comparison = payload.get("comparison")
    if not isinstance(comparison, dict) and callable(getattr(comparison, "model_dump", None)):
        comparison = comparison.model_dump()
    if isinstance(comparison, dict):
        for phase in ("previous", "yoy"):
            comparison_row = comparison.get(phase)
            if isinstance(comparison_row, dict):
                for sub_key, sub_value in comparison_row.items():
                    yield [f"comparison.{phase}", sub_key, _format_scalar(sub_value)]

    data = payload.get("data")
    if not isinstance(data, dict):
        return

    cards = data.get("cards")
    if isinstance(cards, list):
        for idx, card in enumerate(cards):
            if not isinstance(card, dict):
                continue
            for field, value in card.items():
                yield [f"cards[{idx}]", field, _format_scalar(value)]

    for section_name, section_value in data.items():
        if section_name == "cards":
            continue
        if _is_row_collection(section_value):
            for idx, item in enumerate(section_value):
                if isinstance(item, dict):
                    for field, value in item.items():
                        yield [f"{section_name}[{idx}]", field, _format_scalar(value)]
                else:
                    yield [f"{section_name}[{idx}]", "value", _format_scalar(item)]
        elif isinstance(section_value, dict):
            for field, value in section_value.items():
                if isinstance(value, (list, dict)):
                    yield [section_name, field, json.dumps(value, ensure_ascii=False, default=_format_scalar)]
                else:
                    yield [section_name, field, _format_scalar(value)]
        else:
            yield [section_name, "value", _format_scalar(section_value)]


def _is_row_collection(value: Any) -> bool:
    return isinstance(value, IterableABC) and not isinstance(value, (dict, str, bytes, bytearray))


def _flatten_payload_rows(payload: dict[str, Any]) -> list[list[str]]:
    """Compatibility helper for renderers that need random access to rows."""
    return list(_iter_export_payload_rows(payload))


def _rows_to_csv_bytes(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows([[spreadsheet_safe_value(value) for value in row] for row in rows])
    return buffer.getvalue().encode("utf-8-sig")


def _iter_csv_chunks(rows: Iterable[list[str]], *, batch_rows: int = 128) -> Iterator[bytes]:
    """Encode rows in small batches so exports do not copy the full CSV in RAM."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    pending_rows = 0
    first_chunk = True
    for row in rows:
        writer.writerow([spreadsheet_safe_value(value) for value in row])
        pending_rows += 1
        if pending_rows < batch_rows:
            continue
        chunk = buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)
        if first_chunk:
            chunk = b"\xef\xbb\xbf" + chunk
            first_chunk = False
        if chunk:
            yield chunk
        pending_rows = 0
    remainder = buffer.getvalue().encode("utf-8")
    if remainder or first_chunk:
        yield (b"\xef\xbb\xbf" if first_chunk else b"") + remainder


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


def _png_export_content(rows: Iterable[list[str]], *, title: str) -> bytes | SpooledTemporaryFile:
    """Return one PNG for ordinary reports or a disk-spooled ZIP of pages for long reports."""
    row_iterator = iter(rows)
    header = next(row_iterator, ["section", "key", "value"])
    first_page = list(islice(row_iterator, PNG_EXPORT_PAGE_ROWS))
    second_page = list(islice(row_iterator, PNG_EXPORT_PAGE_ROWS))
    if not second_page:
        return _png_from_rows([header, *first_page], title=title)

    archive_file = SpooledTemporaryFile(max_size=PNG_EXPORT_SPOOL_MEMORY_BYTES, mode="w+b")
    try:
        with zipfile.ZipFile(archive_file, "w", compression=zipfile.ZIP_STORED) as archive:
            page_number = 1
            for page_rows in (first_page, second_page):
                archive.writestr(
                    f"page-{page_number:04d}.png",
                    _png_from_rows([header, *page_rows], title=f"{title} - page {page_number}"),
                )
                page_number += 1
            while True:
                page_rows = list(islice(row_iterator, PNG_EXPORT_PAGE_ROWS))
                if not page_rows:
                    break
                archive.writestr(
                    f"page-{page_number:04d}.png",
                    _png_from_rows([header, *page_rows], title=f"{title} - page {page_number}"),
                )
                page_number += 1
        archive_file.seek(0)
        return archive_file
    except Exception:
        archive_file.close()
        raise


def iter_export_file_chunks(file_obj: BinaryIO, *, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    """Read a spooled export in bounded chunks and always release its temporary file."""
    try:
        file_obj.seek(0)
        while chunk := file_obj.read(chunk_size):
            yield chunk
    finally:
        file_obj.close()


def _iter_sheet_xml_chunks(rows: Iterable[list[str]]) -> Iterator[str]:
    def col_name(index: int) -> str:
        result = ""
        while index:
            index, rem = divmod(index - 1, 26)
            result = chr(65 + rem) + result
        return result

    yield (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
    )
    for row_number, row in enumerate(rows, start=1):
        cells: list[str] = []
        for col_index, value in enumerate(row, start=1):
            ref = f"{col_name(col_index)}{row_number}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{xml_escape(_xml_10_text(str(value)))}</t></is></c>'
            )
        yield f'<row r="{row_number}">{"".join(cells)}</row>'
    yield "</sheetData></worksheet>"


def _sheet_xml_from_table(rows: list[list[str]]) -> str:
    """Compatibility helper for callers that need a complete XML string."""
    return "".join(_iter_sheet_xml_chunks(rows))


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


def _build_xlsx_spool(
    sheets: list[tuple[str, Iterable[list[str]]]],
    *,
    max_rows_per_sheet: int = XLSX_MAX_ROWS_PER_SHEET,
) -> SpooledTemporaryFile:
    if max_rows_per_sheet < 2:
        raise ValueError("max_rows_per_sheet must allow a header and at least one data row")
    workbook_rels = []
    workbook_sheets = []
    used_names: set[str] = set()
    worksheet_count = 0
    output = SpooledTemporaryFile(max_size=XLSX_EXPORT_SPOOL_MEMORY_BYTES, mode="w+b")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
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

        sentinel = object()
        for name, rows in sheets:
            row_iterator = iter(rows)
            header = next(row_iterator, [])
            first_data_row = next(row_iterator, sentinel)
            page_number = 1
            while True:
                worksheet_count += 1
                page_name = name if page_number == 1 else f"{name} ({page_number})"
                sheet_name = _sheet_name(page_name, used_names)
                data_slots = max_rows_per_sheet - (2 if first_data_row is not sentinel else 1)
                page_rows = chain(
                    (header,),
                    (first_data_row,) if first_data_row is not sentinel else (),
                    islice(row_iterator, data_slots),
                )
                with zf.open(f"xl/worksheets/sheet{worksheet_count}.xml", "w") as worksheet:
                    for xml_chunk in _iter_sheet_xml_chunks(page_rows):
                        worksheet.write(xml_chunk.encode("utf-8"))
                workbook_rels.append(
                    f'<Relationship Id="rId{worksheet_count}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{worksheet_count}.xml"/>'
                )
                workbook_sheets.append(
                    f'<sheet name="{xml_escape(sheet_name)}" sheetId="{worksheet_count}" r:id="rId{worksheet_count}"/>'
                )

                first_data_row = next(row_iterator, sentinel)
                if first_data_row is sentinel:
                    break
                page_number += 1

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
                for index in range(1, worksheet_count + 1)
            )
            + "</Types>",
        )

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
    output.seek(0)
    return output


def _build_xlsx_bytes(
    sheets: list[tuple[str, Iterable[list[str]]]],
    *,
    max_rows_per_sheet: int = XLSX_MAX_ROWS_PER_SHEET,
) -> bytes:
    output = _build_xlsx_spool(sheets, max_rows_per_sheet=max_rows_per_sheet)
    try:
        return output.read()
    finally:
        output.close()


def _build_payload_for_request(
    db: Session,
    *,
    hotel_id: int,
    request: AnalyticsExportRequest,
    stream_details: bool = False,
) -> dict[str, Any]:
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
                stream_details=stream_details,
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
                stream_details=stream_details,
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
        company_detail = get_company_fact_detail(
            db,
            hotel_id=hotel_id,
            company_id=request.company_id,
            date_from=window.date_from,
            date_to=window.date_to,
            stream_details=stream_details,
        )
        company_detail.pop("_data_as_of", None)
        return {
            "hotel_id": hotel_id,
            "date_from": window.date_from,
            "date_to": window.date_to,
            "currency_display": request.currency_display,
            "comparison": window.comparison,
            "data": company_detail,
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
                stream_details=stream_details,
            )
        )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entity_code inválido")


def build_export_payload(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> dict[str, Any]:
    return _build_payload_for_request(db, hotel_id=hotel_id, request=request)


def iter_render_export_csv(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> Iterator[bytes]:
    """Stream CSV encoding and page detail queries without a second row table."""
    payload = _build_payload_for_request(db, hotel_id=hotel_id, request=request, stream_details=True)
    return _iter_csv_chunks(_iter_export_payload_rows(payload))


def render_export_csv(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> bytes:
    return b"".join(iter_render_export_csv(db, hotel_id=hotel_id, request=request))


def render_export_png(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> bytes | SpooledTemporaryFile:
    payload = _build_payload_for_request(db, hotel_id=hotel_id, request=request, stream_details=True)
    return _png_export_content(
        _iter_export_payload_rows(payload),
        title=f"Analytics export - {request.entity_code}",
    )


def render_export_xlsx_file(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> SpooledTemporaryFile:
    payload = _build_payload_for_request(db, hotel_id=hotel_id, request=request, stream_details=True)
    sheets: list[tuple[str, Iterable[list[str]]]] = [
        ("Summary", _iter_export_payload_rows(payload)),
    ]

    data = payload.get("data")
    if isinstance(data, dict):
        cards = data.get("cards")
        if isinstance(cards, list) and cards:
            def card_rows(card_values: list[Any] = cards) -> Iterator[list[str]]:
                yield ["card_code", "label", "value_count", "value_pct", "value_ars", "value_usd"]
                for card in card_values:
                    if not isinstance(card, dict):
                        continue
                    yield [
                        _format_scalar(card.get("card_code")),
                        _format_scalar(card.get("label")),
                        _format_scalar(card.get("value_count")),
                        _format_scalar(card.get("value_pct")),
                        _format_scalar(card.get("value_ars")),
                        _format_scalar(card.get("value_usd")),
                    ]

            sheets.append(("Cards", card_rows()))

        for section_name, section_value in data.items():
            if section_name == "cards":
                continue
            if _is_row_collection(section_value):
                known_headers = getattr(section_value, "column_names", None)
                if known_headers:
                    headers = list(known_headers)
                    item_iterator = iter(section_value)
                elif isinstance(section_value, (list, tuple)):
                    if not section_value:
                        continue
                    first_item = section_value[0]
                    headers = list(first_item.keys()) if isinstance(first_item, dict) else []
                    item_iterator = iter(section_value)
                else:
                    item_iterator = iter(section_value)
                    first_item = next(item_iterator, None)
                    if first_item is None:
                        continue
                    headers = list(first_item.keys()) if isinstance(first_item, dict) else []
                    item_iterator = chain((first_item,), item_iterator)
                if headers:
                    def section_rows(
                        items: Iterator[Any] = item_iterator,
                        columns: list[str] = headers,
                    ) -> Iterator[list[str]]:
                        yield columns
                        for item in items:
                            if isinstance(item, dict):
                                yield [_format_scalar(item.get(header)) for header in columns]
                            else:
                                yield [_format_scalar(item)]

                    sheets.append((section_name[:31], section_rows()))
            elif isinstance(section_value, dict) and section_value:
                def mapping_rows(values: dict[str, Any] = section_value) -> Iterator[list[str]]:
                    yield ["key", "value"]
                    for key, value in values.items():
                        yield [key, _format_scalar(value)]

                sheets.append((section_name[:31], mapping_rows()))
    return _build_xlsx_spool(sheets)


def render_export_xlsx(db: Session, *, hotel_id: int, request: AnalyticsExportRequest) -> bytes:
    output = render_export_xlsx_file(db, hotel_id=hotel_id, request=request)
    try:
        return output.read()
    finally:
        output.close()


def create_xlsx_export_job(db: Session, *, hotel_id: int, user_id: int, request: AnalyticsExportRequest) -> AnalyticsExportJob:
    window = _analytics_window(
        db,
        hotel_id,
        date_from=request.date_from,
        date_to=request.date_to,
        compare_previous=request.compare_previous,
        compare_yoy=request.compare_yoy,
    )
    effective_request = request.model_copy(
        update={"date_from": window.date_from, "date_to": window.date_to}
    )
    job = AnalyticsExportJob(
        hotel_id=hotel_id,
        user_id=user_id,
        entity_code=request.entity_code,
        card_code=request.card_code,
        format=AnalyticsExportFormatEnum.XLSX,
        currency_display=request.currency_display,
        date_from=window.date_from,
        date_to=window.date_to,
        compare_previous=effective_request.compare_previous,
        compare_yoy=effective_request.compare_yoy,
        filters_json=effective_request.model_dump_json(exclude_none=True),
        status=AnalyticsExportStatusEnum.PENDING,
        expires_at=_now() + timedelta(hours=24),
    )
    db.add(job)
    db.flush()
    return job


def prepare_xlsx_export_jobs_for_recovery(db: Session) -> list[tuple[int, int]]:
    """Requeue unexpired XLSX jobs left pending or running by a process restart.

    The export table is protected by tenant RLS, so the worker first reads only
    hotel IDs from the unscoped hotel configuration table, then selects jobs
    inside each tenant context. This is intended for one API instance using a
    persistent database and object-storage directory; the generator's atomic
    status claim remains the final duplicate-execution guard.
    """
    set_tenant_hotel_context(db, None)
    hotel_ids = [
        int(hotel_id)
        for (hotel_id,) in db.query(HotelConfiguration.id).order_by(HotelConfiguration.id).all()
    ]
    recovered: list[tuple[int, int]] = []
    now = _now()
    recoverable_statuses = [AnalyticsExportStatusEnum.PENDING, AnalyticsExportStatusEnum.RUNNING]

    for hotel_id in hotel_ids:
        set_tenant_hotel_context(db, hotel_id)
        jobs = (
            db.query(AnalyticsExportJob.id, AnalyticsExportJob.status)
            .filter(
                AnalyticsExportJob.hotel_id == hotel_id,
                AnalyticsExportJob.format == AnalyticsExportFormatEnum.XLSX,
                AnalyticsExportJob.status.in_(recoverable_statuses),
                AnalyticsExportJob.expires_at > now,
            )
            .order_by(AnalyticsExportJob.created_at.asc(), AnalyticsExportJob.id.asc())
            .with_for_update()
            .all()
        )
        running_ids = [
            int(job_id)
            for job_id, status_value in jobs
            if status_value == AnalyticsExportStatusEnum.RUNNING
        ]
        if running_ids:
            db.query(AnalyticsExportJob).filter(
                AnalyticsExportJob.hotel_id == hotel_id,
                AnalyticsExportJob.id.in_(running_ids),
                AnalyticsExportJob.status == AnalyticsExportStatusEnum.RUNNING,
                AnalyticsExportJob.expires_at > now,
            ).update(
                {
                    AnalyticsExportJob.status: AnalyticsExportStatusEnum.PENDING,
                    AnalyticsExportJob.started_at: None,
                    AnalyticsExportJob.completed_at: None,
                    AnalyticsExportJob.error_code: None,
                    AnalyticsExportJob.error_message: None,
                },
                synchronize_session=False,
            )
        recovered.extend((int(job_id), hotel_id) for job_id, _status_value in jobs)
        db.commit()

    return recovered


def _export_object_key(job: AnalyticsExportJob) -> str:
    created_at = job.created_at or _now()
    return f"analytics-exports/{job.hotel_id}/{created_at.year:04d}/{created_at.month:02d}/{job.id}.xlsx"


def _persist_export_file(db: Session, job: AnalyticsExportJob, file_bytes: bytes) -> None:
    object_key = _export_object_key(job)
    register_uploaded_object(
        db,
        hotel_id=job.hotel_id,
        purpose="analytics_export",
        object_key=object_key,
        data=file_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        created_by_user_id=job.user_id,
    )
    # job.file_path now holds an object-storage key, not a filesystem path.
    job.file_path = object_key
    job.file_size_bytes = len(file_bytes)
    job.sha256_hex = hashlib.sha256(file_bytes).hexdigest()


def _persist_export_file_stream(db: Session, job: AnalyticsExportJob, file_obj: BinaryIO) -> None:
    object_key = _export_object_key(job)
    stored_object = register_uploaded_object_file(
        db,
        hotel_id=job.hotel_id,
        purpose="analytics_export",
        object_key=object_key,
        data_file=file_obj,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        created_by_user_id=job.user_id,
    )
    job.file_path = object_key
    job.file_size_bytes = stored_object.byte_size
    job.sha256_hex = stored_object.sha256_hex


def generate_xlsx_export_job(job_id: int, hotel_id: int | None = None) -> None:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    export_file = None
    try:
        if not hotel_id or hotel_id <= 0:
            raise ValueError("hotel_id is required for tenant-scoped analytics exports")
        set_tenant_hotel_context(db, hotel_id)
        claim = (
            db.query(AnalyticsExportJob)
            .filter(
                AnalyticsExportJob.id == job_id,
                AnalyticsExportJob.hotel_id == hotel_id,
                AnalyticsExportJob.status.in_(
                    [AnalyticsExportStatusEnum.PENDING, AnalyticsExportStatusEnum.FAILED]
                ),
            )
            .update(
                {
                    AnalyticsExportJob.status: AnalyticsExportStatusEnum.RUNNING,
                    AnalyticsExportJob.started_at: _now(),
                    AnalyticsExportJob.error_code: None,
                    AnalyticsExportJob.error_message: None,
                },
                synchronize_session=False,
            )
        )
        if claim != 1:
            # A duplicate invocation, an expired/completed job, or a foreign
            # tenant ID must be a no-op. In particular, never mutate a row
            # after looking it up by globally unique ID in the error path.
            return
        db.commit()
        job = (
            db.query(AnalyticsExportJob)
            .filter(AnalyticsExportJob.id == job_id, AnalyticsExportJob.hotel_id == hotel_id)
            .first()
        )
        if job is None:
            return
        request = AnalyticsExportRequest.model_validate(json.loads(job.filters_json))
        export_file = render_export_xlsx_file(db, hotel_id=job.hotel_id, request=request)
        _persist_export_file_stream(db, job, export_file)
        job.status = AnalyticsExportStatusEnum.COMPLETED
        job.completed_at = _now()
        job.error_code = None
        job.error_message = None
        db.commit()
    except Exception as exc:  # pragma: no cover - exercised through API tests if generation fails
        db.rollback()
        job = (
            db.query(AnalyticsExportJob)
            .filter(
                AnalyticsExportJob.id == job_id,
                AnalyticsExportJob.hotel_id == hotel_id,
                AnalyticsExportJob.status == AnalyticsExportStatusEnum.RUNNING,
            )
            .first()
        )
        if job is not None:
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
        if export_file is not None:
            export_file.close()
        db.close()


def list_export_jobs(
    db: Session,
    *,
    hotel_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[AnalyticsExportJobRead]:
    rows = (
        db.query(AnalyticsExportJob)
        .filter(AnalyticsExportJob.hotel_id == hotel_id)
        .order_by(AnalyticsExportJob.created_at.desc(), AnalyticsExportJob.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
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


def get_export_bytes(job: AnalyticsExportJob) -> bytes:
    """Read a completed export's .xlsx bytes from object storage.

    job.file_path holds an object-storage key (not a filesystem path) since
    exports moved off the ephemeral container disk -- see _persist_export_file.
    """
    if not job.file_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export job no finalizado")
    try:
        return get_object_storage().get_bytes(job.file_path)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo de export no encontrado") from exc


def get_export_file(job: AnalyticsExportJob) -> BinaryIO:
    """Open a completed export for bounded-memory HTTP streaming."""
    if not job.file_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export job no finalizado")
    try:
        return get_object_storage().open_read(job.file_path)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo de export no encontrado") from exc


def delete_export_file(job: AnalyticsExportJob) -> None:
    if job.file_path:
        get_object_storage().delete(job.file_path)


def expire_export_job_if_needed(db: Session, job: AnalyticsExportJob) -> bool:
    if job.status == AnalyticsExportStatusEnum.EXPIRED:
        return True
    expires_at = _ensure_utc(job.expires_at)
    if expires_at and expires_at <= _now():
        job.status = AnalyticsExportStatusEnum.EXPIRED
        db.flush()
        return True
    return False
