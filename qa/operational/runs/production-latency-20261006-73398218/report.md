# Producción: línea de base de latencia en Reportes

## Alcance

- Fecha: 2026-10-06
- SHA desplegado durante la medición: `73398218f9ac118df53ccfd5780322be688519a6`
- Superficie: `https://app.hotels-pms.com/reportes`, sesión autenticada, navegación de solo lectura.
- Método: Chrome CDP `Network.responseReceived`; se registraron ruta, estado HTTP y `Server-Timing`, sin leer cuerpos ni datos de huéspedes.

## Resultado antes del parche

Una carga de Reportes envió dos solicitudes para la misma fecha. Cada endpoint reconstruyó el informe operativo y ejecutó 39 consultas:

| Ruta | HTTP | app | db | dbmax | dbq |
| --- | ---: | ---: | ---: | ---: | ---: |
| `/api/reports/operational/daily` | 200 | 2329.62 ms | 1966.23 ms | 291.43 ms | 39 |
| `/api/reports/operational/alerts` | 200 | 2242.25 ms | 1478.76 ms | 280.09 ms | 39 |

El código confirma que `/operational/alerts` llama a `nightly_summary()`, que a su vez vuelve a ejecutar `daily_report()`. El informe diario ya incluye `alerts` y ambas rutas aplican la misma redacción según permisos. La muestra confirma trabajo duplicado; no es un percentil ni demuestra por sí sola la latencia de todas las pantallas.

## Cambio local

La pantalla consumirá las alertas de la respuesta diaria y dejará de llamar al endpoint redundante. El endpoint de alertas queda disponible para otros clientes. Se añadió una prueba E2E local que verifica la visualización de las alertas y la ausencia de la segunda solicitud.

## Después del despliegue

Pendiente: repetir la misma navegación contra el SHA nuevo y comprobar que haya una única solicitud diaria, con alertas visibles y sin regresión de permisos.
