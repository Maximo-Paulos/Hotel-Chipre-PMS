# Task 10 report — Backups y restore drill

## Implementado

- El drill local compara una base crítica ampliada: hoteles/memberships, rooms, reservas, transacciones, pagos, caja, auditoría, outbox y objetos almacenados.
- SQLite valida `integrity_check`, todas las foreign keys y conteos antes/después del restore.
- Con `--object-storage-dir`, cada objeto `ready` debe existir y coincidir en tamaño y SHA-256; un objeto corrupto hace fallar el verificador.
- La frontera PostgreSQL sigue siendo loopback-only y nunca se acepta una URL provider-bound desde este script.

## Verificación

```text
60 passed, 2 warnings
LOCAL SQLite restore: verified; integrity_check=ok; foreign_key_check=ok
```

## Bloqueo explícito

El restore provider-bound firmado, RPO/RTO observado, PITR y retención contractual no pueden certificarse desde este worktree. Requieren el drill humano en un destino aislado, sin mutar producción.
