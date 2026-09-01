# Frontend i18n

La interfaz usa `i18next` y `react-i18next` con recursos locales versionados en
`frontend/src/locales/<idioma>/<namespace>.json`. `es` conserva el texto
existente como fuente de verdad y `en` se genera junto con cada namespace que se
migra; no se consulta ningún servicio de traducción durante la carga.

La configuración del hotel mantiene dos conceptos separados:

- `languages`: idiomas que habla el equipo del hotel para atender huéspedes.
- `interface_language`: idioma de la interfaz, limitado a `es` o `en`, con
  default `es`.

En esta primera tanda sólo se crearon los namespaces `auth` y `common`, y se
migraron Login y registro. El shell protegido carga `interface_language` cuando
el usuario tiene permiso para leer la configuración, y Settings conserva el
selector separado del campo `languages`. Las demás pantallas y namespaces se
migrarán incrementalmente en tandas posteriores.

Para evitar regresiones, `frontend/i18n-auth-literals.test.mjs` comprueba que
las pantallas auth migradas no vuelvan a introducir literales UI en español y
que `es` y `en` tengan la misma forma de claves.
