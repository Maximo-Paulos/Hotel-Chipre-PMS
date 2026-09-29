# Reporte del día N — <día de semana dd/mm> (ronda NN)

> Escrito para que otro agente lo lea e implemente los arreglos. Todo hallazgo es accionable: síntoma, repro, evidencia, causa raíz, cambio propuesto y criterio de aceptación.

## 0. Ficha del día

- Versión probada: commit `<sha>` de `main`. Entorno: PostgreSQL 16, backend FastAPI, frontend build de producción, reloj simulado.
- Personas que actuaron y qué hicieron (una línea cada una).
- Datos generados hasta hoy: reservas, pagos, cierres de caja, remitos, tareas, bloqueos, etc.
- Puntaje "¿lo seguiría usando?" (1-10) por persona y su variación respecto del día anterior.

## 1. Resumen ejecutivo

- Veredicto en 5 líneas: ¿podría un hotel real operar mañana con esto? ¿Qué lo impide?
- Los 3-5 problemas que más daño hacen hoy, en orden.
- Qué mejoró o empeoró respecto del día anterior.

## 2. Plan de PRs sugerido

Tabla: PR propuesto · hallazgos que cierra · archivos principales · esfuerzo (S/M/L) · riesgo · dependencias. Ordenado por prioridad.

## 3. Qué funcionó (no romper)

Lista de comportamientos verificados en la simulación que están bien, con dónde se comprobó. Incluye lo que gustó a los usuarios y lo que fue rápido/claro.

## 4. Hallazgos

Uno por bloque, con este formato exacto. Orden: P0 → P1 → P2.

### F-### · <título corto> · P0|P1|P2 · [SEGURIDAD] [DINERO] [DATOS] (etiquetas si aplican) · <área> · <persona/día>

- **Síntoma (lo que vive el usuario):** …
- **Cómo reproducir:** pasos numerados, con datos concretos (rol, pantalla, valores).
- **Esperado / Observado:** …
- **Evidencia:** mensaje exacto en pantalla, código HTTP y endpoint, línea de log, cantidad de ocurrencias.
- **Causa raíz:** `archivo:línea` y explicación. Marcar **verificada** (se leyó el código o el log) o **hipótesis**.
- **Cambio propuesto:** opción recomendada (qué archivos tocar y cómo) + alternativas si las hay.
- **Criterio de aceptación / test:** qué debe pasar para darlo por cerrado; test a agregar (incluir PostgreSQL cuando aplique).
- **Esfuerzo / riesgo:** S/M/L y qué podría romperse.
- **Impacto en un hotel real:** por qué importa.

## 5. Feedback por persona

Por cada persona: qué le sirvió, qué le costó, qué le faltó, en sus palabras (citas breves), y qué pediría. Puntaje.

## 6. Propuestas de producto y mejoras posibles

Ideas más allá de los bugs (flujos que faltan, atajos, automatizaciones, reportes), cada una con problema que resuelve, propuesta, valor, esfuerzo estimado y a quién ayuda.

## 7. Mediciones

Requests totales, errores 4xx/5xx por endpoint, tiempos, timeouts del pool, acciones de UI por tarea (p. ej. clics por reserva cargada), tiempos por tarea.

## 8. Intervenciones técnicas de la simulación

Cosas que la simulación tuvo que hacer por fuera de la UI para poder continuar. Qué, por qué, qué debería poder hacer un usuario real en su lugar.

## 9. Textos, traducciones y coherencia

Textos en inglés o técnicos visibles al personal, formatos de fecha/moneda, cifras que no coinciden entre pantallas. Con la pantalla y el texto exacto.

## 10. No cubierto / preguntas abiertas

Qué no se pudo probar hoy y por qué; supuestos que conviene validar con un hotel real.

## 11. Escenario para reejecutar

Datos y pasos mínimos para reproducir los P0/P1 del día en una ronda nueva (semilla, usuarios, orden de acciones), de modo que se pueda verificar que quedaron arreglados.
