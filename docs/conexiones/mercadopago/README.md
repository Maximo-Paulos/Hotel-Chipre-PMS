# Conexiones - Mercado Pago

Guia operativa y de soporte para conectar una cuenta de Mercado Pago al PMS de Hotel Chipre.

## Objetivo de esta guia

Este documento deja registrado, de forma exacta y ordenada, el flujo que seguimos en una conexion real de Mercado Pago dentro del PMS. La idea es que sirva para tres cosas:

- que el cliente pueda conectar su cuenta sin tocar codigo;
- que, si algo falla, pueda reconectar por su cuenta antes de escribir a soporte;
- que nosotros podamos reutilizar este contenido mas adelante en la web publica de tutoriales.

Esta guia esta alineada con:

- el flujo real que seguiste dentro de Mercado Pago;
- los campos y validaciones que hoy existen en el PMS;
- la documentacion oficial de Mercado Pago sobre aplicaciones, credenciales, Checkout Pro, produccion y webhooks.

## Que habilita esta conexion

Cuando Mercado Pago queda bien conectado al hotel, el PMS puede:

- generar links de pago para cobrar senias;
- consultar si un pago fue abonado;
- detectar devoluciones o reembolsos;
- detectar estados pendientes, pagados, devueltos, vencidos o cancelados;
- cancelar links pendientes;
- verificar si la conexion sigue sana sin pedir ayuda a soporte.

Cada conexion queda asociada al hotel activo del usuario dueno o co-dueno. No se comparte con otros hoteles.

## Antes de empezar

Necesitas tener a mano:

- acceso a la cuenta de Mercado Pago del hotel;
- acceso al PMS con usuario dueno o co-dueno;
- una aplicacion de Mercado Pago creada o permiso para crearla;
- la URL del sitio web que vas a declarar en Mercado Pago;
- unos minutos para copiar con cuidado las credenciales.

## Parte 1 - Flujo exacto para crear la aplicacion en Mercado Pago

Este es el flujo exacto que usaste en la prueba real y es el que debemos documentar para el cliente.

1. Ingresar a tu cuenta de Mercado Pago.
2. En la pantalla principal, entrar en el menu lateral izquierdo.
3. Ir a **Configuracion**.
4. Dentro de Configuracion, entrar en **Negocio**.
5. Dentro de Negocio, tocar **Integraciones**.
6. Entrar en **Tus integraciones**.
7. Si Mercado Pago pide verificar el numero de WhatsApp:
   - recibir el codigo;
   - ingresarlo;
   - confirmar la verificacion.
8. Tocar **Crear aplicacion**.
9. Escribir el nombre de la aplicacion.
10. Tocar **Continuar**.
11. Elegir **Pagos online**.
12. Tocar **Continuar**.
13. Cuando Mercado Pago pregunte que tipo de implementacion estas haciendo, elegir **Desarrollo propio**.
14. Tocar **Continuar**.
15. Elegir **Checkout Pro**.
16. Tocar **Continuar**.
17. Completar la verificacion de seguridad si la pide.
18. Tocar **Confirmar**.
19. Esperar unos segundos hasta que Mercado Pago cree la aplicacion.
20. Tocar **Activar credenciales**.
21. Elegir la opcion **Sitio web**.
22. Ingresar la pagina web correspondiente al hotel o al sistema.
23. Confirmar la configuracion del sitio web.
24. Una vez confirmado, Mercado Pago genera las credenciales de produccion.

## Parte 2 - Que credenciales vas a ver y cuales usa el PMS

Segun la prueba real, una vez activadas las credenciales de produccion, Mercado Pago te mostro:

- `Public key`
- `Access token`
- `Client key`

### Importante: que usa hoy el PMS

En la version actual del PMS, la conexion manual de Mercado Pago usa estos campos:

- `access_token` - obligatorio;
- `public_key` - opcional;
- `user_id` o `collector_id` - opcional.

### Como interpretar esto sin confundirte

- Si Mercado Pago te muestra `Public key`, puedes copiarla tal cual al PMS.
- Si Mercado Pago te muestra `Access token`, ese es el dato mas importante y el PMS lo valida de forma real.
- Si Mercado Pago te muestra `Client key`, guardalo como dato de referencia de la aplicacion, pero hoy el PMS no lo pide en el formulario manual.
- Si conoces tu `user_id` o `collector_id`, tambien puedes cargarlo, aunque si no lo pones y el token es valido, el sistema intenta recuperarlo automaticamente durante la validacion.

### Cual es la credencial critica

La credencial critica para que la conexion funcione es el `Access token`, porque es la que usa el backend para hablar con la API de Mercado Pago.

## Parte 3 - Como volver a encontrar las credenciales si algo falla

Si la conexion no funciona o si necesitas copiar otra vez las credenciales:

1. Volver a **Configuracion** en Mercado Pago.
2. Entrar en **Integraciones**.
3. Tocar **Tus integraciones**.
4. Elegir la aplicacion que ya habias creado.
5. Entrar en **Credenciales de produccion**.
6. Volver a copiar:
   - `Public key`
   - `Access token`
   - `Client key` si la pantalla te la muestra
7. Volver al PMS e intentar nuevamente la conexion.

## Parte 4 - Como conectar Mercado Pago dentro del PMS

1. Ingresar al PMS con usuario dueno o co-dueno.
2. Ir a **Configuracion > Conexiones**.
3. Buscar la tarjeta de **Mercado Pago**.
4. Si la cuenta todavia no esta conectada, completar los campos visibles del formulario.
5. Pegar las credenciales copiadas desde Mercado Pago.
6. Tocar **Guardar credenciales**.

### Campos esperados hoy en el PMS

- `access_token de Mercado Pago`
- `public_key (opcional)`
- `user_id / collector_id (opcional)`

## Parte 5 - Que valida el PMS cuando guardas la conexion

El PMS no guarda las credenciales a ciegas.

Cuando tocas **Guardar credenciales**, el sistema hace una validacion real:

1. toma el `access_token`;
2. realiza un ida y vuelta real con la API de Mercado Pago;
3. consulta la cuenta mediante un endpoint de verificacion;
4. confirma que el token existe, es valido y tiene permisos;
5. intenta identificar la cuenta conectada;
6. guarda la conexion cifrada;
7. la asocia al hotel activo.

### Que evita esta validacion

Esta validacion sirve para evitar errores tipicos como:

- pegar mal una letra del token;
- copiar un token incompleto;
- usar una cuenta equivocada;
- usar una credencial vencida o revocada;
- dejar guardada una conexion rota sin darse cuenta.

Si algo falla, el sistema muestra el error en pantalla y la conexion no deberia quedar confirmada como sana.

## Parte 6 - Como saber si Mercado Pago quedo bien conectado

Cuando la conexion queda correcta, la tarjeta de Mercado Pago dentro del PMS muestra:

- estado de conexion activa;
- cuenta validada;
- ultima verificacion;
- ultimo error, si hubiera uno.

## Parte 7 - Para que sirve el boton Refrescar

En la version actual del PMS, **Refrescar** no es un simple recambio visual. Es un chequeo de salud real de la conexion.

Cuando tocas **Refrescar**, el PMS:

1. toma el `access_token` guardado;
2. hace un ida y vuelta real con la API de Mercado Pago;
3. verifica que la cuenta siga respondiendo;
4. actualiza la fecha de ultima verificacion;
5. guarda el ultimo error si algo fallo;
6. deja la conexion en `connected` o `error` segun el resultado.

### Cuando conviene usarlo

Usa **Refrescar** si:

- dudas de si la cuenta sigue conectada;
- cambiaste algo en Mercado Pago;
- volviste a generar credenciales;
- ves errores al querer crear links de pago;
- un cliente te dice que antes funcionaba y ahora no.

## Parte 8 - Como revocar la conexion

Si necesitas desconectar Mercado Pago:

1. Ir a **Configuracion > Conexiones**.
2. Buscar la tarjeta de Mercado Pago.
3. Tocar **Revocar**.

Cuando revocas:

- se elimina la conexion activa para ese hotel;
- los campos del formulario vuelven a aparecer;
- puedes conectar otra cuenta distinta;
- no se mezcla la nueva cuenta con la anterior.

## Parte 9 - Como probar que la conexion sirve de verdad

Una vez conectada la cuenta, puedes verificar el flujo completo desde el PMS.

1. Ir a **Configuracion > Pruebas**.
2. Completar:
   - email del huesped;
   - monto;
   - concepto;
   - moneda;
   - vencimiento en minutos.
3. Tocar **Probar**.

El PMS va a:

- crear un link de pago en Mercado Pago;
- guardar una referencia interna unica;
- enviar el link por mail;
- crear una tarjeta de seguimiento abajo.

### Que puedes seguir desde la tarjeta de prueba

La tarjeta permite ver:

- email del huesped;
- monto enviado;
- estado del pago;
- referencia interna;
- fechas de creacion, pago, devolucion o vencimiento;
- acciones para abrir, copiar, refrescar o cancelar el link.

### Estados posibles hoy

- `Pendiente`
- `Pagado`
- `Devuelto`
- `Devuelto parcial`
- `Vencido`
- `Cancelado`

## Parte 10 - Que hacer si no funciona

### Caso 1 - El sistema rechaza las credenciales al guardar

1. Volver a Mercado Pago.
2. Abrir la aplicacion correcta.
3. Ir a **Credenciales de produccion**.
4. Copiar otra vez el `Access token`.
5. Volver al PMS.
6. Revocar la conexion actual si quedo en estado dudoso.
7. Pegar nuevamente el token.
8. Guardar otra vez.

### Caso 2 - La conexion estaba bien y dejo de funcionar

1. Ir a **Configuracion > Conexiones**.
2. Tocar **Refrescar**.
3. Leer el ultimo error que muestre el sistema.
4. Si el error habla de autenticacion o token invalido:
   - volver a copiar credenciales;
   - guardar de nuevo;
   - volver a verificar.

### Caso 3 - El cliente no encuentra las credenciales

1. Mercado Pago.
2. **Configuracion > Integraciones > Tus integraciones**.
3. Elegir la aplicacion.
4. **Credenciales de produccion**.
5. Copiar otra vez los datos visibles.

### Caso 4 - El cliente duda si quedo bien conectado

1. Abrir la tarjeta de Mercado Pago.
2. Confirmar que aparezca **Conexion activa**.
3. Confirmar que muestre **Cuenta validada**.
4. Tocar **Refrescar** para una verificacion en tiempo real.

## Parte 11 - Lo que el cliente deberia hacer antes de escribir a soporte

Antes de contactarnos, el cliente deberia poder hacer estas comprobaciones por su cuenta:

1. Confirmar que esta en la cuenta correcta de Mercado Pago.
2. Verificar que la aplicacion correcta exista en **Tus integraciones**.
3. Volver a copiar el `Access token` desde **Credenciales de produccion**.
4. Revisar la tarjeta de Mercado Pago en el PMS.
5. Ejecutar **Refrescar**.
6. Revisar el ultimo error mostrado por el sistema.
7. Si hace falta, revocar y volver a conectar.
8. Hacer una prueba real desde **Configuracion > Pruebas**.

Con esto deberiamos reducir mucho los casos que necesitan soporte manual.

## Parte 12 - Buenas practicas

- No compartir el `Access token` por chat, mail o capturas.
- Revocar la conexion anterior antes de cambiar de cuenta.
- Mantener separada la cuenta de cobros de cada hotel.
- Hacer una prueba real despues de conectar o reconectar.
- Si el PMS muestra un error, primero usar **Refrescar** antes de asumir que el sistema esta caido.
- Si Mercado Pago cambia nombres o pantallas en el panel, actualizar este README.

## Referencias oficiales de Mercado Pago

Estas fuentes oficiales se usaron como apoyo para este README y conviene revisarlas cuando actualicemos la guia:

- Developer dashboard / Your integrations:
  [https://www.mercadopago.com.ar/developers/en/docs/your-integrations/dashboard](https://www.mercadopago.com.ar/developers/en/docs/your-integrations/dashboard)
- Checkout Pro / Create application:
  [https://www.mercadopago.com.ar/developers/en/docs/checkout-pro/integrate-preferences](https://www.mercadopago.com.ar/developers/en/docs/checkout-pro/integrate-preferences)
- Go to production / activar credenciales productivas:
  [https://www.mercadopago.com.ar/developers/en/docs/checkout-pro/go-to-production](https://www.mercadopago.com.ar/developers/en/docs/checkout-pro/go-to-production)
- Webhooks / Notifications:
  [https://www.mercadopago.com.ar/developers/en/docs/your-integrations/notifications/webhooks](https://www.mercadopago.com.ar/developers/en/docs/your-integrations/notifications/webhooks)
- Credenciales / buenas practicas de seguridad:
  [https://www.mercadopago.com.ar/developers/es/docs/checkout-api-payments/best-practices/credentials-best-practices/introduction](https://www.mercadopago.com.ar/developers/es/docs/checkout-api-payments/best-practices/credentials-best-practices/introduction)

## Notas para futura publicacion en la web

Cuando llevemos esto a la web publica de tutoriales, conviene conservar esta estructura:

- resumen rapido;
- paso a paso dentro de Mercado Pago;
- paso a paso dentro del PMS;
- como verificar la conexion;
- como revocar;
- como volver a encontrar credenciales;
- que revisar antes de escribir a soporte.

Asi mantenemos una sola fuente de verdad y reducimos confusiones para el cliente.
