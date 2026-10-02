# Cambios de tarifas con revisión

Los cambios de tarifas diarias y de temporada se guardan primero como borrador. El borrador muestra los valores anteriores y propuestos, además del impacto en reservas y noches. Un usuario autorizado debe confirmar o cancelar el borrador; confirmar vuelve a validar que los precios de base no hayan cambiado y conserva los importes ya pactados en las reservas.

Las mutaciones heredadas de `/api/rates/...` responden `409` y apuntan a `/api/rate-change-drafts`. Las rutas de lectura del calendario y de temporadas siguen disponibles. La interfaz ya utiliza exclusivamente el flujo de borradores.
