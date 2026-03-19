/* ═══════════════════════════════════════════════════════════════
   Hotel PMS — Frontend Application (app.js)
   Complete SPA logic for the hotel management system.
   ═══════════════════════════════════════════════════════════════ */

const API = 'http://localhost:8000';
let allReservations = [];
let allRooms = [];
let allCategories = [];
let allGuests = [];
let hotelConfig = {};
let calendarStart = new Date();
calendarStart.setHours(0, 0, 0, 0);

// ── INITIALIZATION ──
document.addEventListener('DOMContentLoaded', async () => {
  await seedIfNeeded();
  await loadAllData();
  renderDashboard();
  setInterval(() => { if (document.querySelector('#sec-dashboard.active')) renderDashboard(); }, 30000);
});

async function seedIfNeeded() {
  try { await api('/api/seed', 'POST'); } catch (e) { }
}

// ── API HELPER ──
async function api(path, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(err.detail || JSON.stringify(err));
  }
  return r.json();
}

async function loadAllData() {
  try {
    [allCategories, allRooms, allReservations, allGuests, hotelConfig] = await Promise.all([
      api('/api/rooms/categories'),
      api('/api/rooms/'),
      api('/api/reservations/'),
      api('/api/guests/'),
      api('/api/config/'),
    ]);
    document.getElementById('hotelNameSidebar').textContent = hotelConfig.hotel_name || 'Hotel PMS';
    const pending = allReservations.filter(r => r.status === 'pending').length;
    const badge = document.getElementById('pendingBadge');
    if (pending > 0) { badge.style.display = 'inline'; badge.textContent = pending; } else { badge.style.display = 'none'; }
  } catch (e) { console.error('Load error:', e); }
}

// ── NAVIGATION ──
function navigate(section) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('sec-' + section)?.classList.add('active');
  document.querySelector(`.nav-item[data-section="${section}"]`)?.classList.add('active');

  const loaders = {
    dashboard: renderDashboard,
    calendar: renderCalendar,
    reservations: renderReservations,
    guests: loadGuests,
    checkin: renderCheckin,
    payments: () => { },
    rooms: renderRooms,
    config: renderConfig,
  };
  if (loaders[section]) loaders[section]();
}

// ── TOAST NOTIFICATIONS ──
function toast(message, type = 'info') {
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ️'}</span><span class="toast-message">${message}</span><button class="toast-close" onclick="this.parentElement.remove()">✕</button>`;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── MODAL HELPERS ──
function openModal(html, large = false) {
  const m = document.getElementById('modalContent');
  m.className = 'modal' + (large ? ' modal-lg' : '');
  m.innerHTML = html;
  document.getElementById('modalOverlay').classList.add('active');
}
function closeModal() {
  document.getElementById('modalOverlay').classList.remove('active');
}

// ── FORMATTING ──
function fmtDate(d) { if (!d) return '—'; const dt = new Date(d + 'T00:00:00'); return dt.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' }); }
function fmtMoney(n) { return `$${Number(n || 0).toLocaleString('es-AR', { minimumFractionDigits: 2 })}`; }
function fmtStatus(s) {
  const labels = { pending: 'Pendiente', deposit_paid: 'Seña Pagada', fully_paid: 'Pago Total', checked_in: 'Alojado', checked_out: 'Check-out', cancelled: 'Cancelada' };
  return `<span class="badge badge-${s}">${labels[s] || s}</span>`;
}
function guestName(gid) { const g = allGuests.find(x => x.id === gid); return g ? `${g.first_name} ${g.last_name}` : `#${gid}`; }
function roomLabel(rid) { const r = allRooms.find(x => x.id === rid); return r ? r.room_number : '—'; }
function catName(cid) { const c = allCategories.find(x => x.id === cid); return c ? c.name : ''; }
function todayStr() { return new Date().toISOString().split('T')[0]; }

// ═══════════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════════
function renderDashboard() {
  const today = todayStr();
  document.getElementById('dashDateLabel').textContent = new Date().toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  const total = allRooms.length;
  const occupied = allReservations.filter(r => r.status === 'checked_in').length;
  const arriving = allReservations.filter(r => r.check_in_date === today && !['cancelled', 'checked_out'].includes(r.status)).length;
  const departing = allReservations.filter(r => r.check_out_date === today && r.status === 'checked_in').length;
  const pendingPay = allReservations.filter(r => ['pending', 'deposit_paid'].includes(r.status)).length;
  const revenue = allReservations.filter(r => !['cancelled'].includes(r.status)).reduce((s, r) => s + r.amount_paid, 0);

  document.getElementById('dashStats').innerHTML = `
    <div class="stat-card accent"><div class="stat-icon">🏨</div><div class="stat-value">${total}</div><div class="stat-label">Habitaciones Totales</div></div>
    <div class="stat-card success"><div class="stat-icon">🛏️</div><div class="stat-value">${occupied}</div><div class="stat-label">Ocupadas Ahora</div></div>
    <div class="stat-card info"><div class="stat-icon">🛬</div><div class="stat-value">${arriving}</div><div class="stat-label">Llegadas Hoy</div></div>
    <div class="stat-card warning"><div class="stat-icon">🛫</div><div class="stat-value">${departing}</div><div class="stat-label">Salidas Hoy</div></div>
    <div class="stat-card teal"><div class="stat-icon">📊</div><div class="stat-value">${total > 0 ? Math.round(occupied / total * 100) : 0}%</div><div class="stat-label">Ocupación</div></div>
    <div class="stat-card purple"><div class="stat-icon">💰</div><div class="stat-value">${fmtMoney(revenue)}</div><div class="stat-label">Ingresos Cobrados</div></div>
  `;

  const arrivalsToday = allReservations.filter(r => r.check_in_date === today && !['cancelled', 'checked_out'].includes(r.status));
  document.getElementById('dashArrivals').innerHTML = arrivalsToday.length ? arrivalsToday.map(r => `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border-light)">
      <div><strong>${guestName(r.guest_id)}</strong>${r.additional_guests && r.additional_guests.length ? '<span style="color:var(--text-muted);font-size:0.8rem"> + ' + r.additional_guests.length + ' acomp.</span>' : ''}<br><span style="font-size:0.8rem;color:var(--text-muted)">Hab. ${roomLabel(r.room_id)} · ${catName(r.category_id)}</span></div>
      <div>${fmtStatus(r.status)}</div>
    </div>`).join('') : '<div class="empty-state"><div class="empty-icon">🛬</div><p>No hay llegadas programadas para hoy</p></div>';

  const depsToday = allReservations.filter(r => r.check_out_date === today && r.status === 'checked_in');
  document.getElementById('dashDepartures').innerHTML = depsToday.length ? depsToday.map(r => `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border-light)">
      <div><strong>${guestName(r.guest_id)}</strong>${r.additional_guests && r.additional_guests.length ? '<span style="color:var(--text-muted);font-size:0.8rem"> + ' + r.additional_guests.length + ' acomp.</span>' : ''}<br><span style="font-size:0.8rem;color:var(--text-muted)">Hab. ${roomLabel(r.room_id)}</span></div>
      <button class="btn btn-sm btn-warning" onclick="doCheckout(${r.id})">Check-out</button>
    </div>`).join('') : '<div class="empty-state"><div class="empty-icon">🛫</div><p>No hay salidas programadas para hoy</p></div>';
}

// ═══════════════════════════════════════════════════════════════
// CALENDAR
// ═══════════════════════════════════════════════════════════════
function calendarPrev() { calendarStart.setDate(calendarStart.getDate() - 7); renderCalendar(); }
function calendarNext() { calendarStart.setDate(calendarStart.getDate() + 7); renderCalendar(); }
function calendarToday() { calendarStart = new Date(); calendarStart.setHours(0, 0, 0, 0); renderCalendar(); }

function renderCalendar() {
  const days = 14;
  const dates = [];
  for (let i = 0; i < days; i++) { const d = new Date(calendarStart); d.setDate(d.getDate() + i); dates.push(d); }
  const today = todayStr();
  const cols = days + 1;

  const catColors = {};
  const palette = ['#6366f1', '#10b981', '#f59e0b', '#3b82f6', '#ef4444', '#8b5cf6', '#14b8a6'];
  allCategories.forEach((c, i) => catColors[c.id] = palette[i % palette.length]);

  const sortedRooms = [...allRooms].sort((a, b) => a.room_number.localeCompare(b.room_number, undefined, { numeric: true }));

  let html = `<div class="calendar-grid" style="grid-template-columns:140px repeat(${days},1fr)">`;
  // Header row
  html += `<div class="calendar-header-cell" style="font-weight:700">Habitación</div>`;
  dates.forEach(d => {
    const ds = d.toISOString().split('T')[0];
    const isToday = ds === today;
    const dayName = d.toLocaleDateString('es-AR', { weekday: 'short' });
    const dayNum = d.getDate();
    const month = d.toLocaleDateString('es-AR', { month: 'short' });
    html += `<div class="calendar-header-cell${isToday ? ' today' : ''}">${dayName}<br><strong>${dayNum}</strong> ${month}</div>`;
  });

  // Room rows
  sortedRooms.forEach(room => {
    const color = catColors[room.category_id] || '#6366f1';
    html += `<div class="calendar-room-label"><span class="room-cat-dot" style="background:${color}"></span>${room.room_number}</div>`;

    dates.forEach(d => {
      const ds = d.toISOString().split('T')[0];
      const res = allReservations.find(r =>
        r.room_id === room.id &&
        r.check_in_date <= ds && r.check_out_date > ds &&
        !['cancelled', 'checked_out'].includes(r.status)
      );
      if (res) {
        const isStart = res.check_in_date === ds;
        const gn = guestName(res.guest_id);
        html += `<div class="calendar-cell occupied">`;
        if (isStart) {
          let extra = res.additional_guests && res.additional_guests.length ? \` (+\${res.additional_guests.length})\` : '';
          html += \`<div class="calendar-booking status-\${res.status}" onclick="showReservationDetail(\${res.id})" title="\${gn}\${extra} (\${res.confirmation_code})">\${gn}\${extra}</div>\`;
        } else {
          html += `<div class="calendar-booking status-${res.status}" style="opacity:0.6" onclick="showReservationDetail(${res.id})"></div>`;
        }
        html += `</div>`;
      } else {
        html += `<div class="calendar-cell"></div>`;
      }
    });
  });

  html += '</div>';
  document.getElementById('calendarGrid').innerHTML = html;
}

// ═══════════════════════════════════════════════════════════════
// RESERVATIONS
// ═══════════════════════════════════════════════════════════════
function renderReservations() {
  filterReservations();
}

function filterReservations() {
  const search = (document.getElementById('resSearch')?.value || '').toLowerCase();
  const status = document.getElementById('resStatusFilter')?.value || '';
  let filtered = allReservations;
  if (status) filtered = filtered.filter(r => r.status === status);
  if (search) filtered = filtered.filter(r => r.confirmation_code.toLowerCase().includes(search) || guestName(r.guest_id).toLowerCase().includes(search));
  filtered = filtered.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  document.getElementById('resTbody').innerHTML = filtered.length ? filtered.map(r => `<tr>
    <td><strong style="color:var(--accent);cursor:pointer" onclick="showReservationDetail(${r.id})">${r.confirmation_code}</strong></td>
    <td>${guestName(r.guest_id)}</td>
    <td>${roomLabel(r.room_id)}</td>
    <td>${fmtDate(r.check_in_date)}</td>
    <td>${fmtDate(r.check_out_date)}</td>
    <td>${fmtMoney(r.total_amount)}</td>
    <td style="color:${r.balance_due > 0 ? 'var(--danger)' : 'var(--success)'};font-weight:600">${fmtMoney(r.balance_due)}</td>
    <td>${fmtStatus(r.status)}</td>
    <td>
      ${r.status === 'fully_paid' ? `<button class="btn btn-sm btn-success" onclick="doCheckin(${r.id})">Check-in</button>` : ''}
      ${r.status === 'checked_in' ? `<button class="btn btn-sm btn-warning" onclick="doCheckout(${r.id})">Check-out</button>` : ''}
      ${['pending', 'deposit_paid'].includes(r.status) ? `<button class="btn btn-sm btn-primary" onclick="openPaymentModal(${r.id})">💰 Pagar</button>` : ''}
    </td>
  </tr>`).join('') : '<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">📋</div><h3>Sin reservas</h3><p>No se encontraron reservas con los filtros aplicados</p></div></td></tr>';
}

function showReservationDetail(id) {
  const r = allReservations.find(x => x.id === id);
  if (!r) return;
  const g = allGuests.find(x => x.id === r.guest_id);
  openModal(`
    <div class="modal-header"><h2>📋 Reserva ${r.confirmation_code}</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
    <div class="modal-body">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div>
          <h4 style="margin-bottom:12px">👤 Huésped</h4>
          <p><strong>${g ? g.first_name + ' ' + g.last_name : '—'}</strong></p>
          <p style="color:var(--text-muted);font-size:0.85rem">${g?.email || ''} · ${g?.phone || ''}</p>
          <p style="color:var(--text-muted);font-size:0.85rem">${g?.document_type || ''} ${g?.document_number || ''}</p>
        </div>
        <div>
          <h4 style="margin-bottom:12px">🏨 Estancia</h4>
          <p>Hab. <strong>${roomLabel(r.room_id)}</strong> · ${catName(r.category_id)}</p>
          <p>${fmtDate(r.check_in_date)} → ${fmtDate(r.check_out_date)} (${r.nights} noches)</p>
          <p>Estado: ${fmtStatus(r.status)}</p>
        </div>
      </div>
      <hr style="margin:20px 0;border:none;border-top:1px solid var(--border-light)">
      <h4 style="margin-bottom:12px">💰 Finanzas</h4>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;text-align:center">
        <div style="padding:16px;background:var(--bg-body);border-radius:var(--radius-md)"><div style="font-size:1.3rem;font-weight:700">${fmtMoney(r.total_amount)}</div><div style="font-size:0.8rem;color:var(--text-muted)">Total</div></div>
        <div style="padding:16px;background:var(--success-light);border-radius:var(--radius-md)"><div style="font-size:1.3rem;font-weight:700;color:var(--success)">${fmtMoney(r.amount_paid)}</div><div style="font-size:0.8rem;color:var(--text-muted)">Pagado</div></div>
        <div style="padding:16px;background:${r.balance_due > 0 ? 'var(--danger-light)' : 'var(--success-light)'};border-radius:var(--radius-md)"><div style="font-size:1.3rem;font-weight:700;color:${r.balance_due > 0 ? 'var(--danger)' : 'var(--success)'}">${fmtMoney(r.balance_due)}</div><div style="font-size:0.8rem;color:var(--text-muted)">Saldo</div></div>
      </div>
    </div>
    <div class="modal-footer">
      ${r.balance_due > 0 && !['cancelled', 'checked_out'].includes(r.status) ? `<button class="btn btn-primary" onclick="closeModal();openPaymentModal(${r.id})">💰 Registrar Pago</button>` : ''}
      ${r.status === 'fully_paid' ? `<button class="btn btn-success" onclick="closeModal();doCheckin(${r.id})">🛎️ Check-in</button>` : ''}
      ${r.status === 'checked_in' ? `<button class="btn btn-warning" onclick="closeModal();doCheckout(${r.id})">🛫 Check-out</button>` : ''}
      <button class="btn btn-outline" onclick="closeModal()">Cerrar</button>
    </div>`, true);
}

// ── NEW RESERVATION MODAL ──
function openNewReservationModal() {
  const guestOpts = allGuests.map(g => `<option value="${g.id}">${g.first_name} ${g.last_name}</option>`).join('');
  const catOpts = allCategories.map(c => `<option value="${c.id}">${c.name} — ${fmtMoney(c.base_price_per_night)}/noche</option>`).join('');
  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1);
  const dayAfter = new Date(); dayAfter.setDate(dayAfter.getDate() + 2);

  openModal(`
    <div class="modal-header"><h2>📝 Nueva Reserva</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
    <div class="modal-body">
      <div class="form-group"><label>Huésped <span class="required">*</span></label>
        <select class="form-control" id="nrGuest">${guestOpts.length ? guestOpts : '<option value="">— Primero cree un huésped —</option>'}</select>
      </div>
      <div class="form-group"><label>Categoría de Habitación <span class="required">*</span></label>
        <select class="form-control" id="nrCategory">${catOpts}</select>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Fecha Check-in <span class="required">*</span></label><input type="date" class="form-control" id="nrCheckin" value="${tomorrow.toISOString().split('T')[0]}"></div>
        <div class="form-group"><label>Fecha Check-out <span class="required">*</span></label><input type="date" class="form-control" id="nrCheckout" value="${dayAfter.toISOString().split('T')[0]}"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Adultos</label><input type="number" class="form-control" id="nrAdults" value="1" min="1"></div>
        <div class="form-group"><label>Niños</label><input type="number" class="form-control" id="nrChildren" value="0" min="0"></div>
      </div>
      <div class="form-group"><label>Notas</label><textarea class="form-control" id="nrNotes" rows="2" placeholder="Observaciones opcionales..."></textarea></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="submitNewReservation()">✅ Crear Reserva</button>
    </div>`);
}

async function submitNewReservation() {
  try {
    const data = {
      guest_id: parseInt(document.getElementById('nrGuest').value),
      category_id: parseInt(document.getElementById('nrCategory').value),
      check_in_date: document.getElementById('nrCheckin').value,
      check_out_date: document.getElementById('nrCheckout').value,
      num_adults: parseInt(document.getElementById('nrAdults').value),
      num_children: parseInt(document.getElementById('nrChildren').value),
      notes: document.getElementById('nrNotes').value || null,
    };
    if (!data.guest_id) { toast('Seleccione un huésped', 'warning'); return; }
    const res = await api('/api/reservations/', 'POST', data);
    closeModal();
    toast(`Reserva ${res.confirmation_code} creada exitosamente — Total: ${fmtMoney(res.total_amount)}`, 'success');
    await loadAllData();
    if (document.querySelector('#sec-reservations.active')) renderReservations();
    else if (document.querySelector('#sec-dashboard.active')) renderDashboard();
  } catch (e) { toast(e.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════════
// GUESTS
// ═══════════════════════════════════════════════════════════════
async function loadGuests() {
  const search = document.getElementById('guestSearch')?.value || '';
  try {
    allGuests = await api(`/api/guests/?search=${encodeURIComponent(search)}&limit=100`);
    renderGuests();
  } catch (e) { console.error(e); }
}

function renderGuests() {
  document.getElementById('guestsTbody').innerHTML = allGuests.length ? allGuests.map(g => `<tr>
    <td><strong>${g.first_name} ${g.last_name}</strong></td>
    <td>${g.document_type ? `${g.document_type}: ${g.document_number}` : '<span style="color:var(--danger)">⚠️ Sin documento</span>'}</td>
    <td>${g.nationality || '—'}</td>
    <td>${g.email || '—'}</td>
    <td>${g.phone || '—'}</td>
    <td>${g.terms_accepted ? '<span style="color:var(--success)">✅ Sí</span>' : '<span style="color:var(--danger)">❌ No</span>'}</td>
    <td><button class="btn btn-sm btn-outline" onclick="openEditGuestModal(${g.id})">✏️ Editar</button></td>
  </tr>`).join('') : '<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">👤</div><h3>Sin huéspedes</h3><p>Agregue un huésped para comenzar</p></div></td></tr>';
}

function openNewGuestModal() {
  openModal(`
    <div class="modal-header"><h2>👤 Nuevo Huésped</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
    <div class="modal-body">
      <div class="form-row">
        <div class="form-group"><label>Nombre <span class="required">*</span></label><input type="text" class="form-control" id="ngFirst" placeholder="Carlos"></div>
        <div class="form-group"><label>Apellido <span class="required">*</span></label><input type="text" class="form-control" id="ngLast" placeholder="Pérez"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Tipo Documento</label><select class="form-control" id="ngDocType"><option value="">Seleccionar...</option><option value="DNI">DNI</option><option value="PASSPORT">Pasaporte</option><option value="CEDULA">Cédula</option><option value="OTHER">Otro</option></select></div>
        <div class="form-group"><label>Nro Documento</label><input type="text" class="form-control" id="ngDocNum" placeholder="12345678"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Nacionalidad</label><input type="text" class="form-control" id="ngNat" placeholder="Argentina"></div>
        <div class="form-group"><label>Email</label><input type="email" class="form-control" id="ngEmail" placeholder="email@ejemplo.com"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Teléfono</label><input type="text" class="form-control" id="ngPhone" placeholder="+54 11 1234 5678"></div>
        <div class="form-group"><label>País</label><input type="text" class="form-control" id="ngCountry" placeholder="Argentina"></div>
      </div>
      <div class="form-group" style="display:flex;align-items:center;gap:10px">
        <label class="toggle-switch"><input type="checkbox" id="ngTerms"><span class="toggle-slider"></span></label>
        <span style="font-size:0.88rem">Acepta términos y condiciones</span>
      </div>
      <div class="form-group"><label>Observaciones</label><textarea class="form-control" id="ngObs" rows="2"></textarea></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="submitNewGuest()">✅ Guardar Huésped</button>
    </div>`, true);
}

async function submitNewGuest() {
  try {
    const data = {
      first_name: document.getElementById('ngFirst').value,
      last_name: document.getElementById('ngLast').value,
      document_type: document.getElementById('ngDocType').value || null,
      document_number: document.getElementById('ngDocNum').value || null,
      nationality: document.getElementById('ngNat').value || null,
      email: document.getElementById('ngEmail').value || null,
      phone: document.getElementById('ngPhone').value || null,
      country: document.getElementById('ngCountry').value || null,
      terms_accepted: document.getElementById('ngTerms').checked,
      observations: document.getElementById('ngObs').value || null,
    };
    if (!data.first_name || !data.last_name) { toast('Nombre y apellido son obligatorios', 'warning'); return; }
    await api('/api/guests/', 'POST', data);
    closeModal();
    toast('Huésped creado exitosamente', 'success');
    await loadAllData();
    if (document.querySelector('#sec-guests.active')) renderGuests();
  } catch (e) { toast(e.message, 'error'); }
}

function openEditGuestModal(id) {
  const g = allGuests.find(x => x.id === id);
  if (!g) return;
  openModal(`
    <div class="modal-header"><h2>✏️ Editar Huésped</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
    <div class="modal-body">
      <div class="form-row">
        <div class="form-group"><label>Nombre <span class="required">*</span></label><input type="text" class="form-control" id="egFirst" value="${g.first_name}"></div>
        <div class="form-group"><label>Apellido <span class="required">*</span></label><input type="text" class="form-control" id="egLast" value="${g.last_name}"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Tipo Documento</label><select class="form-control" id="egDocType">
          <option value="">Seleccionar...</option><option value="DNI" ${g.document_type === 'DNI' ? 'selected' : ''}>DNI</option><option value="PASSPORT" ${g.document_type === 'PASSPORT' ? 'selected' : ''}>Pasaporte</option><option value="CEDULA" ${g.document_type === 'CEDULA' ? 'selected' : ''}>Cédula</option></select></div>
        <div class="form-group"><label>Nro Documento</label><input type="text" class="form-control" id="egDocNum" value="${g.document_number || ''}"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Nacionalidad</label><input type="text" class="form-control" id="egNat" value="${g.nationality || ''}"></div>
        <div class="form-group"><label>Email</label><input type="email" class="form-control" id="egEmail" value="${g.email || ''}"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Teléfono</label><input type="text" class="form-control" id="egPhone" value="${g.phone || ''}"></div>
        <div class="form-group"><label>País</label><input type="text" class="form-control" id="egCountry" value="${g.country || ''}"></div>
      </div>
      <div class="form-group" style="display:flex;align-items:center;gap:10px">
        <label class="toggle-switch"><input type="checkbox" id="egTerms" ${g.terms_accepted ? 'checked' : ''}><span class="toggle-slider"></span></label>
        <span style="font-size:0.88rem">Acepta términos y condiciones</span>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="submitEditGuest(${g.id})">💾 Guardar Cambios</button>
    </div>`, true);
}

async function submitEditGuest(id) {
  try {
    const data = {
      first_name: document.getElementById('egFirst').value,
      last_name: document.getElementById('egLast').value,
      document_type: document.getElementById('egDocType').value || null,
      document_number: document.getElementById('egDocNum').value || null,
      nationality: document.getElementById('egNat').value || null,
      email: document.getElementById('egEmail').value || null,
      phone: document.getElementById('egPhone').value || null,
      country: document.getElementById('egCountry').value || null,
      terms_accepted: document.getElementById('egTerms').checked,
    };
    await api(`/api/guests/${id}`, 'PATCH', data);
    closeModal();
    toast('Huésped actualizado', 'success');
    await loadAllData();
    renderGuests();
  } catch (e) { toast(e.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════════
// CHECK-IN / CHECK-OUT
// ═══════════════════════════════════════════════════════════════
function renderCheckin() {
  const readyForCheckin = allReservations.filter(r => r.status === 'fully_paid');
  const checkedIn = allReservations.filter(r => r.status === 'checked_in');

  document.getElementById('ciCount').textContent = readyForCheckin.length;
  document.getElementById('coCount').textContent = checkedIn.length;

  document.getElementById('checkinList').innerHTML = readyForCheckin.length ? readyForCheckin.map(r => `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 0;border-bottom:1px solid var(--border-light)">
      <div>
        <strong>${guestName(r.guest_id)}</strong><br>
        <span style="font-size:0.82rem;color:var(--text-muted)">Hab. ${roomLabel(r.room_id)} · ${catName(r.category_id)} · ${fmtDate(r.check_in_date)} → ${fmtDate(r.check_out_date)}</span>
      </div>
      <button class="btn btn-sm btn-success" onclick="doCheckin(${r.id})">🛎️ Check-in</button>
    </div>`).join('') : '<div class="empty-state"><div class="empty-icon">✅</div><h3>Todo al día</h3><p>No hay reservas pendientes de check-in</p></div>';

  document.getElementById('checkoutList').innerHTML = checkedIn.length ? checkedIn.map(r => `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 0;border-bottom:1px solid var(--border-light)">
      <div>
        <strong>${guestName(r.guest_id)}</strong><br>
        <span style="font-size:0.82rem;color:var(--text-muted)">Hab. ${roomLabel(r.room_id)} · Sale ${fmtDate(r.check_out_date)}</span>
      </div>
      <button class="btn btn-sm btn-warning" onclick="doCheckout(${r.id})">🛫 Check-out</button>
    </div>`).join('') : '<div class="empty-state"><div class="empty-icon">🏨</div><h3>Sin huéspedes</h3><p>No hay huéspedes alojados actualmente</p></div>';
}

async function doCheckin(id) {
  try {
    await api(`/api/checkin/${id}`, 'POST');
    toast('✅ Check-in realizado con éxito', 'success');
    await loadAllData();
    renderCheckin();
    if (document.querySelector('#sec-reservations.active')) renderReservations();
    if (document.querySelector('#sec-dashboard.active')) renderDashboard();
  } catch (e) { toast(e.message, 'error'); }
}

async function doCheckout(id) {
  try {
    await api(`/api/checkin/checkout/${id}`, 'POST');
    toast('✅ Check-out realizado con éxito', 'success');
    await loadAllData();
    renderCheckin();
    if (document.querySelector('#sec-reservations.active')) renderReservations();
    if (document.querySelector('#sec-dashboard.active')) renderDashboard();
  } catch (e) { toast(e.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════════
// PAYMENTS
// ═══════════════════════════════════════════════════════════════
function openPaymentModal(resId) {
  const r = allReservations.find(x => x.id === resId);
  if (!r) return;
  openModal(`
    <div class="modal-header"><h2>💰 Registrar Pago</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
    <div class="modal-body">
      <div style="background:var(--bg-body);border-radius:var(--radius-md);padding:16px;margin-bottom:20px">
        <strong>${r.confirmation_code}</strong> — ${guestName(r.guest_id)}<br>
        <span style="font-size:0.85rem;color:var(--text-muted)">Total: ${fmtMoney(r.total_amount)} · Pagado: ${fmtMoney(r.amount_paid)} · <strong style="color:var(--danger)">Saldo: ${fmtMoney(r.balance_due)}</strong></span>
      </div>
      <div class="form-group"><label>Monto a pagar <span class="required">*</span></label>
        <input type="number" class="form-control" id="payAmount" value="${r.balance_due.toFixed(2)}" step="0.01" min="0.01" max="${r.balance_due.toFixed(2)}">
      </div>
      <div class="form-group"><label>Método de Pago <span class="required">*</span></label>
        <select class="form-control" id="payMethod">
          ${hotelConfig.enable_cash ? '<option value="cash">💵 Efectivo</option>' : ''}
          ${hotelConfig.enable_mercado_pago ? '<option value="mercado_pago">📱 Mercado Pago</option>' : ''}
          ${hotelConfig.enable_paypal ? '<option value="paypal">🅿️ PayPal</option>' : ''}
          ${hotelConfig.enable_credit_card ? '<option value="credit_card">💳 Tarjeta Crédito</option>' : ''}
          ${hotelConfig.enable_debit_card ? '<option value="debit_card">💳 Tarjeta Débito</option>' : ''}
        </select>
      </div>
      <div class="form-group"><label>Tipo de Transacción</label>
        <select class="form-control" id="payType">
          <option value="deposit">Seña / Depósito</option>
          <option value="balance_payment" ${r.status === 'deposit_paid' ? 'selected' : ''}>Pago de Saldo</option>
          <option value="full_payment">Pago Total</option>
          <option value="partial_payment">Pago Parcial</option>
        </select>
      </div>
      <div class="form-group"><label>Descripción</label><input type="text" class="form-control" id="payDesc" placeholder="Descripción opcional..."></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="submitPayment(${resId})">💰 Confirmar Pago</button>
    </div>`);
}

async function submitPayment(resId) {
  try {
    const data = {
      reservation_id: resId,
      amount: parseFloat(document.getElementById('payAmount').value),
      payment_method: document.getElementById('payMethod').value,
      transaction_type: document.getElementById('payType').value,
      description: document.getElementById('payDesc').value || null,
    };
    await api('/api/payments/', 'POST', data);
    closeModal();
    toast('Pago procesado exitosamente', 'success');
    await loadAllData();
    if (document.querySelector('#sec-reservations.active')) renderReservations();
    if (document.querySelector('#sec-checkin.active')) renderCheckin();
    if (document.querySelector('#sec-dashboard.active')) renderDashboard();
    if (document.querySelector('#sec-payments.active')) searchPayment();
  } catch (e) { toast(e.message, 'error'); }
}

async function searchPayment() {
  const code = document.getElementById('paySearch')?.value?.trim();
  if (!code) {
    document.getElementById('paymentDetail').innerHTML = '<div class="empty-state"><div class="empty-icon">🔍</div><h3>Buscar Reserva</h3><p>Ingrese un código de reserva para ver su detalle financiero</p></div>';
    return;
  }
  const r = allReservations.find(x => x.confirmation_code.toLowerCase().includes(code.toLowerCase()));
  if (!r) { document.getElementById('paymentDetail').innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><h3>No encontrada</h3><p>No se encontró una reserva con ese código</p></div>'; return; }

  try {
    const summary = await api(`/api/payments/summary/${r.id}`);
    document.getElementById('paymentDetail').innerHTML = `
      <div class="card" style="margin-bottom:20px">
        <div class="card-header"><h3>📋 Reserva ${summary.confirmation_code}</h3>${fmtStatus(summary.status)}</div>
        <div class="card-body">
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;text-align:center;margin-bottom:20px">
            <div style="padding:16px;background:var(--bg-body);border-radius:var(--radius-md)"><div style="font-size:1.5rem;font-weight:800">${fmtMoney(summary.total_amount)}</div><div style="font-size:0.8rem;color:var(--text-muted)">Total</div></div>
            <div style="padding:16px;background:var(--info-light);border-radius:var(--radius-md)"><div style="font-size:1.5rem;font-weight:800;color:var(--info)">${fmtMoney(summary.deposit_required)}</div><div style="font-size:0.8rem;color:var(--text-muted)">Seña Requerida</div></div>
            <div style="padding:16px;background:var(--success-light);border-radius:var(--radius-md)"><div style="font-size:1.5rem;font-weight:800;color:var(--success)">${fmtMoney(summary.amount_paid)}</div><div style="font-size:0.8rem;color:var(--text-muted)">Pagado</div></div>
            <div style="padding:16px;background:${summary.balance_due > 0 ? 'var(--danger-light)' : 'var(--success-light)'};border-radius:var(--radius-md)"><div style="font-size:1.5rem;font-weight:800;color:${summary.balance_due > 0 ? 'var(--danger)' : 'var(--success)'}">${fmtMoney(summary.balance_due)}</div><div style="font-size:0.8rem;color:var(--text-muted)">Saldo</div></div>
          </div>
          ${summary.balance_due > 0 ? `<button class="btn btn-primary" onclick="openPaymentModal(${r.id})" style="margin-bottom:20px">💰 Registrar Pago</button>` : ''}
          <h4 style="margin-bottom:12px">📜 Historial de Transacciones</h4>
          <table><thead><tr><th>ID</th><th>Monto</th><th>Método</th><th>Tipo</th><th>Estado</th><th>Fecha</th></tr></thead><tbody>
          ${summary.transactions.length ? summary.transactions.map(t => `<tr>
            <td>#${t.id}</td>
            <td><strong>${fmtMoney(t.amount)}</strong></td>
            <td>${{ cash: '💵 Efectivo', mercado_pago: '📱 MP', paypal: '🅿️ PayPal', credit_card: '💳 Crédito', debit_card: '💳 Débito' }[t.method] || t.method}</td>
            <td>${{ deposit: 'Seña', full_payment: 'Pago Total', balance_payment: 'Saldo', partial_payment: 'Parcial', refund: 'Reembolso' }[t.type] || t.type}</td>
            <td><span class="badge badge-${t.status === 'completed' ? 'checked_in' : 'pending'}">${t.status === 'completed' ? '✅ Completado' : '⏳ Pendiente'}</span></td>
            <td style="font-size:0.8rem;color:var(--text-muted)">${new Date(t.created_at).toLocaleString('es-AR')}</td>
          </tr>`).join('') : '<tr><td colspan="6"><div class="empty-state"><p>Sin transacciones</p></div></td></tr>'}
          </tbody></table>
        </div>
      </div>`;
  } catch (e) { toast(e.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════════
// ROOMS
// ═══════════════════════════════════════════════════════════════
function renderRooms() {
  const catColors = {};
  const palette = ['#6366f1', '#10b981', '#f59e0b', '#3b82f6', '#ef4444', '#8b5cf6', '#14b8a6'];
  allCategories.forEach((c, i) => catColors[c.id] = palette[i % palette.length]);

  let html = '';
  allCategories.forEach(cat => {
    const catRooms = allRooms.filter(r => r.category_id === cat.id).sort((a, b) => a.room_number.localeCompare(b.room_number, undefined, { numeric: true }));
    const color = catColors[cat.id];
    html += `
      <div class="card" style="margin-bottom:20px">
        <div class="card-header">
          <h3><span style="display:inline-block;width:12px;height:12px;background:${color};border-radius:3px;margin-right:8px;vertical-align:middle"></span>${cat.name} <span style="font-weight:400;color:var(--text-muted)">(${cat.code})</span></h3>
          <span style="font-size:0.85rem;color:var(--text-muted)">${fmtMoney(cat.base_price_per_night)}/noche · Máx ${cat.max_occupancy} personas · ${catRooms.length} hab.</span>
        </div>
        <div class="card-body" style="display:flex;flex-wrap:wrap;gap:10px">
          ${catRooms.map(r => {
      const occupied = allReservations.some(res => res.room_id === r.id && res.status === 'checked_in');
      return `<div style="width:90px;padding:14px;text-align:center;border-radius:var(--radius-md);border:1.5px solid ${occupied ? 'var(--success)' : 'var(--border)'};background:${occupied ? 'var(--success-light)' : 'var(--bg-input)'};transition:var(--transition);cursor:default">
              <div style="font-size:1.1rem;font-weight:700">${r.room_number}</div>
              <div style="font-size:0.72rem;color:var(--text-muted)">Piso ${r.floor}</div>
              <div style="font-size:0.68rem;margin-top:4px">${occupied ? '<span style="color:var(--success)">🟢 Ocupada</span>' : '<span style="color:var(--text-muted)">⚪ Libre</span>'}</div>
            </div>`;
    }).join('')}
        </div>
      </div>`;
  });
  document.getElementById('roomsGrid').innerHTML = html;
}

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════
function renderConfig() {
  const c = hotelConfig;
  document.getElementById('configPanel').innerHTML = `
    <div class="config-grid">
      <div class="config-card">
        <h3>💰 Políticas Financieras</h3>
        <div class="config-item">
          <div><div class="config-item-label">Porcentaje de Seña</div><div class="config-item-desc">Monto requerido como depósito al reservar</div></div>
          <div style="display:flex;align-items:center;gap:8px"><input type="number" class="form-control" style="width:80px" id="cfgDeposit" value="${c.deposit_percentage}" min="0" max="100" step="5"><span>%</span></div>
        </div>
        <div class="config-item">
          <div><div class="config-item-label">Permitir Pago Total</div><div class="config-item-desc">Clientes pueden pagar el 100% al reservar</div></div>
          <label class="toggle-switch"><input type="checkbox" id="cfgFullPay" ${c.enable_full_payment ? 'checked' : ''}><span class="toggle-slider"></span></label>
        </div>
        <div class="config-item">
          <div><div class="config-item-label">Permitir Pago de Seña</div><div class="config-item-desc">Clientes pueden pagar solo el depósito</div></div>
          <label class="toggle-switch"><input type="checkbox" id="cfgDepPay" ${c.enable_deposit_payment ? 'checked' : ''}><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="config-card">
        <h3>💳 Pasarelas de Pago</h3>
        <div class="config-item"><div class="config-item-label">💵 Efectivo</div><label class="toggle-switch"><input type="checkbox" id="cfgCash" ${c.enable_cash ? 'checked' : ''}><span class="toggle-slider"></span></label></div>
        <div class="config-item"><div class="config-item-label">📱 Mercado Pago</div><label class="toggle-switch"><input type="checkbox" id="cfgMP" ${c.enable_mercado_pago ? 'checked' : ''}><span class="toggle-slider"></span></label></div>
        <div class="config-item"><div class="config-item-label">🅿️ PayPal</div><label class="toggle-switch"><input type="checkbox" id="cfgPP" ${c.enable_paypal ? 'checked' : ''}><span class="toggle-slider"></span></label></div>
        <div class="config-item"><div class="config-item-label">💳 Tarjeta Crédito</div><label class="toggle-switch"><input type="checkbox" id="cfgCC" ${c.enable_credit_card ? 'checked' : ''}><span class="toggle-slider"></span></label></div>
        <div class="config-item"><div class="config-item-label">💳 Tarjeta Débito</div><label class="toggle-switch"><input type="checkbox" id="cfgDC" ${c.enable_debit_card ? 'checked' : ''}><span class="toggle-slider"></span></label></div>
        <div class="config-item"><div class="config-item-label">🏦 Transferencia Bancaria</div><label class="toggle-switch"><input type="checkbox" id="cfgBT" ${c.enable_bank_transfer ? 'checked' : ''}><span class="toggle-slider"></span></label></div>
      </div>
      <div class="config-card">
        <h3>🛎️ Políticas de Check-in</h3>
        <div class="config-item">
          <div><div class="config-item-label">Requerir Documento</div><div class="config-item-desc">DNI/Pasaporte obligatorio para check-in</div></div>
          <label class="toggle-switch"><input type="checkbox" id="cfgReqDoc" ${c.require_document_for_checkin ? 'checked' : ''}><span class="toggle-slider"></span></label>
        </div>
        <div class="config-item">
          <div><div class="config-item-label">Aceptación de Términos</div><div class="config-item-desc">Huésped debe aceptar T&C para check-in</div></div>
          <label class="toggle-switch"><input type="checkbox" id="cfgReqTerms" ${c.require_terms_acceptance ? 'checked' : ''}><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="config-card">
        <h3>🌐 Cancelación y OTA</h3>
        <div class="config-item">
          <div><div class="config-item-label">Horas de Cancelación Gratis</div><div class="config-item-desc">Tiempo para cancelar sin cargo</div></div>
          <div style="display:flex;align-items:center;gap:8px"><input type="number" class="form-control" style="width:80px" id="cfgCancelHrs" value="${c.free_cancellation_hours}" min="0"><span>hrs</span></div>
        </div>
        <div class="config-item">
          <div><div class="config-item-label">Sync Booking.com</div></div>
          <label class="toggle-switch"><input type="checkbox" id="cfgBooking" ${c.enable_booking_sync ? 'checked' : ''}><span class="toggle-slider"></span></label>
        </div>
        <div class="config-item">
          <div><div class="config-item-label">Sync Expedia</div></div>
          <label class="toggle-switch"><input type="checkbox" id="cfgExpedia" ${c.enable_expedia_sync ? 'checked' : ''}><span class="toggle-slider"></span></label>
        </div>
      </div>
    </div>
    <div style="margin-top:24px;text-align:right">
      <button class="btn btn-primary btn-lg" onclick="saveConfig()">💾 Guardar Configuración</button>
    </div>`;
}

async function saveConfig() {
  try {
    const data = {
      deposit_percentage: parseFloat(document.getElementById('cfgDeposit').value),
      enable_full_payment: document.getElementById('cfgFullPay').checked,
      enable_deposit_payment: document.getElementById('cfgDepPay').checked,
      enable_cash: document.getElementById('cfgCash').checked,
      enable_mercado_pago: document.getElementById('cfgMP').checked,
      enable_paypal: document.getElementById('cfgPP').checked,
      enable_credit_card: document.getElementById('cfgCC').checked,
      enable_debit_card: document.getElementById('cfgDC').checked,
      enable_bank_transfer: document.getElementById('cfgBT').checked,
      require_document_for_checkin: document.getElementById('cfgReqDoc').checked,
      require_terms_acceptance: document.getElementById('cfgReqTerms').checked,
      free_cancellation_hours: parseInt(document.getElementById('cfgCancelHrs').value),
      enable_booking_sync: document.getElementById('cfgBooking').checked,
      enable_expedia_sync: document.getElementById('cfgExpedia').checked,
    };
    hotelConfig = await api('/api/config/', 'PATCH', data);
    toast('Configuración guardada exitosamente', 'success');
  } catch (e) { toast(e.message, 'error'); }
}
