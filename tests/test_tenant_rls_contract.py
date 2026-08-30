from __future__ import annotations

import importlib.util
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import app.models  # noqa: F401
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import UniqueConstraint, create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.database import Base
from app.services.tenant_context import set_tenant_context, set_tenant_hotel_context


CORE_COMPOSITE_FK_REQUIREMENTS = (
    ("rooms", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id")),
    ("sellable_products", ("hotel_id", "primary_room_category_id"), "room_categories", ("hotel_id", "id")),
    ("product_room_compatibility", ("hotel_id", "sellable_product_id"), "sellable_products", ("hotel_id", "id")),
    ("product_room_compatibility", ("hotel_id", "room_category_id"), "room_categories", ("hotel_id", "id")),
    ("rate_plans", ("hotel_id", "sellable_product_id"), "sellable_products", ("hotel_id", "id")),
    ("rate_plan_prices", ("hotel_id", "rate_plan_id"), "rate_plans", ("hotel_id", "id")),
    ("tax_rules", ("hotel_id", "tax_policy_id"), "tax_policies", ("hotel_id", "id")),
    ("reservations", ("hotel_id", "guest_id"), "guests", ("hotel_id", "id")),
    ("reservations", ("hotel_id", "room_id"), "rooms", ("hotel_id", "id")),
    ("reservations", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id")),
    ("reservations", ("hotel_id", "company_id"), "companies", ("hotel_id", "id")),
    ("reservations", ("hotel_id", "sellable_product_id"), "sellable_products", ("hotel_id", "id")),
    ("reservations", ("hotel_id", "rate_plan_id"), "rate_plans", ("hotel_id", "id")),
    ("reservations", ("hotel_id", "tax_policy_id"), "tax_policies", ("hotel_id", "id")),
    ("transactions", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id")),
    ("payments", ("hotel_id", "payment_link_id"), "payment_links", ("hotel_id", "id")),
    ("payment_proofs", ("hotel_id", "transaction_id"), "transactions", ("hotel_id", "id")),
    ("payment_proof_blobs", ("hotel_id", "proof_id"), "payment_proofs", ("hotel_id", "id")),
    ("cash_movements", ("hotel_id", "session_id"), "cash_sessions", ("hotel_id", "id")),
    ("cash_movements", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id")),
    ("cash_movements", ("hotel_id", "transaction_id"), "transactions", ("hotel_id", "id")),
    ("cash_close_reports", ("hotel_id", "session_id"), "cash_sessions", ("hotel_id", "id")),
    ("cash_close_reports", ("hotel_id", "successor_session_id"), "cash_sessions", ("hotel_id", "id")),
    ("cash_custody_handoffs", ("hotel_id", "close_report_id"), "cash_close_reports", ("hotel_id", "id")),
    ("stock_movements", ("hotel_id", "item_id"), "stock_items", ("hotel_id", "id")),
    ("stock_movements", ("hotel_id", "location_id"), "stock_locations", ("hotel_id", "id")),
    ("stock_movements", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id")),
    ("guest_tags", ("hotel_id", "guest_id"), "guests", ("hotel_id", "id")),
    ("fact_reservation_daily", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id")),
    ("fact_reservation_daily", ("hotel_id", "room_id"), "rooms", ("hotel_id", "id")),
    ("fact_reservation_daily", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id")),
    ("fact_reservation_daily", ("hotel_id", "company_id"), "companies", ("hotel_id", "id")),
    ("fact_room_occupancy_daily", ("hotel_id", "room_id"), "rooms", ("hotel_id", "id")),
    ("fact_room_occupancy_daily", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id")),
    ("fact_room_occupancy_daily", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id")),
)


ADDITIVE_RLS_TABLE_CONTRACT = (
    ("20260724_payment_proofs.py", ("payment_proofs",)),
    (
        "20260820_missing_tenant_rls.py",
        ("hotel_api_keys",),
    ),
    (
        "e6aadf684343_add_subscription_adjustment_ledger.py",
        ("subscription_adjustments",),
    ),
    (
        "3bc5882f756d_add_role_visibility_windows.py",
        ("hotel_role_visibility_window",),
    ),
    (
        "20260830_guest_room_avoidance.py",
        ("guest_room_avoidance",),
    ),
)


def _load_rls_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260724_tenant_rls_context.py"
    spec = importlib.util.spec_from_file_location("tenant_rls_context_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_user_override_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260813_rbac_user_overrides.py"
    spec = importlib.util.spec_from_file_location("rbac_user_overrides_rls_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_composite_fk_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260724_core_tenant_composite_fks.py"
    spec = importlib.util.spec_from_file_location("core_tenant_composite_fks_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_extended_composite_fk_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260724_extended_tenant_composite_fks.py"
    spec = importlib.util.spec_from_file_location("extended_tenant_composite_fks_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _remaining_scoped_scalar_fks():
    """Return model relationships not covered by the core composite contract."""
    rows = set()
    for table in Base.metadata.sorted_tables:
        if "hotel_id" not in table.c:
            continue
        for constraint in table.foreign_key_constraints:
            parent = constraint.referred_table
            if "hotel_id" not in parent.c or "id" not in parent.c or "id" not in table.c:
                continue
            local = tuple(element.parent.name for element in constraint.elements)
            remote = tuple(element.column.name for element in constraint.elements)
            # This lifecycle row intentionally keeps the source movement FK
            # scalar: SQLite and PostgreSQL can then honour ON DELETE SET NULL
            # without attempting to null the non-null tenant key. The value is
            # never supplied by an API caller; it is written from the just
            # created, same-hotel RoomMoveEvent inside the move transaction.
            if (
                table.name == "guest_room_avoidance"
                and local == ("source_move_event_id",)
                and parent.name == "room_move_events"
            ):
                continue
            if len(local) == 1 and local[0] != "hotel_id":
                rows.add((table.name, ("hotel_id", local[0]), parent.name, ("hotel_id", remote[0])))
    core = set(CORE_COMPOSITE_FK_REQUIREMENTS)
    return rows - core


def test_core_hotel_scoped_relationships_use_composite_foreign_keys():
    actual = {
        (
            constraint.table.name,
            tuple(element.parent.name for element in constraint.elements),
            constraint.elements[0].target_fullname.rsplit(".", 1)[0],
            tuple(element.column.name for element in constraint.elements),
        )
        for table in Base.metadata.tables.values()
        for constraint in table.foreign_key_constraints
        if len(constraint.column_keys) > 1
    }
    missing = [requirement for requirement in CORE_COMPOSITE_FK_REQUIREMENTS if requirement not in actual]
    assert not missing, f"Core tenant composite FKs missing: {missing}"


def test_core_composite_fk_migration_covers_the_metadata_contract():
    migration = _load_composite_fk_migration()
    migrated = {
        (table, columns, referred_table, referred_columns)
        for table, _name, columns, referred_table, referred_columns, _ondelete in migration.COMPOSITE_FKS
    }
    assert set(CORE_COMPOSITE_FK_REQUIREMENTS) <= migrated


def test_extended_composite_fk_migration_covers_every_remaining_scoped_fk():
    migration = _load_extended_composite_fk_migration()
    migrated = {
        (table, columns, referred_table, referred_columns)
        for table, _name, columns, referred_table, referred_columns, _ondelete in migration.COMPOSITE_FKS
    }
    missing = sorted(_remaining_scoped_scalar_fks() - migrated)
    assert not missing, f"Extended tenant composite FKs missing: {missing}"
    assert len(migration.COMPOSITE_FKS) == len(migrated)


def test_extended_composite_fk_migration_has_unique_target_for_every_parent():
    migration = _load_extended_composite_fk_migration()
    core_migration = _load_composite_fk_migration()
    targets = {
        table for table, _name in (*core_migration.UNIQUE_TARGETS, *migration.UNIQUE_TARGETS)
    }
    expected = {
        referred_table
        for _table, _columns, referred_table, _referred_columns in _remaining_scoped_scalar_fks()
    }
    assert expected <= targets


def test_core_parents_have_tenant_scoped_unique_targets():
    required_tables = {
        "room_categories", "rooms", "guests", "companies", "sellable_products", "rate_plans",
        "tax_policies", "reservations", "transactions", "cash_sessions", "cash_close_reports",
        "stock_items", "stock_locations", "payment_links", "payment", "payment_proofs",
    }
    # Payment is plural in SQL; keep this assertion close to the relationship contract.
    required_tables.discard("payment")
    required_tables.add("payments")
    missing = []
    for table_name in required_tables:
        table = Base.metadata.tables[table_name]
        if not any(
            isinstance(constraint, UniqueConstraint)
            and tuple(column.name for column in constraint.columns) == ("hotel_id", "id")
            for constraint in table.constraints
        ):
            missing.append(table_name)
    assert not missing, f"Tenant-scoped FK targets missing unique (hotel_id, id): {missing}"


def test_rls_migration_covers_every_hotel_scoped_model_table():
    migration = _load_rls_migration()
    model_tables = {
        table.name
        for table in Base.metadata.sorted_tables
        if "hotel_id" in table.c
    }
    # Tables introduced after the baseline migration own their RLS DDL in the
    # additive migration that creates them. Keeping them out of the historical
    # inventory preserves linear migration compatibility.
    expected = model_tables - {
        "hotel_api_keys",
        "hotel_memberships",
        "payment_proofs",
        "user_permission_overrides",
        "guest_restrictions",
        "guest_room_avoidance",
        "promotions",
        "notifications",
        "push_subscriptions",
        "notification_preferences",
        "notification_outbox",
        "daily_report_schedules",
        "temporary_action_grants",
        "subscription_adjustments",
        "hotel_role_visibility_window",
    }
    assert set(migration.TENANT_TABLES) == expected
    assert "hotel_memberships" not in migration.TENANT_TABLES


@pytest.mark.parametrize("migration_filename,table_names", ADDITIVE_RLS_TABLE_CONTRACT)
def test_new_tenant_table_enables_its_own_rls_policy(migration_filename, table_names):
    path = Path(__file__).parents[1] / "alembic" / "versions" / migration_filename
    source = path.read_text(encoding="utf-8")
    for table_name in table_names:
        assert f'"{table_name}"' in source
    assert "tenant_isolation_" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)" in source
    assert "WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)" in source
    assert "DROP POLICY IF EXISTS" in source
    assert "NO FORCE ROW LEVEL SECURITY" in source
    assert "DISABLE ROW LEVEL SECURITY" in source


def test_user_override_rls_round_trip_records_valid_postgresql_ddl(monkeypatch):
    """Compile the additive RLS helpers through Alembic's PostgreSQL recorder.

    This is deterministic and executable without a production or preview
    database. It validates dialect rendering and statement ordering, but it is
    intentionally not a substitute for a release-time PostgreSQL migration run.
    """

    migration = _load_user_override_migration()
    output = StringIO()
    dialect = postgresql.dialect()
    context = MigrationContext.configure(
        dialect=dialect,
        opts={"as_sql": True, "output_buffer": output},
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    connection = SimpleNamespace(dialect=dialect)

    migration._install_user_override_rls(connection)
    migration._remove_user_override_rls(connection)

    ddl = output.getvalue()
    enable_pos = ddl.index('ALTER TABLE "user_permission_overrides" ENABLE ROW LEVEL SECURITY')
    force_pos = ddl.index('ALTER TABLE "user_permission_overrides" FORCE ROW LEVEL SECURITY')
    drop_before_create = ddl.index('DROP POLICY IF EXISTS "tenant_isolation_user_permission_overrides"')
    create_pos = ddl.index('CREATE POLICY "tenant_isolation_user_permission_overrides"')
    using_pos = ddl.index("USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)")
    check_pos = ddl.index("WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)")
    drop_before_disable = ddl.rindex('DROP POLICY IF EXISTS "tenant_isolation_user_permission_overrides"')
    no_force_pos = ddl.index('ALTER TABLE "user_permission_overrides" NO FORCE ROW LEVEL SECURITY')
    disable_pos = ddl.index('ALTER TABLE "user_permission_overrides" DISABLE ROW LEVEL SECURITY')
    positions = [
        enable_pos, force_pos, drop_before_create, create_pos, using_pos,
        check_pos, drop_before_disable, no_force_pos, disable_pos,
    ]
    assert positions == sorted(positions)


def test_rls_migration_keeps_api_key_bootstrap_exception_explicit():
    migration = _load_rls_migration()
    source = Path(migration.__file__).read_text(encoding="utf-8")
    assert "hotel_api_keys is intentionally" in source
    assert "current_setting('app.hotel_id', true)" in source
    assert "FORCE ROW LEVEL SECURITY" in source


def test_tenant_context_is_safe_for_local_sqlite_sessions():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        set_tenant_context(db, user_id=7, hotel_id=42)
        set_tenant_hotel_context(db, None)


def _load_master_admin_bypass_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "f3bdaadd3d15_master_admin_rls_bypass.py"
    spec = importlib.util.spec_from_file_location("master_admin_rls_bypass_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_master_admin_bypass_migration_only_touches_tables_the_panel_actually_queries():
    """C2: app/master_admin/router.py queries Subscription directly, and
    transitively (via app/services/subscription_entitlements.py) touches
    subscription_events and hotel_subscriptions. No other tenant table
    should get the master_admin bypass clause without a matching router change.
    """
    migration = _load_master_admin_bypass_migration()
    assert set(migration.MASTER_ADMIN_BYPASS_TABLES) == {
        "subscriptions",
        "subscription_events",
        "hotel_subscriptions",
    }
    # Every bypass table must already be a reviewed tenant table -- the
    # bypass only ever widens an existing hotel_id policy, never installs a
    # brand-new one.
    baseline = _load_rls_migration()
    assert set(migration.MASTER_ADMIN_BYPASS_TABLES) <= set(baseline.TENANT_TABLES)


def test_master_admin_bypass_migration_uses_the_documented_session_flag():
    migration = _load_master_admin_bypass_migration()
    source = Path(migration.__file__).read_text(encoding="utf-8")
    assert "current_setting('app.master_admin', true) = 'true'" in source
    assert "OR hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer" in source
    # Reversible: downgrade must restore the original hotel_id-only clause,
    # not just drop the policy and leave the table unprotected.
    assert source.count("hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer") >= 3
    assert "NO FORCE ROW LEVEL SECURITY" not in source  # bypass never disables RLS entirely


def test_set_master_admin_context_is_safe_for_local_sqlite_sessions():
    from app.services.tenant_context import set_master_admin_context

    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        set_master_admin_context(db)
        set_master_admin_context(db, enabled=False)


@pytest.mark.parametrize("user_id,hotel_id", [(0, 1), (1, 0), (-1, 1), (1, -1)])
def test_tenant_context_rejects_invalid_principals(user_id: int, hotel_id: int):
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        with pytest.raises(ValueError):
            set_tenant_context(db, user_id=user_id, hotel_id=hotel_id)
