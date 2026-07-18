---
name: release-gate
description: Aplica la puerta de entrega antes de cerrar o fusionar.
---

# release-gate

Comprueba validación local, paridad de agentes/skills, inventarios/vault, Graphify fresco, revisión de seguridad, preview aislado saludable y evidencia QA posterior al último cambio funcional.

Usa `knowledge/40-delivery/release-gates.md` y el verificador de evidencia. Si falta un requisito, declara el bloqueo con reproducción y no marques la tarea como terminada.

No reduzcas la matriz QA ni aceptes una base compartida como preview.
