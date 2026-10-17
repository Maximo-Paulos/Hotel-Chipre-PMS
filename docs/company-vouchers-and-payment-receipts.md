# Vouchers de empresas y comprobantes de pago

## Cargar un voucher corporativo

En **Empresas**, seleccioná la empresa y abrí **Vouchers y firmas**. El formulario
pide el ID de una reserva, el tipo de documento y un PDF de hasta 5 MB; también
permite indicar si requiere firma y agregar notas. La carga requiere el permiso
`company:manage`. El backend valida que la reserva pertenezca al hotel activo y
que esté vinculada a la empresa seleccionada. El PMS mantiene los metadatos en
su base existente y guarda el contenido en el almacenamiento privado de objetos
configurado; no hace falta una base de datos separada. En local, el adaptador usa
`OBJECT_STORAGE_BACKEND=local` y `OBJECT_STORAGE_LOCAL_DIR` (por defecto,
`./var/object-storage`).

Los vouchers quedan asociados a la reserva y la validación de check-in de
empresas puede exigirlos. La pantalla actual los lista desde la ficha de
**Empresas**; no hay una carga directa en el detalle de reserva. Cargar un
archivo no registra aceptación de términos ni completa el check-in.

## Liquidar cargos nocturnos de empresa

Los cargos por persona extra se calculan y guardan por noche. Un cambio
posterior en la tarifa no vuelve a calcular cargos ya registrados; una
corrección explícita usa el flujo auditado de ajustes. Las noches anteriores a
la fecha de negocio permanecen marcadas para revisión mientras tengan saldo,
pero se pueden cobrar desde el flujo normal por su importe pendiente guardado
cuando la moneda del pago, la del cargo y la de la reserva coinciden. No se
convierte un cargo histórico con una cotización actual: si las monedas difieren
y no hay una cotización histórica persistida, el pago se rechaza sin crear una
transacción ni una asignación.

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
