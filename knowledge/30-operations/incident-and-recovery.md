# Incidente y recuperación

1. Clasificar severidad: seguridad/PII, pagos, reserva/habitaciones, disponibilidad o UX.
2. Preservar evidencia redactada: timestamp, entorno, `code_sha`, persona, pasos y observación.
3. Detener efectos externos y aislar previews antes de intentar mitigación.
4. Reproducir sobre datos QA aislados; no borrar logs ni datos auditables.
5. Aplicar mitigación reversible autorizada, validar local + preview + rol afectado y registrar decisión.

Escalar inmediatamente ante exposición, pérdida de integridad, duplicación de cobros o operaciones OTA. Nunca atribuir causa raíz sin evidencia.
