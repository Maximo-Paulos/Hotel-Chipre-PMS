# Gemma 4 dentro del PMS

## Objetivo

Definir el rol de Gemma 4 como capa inteligente del PMS sin reemplazar al motor
matematico de autoasignacion. Gemma 4 debe funcionar como:

- asesor experto en gestion hotelera,
- traductor de lenguaje natural a configuraciones validas del sistema,
- asistente analitico basado en datos reales del hotel,
- capa de aprendizaje del negocio para mejorar politicas y reglas.

Este documento deja la arquitectura lista para empezar el desarrollo.

## Principios obligatorios

1. Gemma 4 no asigna habitaciones por su cuenta.
2. La asignacion final sigue en el solver deterministico.
3. Gemma 4 nunca ejecuta SQL ni cambios directos fuera del catalogo permitido.
4. Toda accion debe estar tipada, validada, auditada y acotada por `hotel_id`.
5. Toda respuesta analitica debe basarse en datos reales del hotel activo.
6. Si el sistema no soporta algo, Gemma 4 debe decirlo y no inventarlo.
7. Para produccion, la inferencia corre local o en infraestructura propia, no en
   APIs externas.

## No objetivos

- No reemplazar el solver de optimizacion.
- No permitir que el modelo publique reglas sin pasar por validaciones.
- No abrir una experiencia de chat libre sin permisos ni contexto.
- No dejar que el modelo modifique datos operativos sensibles sin capa de
  aprobacion.

## Modos de operacion

### 1. Configuracion conversacional

Entrada:

- objetivos del hotel,
- problemas operativos,
- preferencias de asignacion,
- preferencias de disponibilidad, restricciones y canales.

Salida:

- propuesta estructurada de configuracion,
- explicacion simple del impacto,
- opcion de aplicar el cambio si el usuario tiene permisos.

Ejemplos:

- "Quiero dejar ciertas habitaciones para estadias largas."
- "No quiero tantas noches sueltas."
- "Quiero priorizar ciertas habitaciones para Booking."

### 2. Asistente de negocio

Entrada:

- preguntas sobre desempeno, demanda, ocupacion, restricciones, canales y
  configuraciones.

Salida:

- respuesta explicativa basada en datos reales,
- posibles causas detectadas,
- recomendacion concreta,
- accion sugerida si existe una accion valida dentro del PMS.

Ejemplos:

- "Por que estoy recibiendo menos reservas por Booking?"
- "Que dias tengo peor ocupacion?"
- "Estoy perdiendo reservas por restricciones demasiado duras?"

### 3. Ejecutor controlado

Entrada:

- intencion del usuario ya mapeada a una accion valida.

Salida:

- vista previa del cambio,
- validacion de permisos,
- ejecucion controlada,
- registro de auditoria.

Ejemplos:

- publicar una nueva politica de asignacion,
- ajustar restricciones minimas,
- activar o desactivar una regla comercial,
- cambiar prioridades operativas configurables.

### 4. Aprendizaje del negocio

Disparadores:

- cambio manual de asignacion,
- room move operativo,
- correccion de una decision del sistema,
- rechazo de una sugerencia automatica,
- override comercial o de restricciones.

Salida:

- captura estructurada del motivo,
- clasificacion de si fue excepcion o patron,
- generacion de feedback reutilizable por la capa de politicas,
- borrador de sugerencia para revisar/publicar.

## Arquitectura objetivo

## Resumen

La arquitectura correcta es:

`UI/Chat -> Gemma Orchestrator -> Context Builder -> Intent Router -> Action Catalog -> PMS Services`

El modelo nunca llama servicios internos por su cuenta. El orquestador le da
contexto acotado, recibe una respuesta estructurada y decide si corresponde
responder, proponer o ejecutar.

## Componentes

### A. Runtime local de inferencia

Responsabilidad:

- servir Gemma 4 en modo local,
- exponer endpoint OpenAI-compatible,
- no depender de internet para responder.

Estrategia inicial:

- Windows local en desarrollo,
- endpoint local HTTP,
- PMS configurado con `GEMMA_PROVIDER=openai_compatible`.

Configuracion objetivo:

- `GEMMA_ENABLED=true`
- `GEMMA_PROVIDER=openai_compatible`
- `GEMMA_ENDPOINT_URL=http://127.0.0.1:<puerto>/v1/chat/completions`
- `GEMMA_MODEL=<modelo-local>`

Nota:

La integracion actual del repo ya soporta este modo de conexion.

### B. Gemma Orchestrator

Nuevo modulo propuesto:

- `app/services/gemma_orchestrator.py`

Responsabilidad:

- clasificar la intencion del usuario,
- decidir modo: consulta / propuesta / ejecucion / aprendizaje,
- reunir contexto del hotel,
- invocar al runtime local,
- validar la salida estructurada,
- disparar acciones internas permitidas,
- dejar auditoria.

El orquestador debe ser el unico punto que conversa con el modelo para la
experiencia "copilot" del producto.

### C. Intent Router

Nuevo modulo propuesto:

- `app/services/gemma_intent_service.py`

Responsabilidad:

- mapear cada mensaje a una `intent_type`,
- identificar si requiere datos, propuesta o ejecucion,
- detectar ambiguedad,
- detectar si falta contexto.

Intenciones iniciales:

- `configure_allocation_policy`
- `configure_commercial_rule`
- `configure_channel_rule`
- `analyze_performance`
- `analyze_channel_drop`
- `explain_solver_behavior`
- `capture_override_reason`
- `recommend_change`
- `apply_approved_change`
- `unsupported_request`

### D. Context Builder

Nuevo modulo propuesto:

- `app/services/gemma_context_service.py`

Responsabilidad:

- reunir solo el contexto necesario para cada intencion,
- acotar por hotel, rango temporal y permisos,
- resumir datos para no saturar contexto,
- redactar PII antes de enviar al modelo.

Fuentes iniciales de contexto:

- configuracion activa de politicas de asignacion,
- restricciones y reglas comerciales,
- reservas y ocupacion agregadas,
- metrics por canal,
- acciones pendientes,
- historial reciente de overrides y room moves,
- feedback events ya guardados.

### E. Catalogo de acciones permitidas

Nuevo modulo propuesto:

- `app/services/gemma_action_catalog.py`

Responsabilidad:

- definir el listado exacto de acciones que Gemma puede pedir,
- validar payloads,
- rechazar cambios fuera del catalogo.

Formato esperado de salida del modelo:

```json
{
  "mode": "proposal",
  "intent_type": "configure_allocation_policy",
  "summary": "Reducir noches sueltas y proteger estadias largas",
  "requires_confirmation": true,
  "actions": [
    {
      "action_type": "allocation_policy.update_weights",
      "payload": {
        "prefer_exact_match": 850,
        "room_usage_penalty": 70,
        "fallback_priority_penalty": 40
      }
    }
  ],
  "explanation": "..."
}
```

Acciones v1 recomendadas:

- `allocation_policy.create_draft_from_natural_language`
- `allocation_policy.publish_existing_suggestion`
- `allocation_policy.update_weights`
- `allocation_policy.update_constraints`
- `commercial.rate_plan.adjust_restrictions`
- `commercial.tax_policy.toggle_rule`
- `channel.rule.update`
- `reservation.override_feedback.record`
- `report.generate_snapshot`

Acciones explicitamente prohibidas en v1:

- borrar reservas,
- mover reservas existentes sin aprobacion,
- cobrar pagos,
- cancelar reservas,
- tocar inventario fisico,
- ejecutar SQL libre,
- cambiar permisos de usuarios.

## Experiencia de producto

## Superficies UI

### 1. Onboarding del hotel

Gemma hace preguntas guiadas y construye:

- objetivos comerciales,
- tolerancia a huecos,
- preferencias de asignacion,
- reglas operativas iniciales,
- politicas a revisar antes de publicar.

### 2. Centro de configuracion inteligente

Pantalla dedicada donde el dueno conversa con Gemma para:

- cambiar comportamiento del sistema,
- pedir recomendaciones,
- revisar propuestas antes de aplicar.

### 3. Asistente analitico

Panel de preguntas sobre negocio, por ejemplo:

- ocupacion por dia,
- reservas por canal,
- restricciones que limitan demanda,
- cambios recientes con impacto negativo.

### 4. Captura de aprendizaje operativo

Cuando un usuario corrige algo importante, el sistema abre un prompt corto:

- que se cambio,
- por que se cambio,
- si es excepcion o regla recurrente.

Ese input alimenta a `LLMFeedbackEvent`, `ManualOverrideReason` y futuras
sugerencias de politica.

## API y backend propuestos

## Endpoints nuevos recomendados

### Conversacion

- `POST /api/gemma/chat/message`
- `GET /api/gemma/chat/session/{session_id}`
- `GET /api/gemma/chat/history`

### Ejecucion controlada

- `POST /api/gemma/actions/preview`
- `POST /api/gemma/actions/execute`
- `POST /api/gemma/actions/{action_id}/approve`
- `POST /api/gemma/actions/{action_id}/reject`

### Analitica

- `POST /api/gemma/analysis/query`

### Aprendizaje

- `POST /api/gemma/feedback/override-reason`
- `POST /api/gemma/feedback/manual-correction`

## Servicios backend a reutilizar

El repo ya tiene piezas utiles y deben ser reutilizadas:

- `app/services/gemma_service.py`
- `app/services/allocation_learning_service.py`
- `app/services/allocation_policy_service.py`
- `app/services/reservation_action_service.py`
- `app/services/commercial_service.py`
- `app/services/pricing_policy_service.py`

La idea correcta no es reemplazar estas piezas, sino orquestarlas.

## Modelo de datos propuesto

Tablas nuevas recomendadas:

### `ai_assistant_session`

- `id`
- `hotel_id`
- `user_id`
- `mode`
- `status`
- `title`
- `created_at`
- `updated_at`

### `ai_assistant_message`

- `id`
- `session_id`
- `hotel_id`
- `role` (`user`, `assistant`, `system`)
- `raw_text`
- `redacted_text`
- `intent_type`
- `created_at`

### `ai_assistant_action_run`

- `id`
- `session_id`
- `hotel_id`
- `requested_by_user_id`
- `action_type`
- `status` (`draft`, `pending_confirmation`, `approved`, `executed`, `failed`, `rejected`)
- `payload_json`
- `preview_json`
- `result_json`
- `error_message`
- `created_at`
- `executed_at`

### `ai_assistant_insight`

- `id`
- `hotel_id`
- `session_id`
- `insight_type`
- `summary`
- `details_json`
- `created_at`

No hace falta crear una tabla separada para aprendizaje de asignacion si se sigue
reutilizando:

- `LLMFeedbackEvent`
- `ManualOverrideReason`
- `LLMPolicySuggestion`

## Contrato de salida del modelo

El modelo no debe responder texto libre sin estructura. La salida debe ajustarse
a un schema estricto.

Campos base:

- `mode`
- `intent_type`
- `summary`
- `answer`
- `requires_confirmation`
- `confidence`
- `missing_information`
- `actions`
- `analysis`
- `warnings`

Si el modelo no puede completar la tarea, debe devolver:

- `mode=clarify`
- `missing_information=[...]`

Si el pedido esta fuera de alcance:

- `mode=unsupported`
- `warnings=[...]`

## Guardrails

Obligatorios desde v1:

- `hotel_id` obligatorio en toda resolucion.
- permisos por rol antes de ejecutar.
- acciones siempre validadas contra schema tipado.
- redaccion de PII antes de salir al modelo.
- auditoria de propuestas y ejecuciones.
- idempotencia para acciones ejecutables.
- timeouts y limites de contexto.
- fallback deterministico cuando Gemma no responda.

## Integracion local inicial

## Desarrollo en la PC actual

Objetivo:

- correr PMS localmente,
- correr Gemma localmente,
- no depender de API externa.

Diseno recomendado:

1. levantar runtime local compatible con OpenAI API en Windows,
2. apuntar `GEMMA_ENDPOINT_URL` a `127.0.0.1`,
3. mantener el backend del PMS desacoplado del runtime,
4. no embutir el modelo dentro del proceso FastAPI.

Ventaja:

- despues el mismo backend puede apuntar a un servidor local en tu rig Linux o a
  otro host privado sin reescribir la integracion.

## Fases de implementacion

### Fase 1. Runtime local y chat seguro

- agregar `gemma_orchestrator`,
- crear endpoint de conversacion,
- conectar al runtime local,
- clasificar intenciones simples,
- responder en modo consulta,
- dejar auditoria de sesiones y mensajes.

Aceptacion:

- el dueno puede consultar y recibir respuestas basadas en datos reales,
- no hay ejecucion de cambios todavia.

### Fase 2. Configuracion conversacional controlada

- mapear pedidos a propuestas estructuradas,
- permitir preview de cambios,
- ejecutar solo acciones permitidas con confirmacion.

Aceptacion:

- el dueno puede pedir cambios de configuracion en lenguaje natural y el sistema
  genera propuestas aplicables.

### Fase 3. Analitica explicativa

- agregar preguntas sobre rendimiento, ocupacion y canales,
- sumar deteccion de causas probables,
- guardar insights consultables.

Aceptacion:

- el sistema responde preguntas del negocio con datos reales del hotel.

### Fase 4. Aprendizaje operativo

- capturar motivos de room moves y overrides,
- estructurar feedback,
- generar sugerencias de politica reutilizando el flujo ya existente.

Aceptacion:

- cada correccion manual importante puede convertirse en feedback util para
  mejorar politicas.

### Fase 5. Endurecimiento productivo

- cuotas,
- rate limit,
- timeout,
- metricas,
- observabilidad,
- pruebas de regresion,
- despliegue hacia runtime en infraestructura privada.

## Criterios de aceptacion funcionales

- El dueno puede escribir pedidos no tecnicos y el sistema los entiende.
- Gemma responde solo dentro de capacidades reales del PMS.
- Las propuestas de cambio se pueden explicar antes de aplicar.
- Toda ejecucion deja auditoria.
- Toda respuesta analitica usa datos del hotel activo.
- Toda correccion manual relevante se puede registrar como aprendizaje.
- El solver sigue siendo quien asigna habitaciones.

## Decisiones tomadas

- Gemma 4 corre en infraestructura propia.
- En desarrollo inicial corre localmente en la PC.
- La integracion del PMS con el runtime se hace por HTTP local compatible con
  OpenAI API.
- Gemma 4 no reemplaza el motor de asignacion.
- El catalogo de acciones permitidas define el limite exacto de su poder.

## Proximo paso recomendado

Empezar por Fase 1 con este alcance minimo:

- `gemma_orchestrator.py`
- `gemma_context_service.py`
- `gemma_intent_service.py`
- endpoints `/api/gemma/chat/*`
- tablas `ai_assistant_session` y `ai_assistant_message`
- UI minima de chat para dueno
- conexion al runtime local por `openai_compatible`

Con eso se obtiene una base segura y reutilizable para despues sumar ejecucion
controlada, analitica y aprendizaje sin rehacer la arquitectura.

## Referencias operativas

- `docs/gemma4/local-runtime-testing.md`: checklist para levantar y probar el
  runtime local OpenAI-compatible.
