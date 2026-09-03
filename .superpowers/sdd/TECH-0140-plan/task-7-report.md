# Task 7 report — Object storage y archivos

## Implementado

- `StoredObject` agrega metadata tenant-scoped, propósito, backend, tamaño, SHA-256, versión, estado y soft delete.
- El flujo `register_uploaded_object` persiste `pending_upload`, sube, ejecuta `stat`, valida tamaño/checksum y recién entonces marca `ready`; un error nunca deja una fila `ready`.
- El adaptador local implementa `stat` y URLs firmadas acotadas a 15 minutos.
- Se agregó un adaptador GCS lazy, sin provisionar bucket ni credenciales. La dependencia del proveedor sólo se carga al seleccionar `OBJECT_STORAGE_BACKEND=gcs`.
- Comprobantes y exports registran metadata durable. `CompanyDocument` admite referencia opcional a un objeto `ready`, validada por hotel.
- La migración es aditiva: no copia ni elimina blobs legacy y conserva `file_url`, `content` y referencias anteriores para dual-read.

## Verificación

```text
37 passed, 23 warnings
```

También se ejecutó `alembic upgrade head` sobre SQLite descartable desde esquema vacío y se confirmó la creación de `stored_objects` y `company_documents.stored_object_id`.

## Pendiente provider-bound

- Instalar/probar `google-cloud-storage` con un bucket privado real y IAM mínimo.
- Implementar job de copia/reconciliación para referencias legacy y observar 30 días antes de cualquier cleanup físico.
