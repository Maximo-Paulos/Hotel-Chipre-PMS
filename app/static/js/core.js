/* ═══ CORE: API, Navigation, Modals, Toast, Confirm ═══ */
const API = '/api';
let _confirmCb = null;
let _allReservations = [];
let _allGuests = [];
let _categories = [];
let _rooms = [];
let _config = {};
let _pricings = [];

// ── API helpers ──
async function api(path, opts = {}) {
  const o = { headers: { 'Content-Type': 'application/json' }, ...opts };
  if (o.body && typeof o.body === 'object') o.body = JSON.stringify(o.body);
  const r = await fetch(`${API}${path}`, o);
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || r.statusText); }
  if (r.status === 204) return null;
  return r.json();
}
const GET = p => api(p);
const POST = (p, b) => api(p, { method: 'POST', body: b });
const PATCH = (p, b) => api(p, { method: 'PATCH', body: b });

// ── Navigation ──
function navigate(section) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const sec = document.getElementById('sec-' + section);
  const nav = document.querySelector(`.nav-item[data-section="${section}"]`);
  if (sec) sec.classList.add('active');
  if (nav) nav.classList.add('active');
  const loaders = {
    dashboard: loadDashboard, calendar: loadCalendar, reservations: loadReservations,
    guests: loadGuests, checkin: loadCheckin, payments: () => {}, rooms: loadRooms,
    config: loadConfig, housekeeping: loadHousekeeping, reports: loadDailyReport
  };
  if (loaders[section]) loaders[section]();
}

// ── Modal ──
function openModal(html) {
  document.getElementById('modalContent').innerHTML = html;
  document.getElementById('modalOverlay').classList.add('active');
}
function closeModal() { document.getElementById('modalOverlay').classList.remove('active'); }

// ── Confirm Dialog ──
function showConfirm(title, msg, btnText, btnClass, cb) {
  document.getElementById('confirmTitle').textContent = title;
  document.getElementById('confirmMessage').textContent = msg;
  const btn = document.getElementById('confirmBtn');
  btn.textContent = btnText;
  btn.className = 'btn ' + (btnClass || 'btn-danger');
  _confirmCb = cb;
  document.getElementById('confirmOverlay').classList.add('active');
}
function closeConfirm() { document.getElementById('confirmOverlay').classList.remove('active'); _confirmCb = null; }
function executeConfirm() { if (_confirmCb) _confirmCb(); closeConfirm(); }

// ── Toast ──
function toast(msg, type = 'success') {
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.innerHTML = `<span class="toast-icon">${icons[type]||'ℹ️'}</span><span class="toast-message">${msg}</span><button class="toast-close" onclick="this.parentElement.remove()">✕</button>`;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// ── Formatting ──
function fmtDate(d) { if (!d) return '-'; return new Date(d + 'T12:00:00').toLocaleDateString('es-AR', { day: 'numeric', month: 'short', year: 'numeric' }); }
function fmtMoney(n) { return '$' + (n || 0).toLocaleString('es-AR', { minimumFractionDigits: 2 }); }
function fmtStatus(s) {
  const m = { pending: 'Pendiente', deposit_paid: 'Seña Pagada', fully_paid: 'Pago Total', checked_in: 'Alojado', checked_out: 'Check-out', cancelled: 'Cancelada' };
  return `<span class="badge badge-${s}">${m[s] || s}</span>`;
}
function fmtRoomStatus(s) {
  const m = { available: 'Disponible', occupied: 'Ocupada', cleaning: 'Limpieza', maintenance: 'Mantenimiento', blocked: 'Bloqueada' };
  return m[s] || s;
}
function todayStr() { return new Date().toISOString().split('T')[0]; }
function tomorrowStr() { const d = new Date(); d.setDate(d.getDate() + 1); return d.toISOString().split('T')[0]; }

// ── Print ──
function printReport() { window.print(); }

// ── Boot ──
document.addEventListener('DOMContentLoaded', async () => {
  try {
    [_categories, _rooms, _config, _pricings] = await Promise.all([GET('/rooms/categories'), GET('/rooms'), GET('/config/'), GET('/rooms/categories/pricing/all').catch(()=>[])]);
    document.getElementById('hotelNameSidebar').textContent = _config.hotel_name || 'Hotel PMS';
  } catch(e) { console.warn('Boot fetch error', e); }
  navigate('dashboard');
  document.getElementById('reportDate').value = todayStr();
});
