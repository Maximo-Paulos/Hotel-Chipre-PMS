# Frontend y UX

Estado: `confirmed` para router; `needs-verification` para comportamiento por persona tras cada cambio.

React 18/Vite usa `createBrowserRouter`. `app.hotels-pms.com` aloja dashboard, huéspedes, reservas, habitaciones, caja, reportes, operaciones, analytics, settings, onboarding y master-admin. `hotels-pms.com` aloja marketing y redirige los flujos de aplicación al host correspondiente. Ver [rutas generadas](../_generated/frontend-routes.md).

Las rutas protegidas no sustituyen controles backend: cliente y API deben coincidir en roles, tenant y errores. Cada ajuste visual debe probar móvil, accesibilidad y estados no felices.

## Efectivo y housekeeping

Estado: `validated-local` en el working tree, sin QA cloud.

El flujo de efectivo distingue monto aplicado, efectivo entregado, vuelto y propina voluntaria. El valor por defecto para el excedente es devolverlo. El formatter local de efectivo conserva dos decimales en preview, historial, caja y comprobantes; por ejemplo, ARS 12,50 no debe mostrarse como ARS 13. Se mantiene intacto el formatter monetario global. Referencias: [CashTenderField.tsx](../../frontend/src/components/CashTenderField.tsx), [cashTender.mjs](../../frontend/src/utils/cashTender.mjs), [ReservationsPage.tsx](../../frontend/src/views/protected/ReservationsPage.tsx) y [CashRegisterPage.tsx](../../frontend/src/views/protected/CashRegisterPage.tsx).

Housekeeping usa un checklist fijo generado al checkout: cambiar sábanas, limpiar baño, reponer toallas, vaciar residuos y revisar amenities. Completarlo libera una habitación que esté en limpieza; habitaciones ocupadas, bloqueadas o en mantenimiento no se liberan. Validación local del 2026-10-23: `npm test` (148), `npm run test:i18n` (5), typecheck, lint, build y 3 E2E Chromium sobre PostgreSQL. Ver [HousekeepingTodayPage.tsx](../../frontend/src/views/protected/HousekeepingTodayPage.tsx), [E2E de housekeeping](../../frontend/e2e/housekeeping-laundry-journey.spec.ts) y [auditoría de escenarios](../../docs/audits/auditoria-thermos-antislop-escenarios-pms-2026-10-22.md). El código no está committed; la evidencia no certifica cloud.
