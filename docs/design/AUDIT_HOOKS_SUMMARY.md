# Hooks de Auditoría - Resumen Completo

## Descripción General

Sistema completo de auditoría automática para Hotel Chipre PMS que:
1. **Captura cambios automáticamente** antes/después en todas las entidades
2. **Integra en 5 servicios críticos** (Reservations, Payments, CheckIn, Guest, Hotel)
3. **Proporciona decorator & API manual** para registrar cambios
4. **Maneja errores gracefully** (falla de auditoría no afecta operación principal)
5. **Incluye tests completos** y templates copy-paste ready

---

## Archivos Generados

### 1. Core Implementation

#### `app/decorators/audit_hooks.py`
**Decorator y utilidades para auditoría automática**
- `@audited_change(entity_type, action, ...)` - Decorator para métodos
- `AuditContext(db, user_id, hotel_id)` - API manual para registro
- `_entity_to_dict(entity)` - Convierte ORM entity a diccionario
- `make_audit_extractor(obj_index)` - Factory para extractores

**Características:**
- Captura automática de before/after
- Manejo graceful de errores (try/except)
- Soporte para callbacks personalizados
- Context thread-safe

**Ubicación:** `C:\PROJECTO\Hotel-Chipre-PMS\.claude\worktrees\cranky-robinson-89dfad\app\decorators\audit_hooks.py`

---

### 2. Documentación

#### `AUDIT_HOOKS_INTEGRATION_GUIDE.md`
**Guía completa de integración en los 5 servicios**

Contiene:
- Explicación de cada servicio (Reservation, Payment, CheckIn, Guest, Hotel)
- Código copy-paste listo para cada acción (CREATE, UPDATE, DELETE, CANCEL)
- Ejemplos específicos para cada método crítico
- Enums disponibles y mejores prácticas
- Guía de testing

**Secciones:**
1. RESERVATION_SERVICE - 3 templates (CREATE, UPDATE, CANCEL)
2. PAYMENT_SERVICE - 3 templates (DEPOSIT, FULL_PAYMENT, REFUND)
3. CHECKIN_SERVICE - 2 templates (CHECK_IN, CHECK_OUT)
4. GUEST_SERVICE - 2 templates (CREATE, UPDATE)
5. HOTEL_SERVICE - 2 templates (CONFIG, MEMBERSHIP)

**Ubicación:** `C:\PROJECTO\Hotel-Chipre-PMS\.claude\worktrees\cranky-robinson-89dfad\AUDIT_HOOKS_INTEGRATION_GUIDE.md`

---

#### `AUDIT_HOOKS_QUICK_REFERENCE.md`
**Referencia rápida (1-2 páginas)**

Perfect para developers en prisa:
- TL;DR snippet de 20 líneas
- API rápida
- Entity types y action codes
- Source codes
- Patrones comunes (CREATE, UPDATE, DELETE, CANCEL, MULTI-ENTITY)
- Errores frecuentes
- Verificación en tests
- Ubicación de código

**Ubicación:** `C:\PROJECTO\Hotel-Chipre-PMS\.claude\worktrees\cranky-robinson-89dfad\AUDIT_HOOKS_QUICK_REFERENCE.md`

---

#### `AUDIT_HOOKS_IMPLEMENTATION_TEMPLATES.py`
**Código Python 100% copy-paste ready**

Contiene:
- 12 funciones template para cada método
- Incluye marks de inicio/fin (===== AUDIT CODE =====)
- Imports necesarios para cada servicio
- Checklist de integración final

**Templates incluidos:**
1. `create_reservation_with_audit()`
2. `update_reservation_with_audit()`
3. `cancel_reservation_with_audit()`
4. `process_deposit_payment_with_audit()`
5. `process_full_payment_with_audit()`
6. `process_refund_with_audit()`
7. `perform_checkin_with_audit()`
8. `perform_checkout_with_audit()`
9. `create_guest_with_audit()`
10. `update_guest_with_audit()`
11. `update_hotel_config_with_audit()`
12. `add_user_to_hotel_with_audit()`

**Ubicación:** `C:\PROJECTO\Hotel-Chipre-PMS\.claude\worktrees\cranky-robinson-89dfad\AUDIT_HOOKS_IMPLEMENTATION_TEMPLATES.py`

---

### 3. Tests

#### `app/tests/test_audit_hooks.py`
**Suite completa de tests**

Cubre:
- **Entity snapshot:** `test_entity_to_dict_*` (3 tests)
- **Audit context direct API:** `test_audit_context_record_*` (4 tests)
- **Field-level changes:** `test_audit_field_level_changes()`
- **Source code tracking:** `test_audit_source_code_*` (3 tests)
- **Multi-entity scenarios:** `test_audit_multiple_entities_in_transaction()`
- **Edge cases:** `test_audit_with_none_values()`, `test_audit_with_empty_before_and_after()`

Total: **14 tests** que verifican:
- Creación de registros de auditoría
- Captura correcta de before/after
- Enums y códigos fuente
- Cambios a nivel de campo
- Manejo de valores None
- Operaciones multi-entidad

**Ubicación:** `C:\PROJECTO\Hotel-Chipre-PMS\.claude\worktrees\cranky-robinson-89dfad\app\tests\test_audit_hooks.py`

---

## Cómo Usar

### Opción 1: API Manual (Recomendado para Iniciar)

```python
from app.decorators.audit_hooks import AuditContext, _entity_to_dict
from app.models.audit import ActionCodeEnum, EntityTypeEnum, SourceCodeEnum

def my_service_method(db, entity, user_id):
    # Capture before
    before = _entity_to_dict(entity)
    
    # Make changes
    entity.field = new_value
    db.flush()
    
    # Capture after
    after = _entity_to_dict(entity)
    
    # Record audit
    audit = AuditContext(db, user_id, entity.hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.UPDATE,
        entity_id=entity.id,
        before=before,
        after=after,
        change_summary="Description",
        source_code=SourceCodeEnum.API,
    )
    
    return entity
```

**Ventajas:**
- Simple de implementar
- Control total
- Fácil debuggear
- No requiere decorators

---

### Opción 2: Decorator (Para Métodos Genéricos)

```python
from app.decorators.audit_hooks import audited_change

@audited_change(
    EntityTypeEnum.GUEST,
    ActionCodeEnum.CREATE,
    extract_entity_id=lambda ctx: ctx[2]["result"].id,
    extract_hotel_id=lambda ctx: ctx[1],  # args[1]
    extract_user_id=lambda ctx: get_current_user_id(),
)
def create_guest(self, hotel_id, data):
    guest = Guest(hotel_id=hotel_id, **data)
    self.db.add(guest)
    self.db.flush()
    return guest
```

**Ventajas:**
- Menos código boilerplate
- Automático
- Limpio visualmente

**Desventajas:**
- Más complejo de entender
- Harder to debug

---

## Pasos de Integración

### 1. Copiar archivos base
```bash
# Decorator y utilidades
cp app/decorators/audit_hooks.py proyecto/

# Tests
cp app/tests/test_audit_hooks.py proyecto/
```

### 2. Agregar imports a cada servicio

```python
# reservation_service.py
from app.decorators.audit_hooks import AuditContext, _entity_to_dict
from app.models.audit import ActionCodeEnum, EntityTypeEnum, SourceCodeEnum

# payment_service.py
from app.decorators.audit_hooks import AuditContext, _entity_to_dict
from app.models.audit import ActionCodeEnum, EntityTypeEnum, SourceCodeEnum

# ... etc para cada servicio
```

### 3. Integrar en métodos críticos

**Reservations:**
```python
# Usar templates de AUDIT_HOOKS_IMPLEMENTATION_TEMPLATES.py
create_reservation() → add audit.record(CREATE)
update_reservation() → add audit.record(UPDATE)
cancel_reservation() → add audit.record(CANCEL)
```

**Payments:**
```python
process_deposit_payment() → audit.record(CREATE transaction) + audit.record(UPDATE reservation)
process_full_payment() → audit.record(CREATE transaction) + audit.record(UPDATE reservation)
process_refund() → audit.record(CREATE transaction) + audit.record(UPDATE reservation)
```

**CheckIn:**
```python
perform_checkin() → audit.record(UPDATE reservation) + audit.record(UPDATE room)
perform_checkout() → audit.record(UPDATE reservation) + audit.record(UPDATE room)
```

**Guest:**
```python
create_guest() → audit.record(CREATE)
update_guest() → audit.record(UPDATE)
```

**Hotel:**
```python
update_hotel_config() → audit.record(UPDATE)
add_user_to_hotel() → audit.record(CREATE membership)
```

### 4. Verificar en tests

```bash
pytest app/tests/test_audit_hooks.py -v
```

### 5. Verificar en base de datos

```sql
-- Verificar registros de auditoría
SELECT * FROM hotel_audit_event 
WHERE hotel_id = 1 
ORDER BY created_at DESC 
LIMIT 10;

-- Verificar cambios a nivel de campo
SELECT * FROM audit_log_entry 
WHERE hotel_audit_event_id = <event_id> 
LIMIT 20;
```

---

## Referencia Rápida de Enums

### ActionCodeEnum
```
CREATE   = Nueva entidad
UPDATE   = Modificación
DELETE   = Eliminación
CANCEL   = Cancelación (reservas)
APPROVE  = Aprobación workflow
REJECT   = Rechazo
REVERT   = Deshacer
RESTORE  = Restaurar
MERGE    = Fusionar
SPLIT    = Dividir
```

### EntityTypeEnum (Principales)
```
RESERVATION          # Bookings
GUEST                # Huéspedes
ROOM                 # Habitaciones
HOTEL_CONFIGURATION  # Configuración
PAYMENT_TRANSACTION  # Transacciones (si custom)
HOTEL_MEMBERSHIP     # Membresías
```

### SourceCodeEnum
```
API           # HTTP call
MANUAL        # UI action
SYSTEM        # Auto-triggered
OTA_SYNC      # OTA sync
ADMIN_BULK    # Batch operation
IMPORT        # Data import
WEBHOOK       # Inbound webhook
```

---

## Mejores Prácticas

1. **Siempre capturar BEFORE antes de cambios**
   ```python
   before = _entity_to_dict(entity)  # ANTES
   entity.field = value
   db.flush()
   after = _entity_to_dict(entity)   # DESPUÉS
   ```

2. **Usar change_summary descriptivo**
   ```python
   # Bueno
   f"Reservation {res.id} cancelled by {user_name}: {reason}"
   
   # Malo
   "Updated"
   ```

3. **Establecer source_code correctamente**
   ```python
   SourceCodeEnum.API      # Para endpoints HTTP
   SourceCodeEnum.MANUAL   # Para UI actions
   SourceCodeEnum.SYSTEM   # Para background jobs
   SourceCodeEnum.OTA_SYNC # Para sincronización automática
   ```

4. **No dejar que auditoría rompa operación principal**
   - AuditContext ya maneja esto (try/except)
   - Logs error pero continúa

5. **Entity ID siempre coincide con Entity Type**
   ```python
   # Correcto
   entity_type=EntityTypeEnum.RESERVATION,
   entity_id=reservation.id,
   
   # Incorrecto
   entity_type=EntityTypeEnum.RESERVATION,
   entity_id=guest.id,  # NO! guest_id, no reservation_id
   ```

---

## Archivos Relacionados Existentes

Asume que existen en el proyecto:
- `app/models/audit.py` - Modelos de auditoría (HotelAuditEvent, AuditLogEntry, etc.)
- `app/services/audit_service.py` - AuditService (record_change, etc.)
- Base de datos con tablas de auditoría (hotel_audit_event, audit_log_entry)

---

## Troubleshooting

### Problema: Audit logs no se crean
**Causa:** Probablemente db.commit() no se ejecuta
**Solución:** Verificar que se llame db.commit() después de audit.record()

### Problema: before/after son None
**Causa:** _entity_to_dict() no capturó el estado
**Solución:** Verificar que entity tenga atributo __table__ (ORM entity)

### Problema: User ID no encontrado
**Causa:** user_id no disponible en contexto
**Solución:** Pasar user_id explícitamente o extraerlo del request/token

### Problema: Auditoría lenta la aplicación
**Causa:** Demasiadas entidades siendo auditadas
**Solución:** Ser selectivo (solo métodos de escritura críticos)

---

## Métricas de Auditoría

Para monitorear auditoría:

```sql
-- Auditorías por usuario
SELECT user_id, COUNT(*) as count 
FROM hotel_audit_event 
GROUP BY user_id;

-- Cambios por tipo de entidad
SELECT entity_type, action_code, COUNT(*) 
FROM hotel_audit_event 
GROUP BY entity_type, action_code;

-- Fuentes de cambio
SELECT source_code, COUNT(*) 
FROM hotel_audit_event 
GROUP BY source_code;

-- Timeline de un objeto
SELECT * FROM hotel_audit_event 
WHERE entity_type = 'reservation' AND entity_id = 123 
ORDER BY created_at DESC;
```

---

## Resumen de Archivos

| Archivo | Propósito | Ubicación |
|---------|-----------|-----------|
| audit_hooks.py | Core implementation | app/decorators/ |
| test_audit_hooks.py | Test suite (14 tests) | app/tests/ |
| AUDIT_HOOKS_INTEGRATION_GUIDE.md | Guía completa (5 servicios) | Raíz |
| AUDIT_HOOKS_QUICK_REFERENCE.md | Referencia rápida | Raíz |
| AUDIT_HOOKS_IMPLEMENTATION_TEMPLATES.py | 12 templates copy-paste | Raíz |
| AUDIT_HOOKS_SUMMARY.md | Este archivo | Raíz |

---

## Contacto y Preguntas

Para dudas específicas:
1. Revisar AUDIT_HOOKS_QUICK_REFERENCE.md
2. Ver ejemplos en AUDIT_HOOKS_INTEGRATION_GUIDE.md
3. Ejecutar tests: `pytest app/tests/test_audit_hooks.py -v`
4. Revisar modelos existentes: `app/models/audit.py`

---

**Última actualización:** 2026-06-10
**Versión:** 1.0
**Estado:** Listo para integración
