# Frontend y UX

Estado: `confirmed` para router; `needs-verification` para comportamiento por persona tras cada cambio.

React 18/Vite usa `createBrowserRouter`. `app.hotels-pms.com` aloja dashboard, huéspedes, reservas, habitaciones, caja, reportes, operaciones, analytics, settings, onboarding y master-admin. `hotels-pms.com` aloja marketing y redirige los flujos de aplicación al host correspondiente. Ver [rutas generadas](../_generated/frontend-routes.md).

Las rutas protegidas no sustituyen controles backend: cliente y API deben coincidir en roles, tenant y errores. Cada ajuste visual debe probar móvil, accesibilidad y estados no felices.
