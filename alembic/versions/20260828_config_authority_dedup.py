"""Make hotel configuration columns the authority and retire dead scaffolding.

Dead fields are removed from the runtime model/API but their legacy columns are
preserved so this migration remains additive and reversible for existing data.

Revision ID: 20260828_config_authority_dedup
Revises: 3bc5882f756d
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "20260828_config_authority_dedup"
down_revision = "3bc5882f756d"
branch_labels = None
depends_on = None


NEW_COLUMNS = {
    "enable_despegar_sync": sa.Column("enable_despegar_sync", sa.Boolean(), nullable=True),
    "languages": sa.Column("languages", sa.JSON(), nullable=True),
    "jurisdiction_code": sa.Column("jurisdiction_code", sa.String(3), nullable=True),
    "operational_report_recipients": sa.Column("operational_report_recipients", sa.JSON(), nullable=True),
}
DEAD_COLUMNS = [
    "allow_revenue_manager",
    "allow_revenue_receptionist",
    "sync_interval_minutes",
    "safety_buffer_rooms",
    "max_overallocation_pct",
    "ota_autopush_enabled",
    "card_validation_enabled",
    "payment_retry_attempts",
    "auth_amount_pct",
    "stop_sell_channels",
    "event_notifications",
]
LEGACY_DEFAULTS = {
    "receptionist_view_past_days": "0",
    "receptionist_view_future_days": "7",
    "allow_revenue_manager": "true",
    "allow_revenue_receptionist": "false",
    "sync_interval_minutes": "5",
    "safety_buffer_rooms": "0",
    "max_overallocation_pct": "0",
    "ota_autopush_enabled": "false",
    "card_validation_enabled": "false",
    "payment_retry_attempts": "2",
    "auth_amount_pct": "0",
}


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _decode(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _backfill_authoritative_values() -> None:
    bind = op.get_bind()
    config = sa.table(
        "hotel_configuration",
        sa.column("id", sa.Integer()),
        sa.column("extra_policies", sa.Text()),
        sa.column("enable_despegar_sync", sa.Boolean()),
        sa.column("languages", sa.JSON()),
        sa.column("jurisdiction_code", sa.String(3)),
        sa.column("operational_report_recipients", sa.JSON()),
    )
    state = sa.table(
        "onboarding_state",
        sa.column("hotel_id", sa.Integer()),
        sa.column("hotel_identity_json", sa.Text()),
        sa.column("ota_channels_json", sa.Text()),
    )
    state_by_hotel = {
        row.hotel_id: row
        for row in bind.execute(sa.select(state.c.hotel_id, state.c.hotel_identity_json, state.c.ota_channels_json))
    }
    for row in bind.execute(sa.select(config.c.id, config.c.extra_policies)):
        policies = _decode(row.extra_policies)
        identity = _decode(getattr(state_by_hotel.get(row.id), "hotel_identity_json", None))
        ota = _decode(getattr(state_by_hotel.get(row.id), "ota_channels_json", None))
        despegar = policies.get("ota_channels", {}).get("despegar", {}).get("enabled")
        if despegar is None:
            despegar = ota.get("despegar", {}).get("enabled", False)
        languages = policies.get("languages") or identity.get("languages") or ["es"]
        jurisdiction = policies.get("jurisdiction_code") or identity.get("jurisdiction_code") or "AR"
        recipients = policies.get("operational_report_recipients")
        bind.execute(
            config.update().where(config.c.id == row.id).values(
                enable_despegar_sync=bool(despegar),
                languages=languages if isinstance(languages, list) else ["es"],
                jurisdiction_code=str(jurisdiction).strip().upper()[:3] or "AR",
                operational_report_recipients=recipients if isinstance(recipients, list) else None,
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    existing = _columns("hotel_configuration")
    for name, column in NEW_COLUMNS.items():
        if name not in existing:
            op.add_column("hotel_configuration", column)

    _backfill_authoritative_values()

    existing = _columns("hotel_configuration")
    with op.batch_alter_table("hotel_configuration", recreate="auto") as batch:
        for name in ("enable_despegar_sync", "languages", "jurisdiction_code"):
            if name in existing or name in NEW_COLUMNS:
                batch.alter_column(name, nullable=False)
        # These columns are intentionally no longer mapped or writable, but
        # old schemas have them as NOT NULL without defaults. Give legacy
        # columns a safe server default so current ORM inserts remain valid
        # without reviving them as runtime configuration.
        for name, default in LEGACY_DEFAULTS.items():
            if name in existing:
                batch.alter_column(name, server_default=sa.text(default))


def downgrade() -> None:
    bind = op.get_bind()
    config = sa.table(
        "hotel_configuration",
        sa.column("id", sa.Integer()),
        sa.column("extra_policies", sa.Text()),
        sa.column("enable_despegar_sync", sa.Boolean()),
        sa.column("languages", sa.JSON()),
        sa.column("jurisdiction_code", sa.String(3)),
        sa.column("operational_report_recipients", sa.JSON()),
    )
    for row in bind.execute(sa.select(config)):
        policies = _decode(row.extra_policies)
        policies.setdefault("languages", row.languages or ["es"])
        policies.setdefault("jurisdiction_code", row.jurisdiction_code or "AR")
        policies.setdefault("ota_channels", {})["despegar"] = {"enabled": bool(row.enable_despegar_sync)}
        if row.operational_report_recipients:
            policies.setdefault("operational_report_recipients", row.operational_report_recipients)
        bind.execute(
            config.update().where(config.c.id == row.id).values(extra_policies=json.dumps(policies))
        )

    existing = _columns("hotel_configuration")
    with op.batch_alter_table("hotel_configuration", recreate="auto") as batch:
        for name in ("operational_report_recipients", "jurisdiction_code", "languages", "enable_despegar_sync"):
            if name in existing:
                batch.drop_column(name)
        if "allow_revenue_manager" not in existing:
            batch.add_column(sa.Column("allow_revenue_manager", sa.Boolean(), nullable=False, server_default=sa.true()))
        if "allow_revenue_receptionist" not in existing:
            batch.add_column(sa.Column("allow_revenue_receptionist", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "sync_interval_minutes" not in existing:
            batch.add_column(sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="5"))
        if "safety_buffer_rooms" not in existing:
            batch.add_column(sa.Column("safety_buffer_rooms", sa.Integer(), nullable=False, server_default="0"))
        if "max_overallocation_pct" not in existing:
            batch.add_column(sa.Column("max_overallocation_pct", sa.Float(), nullable=False, server_default="0"))
        if "ota_autopush_enabled" not in existing:
            batch.add_column(sa.Column("ota_autopush_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "card_validation_enabled" not in existing:
            batch.add_column(sa.Column("card_validation_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "payment_retry_attempts" not in existing:
            batch.add_column(sa.Column("payment_retry_attempts", sa.Integer(), nullable=False, server_default="2"))
        if "auth_amount_pct" not in existing:
            batch.add_column(sa.Column("auth_amount_pct", sa.Float(), nullable=False, server_default="0"))
        if "stop_sell_channels" not in existing:
            batch.add_column(sa.Column("stop_sell_channels", sa.Text(), nullable=True))
        if "event_notifications" not in existing:
            batch.add_column(sa.Column("event_notifications", sa.Text(), nullable=True))
        for name in LEGACY_DEFAULTS:
            if name in existing:
                batch.alter_column(name, server_default=None)
