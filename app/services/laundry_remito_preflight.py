"""Read-only duplicate detection shared by migration and operator tooling."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import inspect, text


def duplicate_laundry_remitos(connection) -> list[dict[str, object]]:
    """Return normalized duplicate remito groups, including every row id.

    Service writes remito numbers with Python ``str.strip()`` before checking
    them. Apply the same normalization here and report non-canonical legacy
    values too, because a raw unique constraint cannot protect a padded value
    from a later canonical write.
    """
    if "laundry_remitos" not in set(inspect(connection).get_table_names()):
        return []

    rows = connection.execute(
        text(
            "SELECT id, hotel_id, vendor_id, direction, remito_number "
            "FROM laundry_remitos "
            "ORDER BY hotel_id, vendor_id, direction, id"
        )
    ).mappings().all()
    groups: dict[tuple[object, object, object, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        normalized_number = str(row["remito_number"]).strip()
        groups[(row["hotel_id"], row["vendor_id"], row["direction"], normalized_number)].append(dict(row))

    report = []
    for (hotel_id, vendor_id, direction, normalized_number), matching_rows in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][1], item[0][2], item[0][3])
    ):
        has_noncanonical_value = any(str(row["remito_number"]) != normalized_number for row in matching_rows)
        if len(matching_rows) < 2 and not has_noncanonical_value:
            continue
        report.append(
            {
                "hotel_id": hotel_id,
                "vendor_id": vendor_id,
                "direction": direction,
                "remito_number": normalized_number,
                "duplicate_count": len(matching_rows),
                "row_ids": [row["id"] for row in matching_rows],
            }
        )
    return report


def format_duplicate_report(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "No se encontraron remitos duplicados por hotel, lavadero, sentido y número normalizado."
    lines = [
        "Hay remitos duplicados o números con espacios externos. Corregí los registros informados antes de aplicar la unicidad:",
        "hotel_id | vendor_id | direction | remito_number | count | row_ids",
    ]
    lines.extend(
        "{hotel_id} | {vendor_id} | {direction} | {remito_number} | {duplicate_count} | {row_ids}".format(
            **{**row, "row_ids": ",".join(str(value) for value in row["row_ids"])}
        )
        for row in rows
    )
    return "\n".join(lines)
