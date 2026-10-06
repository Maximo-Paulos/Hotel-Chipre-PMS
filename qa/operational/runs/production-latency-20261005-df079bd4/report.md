QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

# Latencia de navegación en producción

## Alcance

- Servicio observado: app pública en producción, código `df079bd4d555a412461b4943a08a425304e760b3`.
- Recorrido: lectura de Dashboard, Habitaciones, Reservas y Caja desde sesiones autenticadas de Dueño y Gerencia.
- Efectos: solo navegación y solicitudes GET; no se guardaron cambios, pagos, cierres ni movimientos.
- No se conservaron cuerpos de respuestas, cookies, tokens, nombres de huéspedes ni importes.

## Observaciones

- Las solicitudes API visibles en el navegador tardaron aproximadamente **0,4–2,2 s** en los recorridos medidos. Son muestras puntuales de extremo a extremo, no una medición p95 ni tiempo puro de servidor.
- Dashboard hizo alrededor de 15 solicitudes API al cargar; Habitaciones, Reservas y Caja hicieron varias lecturas paralelas. Caja emitió cerca de 18 solicitudes en la primera carga observada.
- El endpoint de colaboración devolvió **503** durante la caída de Redis. Las lecturas principales de esas pantallas devolvieron **200**.
- El proveedor mostraba la advertencia de que su instancia gratuita puede tardar **50 s o más** en arrancar después de inactividad. No se observó ni se midió un cold start en esta campaña.
- No había encabezado `Server-Timing`, por lo que no era posible separar el tiempo de aplicación del tiempo de red/proxy.

## Diagnóstico

Redis figuraba desconectado, la caché distribuida estaba deshabilitada y el servicio mantenía eventos en tiempo real mediante el fallback de PostgreSQL. La implementación anterior usaba un generador síncrono con `time.sleep` dentro de `StreamingResponse`; Starlette ejecuta iteradores síncronos en su threadpool compartido. **Inferencia:** varias conexiones SSE inactivas podían ocupar workers y competir con solicitudes API normales. Esta campaña no hizo una prueba de concurrencia en producción, así que no cuantifica el efecto.

El 503 de colaboración coincide con la dependencia de Redis que el endpoint comunica; se registró como un problema independiente de disponibilidad y no como causa confirmada de la demora de las lecturas.

## Cobertura y límites

- Se observaron Dueño y Gerencia. Una tercera pestaña PMS estaba reclamada por otra sesión automatizada; no se la tomó ni interrumpió.
- Los tiempos son valores puntuales de Network/CDP y pueden incluir navegador, red, proxy y arranque del proveedor.
- Esta campaña no realizó carga concurrente, operaciones financieras ni escrituras sobre el dominio compartido.
- Este documento sirve para diagnóstico operativo; no acredita un release, un SLA ni la ausencia de errores.

## Acciones de código preparadas

- Cambiar el fallback SSE de PostgreSQL a un iterador asíncrono: ejecutar consultas breves en el threadpool, cerrar cada sesión y esperar entre sondeos con `asyncio.sleep`.
- Exponer `Server-Timing` y `X-Request-Id` mediante CORS para obtener tiempos de aplicación en futuras mediciones autorizadas.
- Repetir pruebas de concurrencia localmente y comparar tiempos en la aplicación después de desplegar el cambio. No se ejecutará carga sobre producción.
