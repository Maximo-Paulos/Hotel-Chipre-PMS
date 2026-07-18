# Jerarquía de verdad

1. **Runtime, configuración desplegada y código vigente** — comportamiento actual.
2. **Tests vigentes** — contrato verificable, salvo que contradigan el runtime/código.
3. **Graphify** — mapa estructural e impacto; requiere comprobar frescura.
4. **Vault y documentación histórica** — intención, decisiones y operación.

Cada afirmación material debe llevar uno de estos estados:

- `confirmed`: observada en fuente canónica o prueba ejecutada.
- `inferred`: deducida de evidencia parcial; no usarla para cambios riesgosos sin comprobar.
- `historical`: preservada para contexto; no describe necesariamente el sistema actual.
- `needs-verification`: falta acceso, ejecución o dato para decidir.

Cuando haya conflicto, registrar la discrepancia en `DECISION-LOG.md` o `STATUS-TODAY.md`, citar la fuente y corregir la nota curada. No resolver contradicciones por antigüedad de un documento.
