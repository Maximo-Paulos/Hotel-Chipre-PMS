# Gmail ? Conexion del correo operativo del hotel

## Objetivo

Separar dos correos dentro del producto:

1. **Correo de PMS Paulus**
   - Verificacion de cuenta
   - Recuperacion de acceso
   - Invitaciones al staff
   - Avisos propios del sistema

2. **Correo del hotel**
   - Envio de links de pago
   - Recibos
   - Confirmaciones de reserva
   - Mensajes operativos a huespedes

El correo del hotel no debe salir desde PMS Paulus. Debe salir desde la cuenta Gmail conectada por el dueno del hotel.

---

## Resumen ejecutivo

Hay dos decisiones distintas:

1. **Correo oficial de PMS Paulus**
   - Lo usamos nosotros como plataforma.
   - Reemplaza al Gmail personal que hoy sirve para pruebas.
   - Envia: verificacion de cuenta, recuperacion de acceso, invitaciones y avisos del sistema.

2. **App OAuth de Google de PMS Paulus**
   - Tambien la preparamos nosotros una sola vez.
   - Sirve para que cada hotel conecte su propio Gmail desde el UI.
   - El cliente del hotel **no** deberia tocar Google Cloud ni crear credenciales.

Mientras estemos en desarrollo se puede seguir usando el Gmail personal del dueno del PMS como correo de prueba.
**Antes del lanzamiento publico hay que reemplazarlo por el correo oficial de empresa y completar el setup productivo de Google.**

---

## Setup rapido para testing local ahora mismo

Si solo queremos probar el popup de Gmail en desarrollo local, lo minimo que falta es crear el OAuth client del PMS y copiar 3 datos:

- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REDIRECT_URI`

### Paso a paso corto

1. Entrar a Google Cloud Console.
2. Crear un proyecto de testing para PMS Paulus o usar uno de pruebas.
3. Habilitar **Gmail API**.
4. Ir a **OAuth consent screen** y dejar la app como **External**.
5. Crear un **OAuth Client ID** de tipo **Web application**.
6. Cargar este redirect URI exacto:
   - `http://127.0.0.1:8040/api/integrations/oauth/gmail/callback`
7. Copiar:
   - Client ID
   - Client Secret
8. Pegarlos en `.env` local:
   - `GMAIL_CLIENT_ID=...`
   - `GMAIL_CLIENT_SECRET=...`
   - `GMAIL_REDIRECT_URI=http://127.0.0.1:8040/api/integrations/oauth/gmail/callback`
9. Reiniciar backend.
10. Ir a **Configuracion > Conexiones > Gmail** y tocar **Conectar Gmail**.

### Resultado esperado en testing

- se abre el popup de Google
- el duenio del hotel elige su cuenta Gmail
- acepta permisos
- vuelve al PMS
- la conexion queda guardada para ese hotel

> En testing de Google puede ser necesario agregar manualmente la cuenta como tester. Eso es normal en esta etapa.

---

## Parte A ? Lo que debe preparar PMS Paulus

Esta parte la hace el equipo de PMS Paulus una sola vez antes del lanzamiento.

### 1. Definir el correo oficial de plataforma

Antes de lanzar, el correo personal usado en desarrollo debe salir del flujo de produccion.

Recomendado:

- `soporte@pmspaulus.com`
- `noreply@pmspaulus.com`
- `cuentas@pmspaulus.com`

Ese correo sera el remitente de:

- verificacion de cuenta
- recuperacion de contrasena
- invitaciones al staff
- avisos del sistema

**No** debe usarse para enviar links de pago o mensajes del hotel a sus huespedes.

### 2. Preparar el dominio y la autenticacion del correo oficial

Antes de salir a produccion:

1. Tener dominio propio de la empresa, por ejemplo `pmspaulus.com`.
2. Crear el buzon oficial que usara el sistema.
3. Configurar autenticacion del dominio para envio:
   - SPF
   - DKIM
   - DMARC
4. Probar que el dominio envia correctamente y no cae en spam.

Esto es importante para reputacion de envio y para que Google y otros proveedores confien en el remitente.

### 3. Cargar el correo oficial de PMS Paulus en el sistema

Cuando se reemplace el Gmail personal por el correo oficial, actualizar en produccion:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASS`
- `SMTP_FROM`

Luego validar manualmente:

- envio de verificacion
- envio de reset de contrasena
- invitacion al staff
- aviso simple del sistema

### 4. Crear la app OAuth en Google Cloud

1. Entrar a Google Cloud Console.
2. Crear o elegir el proyecto productivo del PMS.
3. Habilitar **Gmail API**.
4. Ir a **Google Auth Platform** / **OAuth consent screen**.
5. Configurar:
   - nombre de la app
   - logo
   - dominio oficial de PMS Paulus
   - email de soporte oficial
   - politica de privacidad publica
   - terminos si aplica
6. Publicar la app como **External** y luego **In production**.

> Google recomienda separar testing y produccion en proyectos distintos cuando sea posible. Para lanzamiento comercial conviene tener un proyecto productivo propio.

### 5. Usar scopes minimos

Para este flujo no debemos pedir lectura de casilla. Solo:

- `openid`
- `email`
- `profile`
- `https://www.googleapis.com/auth/gmail.send`

No usar `gmail.readonly` ni `mail.google.com` para este caso.

### 6. Crear el OAuth client

Tipo recomendado:

- **Web application**

Configurar los redirect URIs exactos del PMS, por ejemplo:

- desarrollo: `http://127.0.0.1:8040/api/integrations/oauth/gmail/callback`
- produccion: `https://tu-dominio/api/integrations/oauth/gmail/callback`

> El valor exacto final tiene que coincidir con la URL real del backend donde corre el callback.

### 7. Pasar la app a produccion

No lanzar con la app en **Testing**.

Si queda en **Testing**:

- solo entran usuarios agregados como testers
- los refresh tokens pueden vencer a los 7 dias

Para un producto cobrado, la app debe quedar en **In production** antes del lanzamiento.

### 8. Variables que PMS Paulus debe cargar

En el backend:

- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REDIRECT_URI`
- `APP_BASE_URL` correcto para backend

Y en produccion:

- `APP_ENV=production`
- `JWT_SECRET` fuerte
- `INTEGRATIONS_ENCRYPTION_KEY` valida

### 9. Verificacion de Google antes del lanzamiento

Como el sistema pide `gmail.send`, Google puede requerir verificacion de la app.

Antes de lanzar:

1. Completar dominio autorizado.
2. Tener publicadas:
   - homepage del producto
   - politica de privacidad
   - email de soporte
3. Revisar si Google solicita:
   - brand verification
   - sensitive scope verification
4. Dejar aprobado el proyecto productivo si aplica.

### 10. Prueba final de pre-lanzamiento

Antes de abrir a clientes:

1. Crear una cuenta nueva de prueba en el PMS.
2. Verificar que el correo de verificacion salga desde PMS Paulus.
3. Conectar un Gmail de prueba como si fuera un hotel real.
4. Generar un link de pago.
5. Verificar que el link salga desde el Gmail del hotel, no desde PMS Paulus.
6. Revocar y reconectar Gmail.
7. Confirmar que el health check de Gmail funciona.

---

## Parte B ? Lo que hace el dueno del hotel

Esta parte la hace el cliente desde el UI, sin tocar Google Cloud.

### Flujo ideal dentro del PMS

1. Crear su cuenta en el PMS con cualquier email.
2. Verificar su cuenta con el correo enviado por PMS Paulus.
3. Entrar al PMS.
4. Ir a **Configuracion > Conexiones**.
5. Conectar **Gmail** como primer paso recomendado.
6. Elegir la cuenta Gmail que usara el hotel.
7. Aceptar permisos.
8. Volver al PMS y ver el estado **Conectado**.

### Resultado esperado

Una vez conectado Gmail:

- los links de pago se envian desde el Gmail del hotel
- los recibos salen desde el Gmail del hotel
- los mensajes a huespedes salen desde el Gmail del hotel
- PMS Paulus sigue enviando solo los correos del sistema

El cliente del hotel no deberia:

- crear proyectos en Google Cloud
- configurar redirect URIs
- generar client IDs
- tocar secretos tecnicos

Su unica accion deberia ser autorizar su cuenta desde el PMS.

---

## Como validar que la conexion quedo bien

En **Configuracion > Conexiones > Gmail** debe verse:

- estado conectado
- cuenta validada
- ultima verificacion
- opcion de refrescar y revocar

En **Configuracion > Pruebas**:

- crear una prueba de Mercado Pago
- enviar link por email
- confirmar que abajo aparezca el remitente del hotel

---

## Troubleshooting

### 1. El hotel no puede conectar Gmail

Revisar:

- que la app OAuth de Google este en produccion
- que el redirect URI coincida exactamente
- que el cliente y secreto cargados sean correctos
- que la cuenta Workspace no tenga bloqueada la app por su administrador
- que el proyecto productivo sea el correcto y no el de testing

### 2. La conexion se corta a los pocos dias

Causa probable:

- la app sigue en modo **Testing**
- no se obtuvo refresh token
- la cuenta revoco permisos

### 3. El PMS dice conectado pero no envia

Revisar:

- health check de Gmail
- ultima verificacion
- ultimo error
- si la conexion fue revocada o expiro

### 4. El link de pago no sale por correo

Revisar:

- Mercado Pago conectado
- Gmail conectado
- que el email del huesped sea valido
- que Google no haya rechazado el envio

### 5. Estamos usando todavia el Gmail personal del dueno del PMS

Eso puede estar bien en desarrollo, pero **no** en lanzamiento.

Antes de vender el sistema:

1. crear el correo oficial de empresa
2. reemplazar las variables SMTP del sistema
3. probar todos los correos transaccionales
4. dejar el Gmail personal fuera del flujo de produccion

---

## Politica de producto

- **PMS Paulus** envia correos de identidad y sistema.
- **El hotel** envia correos operativos a huespedes desde su Gmail conectado.
- No mezclar ambos canales en produccion.
- Si el hotel no conecta Gmail, el sistema no debe fingir ser el hotel usando el correo de PMS Paulus.

---

## Checklist de lanzamiento publico

### Lo que puede seguir igual durante desarrollo

- usar Gmail personal del dueno del PMS para pruebas SMTP
- probar conexiones Gmail con cuentas de prueba
- trabajar en localhost

### Lo que debe quedar hecho antes de vender

#### Plataforma PMS Paulus

- [ ] crear dominio oficial de empresa
- [ ] crear correo oficial de empresa para el sistema
- [ ] configurar SPF
- [ ] configurar DKIM
- [ ] configurar DMARC
- [ ] reemplazar `SMTP_*` por credenciales del correo oficial
- [ ] probar verificacion, reset e invitaciones

#### Google Cloud / OAuth

- [ ] crear o confirmar proyecto productivo
- [ ] habilitar Gmail API
- [ ] configurar OAuth consent screen
- [ ] cargar dominios autorizados
- [ ] publicar homepage y politica de privacidad
- [ ] configurar `GMAIL_CLIENT_ID`
- [ ] configurar `GMAIL_CLIENT_SECRET`
- [ ] configurar `GMAIL_REDIRECT_URI`
- [ ] pasar la app a `In production`
- [ ] completar verificacion de Google si aplica

#### Producto

- [ ] probar que el cliente conecta Gmail sin pasos tecnicos
- [ ] probar envio de link de pago desde Gmail del hotel
- [ ] probar health check y revocacion
- [ ] probar reconexion
- [ ] confirmar que PMS Paulus solo envia correos del sistema

---

## Que tengo que hacer yo como dueno de PMS Paulus

### Ahora mismo

No hace falta hacer un cambio urgente si seguimos en desarrollo.

Podes seguir usando tu Gmail personal **solo para pruebas** mientras:

- desarrollamos
- testeamos flujos
- ajustamos la UX

### Antes del lanzamiento

Si o si vas a tener que hacer estas dos cosas:

1. **Cambiar el correo del sistema**
   - dejar de usar tu Gmail personal
   - crear y usar el correo oficial de empresa para SMTP

2. **Dejar lista la app Google del PMS**
   - preparar Google Cloud
   - publicar la app OAuth
   - cargar las variables reales de produccion

En otras palabras:

- tu Gmail personal puede seguir ahora
- **no** debe quedar como remitente final del producto
- el dia del lanzamiento el sistema ya tiene que salir con identidad oficial de PMS Paulus

---

## Fuentes oficiales

- Gmail API scopes:
  - [https://developers.google.com/workspace/gmail/api/auth/scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- Gmail send guide:
  - [https://developers.google.com/workspace/gmail/api/guides/sending](https://developers.google.com/workspace/gmail/api/guides/sending)
- OAuth web server flow:
  - [https://developers.google.com/identity/protocols/oauth2/web-server](https://developers.google.com/identity/protocols/oauth2/web-server)
- OAuth consent configuration:
  - [https://developers.google.com/workspace/guides/configure-oauth-consent](https://developers.google.com/workspace/guides/configure-oauth-consent)
- OAuth general lifecycle / refresh tokens:
  - [https://developers.google.com/identity/protocols/oauth2](https://developers.google.com/identity/protocols/oauth2)
- OAuth apps in production / brand verification:
  - [https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification)
- Sensitive scope verification:
  - [https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification)
- Sender authentication guidance:
  - [https://support.google.com/a/answer/14289100](https://support.google.com/a/answer/14289100)
