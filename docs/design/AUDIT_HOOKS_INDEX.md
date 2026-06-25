# Audit Hooks - Índice y Navegación

## Mapa de Contenido

```
AUDIT_HOOKS_*
├── INDEX (este archivo)
├── SUMMARY - Resumen ejecutivo de todo el sistema
├── QUICK_REFERENCE - 2 páginas de referencia rápida
├── INTEGRATION_GUIDE - Guía completa con ejemplos en 5 servicios
└── IMPLEMENTATION_TEMPLATES - 12 funciones copy-paste ready

app/decorators/
└── audit_hooks.py - Implementación core (decorator + API)

app/tests/
└── test_audit_hooks.py - Suite de 14 tests
```

---

## Guía de Lectura por Rol

### Para Product Managers / Arquitectos
1. Leer: **AUDIT_HOOKS_SUMMARY.md** (5 min)
   - Qué es, para qué sirve, ventajas
2. Leer: **AUDIT_HOOKS_INTEGRATION_GUIDE.md** (sección Overview)
   - Entender que cubre 5 servicios críticos

### Para Desarrolladores (Nuevo en auditoría)
1. Leer: **AUDIT_HOOKS_QUICK_REFERENCE.md** (10 min)
   - TL;DR + API rápida
2. Ver: **AUDIT_HOOKS_IMPLEMENTATION_TEMPLATES.py**
   - Entender patrón de integración
3. Copiar un template y adaptarlo a su caso
4. Ejecutar tests para verificar

### Para Desarrolladores (Integrando en Servicio X)
1. Abrir: **AUDIT_HOOKS_INTEGRATION_GUIDE.md**
2. Buscar: Sección correspondiente a su servicio (1-5)
3. Copiar código del template
4. Ejecutar tests: `pytest app/tests/test_audit_hooks.py -v`
5. Verificar en BD

### Para Code Reviewers
1. Leer: **AUDIT_HOOKS_QUICK_REFERENCE.md** (Patrones Comunes)
2. Usar como checklist:
   - ¿before/after capturado correctamente?
   - ¿entity_type y entity_id coinciden?
   - ¿change_summary es descriptivo?
   - ¿source_code es apropiado?

### Para QA / Testers
1. Ejecutar: **app/tests/test_audit_hooks.py**
2. Leer: Casos de test en test_audit_hooks.py
3. Crear BD queries según **AUDIT_HOOKS_SUMMARY.md** (sección Métricas)
4. Verificar registros de auditoría en hotel_audit_event / audit_log_entry

---

## Índice de Referencia Rápida

### API Core
```python
# Lectura recomendada: AUDIT_HOOKS_QUICK_REFERENCE.md -> API Rápida

AuditContext(db, user_id, hotel_id)
├── record(entity_type, action, entity_id, before, after, ...)
└── Maneja errores automáticamente

_entity_to_dict(entity)
└── Convierte ORM entity a diccionario

audited_change(entity_type, action, ...)
└── Decorator para métodos (opcional)
```

### Enums
```python
# Lectura recomendada: AUDIT_HOOKS_QUICK_REFERENCE.md -> Entity Types

ActionCodeEnum
├── CREATE, UPDATE, DELETE, CANCEL
├── APPROVE, REJECT
├── REVERT, RESTORE
└── MERGE, SPLIT

EntityTypeEnum
├── RESERVATION, GUEST, ROOM
├── RATE_PLAN, SELLABLE_PRODUCT
├── OTA_CONNECTION
├── HOTEL_CONFIGURATION, USER
└── ... (ver audit.py para lista completa)

SourceCodeEnum
├── API, MANUAL, SYSTEM
├── OTA_SYNC, ADMIN_BULK
├── IMPORT, WEBHOOK
└── Default: API
```

### Patrones de Integración
```
# Lectura recomendada: AUDIT_HOOKS_INTEGRATION_GUIDE.md

Patrón       Servicios                    Action
═════════════════════════════════════════════════════════════
CREATE       Guest, Reservation, Payment   CREATE
UPDATE       Reservation, Guest, Hotel     UPDATE
CANCEL       Reservation                   CANCEL
CHECK_IN     Reservation + Room            UPDATE (multi)
CHECK_OUT    Reservation + Room            UPDATE (multi)
REFUND       Reservation + Transaction     UPDATE + CREATE
```

---

## Búsqueda por Pregunta

### ¿Dónde pongo la auditoría en X servicio?

**Si X = Reservation:**
→ AUDIT_HOOKS_INTEGRATION_GUIDE.md, Sección 1

**Si X = Payment:**
→ AUDIT_HOOKS_INTEGRATION_GUIDE.md, Sección 2

**Si X = CheckIn:**
→ AUDIT_HOOKS_INTEGRATION_GUIDE.md, Sección 3

**Si X = Guest:**
→ AUDIT_HOOKS_INTEGRATION_GUIDE.md, Sección 4

**Si X = Hotel:**
→ AUDIT_HOOKS_INTEGRATION_GUIDE.md, Sección 5

---

### ¿Cuál es el código exacto para [acción]?

**Si [acción] = crear entidad:**
→ AUDIT_HOOKS_QUICK_REFERENCE.md, Patrones Comunes -> CREATE

**Si [acción] = modificar entidad:**
→ AUDIT_HOOKS_QUICK_REFERENCE.md, Patrones Comunes -> UPDATE

**Si [acción] = cancelar (reserva, etc):**
→ AUDIT_HOOKS_QUICK_REFERENCE.md, Patrones Comunes -> CANCEL

**Si [acción] = multi-entidad (checkin, etc):**
→ AUDIT_HOOKS_QUICK_REFERENCE.md, Patrones Comunes -> MULTI-ENTITY

---

### ¿Cómo configuro X parámetro?

**Si X = entity_type:**
→ AUDIT_HOOKS_QUICK_REFERENCE.md, Entity Types

**Si X = action:**
→ AUDIT_HOOKS_QUICK_REFERENCE.md, Action Codes

**Si X = source_code:**
→ AUDIT_HOOKS_QUICK_REFERENCE.md, Source Codes

**Si X = change_summary:**
→ AUDIT_HOOKS_SUMMARY.md, Mejores Prácticas

---

### ¿Qué hace el código [fragmento]?

**Si [fragmento] contiene @audited_change:**
→ app/decorators/audit_hooks.py, línea ~45

**Si [fragmento] contiene AuditContext:**
→ app/decorators/audit_hooks.py, línea ~133

**Si [fragmento] contiene _entity_to_dict:**
→ app/decorators/audit_hooks.py, línea ~20

---

## Checklist de Integración

```
[ ] 1. Copiar app/decorators/audit_hooks.py
[ ] 2. Copiar app/tests/test_audit_hooks.py
[ ] 3. Agregar imports en cada servicio
[ ] 4. Integrar en reservation_service (CREATE, UPDATE, CANCEL)
[ ] 5. Integrar en payment_service (DEPOSIT, FULL, REFUND)
[ ] 6. Integrar en checkin_service (CHECKIN, CHECKOUT)
[ ] 7. Integrar en guest_service (CREATE, UPDATE)
[ ] 8. Integrar en hotel_service (CONFIG, MEMBERSHIP)
[ ] 9. Ejecutar tests: pytest app/tests/test_audit_hooks.py -v
[ ] 10. Verificar BD: SELECT * FROM hotel_audit_event
```

---

## Ubicación de Archivos en el Proyecto

### Archivos Nuevos (Crear)
```
C:\PROJECTO\Hotel-Chipre-PMS\.claude\worktrees\cranky-robinson-89dfad\
├── app/decorators/audit_hooks.py              [NUEVO]
├── app/tests/test_audit_hooks.py              [NUEVO]
├── AUDIT_HOOKS_SUMMARY.md                     [NUEVO]
├── AUDIT_HOOKS_QUICK_REFERENCE.md             [NUEVO]
├── AUDIT_HOOKS_INTEGRATION_GUIDE.md           [NUEVO]
├── AUDIT_HOOKS_IMPLEMENTATION_TEMPLATES.py    [NUEVO]
└── AUDIT_HOOKS_INDEX.md                       [NUEVO - Este archivo]
```

### Archivos Existentes (Que asumimos existen)
```
app/models/audit.py                            [Existente]
app/services/audit_service.py                  [Existente]

Servicios a modificar:
├── app/services/reservation_service.py        [Modificar]
├── app/services/payment_service.py            [Modificar]
├── app/services/checkin_service.py            [Modificar]
├── app/services/guest_service.py              [Crear o Modificar]
└── app/services/hotel_service.py              [Modificar]
```

---

## Flujo de Lectura Recomendado

```
Paso 1 (5 min)
└─ AUDIT_HOOKS_QUICK_REFERENCE.md
   ├─ TL;DR (copy-paste snippet)
   └─ Entender patrón básico

Paso 2 (10 min)
└─ Elegir un servicio y leer su sección
   en AUDIT_HOOKS_INTEGRATION_GUIDE.md
   └─ Entender contexto específico

Paso 3 (15 min)
└─ Copiar template de
   AUDIT_HOOKS_IMPLEMENTATION_TEMPLATES.py
   └─ Adaptar a caso real

Paso 4 (5 min)
└─ Ejecutar tests
   └─ pytest app/tests/test_audit_hooks.py -v

Paso 5 (5 min)
└─ Verificar en BD
   └─ SELECT * FROM hotel_audit_event
```

Total: ~40 minutos para integración completa en 1 servicio

---

## Links Internos

### Por Tipo de Contenido
- **Implementación:** app/decorators/audit_hooks.py
- **Tests:** app/tests/test_audit_hooks.py
- **Documentación:**
  - AUDIT_HOOKS_SUMMARY.md (Ejecutivo)
  - AUDIT_HOOKS_QUICK_REFERENCE.md (Rápida)
  - AUDIT_HOOKS_INTEGRATION_GUIDE.md (Completa)
  - AUDIT_HOOKS_IMPLEMENTATION_TEMPLATES.py (Code)

### Por Servicio
- **Reservation:** AUDIT_HOOKS_INTEGRATION_GUIDE.md Sección 1 + Template 1A-1C
- **Payment:** AUDIT_HOOKS_INTEGRATION_GUIDE.md Sección 2 + Template 2A-2C
- **CheckIn:** AUDIT_HOOKS_INTEGRATION_GUIDE.md Sección 3 + Template 3A-3B
- **Guest:** AUDIT_HOOKS_INTEGRATION_GUIDE.md Sección 4 + Template 4A-4B
- **Hotel:** AUDIT_HOOKS_INTEGRATION_GUIDE.md Sección 5 + Template 5A-5B

---

## Glossario

| Término | Definición | Ver |
|---------|-----------|-----|
| **Entity Type** | Qué se está auditando (RESERVATION, GUEST, etc.) | QUICK_REFERENCE |
| **Action Code** | Qué se hizo (CREATE, UPDATE, DELETE, CANCEL) | QUICK_REFERENCE |
| **Source Code** | De dónde vino (API, MANUAL, SYSTEM, OTA_SYNC) | QUICK_REFERENCE |
| **before/after** | Estados antes y después del cambio | QUICK_REFERENCE |
| **AuditContext** | API manual para registrar cambios | audit_hooks.py |
| **_entity_to_dict** | Convierte ORM entity a diccionario | audit_hooks.py |
| **@audited_change** | Decorator automático (opcional) | audit_hooks.py |
| **hotel_audit_event** | Tabla principal (1 registro por cambio) | audit.py |
| **audit_log_entry** | Tabla de detalles (N registros por campo) | audit.py |

---

## FAQ Rápido

**P: ¿Cuál es la diferencia entre AuditContext y @audited_change?**
R: AuditContext es manual (más control), @audited_change es automático (menos código). Usa AuditContext para empezar.

**P: ¿Qué pasa si la auditoría falla?**
R: AuditContext maneja errores automáticamente. Falla no afecta operación principal.

**P: ¿Debo auditar TODOS los métodos?**
R: No, solo métodos de escritura críticos (create, update, delete, cancel).

**P: ¿Es lento?**
R: Mínimo impacto (<1ms por registro). AuditService usa db.flush() (no commit).

**P: ¿Dónde veo los logs?**
R: Base de datos: `SELECT * FROM hotel_audit_event ORDER BY created_at DESC`

**P: ¿Hay un dashboard?**
R: No incluido. Puedes crear uno queryando hotel_audit_event y audit_log_entry.

---

## Support

Cada archivo incluye detalles completos:
- **Código:** Ver docstrings en audit_hooks.py
- **Tests:** Ver ejemplos en test_audit_hooks.py
- **Documentación:** Ver comentarios en cada guía
- **Troubleshooting:** AUDIT_HOOKS_SUMMARY.md, sección Troubleshooting

---

**Última actualización:** 2026-06-10
**Versión:** 1.0
**Status:** Listo para integración
