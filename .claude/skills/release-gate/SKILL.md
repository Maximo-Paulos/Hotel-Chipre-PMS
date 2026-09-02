---
name: release-gate
description: Aplica la puerta de entrega antes de cerrar o fusionar.
---

# release-gate

Comprueba validación local, paridad de agentes/skills, inventarios/vault, Graphify fresco, revisión de seguridad y el resultado del ciclo de QA sobre Render producción posterior al merge.

Usa `knowledge/40-delivery/release-gates.md` y el verificador de evidencia. Si falta un requisito, declara el bloqueo con reproducción y no marques la tarea como terminada.

La QA funcional cloud usa únicamente el hotel de prueba autorizado y datos sintéticos; no exige un servicio Render QA separado.
