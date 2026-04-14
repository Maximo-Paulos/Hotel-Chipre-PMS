# Prueba local de Gemma

## Objetivo

Dejar el PMS conectado a un runtime local OpenAI-compatible para probar Gemma
sin depender de proveedores externos.

## Variables necesarias

En el backend, configurar:

- `GEMMA_ENABLED=true`
- `GEMMA_PROVIDER=openai_compatible`
- `GEMMA_ENDPOINT_URL=http://127.0.0.1:<puerto>/v1/chat/completions`
- `GEMMA_MODEL=<modelo-local>`

Opcionales recomendadas:

- `GEMMA_TIMEOUT_SECONDS=20`
- `GEMMA_MAX_OUTPUT_TOKENS=1024`
- `GEMMA_TEMPERATURE=0.2`
- `GEMMA_STRICT_JSON=true`
- `GEMMA_MAX_CONVERSATION_MESSAGES=6`
- `GEMMA_MAX_INPUT_CHARS=4000`

## Flujo de validacion

### Opcion rapida: runtime mock

Si todavia no vas a levantar un modelo real, podes probar toda la integracion con:

```bash
python -m app.scripts.mock_gemma_runtime --port 11434
```

Y configurar:

- `GEMMA_ENDPOINT_URL=http://127.0.0.1:11434/v1/chat/completions`
- `GEMMA_MODEL=gemma-mock-local`

Con eso, `runtime-status` ya debe pasar a `ready`.

### Opcion real: runtime local propio

1. Levantar el runtime local.
2. Levantar el backend del PMS.
3. Abrir `GET /api/gemma/chat/runtime-status`.
4. Verificar:
   - `status=ready`
   - `reachable=true`
   - `provider=openai_compatible`
5. Entrar a `http://127.0.0.1:8000/settings/assistant`.
6. Enviar una consulta simple.
7. Confirmar que en la UI:
   - aparece `Runtime: Listo`,
   - no aparece la etiqueta `Fallback`,
   - la sesion queda guardada en `Sesiones recientes`.

## Smoke test manual

Mensaje recomendado:

`Quiero reducir noches sueltas y proteger estadias largas.`

Resultado esperado:

- respuesta en modo `proposal` o `analysis`,
- `warnings` vacio o controlado,
- preview de propuesta si corresponde,
- sin errores HTTP,
- historial persistido.

## Si el runtime falla

La API del asistente queda operativa igual, pero:

- `runtime-status` va a mostrar `timeout`, `http_error`, `invalid_payload` o `unreachable`,
- la UI mostrara `Fallback`,
- Gemma respondera con el flujo deterministico seguro del PMS.

## Nota operativa

En esta fase, incluso con runtime local sano, Gemma no publica cambios
automaticamente. Solo:

- conversa,
- propone,
- crea borradores,
- marca revision,
- y aplica nuevas versiones de politica dentro del catalogo permitido.
