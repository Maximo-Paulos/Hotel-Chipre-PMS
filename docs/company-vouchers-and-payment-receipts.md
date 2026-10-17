# Vouchers de empresas y comprobantes de pago

## Cargar un voucher corporativo

Abrí la reserva y usá la sección **Documentos de empresa** para seleccionar un
PDF de hasta 5 MB. La carga se asocia a la empresa y a esa reserva, y requiere
el permiso `company:manage`. El PMS mantiene los metadatos en su base existente
y guarda el contenido en el almacenamiento privado de objetos configurado; no
hace falta una base de datos separada. En local, el adaptador usa
`OBJECT_STORAGE_BACKEND=local` y `OBJECT_STORAGE_LOCAL_DIR` (por defecto,
`./var/object-storage`).

Los vouchers subidos desde esta sección quedan disponibles en la ficha de la
reserva y para las validaciones de check-in de empresas. Cargar el archivo no
registra aceptación de términos ni completa el check-in.

## Descargar o enviar un comprobante de pago

En los movimientos de pago de la reserva, **Descargar PDF** obtiene un
comprobante generado a partir de los datos guardados. **Enviar por email** abre
la confirmación con el correo del huésped como valor inicial; el operador puede
editarlo o escribir otro destinatario. Si cambia la dirección, el sistema crea
una nueva intención idempotente. El PDF adjunto contiene los mismos bytes que
la descarga.

En una simulación local se requiere SQLite, `APP_ENV=development`,
`EXTERNAL_EFFECTS_ENABLED=false`, el reloj local habilitado para el mismo hotel
y un destinatario bajo el dominio reservado `.test`. El resultado se identifica
como **capturado en simulación local**: no se consulta Gmail ni se envía correo
fuera de la máquina. El mensaje MIME y el adjunto se guardan en
`DEV_EMAIL_OUTBOX_PATH`; si está vacío, se usa un outbox local con directorio
`0700` y archivo `0600`. Ese archivo incluye el destinatario y el comprobante,
por lo que debe tratarse como dato privado.

Fuera de ese perfil aislado, `.test` se rechaza y el envío usa el adaptador de
Gmail conectado por el hotel cuando los efectos externos están habilitados,
sujeto a permisos, MFA y confirmación del operador.
