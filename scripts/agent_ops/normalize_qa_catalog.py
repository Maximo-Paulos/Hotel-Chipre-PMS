#!/usr/bin/env python3
"""Split historical QA observations and build the v2 regression contracts."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "qa" / "regression-catalog.json"
HISTORY_ROOT = ROOT / "qa" / "history" / "observations"
OPERATIONAL_PATH = ROOT / "qa" / "operational" / "shared-sandbox-catalog.json"

TENANT_PERSONAS = ["owner", "co_owner", "manager", "reception", "housekeeping"]
DEFAULT_DEVICES = [
    "desktop-chromium-1440x900",
    "mobile-webkit-iphone-15-390x844",
]

# id, area, routes, checks, expected, personas, allowed personas, optional devices
CASE_SPECS: list[tuple] = [
    ("marketing-home", "marketing", ["/"], ["content", "navigation", "responsive"], "La portada publica funciona sin exponer datos del PMS.", ["anonymous"], ["anonymous"]),
    ("marketing-pricing", "marketing", ["/precios"], ["content", "CTA", "responsive"], "Precios muestra contenido y destinos intencionales.", ["anonymous"], ["anonymous"]),
    ("marketing-functions", "marketing", ["/funciones"], ["content", "links", "responsive"], "Funciones mantiene navegacion util y accesible.", ["anonymous"], ["anonymous"]),
    ("marketing-pms-hotelero", "marketing", ["/pms-hotelero"], ["content", "canonical", "responsive"], "La pagina SEO de PMS hotelero es util y navegable.", ["anonymous"], ["anonymous"]),
    ("marketing-software-hoteles", "marketing", ["/software-para-hoteles"], ["content", "links", "responsive"], "La pagina SEO de software hotelero es util y navegable.", ["anonymous"], ["anonymous"]),
    ("marketing-faq", "marketing", ["/faq"], ["accordion", "keyboard", "responsive"], "FAQ funciona con mouse, teclado y viewport estrecho.", ["anonymous"], ["anonymous"]),
    ("auth-owner-registration-contract", "auth", ["/register-owner", "/verify-email"], ["validation", "local outbox", "no delivery"], "El alta valida datos y completa verificacion solo con outbox local.", ["anonymous"], ["anonymous"]),
    ("auth-recovery-contract", "auth", ["/forgot-password", "/reset-password"], ["enumeration resistance", "local outbox", "validation"], "La recuperacion es segura y su recorrido positivo usa solo outbox local.", ["anonymous"], ["anonymous"]),
    ("auth-login", "auth", ["/login"], ["login", "invalid password", "logout"], "Cada persona inicia y cierra sesion; credenciales invalidas fallan de forma segura.", TENANT_PERSONAS, TENANT_PERSONAS),
    ("auth-invitation", "auth", ["/invitations/accept", "/accept-invitation"], ["invite", "accept", "expired state"], "Invitaciones respetan jerarquia y muestran estados validos, vencidos e invalidos.", TENANT_PERSONAS, TENANT_PERSONAS),
    ("onboarding", "onboarding", ["/onboarding"], ["steps", "validation", "resume"], "Solo roles autorizados completan o retoman onboarding sintetico.", TENANT_PERSONAS, ["owner"]),
    ("routing-host-contract", "routing", ["/", "catch-all", "query/hash/back"], ["host routing", "direct load", "back"], "Hosts, deep links, query, hash, recarga y catch-all preservan el destino correcto.", TENANT_PERSONAS, TENANT_PERSONAS),
    ("dashboard-permissions", "dashboard", ["/dashboard"], ["load", "empty/error", "role content"], "Dashboard solo expone informacion permitida para la persona.", TENANT_PERSONAS, TENANT_PERSONAS),
    ("guests", "operations", ["/huespedes"], ["list", "create/edit", "search/tags", "denial"], "Huespedes y acompanantes quedan aislados; housekeeping no accede a PII.", TENANT_PERSONAS, ["owner", "co_owner", "manager", "reception"]),
    ("reservations", "operations", ["/reservas"], ["create/update", "overlap", "move/no-show/cancel"], "El ciclo de reserva persiste, evita solapamientos y respeta permisos.", TENANT_PERSONAS, ["owner", "co_owner", "manager", "reception"]),
    ("occupancy-planning", "operations", ["/operacion/planilla"], ["availability", "occupancy", "cross-module persistence"], "Planilla, disponibilidad, habitacion y reserva permanecen reconciliadas.", TENANT_PERSONAS, ["owner", "co_owner", "manager", "reception", "housekeeping"]),
    ("rooms", "operations", ["/habitaciones"], ["room state", "block create/release", "cleaning boundary"], "Estados y bloqueos muestran solo controles autorizados; limpieza no reasigna reservas.", TENANT_PERSONAS, TENANT_PERSONAS),
    ("cash-register", "finance", ["/caja"], ["open", "movement", "close/custody", "denial"], "Caja conserva trazabilidad y deniega housekeeping.", TENANT_PERSONAS, ["owner", "co_owner", "manager", "reception"]),
    ("reports", "reports", ["/reportes"], ["operational", "financial boundary", "filters/export"], "Manager ve solo operacion; owner y co-owner pueden ver finanzas.", TENANT_PERSONAS, ["owner", "co_owner", "manager"]),
    ("waitlist", "operations", ["/operacion/lista-espera"], ["create", "promote", "validation"], "Lista de espera promociona una vez y respeta alcance hotelero.", TENANT_PERSONAS, ["owner", "co_owner", "manager", "reception"]),
    ("laundry", "operations", ["/operacion/lavanderia"], ["batch", "remito", "status", "denial"], "Lavanderia conserva cantidades y permite housekeeping sin exponer otros modulos.", TENANT_PERSONAS, ["owner", "co_owner", "manager", "housekeeping"]),
    ("stock", "operations", ["/operacion/stock"], ["in/out", "negative balance", "adjustment permission"], "Owner y co-owner ajustan; manager opera; reception y housekeeping no acceden.", TENANT_PERSONAS, ["owner", "co_owner", "manager"]),
    ("rate-calendar", "operations", ["/operacion/tarifas"], ["calendar", "edit", "validation", "denial"], "Tarifas valida cambios y solo autoriza roles operativos superiores.", TENANT_PERSONAS, ["owner", "co_owner", "manager"]),
    ("analytics", "analytics", ["/analytics"], ["filters", "metrics", "empty/error"], "Analytics muestra fuentes claras y datos permitidos.", TENANT_PERSONAS, ["owner", "co_owner", "manager"]),
    ("analytics-subroutes", "analytics", ["/analytics/rooms", "/analytics/segments", "/analytics/channels", "/analytics/operations", "/analytics/ai-chat", "/analytics/rooms/:roomId", "/analytics/categories/:categoryId", "/analytics/companies/:companyId"], ["navigation", "filters", "disabled AI"], "Subrutas de analytics son navegables y la IA desactivada falla de forma clara.", TENANT_PERSONAS, ["owner", "co_owner", "manager"]),
    ("room-state-events", "operations", ["/operacion/room-state-events"], ["audit", "filter", "tenant scope"], "Eventos de habitacion son trazables, filtrables y aislados.", TENANT_PERSONAS, TENANT_PERSONAS),
    ("realtime-cross-tab", "realtime", ["/api/events/stream", "/operacion/planilla"], ["two tabs", "tenant event", "no PII"], "Una mutacion invalida solo el hotel correcto y no emite PII.", TENANT_PERSONAS, TENANT_PERSONAS, ["desktop-chromium-two-tabs"]),
    ("warehouse-reconciliation", "analytics", ["/analytics", "/health/datastores"], ["freshness", "PG source", "mismatch"], "El warehouse declara su lag y nunca oculta una divergencia con PostgreSQL.", ["owner", "co_owner", "manager"], ["owner", "co_owner", "manager"], ["api-contract"]),
    ("tenant-composite-integrity", "security", ["PostgreSQL core domain writes"], ["composite FK", "cross-hotel denial", "cache isolation"], "IDs validos de otro hotel no pueden asociarse ni filtrarse al hotel actual.", TENANT_PERSONAS, TENANT_PERSONAS, ["api-contract"]),
    ("mobile-apple-critical", "responsive", ["/reservas", "/caja", "/operacion/stock", "/reportes"], ["overflow", "touch targets", "keyboard/focus"], "Operaciones criticas funcionan en viewports Apple sin confirmaciones accidentales.", TENANT_PERSONAS, TENANT_PERSONAS, ["mobile-webkit-iphone-se-375x667", "mobile-webkit-iphone-15-390x844", "mobile-webkit-iphone-15-pro-max-430x932"]),
    ("settings-users", "settings", ["/settings/users"], ["invite", "role hierarchy", "revoke"], "Owner y co-owner administran usuarios dentro de su jerarquia.", ["owner", "co_owner"], ["owner", "co_owner"], ["desktop-chromium-1440x900"]),
    ("settings-permissions", "settings", ["/settings/permissions"], ["effective matrix", "override", "denial"], "Permisos efectivos coinciden en API, navegacion y controles.", ["owner", "co_owner"], ["owner", "co_owner"]),
    ("settings-api-keys", "settings", ["/settings/api-keys"], ["issue", "masked secret", "purpose/revoke"], "Claves se muestran una vez, quedan enmascaradas y exigen proposito.", TENANT_PERSONAS, ["owner", "co_owner"]),
    ("settings-connections", "settings", ["/settings/connections"], ["masked state", "external disabled", "no network"], "Conexiones desactivadas no leen credenciales ni llaman proveedores.", TENANT_PERSONAS, ["owner", "co_owner"]),
    ("settings-whatsapp", "settings", ["/settings/whatsapp"], ["validation", "purpose", "no payment assertion"], "WhatsApp no confirma pagos sin evidencia autentica del proveedor.", TENANT_PERSONAS, ["owner", "co_owner"]),
    ("settings-hotel", "settings", ["/settings", "/settings/hotel"], ["redirect", "form", "persistence"], "Configuracion hotelera valida, guarda y persiste solo para roles autorizados.", TENANT_PERSONAS, ["owner", "co_owner"]),
    ("settings-security", "settings", ["/settings/security"], ["overview", "events", "revoke sessions"], "Seguridad muestra datos reales redactados y permite revocar sesiones propias.", TENANT_PERSONAS, ["owner", "co_owner"]),
    ("settings-subscription", "settings", ["/settings/subscription"], ["status", "disabled checkout", "denial"], "Suscripcion muestra estado real sin checkout externo.", TENANT_PERSONAS, ["owner", "co_owner"]),
    ("settings-assistant", "settings", ["/settings/assistant"], ["disabled state", "validation", "denial"], "El asistente desactivado no llama modelos y explica el estado.", TENANT_PERSONAS, ["owner", "co_owner"]),
    ("settings-tests", "settings", ["/settings/tests"], ["local-only payment link", "no polling", "denial"], "Las pruebas de integracion crean solo borradores locales no pagables.", TENANT_PERSONAS, ["owner", "co_owner"]),
    ("settings-companies", "settings", ["/settings/companies"], ["create/edit", "documents", "denial"], "Empresas y documentos son operables por owner, co-owner y manager dentro del hotel.", TENANT_PERSONAS, ["owner", "co_owner", "manager"]),
    ("public-api-key-contract", "security", ["Public booking and WhatsApp API"], ["purpose", "hotel scope", "wrong-purpose denial"], "Cada API publica exige proposito, hotel y operacion correctos.", TENANT_PERSONAS, ["owner", "co_owner"]),
    ("scale-capacity-gate", "capacity", ["isolated preview API"], ["10k steady", "20k burst", "SLO"], "Capacidad solo se mide en infraestructura aislada y nunca en dominios compartidos.", ["master-admin"], ["master-admin"], ["provider-load"]),
    ("master-admin-login", "master-admin", ["/adminpmsmaster/login"], ["login", "lockout", "logout"], "Master-admin autentica en un limite separado y auditable.", ["master-admin"], ["master-admin"]),
    ("master-admin-pages", "master-admin", ["/adminpmsmaster/dashboard", "/adminpmsmaster/billing", "/adminpmsmaster/email", "/adminpmsmaster/stripe", "/adminpmsmaster/audit"], ["navigation", "read-only external state", "audit"], "Panel master funciona sin ejecutar email, Stripe ni billing externo.", ["master-admin"], ["master-admin"]),
]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _archive_historical(source: dict) -> None:
    historical = [case for case in source.get("cases", []) if "scenario" in case]
    if not historical:
        return
    shared = [
        case
        for case in historical
        if str(case.get("preview_url", "")).startswith(
            ("https://app.hotels-pms.com", "https://hotels-pms.com", "https://api.hotels-pms.com")
        )
    ]
    non_shared = [case for case in historical if case not in shared]
    if (len(non_shared), len(shared)) != (90, 9):
        raise RuntimeError("historical split must remain exactly 90 + 9 records")
    for name, records in (
        ("non-certified-local-preview-static.json", non_shared),
        ("shared-production-20260724.json", shared),
    ):
        _write_json(
            HISTORY_ROOT / name,
            {
                "schema_version": 1,
                "archive_type": "historical-non-certified-observations",
                "source": "qa/regression-catalog.json@version-1",
                "record_count": len(records),
                "release_gate_eligible": False,
                "records": records,
            },
        )


def _build_cases() -> list[dict]:
    cases: list[dict] = []
    for spec in CASE_SPECS:
        case_id, area, routes, checks, expected, personas, allowed, *optional = spec
        devices = optional[0] if optional else DEFAULT_DEVICES
        cases.append(
            {
                "id": case_id,
                "area": area,
                "severity": "P0" if area == "security" else "P1",
                "routes": routes,
                "personas": personas,
                "persona_expectations": {
                    persona: {"access": "allowed" if persona in allowed else "denied"}
                    for persona in personas
                },
                "devices": devices,
                "preconditions": ["entorno QA aislado", "identidades sinteticas"],
                "steps": ["abrir la superficie", "ejercer acciones permitidas y denegadas", "recargar y comprobar persistencia"],
                "checks": checks,
                "expected": expected,
            }
        )
    return cases


def main() -> int:
    source = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    _archive_historical(source)
    cases = _build_cases()
    catalog = {
        "schema_version": 2,
        "catalog_type": "certified-isolated-preview-regression",
        "policy": {
            "preview_only": True,
            "required_personas": ["owner", "co_owner", "manager", "reception", "housekeeping", "master-admin"],
            "public_personas": ["anonymous"],
            "persona_runtime_roles": {"owner": "owner", "co_owner": "co_owner", "manager": "manager", "reception": "receptionist", "housekeeping": "housekeeping", "master-admin": "master-admin", "anonymous": None},
            "external_exclusions": ["payment completion", "outgoing email", "webhook delivery", "OTA operation"],
            "required_result_fields": ["case_id", "persona", "device", "status", "preview_url", "precondition", "human_action", "expected", "observed", "severity", "screenshot", "evidence", "code_sha"],
        },
        "cases": cases,
    }
    _write_json(CATALOG_PATH, catalog)

    operational_cases = []
    for case in cases:
        operational_cases.append(
            {
                "operational_case_id": f"ops-{case['id']}",
                "source_case_ids": [case["id"]],
                "area": case["area"],
                "paths": case["routes"],
                "personas": case["personas"],
                "device_profiles": ["desktop-chrome-current", "mobile-chrome-emulation-390x844"],
                "mutation_policy": "synthetic-tagged" if case["area"] not in {"marketing", "capacity"} else "read-only",
                "expected_operational_observation": case["expected"],
            }
        )
    _write_json(
        OPERATIONAL_PATH,
        {
            "schema_version": 1,
            "catalog_type": "production-labelled-shared-sandbox-operational",
            "release_gate_eligible": False,
            "origins": {"site": "https://hotels-pms.com", "app": "https://app.hotels-pms.com", "api": "https://api.hotels-pms.com"},
            "default_mutation_policy": "synthetic-tagged",
            "status_values": ["PASS", "FAIL", "BLOCKED", "NOT_APPLICABLE"],
            "cases": operational_cases,
        },
    )

    old_readme = ROOT / "qa" / "evidence" / "cloud-functional-sweep-20260724" / "README.md"
    new_readme = HISTORY_ROOT / "shared-production-20260724.md"
    if old_readme.exists() and not new_readme.exists():
        new_readme.parent.mkdir(parents=True, exist_ok=True)
        old_readme.replace(new_readme)
        old_readme.parent.rmdir()

    pairs = sum(len(case["personas"]) for case in cases)
    triplets = sum(len(case["personas"]) * len(case["devices"]) for case in cases)
    if (len(cases), pairs, triplets) != (45, 173, 335):
        raise RuntimeError(f"catalog matrix mismatch: {len(cases)}/{pairs}/{triplets}")
    print("Normalized QA catalog: 45 cases, 173 persona pairs, 335 device triplets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
