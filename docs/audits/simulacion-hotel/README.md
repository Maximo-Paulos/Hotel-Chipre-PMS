# Simulación de hotel con usuarios sintéticos — auditoría de uso

## Qué es

Un hotel ficticio ("Hotel Mirador del Lago", Villa Carlos Paz, 30 habitaciones, pagos en efectivo) usa Hotels-PMS durante una semana simulada. Lo operan cinco personas sintéticas que sólo usan la interfaz, sin leer código ni llamar a la API: dueño, codueña, gerente, recepcionista y limpieza (esta última desde celular). El objetivo es encontrar qué impide o dificulta el uso real antes de una prueba con un hotel verdadero.

Cada día simulado produce un reporte en `ronda-NN/dia-NN-<fecha>.md` con el formato de `PLANTILLA-REPORTE.md`. Los reportes están escritos para que **otro agente pueda leerlos, implementar los arreglos y verificarlos** sin tener que redescubrir nada.

## Rondas (iteración)

- **Ronda 01** (sept-oct 2026): app en el commit `24957e5` de `main`. Se ejecuta entera y se deja el reporte de cada día.
- Tras desplegar los arreglos, se abre una **ronda nueva** (`ronda-02`, …) sobre el `main` actualizado, con un hotel nuevo y el mismo guion, para medir qué mejoró y qué apareció. Cada ronda cierra con un `resumen-ronda-NN.md` que compara contra la anterior.
- Los IDs de hallazgo son estables entre rondas (`F-###`); un hallazgo reabierto conserva su ID y se anota "reabierto en ronda N".

## Cómo usar los reportes (para el agente que implementa)

1. Leer primero "Resumen ejecutivo" y "Plan de PRs sugerido" de cada reporte.
2. Trabajar por prioridad: P0 (bloquea la operación) → P1 (rompe un flujo importante o mezcla datos/dinero) → P2 (fricción, textos, UX).
3. Respetar la sección "Qué funcionó (no romper)": cada ítem es un comportamiento verificado en la simulación.
4. Cada hallazgo trae **criterio de aceptación** y, cuando aplica, un test a agregar. Varios bugs sólo aparecen en PostgreSQL y no en la suite (SQLite): los tests deben correr también contra PostgreSQL o validar el SQL generado.
5. PRs pequeños, uno por grupo temático, con CI verde antes de desplegar. Los hallazgos marcados **[SEGURIDAD]** o **[DINERO]** merecen revisión humana antes de mezclar.
6. Al cerrar un hallazgo, anotar el commit en el reporte de la ronda siguiente al reejecutar la simulación.

## Reglas de los reportes

- Sin contraseñas, tokens, secretos TOTP, cookies ni capturas de pantalla. Los correos son sintéticos (`@hotelmirador.sim`).
- Todo dato de causa raíz distingue **verificado** (se leyó el código o el log) de **hipótesis**.
- Las intervenciones técnicas que la simulación tuvo que hacer para poder continuar (cosas que un hotel real no podría hacer) se listan aparte; cada una es, en sí misma, un hallazgo.

## Límites conocidos de la simulación

No se puede: crear cuentas Gmail reales, iniciar sesión con Google, cobrar con tarjeta ni conectar OTAs, WhatsApp o IA reales. Los correos y "WhatsApp" son un buzón local simulado. El reloj se adelanta con `libfaketime` día a día.
