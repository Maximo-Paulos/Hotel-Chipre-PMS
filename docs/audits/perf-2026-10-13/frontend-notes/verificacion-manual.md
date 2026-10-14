# Verificación manual de hallazgos de frontend (partes 1 y 2)

Comprobados por mí contra el código, independientemente del agente que escribió las notas.

| Hallazgo | Resultado | Evidencia |
|---|---|---|
| `/reservas` muestra las 200 reservas de estadía más antigua | **Confirmado** | `ReservationsPage.tsx:403-415` pide `order:"check_in"`, `limit:200`, sin `fromDate`; `reservation_service.py:2093` ordena `check_in_date ASC`. El comentario del código lo presenta como decisión para conservar el orden previo, pero con más de 200 reservas históricas no se ven las vigentes |
| Buscador global sin debounce | **Confirmado** (con matiz) | `ReservationGlobalSearch.tsx:22` usa el texto directo; `useReservations.ts:69-84` exige ≥ 2 caracteres y usa `keepPreviousData`, pero cada cambio de texto lanza una request |
| Locales de reservas en el chunk de entrada | **Confirmado** | `i18n.ts:10,18` importa `es/reservations.json` y `en/reservations.json` (65.843 + 63.350 = 129.193 bytes; 33.378 gzip medidos con `gzip -c`), además de 7 namespaces más |
| `GET /api/laundry/remitos` sin límite | **Confirmado** | `laundry_vendor_service.py:430-445` termina en `.all()`; `LaundryPage.tsx:184-189` lo pide sin filtros |
| `GET /api/cash-register/sessions` sin límite | **Confirmado** | `cash_register_service.py:738-744` termina en `.all()` |
