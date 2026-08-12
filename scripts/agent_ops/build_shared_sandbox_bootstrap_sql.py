#!/usr/bin/env python3
"""Build the guarded SQL used to seed the production-labelled shared QA sandbox.

The command is dry-run by default.  ``--emit-sql`` is intended for a trusted
operator that pipes stdout directly to the Supabase connector without logging
it.  Plaintext credentials are never included in the emitted SQL.
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = ROOT / ".env.qa.local"
PROJECT_REF = "ezkljznogqpmrjxyvklr"
ACK = "production-labelled-shared-sandbox"
BASE_ID = "hotel-chipre-shared-sandbox-v1"
REQUIRED_KEYS = (
    "QA_RUN_ID",
    "QA_EMAIL_DOMAIN",
    "QA_EMAIL_DOMAIN_IS_DEDICATED",
    "QA_OWNER_EMAIL",
    "QA_OWNER_PASSWORD",
    "QA_ISOLATION_OWNER_EMAIL",
    "QA_ISOLATION_OWNER_PASSWORD",
)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


class SharedSandboxBootstrapError(RuntimeError):
    pass


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        if path.is_symlink():
            raise SharedSandboxBootstrapError("the ignored QA persona file cannot be a symlink")
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise SharedSandboxBootstrapError(
                "the ignored QA persona file must be readable only by its owner"
            )
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SharedSandboxBootstrapError("the ignored QA persona file is unavailable") from exc
    for line in lines:
        if not line or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            raise SharedSandboxBootstrapError("the QA persona file is malformed")
        key, value = line.split("=", 1)
        values[key] = value
    missing = [key for key in REQUIRED_KEYS if not values.get(key)]
    if missing:
        raise SharedSandboxBootstrapError("the QA persona file lacks required shared-sandbox identities")
    if values["QA_EMAIL_DOMAIN_IS_DEDICATED"].lower() != "true":
        raise SharedSandboxBootstrapError("QA identities require a dedicated synthetic domain")
    domain = values["QA_EMAIL_DOMAIN"].lower()
    for key in ("QA_OWNER_EMAIL", "QA_ISOLATION_OWNER_EMAIL"):
        email = values[key].lower()
        if not EMAIL_RE.fullmatch(email) or email.rsplit("@", 1)[1] != domain:
            raise SharedSandboxBootstrapError("QA owner identities must use the dedicated domain")
    return values


def _literal(value: str) -> str:
    if "\x00" in value:
        raise SharedSandboxBootstrapError("bootstrap value contains NUL")
    return "'" + value.replace("'", "''") + "'"


def build_sql(values: Mapping[str, str]) -> str:
    from app.services.security import hash_password

    owner_email = values["QA_OWNER_EMAIL"].strip().lower()
    isolation_email = values["QA_ISOLATION_OWNER_EMAIL"].strip().lower()
    if owner_email == isolation_email:
        raise SharedSandboxBootstrapError("main and isolation owners must be distinct")
    owner_hash = hash_password(values["QA_OWNER_PASSWORD"])
    isolation_hash = hash_password(values["QA_ISOLATION_OWNER_PASSWORD"])
    marker_a = json.dumps(
        {
            "_qa_bootstrap": {
                "base_id": BASE_ID,
                "environment_class": "production-labelled-shared-sandbox",
                "synthetic": True,
                "tenant": "primary",
            }
        },
        separators=(",", ":"),
    )
    marker_b = json.dumps(
        {
            "_qa_bootstrap": {
                "base_id": BASE_ID,
                "environment_class": "production-labelled-shared-sandbox",
                "synthetic": True,
                "tenant": "isolation",
            }
        },
        separators=(",", ":"),
    )
    values_sql = {
        "owner_email": _literal(owner_email),
        "owner_hash": _literal(owner_hash),
        "isolation_email": _literal(isolation_email),
        "isolation_hash": _literal(isolation_hash),
        "marker_a": _literal(marker_a),
        "marker_b": _literal(marker_b),
    }
    return f"""begin;
select pg_advisory_xact_lock(hashtext('{BASE_ID}'));

do $bootstrap$
declare
  v_owner_id integer;
  v_isolation_owner_id integer;
  v_primary_hotel_id integer;
  v_isolation_hotel_id integer;
  v_plan_id integer;
begin
  if exists (
    select 1 from hotel_configuration
    where owner_email in ({values_sql['owner_email']}, {values_sql['isolation_email']})
      and coalesce(extra_policies, '') not like '%"base_id":"{BASE_ID}"%'
  ) then
    raise exception 'shared sandbox bootstrap refused an unmarked existing hotel';
  end if;
  if exists (
    select 1 from users u join hotel_memberships hm on hm.user_id = u.id
    join hotel_configuration h on h.id = hm.hotel_id
    where u.email in ({values_sql['owner_email']}, {values_sql['isolation_email']})
      and coalesce(h.extra_policies, '') not like '%"base_id":"{BASE_ID}"%'
  ) then
    raise exception 'shared sandbox bootstrap refused an identity attached to foreign data';
  end if;
  if exists (
    select 1 from users u
    where u.email in ({values_sql['owner_email']}, {values_sql['isolation_email']})
      and not exists (
        select 1 from hotel_memberships hm
        join hotel_configuration h on h.id = hm.hotel_id
        where hm.user_id = u.id
          and coalesce(h.extra_policies, '') like '%"base_id":"{BASE_ID}"%'
      )
  ) then
    raise exception 'shared sandbox bootstrap refused an unmarked existing identity';
  end if;

  insert into users (email, password_hash, is_active, is_verified, role, created_at, updated_at, token_version)
  values ({values_sql['owner_email']}, {values_sql['owner_hash']}, true, true, 'owner', now(), now(), 0)
  on conflict (email) do update set
    password_hash = excluded.password_hash,
    is_active = true,
    is_verified = true,
    role = 'owner',
    updated_at = now();
  select id into strict v_owner_id from users where email = {values_sql['owner_email']};

  insert into users (email, password_hash, is_active, is_verified, role, created_at, updated_at, token_version)
  values ({values_sql['isolation_email']}, {values_sql['isolation_hash']}, true, true, 'owner', now(), now(), 0)
  on conflict (email) do update set
    password_hash = excluded.password_hash,
    is_active = true,
    is_verified = true,
    role = 'owner',
    updated_at = now();
  select id into strict v_isolation_owner_id from users where email = {values_sql['isolation_email']};

  select id into v_primary_hotel_id from hotel_configuration
  where owner_email = {values_sql['owner_email']} and extra_policies like '%"base_id":"{BASE_ID}"%';
  if v_primary_hotel_id is null then
    select coalesce(max(id), 0) + 1 into v_primary_hotel_id from hotel_configuration;
    insert into hotel_configuration (
      id, deposit_percentage, enable_full_payment, enable_deposit_payment,
      enable_cash, enable_mercado_pago, enable_paypal, enable_credit_card,
      enable_debit_card, enable_bank_transfer, free_cancellation_hours,
      cancellation_penalty_percentage, allow_cancellation_after_checkin,
      enable_booking_sync, enable_expedia_sync, require_document_for_checkin,
      require_terms_acceptance, hotel_name, hotel_timezone, default_currency,
      extra_policies, updated_at, owner_email, subscription_active,
      receptionist_view_past_days, receptionist_view_future_days,
      allow_revenue_manager, allow_revenue_receptionist, sync_interval_minutes,
      safety_buffer_rooms, allow_overbooking, max_overallocation_pct,
      no_show_cutoff_hours, ota_autopush_enabled, card_validation_enabled,
      payment_retry_attempts, auth_amount_pct, stop_sell_channels,
      event_notifications, analytics_ai_enabled, public_api_rate_limit_per_minute
    ) values (
      v_primary_hotel_id, 30, true, true, true, false, false, false,
      false, true, 48, 50, false, false, false, true, true,
      'Hotel QA Compartido', 'America/Argentina/Buenos_Aires', 'ARS',
      {values_sql['marker_a']}, now(), {values_sql['owner_email']}, true,
      30, 730, false, false, 15, 0, false, 0, 18, false, false,
      3, 10, '[]', '{{}}', false, 60
    );
  end if;

  select id into v_isolation_hotel_id from hotel_configuration
  where owner_email = {values_sql['isolation_email']} and extra_policies like '%"base_id":"{BASE_ID}"%';
  if v_isolation_hotel_id is null then
    select coalesce(max(id), 0) + 1 into v_isolation_hotel_id from hotel_configuration;
    insert into hotel_configuration (
      id, deposit_percentage, enable_full_payment, enable_deposit_payment,
      enable_cash, enable_mercado_pago, enable_paypal, enable_credit_card,
      enable_debit_card, enable_bank_transfer, free_cancellation_hours,
      cancellation_penalty_percentage, allow_cancellation_after_checkin,
      enable_booking_sync, enable_expedia_sync, require_document_for_checkin,
      require_terms_acceptance, hotel_name, hotel_timezone, default_currency,
      extra_policies, updated_at, owner_email, subscription_active,
      receptionist_view_past_days, receptionist_view_future_days,
      allow_revenue_manager, allow_revenue_receptionist, sync_interval_minutes,
      safety_buffer_rooms, allow_overbooking, max_overallocation_pct,
      no_show_cutoff_hours, ota_autopush_enabled, card_validation_enabled,
      payment_retry_attempts, auth_amount_pct, stop_sell_channels,
      event_notifications, analytics_ai_enabled, public_api_rate_limit_per_minute
    ) select
      v_isolation_hotel_id, deposit_percentage, enable_full_payment, enable_deposit_payment,
      enable_cash, false, false, false, false, enable_bank_transfer,
      free_cancellation_hours, cancellation_penalty_percentage,
      allow_cancellation_after_checkin, false, false, require_document_for_checkin,
      require_terms_acceptance, 'Hotel QA Aislamiento', hotel_timezone,
      default_currency, {values_sql['marker_b']}, now(), {values_sql['isolation_email']},
      true, receptionist_view_past_days, receptionist_view_future_days,
      false, false, sync_interval_minutes, safety_buffer_rooms, allow_overbooking,
      max_overallocation_pct, no_show_cutoff_hours, false, false,
      payment_retry_attempts, auth_amount_pct, '[]', '{{}}', false,
      public_api_rate_limit_per_minute
    from hotel_configuration where id = v_primary_hotel_id;
  end if;

  insert into hotel_memberships (hotel_id, user_id, role, status, created_at)
  values (v_primary_hotel_id, v_owner_id, 'owner', 'active', now())
  on conflict (hotel_id, user_id) do update set role = 'owner', status = 'active';
  insert into hotel_memberships (hotel_id, user_id, role, status, created_at)
  values (v_isolation_hotel_id, v_owner_id, 'owner', 'active', now())
  on conflict (hotel_id, user_id) do update set role = 'owner', status = 'active';
  insert into hotel_memberships (hotel_id, user_id, role, status, created_at)
  values (v_isolation_hotel_id, v_isolation_owner_id, 'owner', 'active', now())
  on conflict (hotel_id, user_id) do update set role = 'owner', status = 'active';

  select id into strict v_plan_id from subscription_plans where code = 'starter';
  insert into hotel_subscriptions (hotel_id, plan_id, status, starts_at)
  values (v_primary_hotel_id, v_plan_id, 'active', now())
  on conflict (hotel_id) do update set plan_id = excluded.plan_id, status = 'active';
  insert into hotel_subscriptions (hotel_id, plan_id, status, starts_at)
  values (v_isolation_hotel_id, v_plan_id, 'active', now())
  on conflict (hotel_id) do update set plan_id = excluded.plan_id, status = 'active';

  insert into onboarding_state (
    hotel_id, owner_name, owner_email, owner_phone, owner_role, staff_json,
    finished, created_at, updated_at, hotel_identity_json, deposit_policy_json,
    payment_methods_json, ota_channels_json, subscription_choice_json,
    identity_set, policy_set, payments_set, ota_set, subscription_set
  ) values (
    v_primary_hotel_id, 'Owner QA', {values_sql['owner_email']}, '0000000000',
    'owner', '[]', false, now(), now(), '{{}}', '{{}}',
    '{{"cash":{{"enabled":true}},"bank_transfer":{{"enabled":true}}}}',
    '{{"booking":{{"enabled":false}},"expedia":{{"enabled":false}}}}',
    '{{"plan":"starter"}}', false, false, true, true, true
  ) on conflict (hotel_id) do nothing;
  insert into onboarding_state (
    hotel_id, owner_name, owner_email, owner_phone, owner_role, staff_json,
    finished, created_at, updated_at, hotel_identity_json, deposit_policy_json,
    payment_methods_json, ota_channels_json, subscription_choice_json,
    identity_set, policy_set, payments_set, ota_set, subscription_set
  ) values (
    v_isolation_hotel_id, 'Isolation Owner QA', {values_sql['isolation_email']},
    '0000000000', 'owner', '[]', false, now(), now(), '{{}}', '{{}}',
    '{{"cash":{{"enabled":true}}}}',
    '{{"booking":{{"enabled":false}},"expedia":{{"enabled":false}}}}',
    '{{"plan":"starter"}}', false, false, true, true, true
  ) on conflict (hotel_id) do nothing;
end
$bootstrap$;

commit;
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--ack")
    parser.add_argument("--emit-sql", action="store_true")
    args = parser.parse_args()
    try:
        if args.project_ref != PROJECT_REF:
            raise SharedSandboxBootstrapError("shared sandbox project ref does not match the allowlist")
        values = load_env(args.env_file)
        if not args.emit_sql:
            print(
                "Dry run OK: two marked QA hotels and two owner identities; "
                "no SQL emitted and no database mutation performed"
            )
            return 0
        if args.ack != ACK:
            raise SharedSandboxBootstrapError("--emit-sql requires the exact shared-sandbox acknowledgement")
        sys.stdout.write(build_sql(values))
        return 0
    except SharedSandboxBootstrapError as exc:
        print(f"Shared sandbox bootstrap refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
