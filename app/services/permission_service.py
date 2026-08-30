"""Tenant-scoped permission catalog, resolution, mutation, and audit services."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from weakref import WeakSet

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.hotel_membership import HotelMembership
from app.models.hotel_role_visibility_window import (
    HotelRoleVisibilityWindow,
    VISIBILITY_WINDOW_HOURS,
    VISIBILITY_WINDOW_ROLES,
)
from app.models.permission import (
    HotelPermissionOverride,
    Permission,
    RolePermissionDefault,
    UserPermissionOverride,
)
from app.models.security_audit_log import SecurityAuditLog


logger = logging.getLogger(__name__)


class PermissionVersionConflict(ValueError):
    """Raised when a permission override was changed after it was read."""


ROLE_OWNER = "owner"
ROLE_CO_OWNER = "co_owner"
ROLE_MANAGER = "manager"
ROLE_RECEPTIONIST = "receptionist"
ROLE_HOUSEKEEPING = "housekeeping"
ROLE_CODES = (ROLE_OWNER, ROLE_CO_OWNER, ROLE_MANAGER, ROLE_RECEPTIONIST, ROLE_HOUSEKEEPING)

# Canonical v2 permissions. Names intentionally describe reads, writes, and
# higher-risk actions independently so UI visibility never implies mutation.
PERMISSION_PERMISSION_MANAGE = "permissions:manage"
PERMISSION_GUEST_READ = "guest:read"
PERMISSION_GUEST_CREATE = "guest:create"
PERMISSION_GUEST_UPDATE = "guest:update"
PERMISSION_GUEST_TAGS_MANAGE = "guest:tags_manage"
PERMISSION_GUEST_PROHIBITION_READ = "guest:prohibition_read"
PERMISSION_GUEST_PROHIBITION_MANAGE = "guest:prohibition_manage"
PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE = "guest:room_avoidance_resolve"
PERMISSION_GUEST_EXPORT = "guest:export"
PERMISSION_RESERVATION_READ = "reservation:read"
PERMISSION_RESERVATION_CREATE = "reservation:create"
PERMISSION_RESERVATION_UPDATE = "reservation:update"
PERMISSION_RESERVATION_CANCEL = "reservation:cancel"
PERMISSION_RESERVATION_CHARGE = "reservation:charge"
PERMISSION_RESERVATION_MOVE = "reservation:move"
PERMISSION_RESERVATION_MOVE_CATEGORY = "reservation:move_category"
PERMISSION_RESERVATION_MOVE_CAPACITY = "reservation:move_capacity"
PERMISSION_RESERVATION_MANUAL_RATE = "reservation:manual_rate"
PERMISSION_RESERVATION_PROHIBITION_OVERRIDE = "reservation:prohibition_override"
PERMISSION_ROOM_READ = "room:read"
PERMISSION_ROOM_STATUS_UPDATE = "room:status_update"
PERMISSION_ROOM_BLOCK_CREATE = "room:block_create"
PERMISSION_ROOM_BLOCK_RELEASE = "room:block_release"
PERMISSION_CHECKIN_PERFORM = "checkin:perform"
PERMISSION_CHECKOUT_PERFORM = "checkout:perform"
PERMISSION_CHECKOUT_FORCE = "checkout:force"
PERMISSION_STOCK_READ = "stock:read"
PERMISSION_STOCK_MOVE = "stock:movement"
PERMISSION_STOCK_ADJUST = "stock:adjust"
PERMISSION_STOCK_ADMIN = "stock:admin"
PERMISSION_LAUNDRY_READ = "laundry:read"
PERMISSION_LAUNDRY_MOVE = "laundry:movement"
PERMISSION_LAUNDRY_VENDOR_MANAGE = "laundry:vendor_manage"
PERMISSION_LAUNDRY_REMITO_MANAGE = "laundry:remito_manage"
PERMISSION_LAUNDRY_PRICE_MANAGE = "laundry:price_manage"
PERMISSION_RATES_READ = "rates:read"
PERMISSION_RATES_UPDATE = "rates:update"
PERMISSION_PROMOTIONS_READ = "promotions:read"
PERMISSION_PROMOTIONS_MANAGE = "promotions:manage"
PERMISSION_HOTEL_SETTINGS_READ = "hotel_settings:read"
PERMISSION_HOTEL_SETTINGS_UPDATE = "hotel_settings:update"
PERMISSION_HOTEL_PROPERTY_MANAGE = "hotel_settings:property_manage"
PERMISSION_HOTEL_SECURITY_MANAGE = "hotel_settings:security_manage"

# Existing capabilities outside the split modules stay canonical.
PERMISSION_COMPANY_MANAGE = "company:manage"
PERMISSION_CASH_OPERATE = "cash:operate"
PERMISSION_CASH_APPROVE_DIFFERENCE = "cash:approve_difference"
PERMISSION_REPORTS_OPERATIONAL_VIEW = "reports:operational:view"
PERMISSION_REPORTS_FINANCIAL_VIEW = "reports:financial:view"
PERMISSION_APIKEY_MANAGE = "apikey:manage"

# Section visibility and management permissions used by the next frontend
# navigation/route gate. They are separate from the existing action
# permissions so visibility never implies mutation.
PERMISSION_ANALYTICS_VIEW = "analytics:view"
PERMISSION_ANALYTICS_ADVANCED_VIEW = "analytics:advanced:view"
PERMISSION_ANALYTICS_AI_VIEW = "analytics:ai:view"
PERMISSION_DASHBOARD_VIEW = "dashboard:view"
PERMISSION_OCCUPANCY_VIEW = "occupancy:view"
PERMISSION_WAITLIST_VIEW = "waitlist:view"
PERMISSION_WAITLIST_MANAGE = "waitlist:manage"
PERMISSION_CASH_VIEW = "cash:view"
PERMISSION_COMPANY_VIEW = "company:view"
PERMISSION_SETTINGS_USERS_VIEW = "settings:users:view"
PERMISSION_SETTINGS_USERS_MANAGE = "settings:users:manage"
PERMISSION_SETTINGS_INTEGRATIONS_VIEW = "settings:integrations:view"
PERMISSION_SETTINGS_INTEGRATIONS_MANAGE = "settings:integrations:manage"
PERMISSION_SETTINGS_SUBSCRIPTION_VIEW = "settings:subscription:view"
PERMISSION_SETTINGS_SECURITY_VIEW = "settings:security:view"
PERMISSION_SETTINGS_NOTIFICATIONS_VIEW = "settings:notifications:view"
PERMISSION_SETTINGS_ASSISTANT_VIEW = "settings:assistant:view"
PERMISSION_SETTINGS_TESTS_VIEW = "settings:tests:view"

# Import-compatible legacy constants. Existing routes and the current frontend
# may keep requesting these during the expand/contract window; resolution
# canonicalizes them and effective responses include readable aliases.
PERMISSION_CONFIG_MANAGE = "config:manage"
PERMISSION_GUEST_VIEW = "guest:view"
PERMISSION_GUEST_EDIT = "guest:edit"
PERMISSION_GUEST_TAGS = "guest:tags"
PERMISSION_RESERVATION_ROOM_MOVE = "reservation:room_move"
PERMISSION_ROOM_CLEANING_STATUS = "room:cleaning_status"
PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO = "checkin:override_prohibido"
PERMISSION_STOCK_OPERATE = "stock:operate"
PERMISSION_LAUNDRY_MANAGE_VENDORS = "laundry:manage_vendors"
PERMISSION_LAUNDRY_OPERATE_REMITOS = "laundry:operate_remitos"

LEGACY_PERMISSION_ALIASES: dict[str, str] = {
    PERMISSION_CONFIG_MANAGE: PERMISSION_HOTEL_SETTINGS_UPDATE,
    PERMISSION_GUEST_VIEW: PERMISSION_GUEST_READ,
    PERMISSION_GUEST_EDIT: PERMISSION_GUEST_UPDATE,
    PERMISSION_GUEST_TAGS: PERMISSION_GUEST_TAGS_MANAGE,
    PERMISSION_RESERVATION_ROOM_MOVE: PERMISSION_RESERVATION_MOVE,
    PERMISSION_ROOM_CLEANING_STATUS: PERMISSION_ROOM_STATUS_UPDATE,
    "room_block:create": PERMISSION_ROOM_BLOCK_CREATE,
    "room_block:release": PERMISSION_ROOM_BLOCK_RELEASE,
    PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO: PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
    PERMISSION_STOCK_OPERATE: PERMISSION_STOCK_MOVE,
    PERMISSION_LAUNDRY_MANAGE_VENDORS: PERMISSION_LAUNDRY_VENDOR_MANAGE,
    PERMISSION_LAUNDRY_OPERATE_REMITOS: PERMISSION_LAUNDRY_REMITO_MANAGE,
}

# Ordered from narrowest to widest. A room-move operation checks the minimum
# tier implied by its source and destination categories, then accepts that
# permission or any later one in this tuple.
RESERVATION_MOVE_TIER_PERMISSIONS = (
    PERMISSION_RESERVATION_MOVE,
    PERMISSION_RESERVATION_MOVE_CATEGORY,
    PERMISSION_RESERVATION_MOVE_CAPACITY,
)

_CANONICAL_DEFINITIONS: dict[str, tuple[str, str, str]] = {
    PERMISSION_PERMISSION_MANAGE: (
        "security", "Administer role and employee permissions",
        "Permite abrir la administración de permisos y asignar o revocar permisos de roles y empleados. No permite saltear las reglas de seguridad ni otorgar permisos exclusivos del owner.",
    ),
    PERMISSION_GUEST_READ: (
        "guests", "Read guest profile data",
        "Permite abrir los perfiles de huéspedes y consultar sus datos. No permite crear, editar, exportar ni administrar restricciones.",
    ),
    PERMISSION_GUEST_CREATE: (
        "guests", "Create guest profiles",
        "Permite dar de alta perfiles de huéspedes. No permite editar datos existentes ni exportar el padrón.",
    ),
    PERMISSION_GUEST_UPDATE: (
        "guests", "Update guest profiles",
        "Permite editar datos de perfiles de huéspedes. No permite crearlos, exportarlos ni administrar restricciones.",
    ),
    PERMISSION_GUEST_TAGS_MANAGE: (
        "guests", "Manage guest tags",
        "Permite crear, editar y quitar etiquetas de huéspedes. No permite cambiar los datos principales del perfil ni exportar el padrón.",
    ),
    PERMISSION_GUEST_PROHIBITION_READ: (
        "guests", "Read lodging prohibition status",
        "Permite consultar si un huésped tiene una prohibición de alojamiento. No permite crear, resolver ni saltear esa prohibición.",
    ),
    PERMISSION_GUEST_PROHIBITION_MANAGE: (
        "guests", "Create and resolve lodging prohibitions",
        "Permite crear y resolver prohibiciones de alojamiento. No permite saltear una prohibición vigente sin el permiso específico.",
    ),
    PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE: (
        "guests", "Resolve guest room rejections",
        "Permite resolver un rechazo activo de habitación dejando una nota de resolución. No permite crear rechazos manualmente ni cambiar el evento de movimiento que los originó.",
    ),
    PERMISSION_GUEST_EXPORT: (
        "guests", "Export guest ledger data",
        "Permite exportar el libro de huéspedes dentro del alcance del hotel. No permite editar perfiles ni modificar el historial exportado.",
    ),
    PERMISSION_RESERVATION_READ: (
        "reservations", "Read reservations",
        "Permite abrir y consultar reservas. No permite crearlas, editarlas, cancelarlas ni moverlas.",
    ),
    PERMISSION_RESERVATION_CREATE: (
        "reservations", "Create reservations",
        "Permite crear reservas. No permite modificar, cancelar o mover reservas existentes.",
    ),
    PERMISSION_RESERVATION_UPDATE: (
        "reservations", "Update reservations",
        "Permite editar datos de reservas. No permite cancelarlas, moverlas ni fijar una tarifa manual salvo que tengas esos permisos.",
    ),
    PERMISSION_RESERVATION_CANCEL: (
        "reservations", "Cancel reservations",
        "Permite cancelar reservas. No permite crearlas, editarlas ni moverlas.",
    ),
    PERMISSION_RESERVATION_CHARGE: (
        "reservations", "Add reservation charges",
        "Permite agregar cargos o consumos a una reserva. No permite cambiar sus fechas, habitación ni tarifa.",
    ),
    PERMISSION_RESERVATION_MOVE: (
        "reservations", "Move reservations between rooms",
        "Permite mover una reserva entre habitaciones de la misma categoría. No permite cambiar de categoría ni de capacidad; los permisos de categoría o capacidad incluyen este alcance.",
    ),
    PERMISSION_RESERVATION_MOVE_CATEGORY: (
        "reservations", "Move reservations to another category with equal capacity",
        "Permite mover una reserva a otra categoría con la misma capacidad máxima. También incluye mover dentro de la misma categoría. No permite cambiar a una categoría con capacidad máxima diferente.",
    ),
    PERMISSION_RESERVATION_MOVE_CAPACITY: (
        "reservations", "Move reservations to another category with different capacity",
        "Permite mover una reserva a otra categoría con capacidad máxima diferente. También incluye los movimientos dentro de la misma categoría y entre categorías de igual capacidad. No permite editar otros datos de la reserva ni saltear la validación de ocupación.",
    ),
    PERMISSION_RESERVATION_MANUAL_RATE: (
        "rates", "Override the quoted reservation rate",
        "Permite fijar una tarifa manual al cotizar o editar una reserva. No permite cambiar la configuración general de tarifas.",
    ),
    PERMISSION_RESERVATION_PROHIBITION_OVERRIDE: (
        "guests", "Override a lodging prohibition with reason",
        "Permite alojar excepcionalmente a un huésped con prohibición, dejando el motivo correspondiente. No permite crear ni resolver la prohibición.",
    ),
    PERMISSION_ROOM_READ: (
        "rooms", "Read rooms and operational state",
        "Permite consultar habitaciones y su estado operativo. No permite cambiar estados ni crear o liberar bloqueos.",
    ),
    PERMISSION_ROOM_STATUS_UPDATE: (
        "rooms", "Update room cleaning status",
        "Permite actualizar el estado de limpieza de una habitación. No permite modificar reservas ni administrar bloqueos.",
    ),
    PERMISSION_ROOM_BLOCK_CREATE: (
        "rooms", "Create room blocks",
        "Permite crear bloqueos operativos de habitaciones. No permite liberar bloqueos existentes.",
    ),
    PERMISSION_ROOM_BLOCK_RELEASE: (
        "rooms", "Release room blocks",
        "Permite liberar bloqueos de habitaciones. No permite crear nuevos bloqueos ni cambiar reservas.",
    ),
    PERMISSION_CHECKIN_PERFORM: (
        "checkin", "Perform check-in",
        "Permite realizar el check-in de una reserva. No permite forzar un checkout ni saltear validaciones de alojamiento.",
    ),
    PERMISSION_CHECKOUT_PERFORM: (
        "checkin", "Perform checkout",
        "Permite realizar el checkout de una reserva. No permite forzar un checkout excepcional.",
    ),
    PERMISSION_CHECKOUT_FORCE: (
        "checkin", "Force an exceptional checkout",
        "Permite ejecutar un checkout excepcional cuando el flujo normal no alcanza. No permite modificar reservas fuera de ese proceso.",
    ),
    PERMISSION_STOCK_READ: (
        "stock", "Read stock",
        "Permite consultar existencias, artículos y ubicaciones. No permite registrar movimientos ni ajustar cantidades.",
    ),
    PERMISSION_STOCK_MOVE: (
        "stock", "Record stock movements",
        "Permite registrar movimientos operativos de stock. No permite corregir diferencias de inventario ni administrar el catálogo.",
    ),
    PERMISSION_STOCK_ADJUST: (
        "stock", "Adjust stock after a physical count",
        "Permite ajustar existencias después de un conteo físico. No permite administrar el catálogo ni cambiar reservas.",
    ),
    PERMISSION_STOCK_ADMIN: (
        "stock", "Manage stock catalog and locations",
        "Permite administrar artículos y ubicaciones de stock. No permite ajustar existencias salvo que tengas el permiso específico.",
    ),
    PERMISSION_LAUNDRY_READ: (
        "laundry", "Read laundry operation",
        "Permite consultar la operación de lavandería y la ropa blanca. No permite registrar movimientos ni administrar proveedores.",
    ),
    PERMISSION_LAUNDRY_MOVE: (
        "laundry", "Record linen movements",
        "Permite registrar movimientos de ropa blanca. No permite administrar proveedores ni sus precios.",
    ),
    PERMISSION_LAUNDRY_VENDOR_MANAGE: (
        "laundry", "Manage laundry vendors",
        "Permite administrar proveedores de lavandería. No permite modificar sus precios salvo que tengas el permiso específico.",
    ),
    PERMISSION_LAUNDRY_REMITO_MANAGE: (
        "laundry", "Create and receive laundry remitos",
        "Permite crear y recibir remitos de lavandería. No permite administrar proveedores ni precios.",
    ),
    PERMISSION_LAUNDRY_PRICE_MANAGE: (
        "laundry", "Manage vendor prices",
        "Permite administrar precios de proveedores de lavandería. No permite crear o recibir remitos.",
    ),
    PERMISSION_RATES_READ: (
        "rates", "Read hotel rates",
        "Permite abrir la pantalla de Tarifas y ver los precios por día y categoría. No permite modificarlos: para eso hace falta 'Editar tarifas'.",
    ),
    PERMISSION_RATES_UPDATE: (
        "rates", "Update hotel rates",
        "Permite modificar las tarifas del hotel por día y categoría. No permite administrar promociones ni fijar una tarifa manual en una reserva.",
    ),
    PERMISSION_PROMOTIONS_READ: (
        "promotions", "Read promotions",
        "Permite consultar las promociones del hotel. No permite crearlas, editarlas ni activarlas.",
    ),
    PERMISSION_PROMOTIONS_MANAGE: (
        "promotions", "Manage promotions",
        "Permite crear, editar y administrar promociones. No permite cambiar las tarifas generales.",
    ),
    PERMISSION_HOTEL_SETTINGS_READ: (
        "hotel_settings", "Read hotel settings",
        "Permite consultar la configuración operativa del hotel. No permite modificarla.",
    ),
    PERMISSION_HOTEL_SETTINGS_UPDATE: (
        "hotel_settings", "Update operational hotel settings",
        "Permite modificar la configuración operativa del hotel. No permite transferir la propiedad ni administrar secretos de seguridad.",
    ),
    PERMISSION_HOTEL_PROPERTY_MANAGE: (
        "hotel_settings", "Transfer or change property ownership",
        "Permite transferir o cambiar la propiedad del hotel. No permite administrar otros permisos críticos ni secretos de seguridad.",
    ),
    PERMISSION_HOTEL_SECURITY_MANAGE: (
        "security", "Manage security secrets and connections",
        "Permite administrar secretos y conexiones de seguridad del hotel. No permite transferir la propiedad.",
    ),
    PERMISSION_COMPANY_MANAGE: (
        "companies", "Manage companies and documents",
        "Permite crear, editar y administrar empresas y sus documentos. No implica acceso automático a otras configuraciones del hotel.",
    ),
    PERMISSION_CASH_OPERATE: (
        "cash", "Operate cash register sessions and movements",
        "Permite abrir, operar y cerrar sesiones de caja y registrar movimientos. No permite aprobar diferencias de cierre.",
    ),
    PERMISSION_CASH_APPROVE_DIFFERENCE: (
        "cash", "Approve cash close differences",
        "Permite aprobar diferencias al cerrar caja. No permite operar sesiones ni registrar movimientos por sí solo.",
    ),
    PERMISSION_REPORTS_OPERATIONAL_VIEW: (
        "reports", "Read operational reports",
        "Permite consultar reportes operativos del hotel. No permite consultar reportes financieros ni modificar datos.",
    ),
    PERMISSION_REPORTS_FINANCIAL_VIEW: (
        "reports", "Read financial reports",
        "Permite consultar reportes financieros del hotel. No permite modificar cobros, caja ni reservas.",
    ),
    PERMISSION_APIKEY_MANAGE: (
        "security", "Manage public hotel API keys",
        "Permite administrar las claves API públicas del hotel. No permite administrar secretos internos ni transferir la propiedad.",
    ),
    PERMISSION_ANALYTICS_VIEW: (
        "analytics", "Read analytics overview",
        "Permite abrir el resumen de analítica y consultar métricas del hotel. No permite acceder a vistas avanzadas ni usar el asistente de IA.",
    ),
    PERMISSION_ANALYTICS_ADVANCED_VIEW: (
        "analytics", "Read advanced analytics views",
        "Permite abrir las vistas avanzadas de analítica, como habitaciones, segmentos y canales. No permite cambiar datos operativos.",
    ),
    PERMISSION_ANALYTICS_AI_VIEW: (
        "analytics", "Use analytics AI assistant",
        "Permite abrir el asistente de IA de analítica y consultar sus respuestas. No permite aplicar cambios críticos de forma automática.",
    ),
    PERMISSION_DASHBOARD_VIEW: (
        "dashboard", "Read dashboard overview",
        "Permite abrir el tablero principal y consultar el resumen operativo. No permite modificar reservas, caja ni configuración.",
    ),
    PERMISSION_OCCUPANCY_VIEW: (
        "operations", "Read occupancy planning",
        "Permite abrir la planilla de ocupación y consultar disponibilidad operativa. No permite modificar reservas ni asignaciones.",
    ),
    PERMISSION_WAITLIST_VIEW: (
        "operations", "Read waitlist",
        "Permite consultar la lista de espera. No permite crear, editar ni quitar entradas.",
    ),
    PERMISSION_WAITLIST_MANAGE: (
        "operations", "Manage waitlist entries",
        "Permite crear, editar y administrar entradas de la lista de espera. No permite modificar reservas confirmadas.",
    ),
    PERMISSION_CASH_VIEW: (
        "cash", "Read cash register",
        "Permite abrir y consultar la caja del hotel. No permite operar sesiones ni registrar movimientos; para eso hace falta 'Operar caja'.",
    ),
    PERMISSION_COMPANY_VIEW: (
        "companies", "Read companies and documents",
        "Permite consultar empresas y sus documentos. No permite crearlos, editarlos ni administrarlos.",
    ),
    PERMISSION_SETTINGS_USERS_VIEW: (
        "settings", "Read staff users and roles",
        "Permite abrir la sección de usuarios y consultar personas, roles y estados. No permite invitar, editar ni desactivar usuarios.",
    ),
    PERMISSION_SETTINGS_USERS_MANAGE: (
        "settings", "Manage staff users and roles",
        "Permite administrar usuarios, roles e invitaciones del hotel. No permite cambiar secretos de seguridad ni transferir la propiedad.",
    ),
    PERMISSION_SETTINGS_INTEGRATIONS_VIEW: (
        "settings", "Read integration connections",
        "Permite consultar las conexiones e integraciones configuradas. No permite conectarlas, desconectarlas ni cambiar credenciales.",
    ),
    PERMISSION_SETTINGS_INTEGRATIONS_MANAGE: (
        "settings", "Manage integration connections",
        "Permite administrar conexiones e integraciones del hotel. No permite modificar otros secretos de seguridad.",
    ),
    PERMISSION_SETTINGS_SUBSCRIPTION_VIEW: (
        "settings", "Read subscription and plan details",
        "Permite consultar el plan, la suscripción y los límites del hotel. No permite cambiar el plan ni aplicar ajustes de facturación.",
    ),
    PERMISSION_SETTINGS_SECURITY_VIEW: (
        "settings", "Read security settings",
        "Permite abrir la configuración de seguridad y consultar su estado. No permite modificar secretos, sesiones ni políticas.",
    ),
    PERMISSION_SETTINGS_NOTIFICATIONS_VIEW: (
        "settings", "Read notifications",
        "Permite abrir y consultar las notificaciones del hotel. No permite cambiar preferencias ni enviar mensajes.",
    ),
    PERMISSION_SETTINGS_ASSISTANT_VIEW: (
        "settings", "Read and use the operations assistant",
        "Permite abrir el asistente de operaciones y consultar sugerencias. No permite aplicar cambios críticos sin un flujo explícito y autorizado.",
    ),
    PERMISSION_SETTINGS_TESTS_VIEW: (
        "settings", "Read test tools and settings",
        "Permite abrir las herramientas de prueba del hotel y consultar sus resultados. No permite ejecutar efectos externos sin las protecciones correspondientes.",
    ),
}

PERMISSION_DEFINITIONS: dict[str, str] = {
    code: description for code, (_module, description, _help_es) in _CANONICAL_DEFINITIONS.items()
}
for _legacy_code, _canonical_code in LEGACY_PERMISSION_ALIASES.items():
    PERMISSION_DEFINITIONS[_legacy_code] = f"Legacy alias for {_canonical_code}"
PERMISSION_DEFINITIONS.update(
    {
        PERMISSION_GUEST_VIEW: "View guest profile data",
        PERMISSION_GUEST_CREATE: "Create guest profiles",
        PERMISSION_GUEST_EDIT: "Edit guest profile data",
        PERMISSION_GUEST_TAGS: "Edit guest tags and segmentation",
    }
)


def canonical_permission_code(code: str) -> str:
    return LEGACY_PERMISSION_ALIASES.get(code, code)


def _permission_help_es(code: str) -> str:
    """Return canonical help text for both current and legacy codes."""
    return _CANONICAL_DEFINITIONS[canonical_permission_code(code)][2]


def _role_permissions(*allowed_codes: str) -> dict[str, bool]:
    allowed = {canonical_permission_code(code) for code in allowed_codes}
    canonical = {code: code in allowed for code in _CANONICAL_DEFINITIONS}
    return {
        **canonical,
        **{legacy: canonical.get(target, False) for legacy, target in LEGACY_PERMISSION_ALIASES.items()},
    }


_OPERATIONS = tuple(
    code
    for code in _CANONICAL_DEFINITIONS
    if code
    not in {
        PERMISSION_PERMISSION_MANAGE,
        PERMISSION_HOTEL_PROPERTY_MANAGE,
        PERMISSION_HOTEL_SECURITY_MANAGE,
        PERMISSION_APIKEY_MANAGE,
        PERMISSION_RESERVATION_MANUAL_RATE,
    }
)
DEFAULT_MATRIX: dict[str, dict[str, bool]] = {
    ROLE_OWNER: _role_permissions(*_CANONICAL_DEFINITIONS),
    ROLE_CO_OWNER: _role_permissions(*_OPERATIONS),
    ROLE_MANAGER: _role_permissions(
        PERMISSION_GUEST_READ, PERMISSION_GUEST_CREATE, PERMISSION_GUEST_UPDATE,
        PERMISSION_GUEST_TAGS_MANAGE, PERMISSION_GUEST_PROHIBITION_READ,
        PERMISSION_GUEST_PROHIBITION_MANAGE, PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE,
        PERMISSION_GUEST_EXPORT,
        PERMISSION_RESERVATION_READ, PERMISSION_RESERVATION_CREATE,
        PERMISSION_RESERVATION_UPDATE, PERMISSION_RESERVATION_CANCEL,
        PERMISSION_RESERVATION_MOVE, PERMISSION_RESERVATION_MOVE_CATEGORY,
        PERMISSION_RESERVATION_MOVE_CAPACITY, PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
        PERMISSION_ROOM_READ, PERMISSION_ROOM_STATUS_UPDATE,
        PERMISSION_ROOM_BLOCK_CREATE, PERMISSION_ROOM_BLOCK_RELEASE,
        PERMISSION_CHECKIN_PERFORM, PERMISSION_CHECKOUT_PERFORM,
        PERMISSION_STOCK_READ, PERMISSION_STOCK_MOVE, PERMISSION_STOCK_ADMIN,
        PERMISSION_LAUNDRY_READ, PERMISSION_LAUNDRY_MOVE,
        PERMISSION_LAUNDRY_VENDOR_MANAGE, PERMISSION_LAUNDRY_REMITO_MANAGE,
        PERMISSION_LAUNDRY_PRICE_MANAGE, PERMISSION_RATES_READ,
        PERMISSION_RATES_UPDATE, PERMISSION_PROMOTIONS_READ,
        PERMISSION_PROMOTIONS_MANAGE, PERMISSION_REPORTS_OPERATIONAL_VIEW,
        PERMISSION_COMPANY_MANAGE, PERMISSION_COMPANY_VIEW,
        PERMISSION_DASHBOARD_VIEW, PERMISSION_OCCUPANCY_VIEW,
        PERMISSION_WAITLIST_VIEW, PERMISSION_WAITLIST_MANAGE,
        PERMISSION_SETTINGS_NOTIFICATIONS_VIEW, PERMISSION_SETTINGS_ASSISTANT_VIEW,
    ),
    ROLE_RECEPTIONIST: _role_permissions(
        PERMISSION_GUEST_READ, PERMISSION_GUEST_CREATE, PERMISSION_GUEST_UPDATE,
        PERMISSION_GUEST_TAGS_MANAGE, PERMISSION_GUEST_PROHIBITION_READ,
        PERMISSION_RESERVATION_READ, PERMISSION_RESERVATION_CREATE,
        PERMISSION_RESERVATION_UPDATE, PERMISSION_RESERVATION_CANCEL,
        PERMISSION_RESERVATION_CHARGE, PERMISSION_RESERVATION_MOVE, PERMISSION_ROOM_READ,
        PERMISSION_ROOM_BLOCK_CREATE, PERMISSION_CHECKIN_PERFORM,
        PERMISSION_CHECKOUT_PERFORM, PERMISSION_CASH_OPERATE,
        PERMISSION_DASHBOARD_VIEW, PERMISSION_OCCUPANCY_VIEW,
        PERMISSION_WAITLIST_VIEW, PERMISSION_WAITLIST_MANAGE,
        PERMISSION_CASH_VIEW, PERMISSION_SETTINGS_NOTIFICATIONS_VIEW,
    ),
    ROLE_HOUSEKEEPING: _role_permissions(
        PERMISSION_ROOM_READ, PERMISSION_ROOM_STATUS_UPDATE, PERMISSION_LAUNDRY_READ,
        PERMISSION_LAUNDRY_MOVE, PERMISSION_LAUNDRY_REMITO_MANAGE,
    ),
}

_OWNER_ONLY = frozenset(
    {
        PERMISSION_PERMISSION_MANAGE,
        PERMISSION_HOTEL_PROPERTY_MANAGE,
        PERMISSION_HOTEL_SECURITY_MANAGE,
        PERMISSION_APIKEY_MANAGE,
    }
)


def immutable_permission_decision(role: str | None, code: str) -> tuple[bool, str] | None:
    canonical = canonical_permission_code(code)
    if canonical in _OWNER_ONLY:
        return role == ROLE_OWNER, "owner_only"
    return None


def can_role_hold_permission(role: str | None, permission_code: str) -> bool:
    invariant = immutable_permission_decision(role, permission_code)
    return True if invariant is None else invariant[0]


def _insert_if_missing(db: Session, table, values, conflict_columns: list[str]) -> None:
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        statement = sqlite_insert(table).values(values).on_conflict_do_nothing(index_elements=conflict_columns)
    elif dialect == "postgresql":
        statement = postgresql_insert(table).values(values).on_conflict_do_nothing(index_elements=conflict_columns)
    else:
        raise RuntimeError(f"Unsupported database dialect for permission seeding: {dialect}")
    db.execute(statement)


def seed_default_permissions(db: Session) -> None:
    _insert_if_missing(
        db,
        Permission.__table__,
        [
            {
                "code": code,
                "description": description,
                "critical": code in _OWNER_ONLY,
                "step_up_required": code in _OWNER_ONLY,
                "delegable": code not in _OWNER_ONLY,
            }
            for code, description in PERMISSION_DEFINITIONS.items()
        ],
        ["code"],
    )
    rows = {row.code: row for row in db.query(Permission).filter(Permission.code.in_(PERMISSION_DEFINITIONS)).all()}
    for code, description in PERMISSION_DEFINITIONS.items():
        rows[code].description = description
        rows[code].critical = code in _OWNER_ONLY
        rows[code].step_up_required = code in _OWNER_ONLY
        rows[code].delegable = code not in _OWNER_ONLY
    db.flush()
    values = [
        {"role": role, "permission_code": code, "allowed": allowed}
        for role, permissions in DEFAULT_MATRIX.items()
        for code, allowed in permissions.items()
    ]
    _insert_if_missing(db, RolePermissionDefault.__table__, values, ["role", "permission_code"])
    # Defaults are deployment data, not runtime configuration. The migration
    # may have backfilled a safer decision from a legacy permission and an
    # operator may already rely on that persisted value. Runtime seeding only
    # fills missing rows; explicit override APIs are the sole mutation path.
    db.flush()


_seeded_engines: WeakSet = WeakSet()
_seed_lock = threading.Lock()


def _engine_key(db: Session):
    bind = db.get_bind()
    return getattr(bind, "engine", bind)


def ensure_permission_matrix_seeded(db: Session) -> None:
    engine = _engine_key(db)
    if engine in _seeded_engines:
        return
    with _seed_lock:
        if engine in _seeded_engines:
            return
        seed_default_permissions(db)
        db.commit()
        _seeded_engines.add(engine)


def reset_permission_seed_cache() -> None:
    _seeded_engines.clear()


def invalidate_effective_permission_cache(db: Session, hotel_id: int, user_id: int | None = None) -> None:
    """Explicit invalidation boundary for callers and future cache adapters.

    Effective authorization is intentionally not cached in-process: a
    revocation committed by another worker must be visible on the very next
    protected request. Mutation paths still call this hook so a distributed
    cache can be introduced without changing their security contract.
    """


def publish_permission_invalidation(hotel_id: int) -> None:
    """Best-effort tenant signal after commit; never roll back the RBAC write."""

    try:
        from app.services.domain_events import RealtimeEventsUnavailable, publish_domain_event

        publish_domain_event(
            hotel_id=hotel_id,
            domain="security",
            event_type="permissions.changed",
            payload={"family": "effective_permissions"},
        )
    except RealtimeEventsUnavailable:
        logger.warning("permission_invalidation.realtime_unavailable", extra={"hotel_id": hotel_id})
    except Exception as exc:
        logger.warning("permission_invalidation.failed", extra={"hotel_id": hotel_id, "error_type": type(exc).__name__})


def get_effective_permission_details(
    db: Session,
    hotel_id: int,
    role: str | None,
    *,
    user_id: int | None = None,
) -> dict[str, dict[str, object]]:
    if role not in ROLE_CODES:
        return {}
    ensure_permission_matrix_seeded(db)
    defaults = {
        row.permission_code: bool(row.allowed)
        for row in db.query(RolePermissionDefault).filter(RolePermissionDefault.role == role).all()
    }
    role_overrides = {
        row.permission_code: bool(row.allowed)
        for row in db.query(HotelPermissionOverride).filter_by(hotel_id=hotel_id, role=role).all()
    }
    user_overrides = {}
    if user_id is not None:
        user_overrides = {
            row.permission_code: bool(row.allowed)
            for row in db.query(UserPermissionOverride).filter_by(hotel_id=hotel_id, user_id=user_id).all()
        }

    details: dict[str, dict[str, object]] = {}
    for code in _CANONICAL_DEFINITIONS:
        invariant = immutable_permission_decision(role, code)
        if invariant is not None:
            allowed, reason = invariant
            details[code] = {"allowed": allowed, "source": "invariant", "locked": True, "lock_reason": reason}
        elif code in user_overrides:
            details[code] = {"allowed": user_overrides[code], "source": "user_override", "locked": False, "lock_reason": None}
        elif code in role_overrides:
            details[code] = {"allowed": role_overrides[code], "source": "role_override", "locked": False, "lock_reason": None}
        elif code in defaults:
            details[code] = {"allowed": defaults[code], "source": "role_default", "locked": False, "lock_reason": None}
        else:
            details[code] = {"allowed": False, "source": "deny", "locked": False, "lock_reason": None}

    return details


def resolve(
    db: Session,
    hotel_id: int,
    role: str | None,
    permission_code: str,
    user_id: int | None = None,
) -> bool:
    canonical = canonical_permission_code(permission_code)
    return bool(get_effective_permission_details(db, hotel_id, role, user_id=user_id).get(canonical, {}).get("allowed"))


def _audit(db: Session, *, hotel_id: int, actor_user_id: int | None, action: str, resource_type: str,
           resource_id: str, before: object, after: object) -> None:
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=json.dumps({"before": before, "after": after}, sort_keys=True),
        )
    )


def get_visibility_window(
    db: Session, hotel_id: int, role: str
) -> HotelRoleVisibilityWindow | None:
    """Return one tenant-scoped role window, or ``None`` for no limit."""
    return (
        db.query(HotelRoleVisibilityWindow)
        .filter_by(hotel_id=hotel_id, role=role)
        .one_or_none()
    )


def list_visibility_windows(db: Session, hotel_id: int) -> list[HotelRoleVisibilityWindow]:
    """Return configured windows for one hotel only."""
    return (
        db.query(HotelRoleVisibilityWindow)
        .filter(
            HotelRoleVisibilityWindow.hotel_id == hotel_id,
            HotelRoleVisibilityWindow.role.in_(VISIBILITY_WINDOW_ROLES),
        )
        .all()
    )


def set_visibility_window(
    db: Session,
    hotel_id: int,
    role: str,
    past_hours: int | None,
    future_hours: int | None,
    actor_user_id: int | None,
) -> HotelRoleVisibilityWindow:
    """Upsert one role window and record the security-sensitive change."""
    if role not in VISIBILITY_WINDOW_ROLES:
        raise ValueError("Rol invalido")
    for value in (past_hours, future_hours):
        if value is not None and value not in VISIBILITY_WINDOW_HOURS:
            raise ValueError("La ventana debe ser 12, 24, 48, 72, 168 horas o Siempre")

    row = get_visibility_window(db, hotel_id, role)
    before = None if row is None else {
        "past_hours": row.past_hours,
        "future_hours": row.future_hours,
    }
    if row is None:
        row = HotelRoleVisibilityWindow(hotel_id=hotel_id, role=role)
        db.add(row)

    row.past_hours = past_hours
    row.future_hours = future_hours
    row.updated_by_user_id = actor_user_id
    row.updated_at = datetime.now(timezone.utc)
    _audit(
        db,
        hotel_id=hotel_id,
        actor_user_id=actor_user_id,
        action="permission.visibility_window.updated",
        resource_type="hotel_role_visibility_window",
        resource_id=role,
        before=before,
        after={
            "role": role,
            "past_hours": past_hours,
            "future_hours": future_hours,
        },
    )
    db.flush()
    return row


def _validate_permission_code(code: str) -> str:
    canonical = canonical_permission_code(code)
    if canonical not in _CANONICAL_DEFINITIONS:
        raise ValueError("Permiso invalido")
    return canonical


def _validate_mutable(role: str, code: str, allowed: bool) -> str:
    canonical = _validate_permission_code(code)
    invariant = immutable_permission_decision(role, canonical)
    if invariant is not None:
        raise ValueError("El permiso esta bloqueado por una regla de seguridad")
    return canonical


def set_role_override(
    db: Session, hotel_id: int, role: str, code: str, allowed: bool, actor_user_id: int | None,
    expected_version: int | None = None,
) -> HotelPermissionOverride:
    canonical = _validate_mutable(role, code, allowed)
    ensure_permission_matrix_seeded(db)
    row = db.query(HotelPermissionOverride).filter_by(hotel_id=hotel_id, role=role, permission_code=canonical).one_or_none()
    if expected_version is not None:
        if row is None and expected_version != 0:
            raise PermissionVersionConflict("El permiso fue modificado por otra solicitud")
        if row is not None and row.version != expected_version:
            raise PermissionVersionConflict("El permiso fue modificado por otra solicitud")
    before = None if row is None else {"allowed": bool(row.allowed)}
    next_version = 1 if row is None else row.version + 1
    if row is not None:
        before["version"] = row.version
    if row is None:
        row = HotelPermissionOverride(
            hotel_id=hotel_id,
            role=role,
            permission_code=canonical,
            allowed=allowed,
            version=1,
        )
        db.add(row)
    row.allowed = allowed
    row.updated_by_user_id = actor_user_id
    row.updated_at = datetime.now(timezone.utc)
    _audit(
        db, hotel_id=hotel_id, actor_user_id=actor_user_id,
        action="permission.override.updated", resource_type="permission_override",
        resource_id=f"{role}:{canonical}", before=before,
        after={"role": role, "permission_code": canonical, "allowed": allowed, "version": next_version},
    )
    db.flush()
    invalidate_effective_permission_cache(db, hotel_id)
    return row


def set_override(
    db: Session, hotel_id: int, role: str, code: str, allowed: bool, user_id: int | None,
    expected_version: int | None = None,
):
    """Backward-compatible alias for the role-override mutation."""
    return set_role_override(
        db, hotel_id, role, code, allowed, actor_user_id=user_id, expected_version=expected_version,
    )


def _active_membership(db: Session, hotel_id: int, user_id: int) -> HotelMembership | None:
    return db.query(HotelMembership).filter_by(hotel_id=hotel_id, user_id=user_id, status="active").one_or_none()


def set_user_override(
    db: Session, hotel_id: int, target_user_id: int, target_role: str | None,
    code: str, allowed: bool, actor_user_id: int | None, expected_version: int | None = None,
) -> UserPermissionOverride:
    membership = _active_membership(db, hotel_id, target_user_id)
    if membership is None or (target_role is not None and membership.role != target_role):
        raise LookupError("Usuario no encontrado")
    canonical = _validate_mutable(membership.role, code, allowed)
    ensure_permission_matrix_seeded(db)
    row = db.query(UserPermissionOverride).filter_by(
        hotel_id=hotel_id, user_id=target_user_id, permission_code=canonical
    ).one_or_none()
    if expected_version is not None:
        if row is None and expected_version != 0:
            raise PermissionVersionConflict("El permiso fue modificado por otra solicitud")
        if row is not None and row.version != expected_version:
            raise PermissionVersionConflict("El permiso fue modificado por otra solicitud")
    before = None if row is None else {"allowed": bool(row.allowed)}
    next_version = 1 if row is None else row.version + 1
    if row is not None:
        before["version"] = row.version
    if row is None:
        row = UserPermissionOverride(
            hotel_id=hotel_id,
            user_id=target_user_id,
            permission_code=canonical,
            allowed=allowed,
            version=1,
        )
        db.add(row)
    row.allowed = allowed
    row.updated_by_user_id = actor_user_id
    row.updated_at = datetime.now(timezone.utc)
    _audit(
        db, hotel_id=hotel_id, actor_user_id=actor_user_id,
        action="permission.user_override.updated", resource_type="user_permission_override",
        resource_id=f"{target_user_id}:{canonical}", before=before,
        after={"user_id": target_user_id, "permission_code": canonical, "allowed": allowed, "version": next_version},
    )
    db.flush()
    invalidate_effective_permission_cache(db, hotel_id, target_user_id)
    return row


def _role_default_allowed(db: Session, role: str, permission_code: str) -> bool:
    default = db.query(RolePermissionDefault).filter_by(
        role=role,
        permission_code=permission_code,
    ).one_or_none()
    if default is None:
        raise ValueError("No existe un default de catalogo para ese rol y permiso")
    return bool(default.allowed)


def _assert_owner_management_restore(role: str, permission_code: str, default_allowed: bool) -> None:
    """Never restore a corrupted owner-management default to a deny decision."""
    if (
        role == ROLE_OWNER
        and permission_code == PERMISSION_PERMISSION_MANAGE
        and not default_allowed
    ):
        raise ValueError("No se puede dejar al owner sin permisos para gestionar el hotel")


def restore_role_override(
    db: Session,
    hotel_id: int,
    role: str,
    code: str,
    actor_user_id: int | None,
    expected_version: int,
) -> dict[str, object]:
    """Delete one hotel-role override so resolution falls back to its default."""
    if role not in ROLE_CODES:
        raise ValueError("Rol invalido")
    canonical = _validate_permission_code(code)
    ensure_permission_matrix_seeded(db)
    row = db.query(HotelPermissionOverride).filter_by(
        hotel_id=hotel_id,
        role=role,
        permission_code=canonical,
    ).one_or_none()
    if row is None:
        raise LookupError("Override no encontrado")
    if row.version != expected_version:
        raise PermissionVersionConflict("El permiso fue modificado por otra solicitud")

    default_allowed = _role_default_allowed(db, role, canonical)
    _assert_owner_management_restore(role, canonical, default_allowed)
    before = {
        "role": row.role,
        "permission_code": row.permission_code,
        "allowed": bool(row.allowed),
        "version": row.version,
    }
    after = {
        "role": role,
        "permission_code": canonical,
        "allowed": default_allowed,
        "source": "role_default",
    }
    db.delete(row)
    _audit(
        db,
        hotel_id=hotel_id,
        actor_user_id=actor_user_id,
        action="permission.override.restored",
        resource_type="permission_override",
        resource_id=f"{role}:{canonical}",
        before=before,
        after=after,
    )
    db.flush()
    invalidate_effective_permission_cache(db, hotel_id)
    return {
        "hotel_id": hotel_id,
        "role": role,
        "permission_code": canonical,
        "allowed": default_allowed,
        "source": "role_default",
        "restored": True,
    }


def restore_user_override(
    db: Session,
    hotel_id: int,
    target_user_id: int,
    actor_user_id: int | None,
    code: str,
    expected_version: int,
) -> dict[str, object]:
    """Delete one user override so resolution falls back to the user's role default."""
    membership = _active_membership(db, hotel_id, target_user_id)
    if membership is None:
        raise LookupError("Usuario no encontrado")
    canonical = _validate_permission_code(code)
    ensure_permission_matrix_seeded(db)
    row = db.query(UserPermissionOverride).filter_by(
        hotel_id=hotel_id,
        user_id=target_user_id,
        permission_code=canonical,
    ).one_or_none()
    if row is None:
        raise LookupError("Override no encontrado")
    if row.version != expected_version:
        raise PermissionVersionConflict("El permiso fue modificado por otra solicitud")

    default_allowed = _role_default_allowed(db, membership.role, canonical)
    _assert_owner_management_restore(membership.role, canonical, default_allowed)
    before = {
        "user_id": row.user_id,
        "permission_code": row.permission_code,
        "allowed": bool(row.allowed),
        "version": row.version,
    }
    after = {
        "user_id": target_user_id,
        "role": membership.role,
        "permission_code": canonical,
        "allowed": default_allowed,
        "source": "role_default",
    }
    db.delete(row)
    _audit(
        db,
        hotel_id=hotel_id,
        actor_user_id=actor_user_id,
        action="permission.user_override.restored",
        resource_type="user_permission_override",
        resource_id=f"{target_user_id}:{canonical}",
        before=before,
        after=after,
    )
    db.flush()
    invalidate_effective_permission_cache(db, hotel_id, target_user_id)
    return {
        "hotel_id": hotel_id,
        "user_id": target_user_id,
        "role": membership.role,
        "permission_code": canonical,
        "allowed": default_allowed,
        "source": "role_default",
        "restored": True,
    }


def restore_role_defaults(db: Session, hotel_id: int, role: str, actor_user_id: int | None) -> int:
    rows = db.query(HotelPermissionOverride).filter_by(hotel_id=hotel_id, role=role).all()
    before = [{"permission_code": row.permission_code, "allowed": bool(row.allowed)} for row in rows]
    for row in rows:
        db.delete(row)
    _audit(
        db, hotel_id=hotel_id, actor_user_id=actor_user_id,
        action="permission.role_overrides.restored", resource_type="permission_override",
        resource_id=role, before=before, after=[],
    )
    db.flush()
    invalidate_effective_permission_cache(db, hotel_id)
    return len(rows)


def restore_user_defaults(db: Session, hotel_id: int, target_user_id: int, actor_user_id: int | None) -> int:
    if _active_membership(db, hotel_id, target_user_id) is None:
        raise LookupError("Usuario no encontrado")
    rows = db.query(UserPermissionOverride).filter_by(hotel_id=hotel_id, user_id=target_user_id).all()
    before = [{"permission_code": row.permission_code, "allowed": bool(row.allowed)} for row in rows]
    for row in rows:
        db.delete(row)
    _audit(
        db, hotel_id=hotel_id, actor_user_id=actor_user_id,
        action="permission.user_overrides.restored", resource_type="user_permission_override",
        resource_id=str(target_user_id), before=before, after=[],
    )
    db.flush()
    invalidate_effective_permission_cache(db, hotel_id, target_user_id)
    return len(rows)


def get_permission_catalog(db: Session | None = None) -> list[dict[str, object]]:
    metadata_by_code: dict[str, Permission] = {}
    if db is not None:
        ensure_permission_matrix_seeded(db)
        metadata_by_code = {
            row.code: row
            for row in db.query(Permission).filter(Permission.code.in_(_CANONICAL_DEFINITIONS)).all()
        }
    result = []
    for code, (module, description, help_es) in _CANONICAL_DEFINITIONS.items():
        metadata = metadata_by_code.get(code)
        result.append(
            {
                "code": code,
                "module": module,
                "description": description,
                "help_es": help_es,
                "legacy_aliases": sorted(alias for alias, target in LEGACY_PERMISSION_ALIASES.items() if target == code),
                "locked": code in _OWNER_ONLY,
                "lock_reason": "owner_only" if code in _OWNER_ONLY else None,
                "critical": bool(metadata.critical) if metadata is not None else code in _OWNER_ONLY,
                "step_up_required": bool(metadata.step_up_required) if metadata is not None else code in _OWNER_ONLY,
                "delegable": bool(metadata.delegable) if metadata is not None else code not in _OWNER_ONLY,
            }
        )
    return sorted(result, key=lambda row: (str(row["module"]), str(row["code"])))


def get_matrix(db: Session, hotel_id: int) -> dict[str, dict[str, dict[str, object]]]:
    matrix = {}
    for role in ROLE_CODES:
        canonical = get_effective_permission_details(db, hotel_id, role)
        role_result = {}
        for code, (module, description, help_es) in _CANONICAL_DEFINITIONS.items():
            detail = dict(canonical[canonical_permission_code(code)])
            source = detail["source"]
            if source == "role_override":
                source = "override"
            elif source == "role_default":
                source = "default"
            role_result[code] = {
                "allowed": detail["allowed"],
                "source": source,
                "description": description,
                "module": module,
                "help_es": help_es,
            }
        matrix[role] = role_result
    return matrix


def get_role_profiles(db: Session, hotel_id: int) -> dict[str, dict[str, dict[str, object]]]:
    """Canonical role profiles with UI-ready source and immutable metadata."""

    profiles = {}
    for role in ROLE_CODES:
        details = get_effective_permission_details(db, hotel_id, role)
        profiles[role] = {
            code: {
                **detail,
                "description": _CANONICAL_DEFINITIONS[code][1],
                "module": _CANONICAL_DEFINITIONS[code][0],
                "help_es": _CANONICAL_DEFINITIONS[code][2],
            }
            for code, detail in details.items()
        }
    return profiles


def get_effective_permissions(db: Session, hotel_id: int, role: str | None, user_id: int | None = None) -> list[str]:
    details = get_effective_permission_details(db, hotel_id, role, user_id=user_id)
    allowed = {code for code, detail in details.items() if detail["allowed"]}
    allowed.update(alias for alias, target in LEGACY_PERMISSION_ALIASES.items() if target in allowed)
    return sorted(allowed)


def audit_permission_denied(
    db: Session, *, hotel_id: int, user_id: int | None, role: str | None, permission_code: str,
) -> None:
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=user_id,
            action="permission.denied",
            resource_type="permission",
            resource_id=canonical_permission_code(permission_code),
            details=json.dumps(
                {
                    "role": role,
                    "permission_code": permission_code,
                    "canonical_permission_code": canonical_permission_code(permission_code),
                },
                sort_keys=True,
            ),
        )
    )
    db.commit()
