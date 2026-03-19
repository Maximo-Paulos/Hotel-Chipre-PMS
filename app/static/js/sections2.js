/* ═══ SECTIONS PART 2: Checkin, Payments, Housekeeping, Rooms, Reports, Config ═══ */

// ══════════════ CHECK-IN / OUT ══════════════
async function loadCheckin() {
  const reservations = await GET('/reservations/');
  const guests = _allGuests.length ? _allGuests : await GET('/guests/');
  // Pending check-in = fully_paid reservations
  const pendingCI = reservations.filter(r => r.status === 'fully_paid');
  const checkedIn = reservations.filter(r => r.status === 'checked_in');
  document.getElementById('ciCount').textContent = pendingCI.length;
  document.getElementById('coCount').textContent = checkedIn.length;

  document.getElementById('checkinList').innerHTML = pendingCI.length ? pendingCI.map(r => {
    const g = guests.find(x => x.id === r.guest_id);
    const gn = g ? g.first_name + ' ' + g.last_name : '--';
    const room = _rooms.find(rm => rm.id === r.room_id);
    return `<div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border-light)"><div><strong>${gn}</strong><br><small>${r.confirmation_code} · Hab. ${room ? room.room_number : '--'} · ${fmtDate(r.check_in_date)}</small></div><button class="btn btn-sm btn-success" onclick="openCheckinModal(${r.id}, ${r.guest_id}, '${r.confirmation_code}')">🛎️ Iniciar Check-in</button></div>`;
  }).join('') : '<div class="empty-state"><p>No hay check-ins pendientes</p></div>';

  document.getElementById('checkoutList').innerHTML = checkedIn.length ? checkedIn.map(r => {
    const g = guests.find(x => x.id === r.guest_id);
    const gn = g ? g.first_name + ' ' + g.last_name : '--';
    const room = _rooms.find(rm => rm.id === r.room_id);
    return `<div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border-light)"><div><strong>${gn}</strong><br><small>${r.confirmation_code} · Hab. ${room ? room.room_number : '--'} · Hasta ${fmtDate(r.check_out_date)}</small></div><div class="btn-group"><button class="btn btn-sm btn-primary" onclick="openExtendModal(${r.id})">📅 Extender</button><button class="btn btn-sm btn-warning" onclick="confirmCheckout(${r.id},'${r.confirmation_code}')">🛫 Check-out</button></div></div>`;
  }).join('') : '<div class="empty-state"><p>No hay huéspedes alojados actualmente</p></div>';
}

async function doCheckin(id) {
  try { await POST(`/checkin/${id}`); toast('Check-in realizado exitosamente'); loadCheckin(); } catch (e) { toast(e.message, 'error'); }
}

async function openCheckinModal(resId, guestId, code) {
  const g = _allGuests.find(x => x.id === guestId);
  const gn = g ? g.first_name + ' ' + g.last_name : 'Huésped Principal';
  
  openModal(`<div class="modal-header"><h2>Check-in: ${code}</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
  <div class="modal-body">
    <div style="background:var(--bg-body);padding:15px;border-radius:var(--radius-md);margin-bottom:20px;border:1px solid var(--border-light)">
        <h3 style="margin-bottom:10px;color:var(--accent);">Titular de la Reserva</h3>
        <p><strong>Nombres:</strong> ${gn}</p>
        <p><strong>Documento:</strong> ${g && g.document_number ? (g.document_type || 'DNI') + ' ' + g.document_number : 'No registrado'}</p>
    </div>
    
    <div style="background:var(--bg-body);padding:15px;border-radius:var(--radius-md);border:1px solid var(--border-light)">
        <h3 style="margin-bottom:10px;color:var(--info);">Acompañantes en la Habitación</h3>
        <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:15px">¿Se aloja alguien más en la habitación junto al titular? Ingresa sus datos para el registro hotelero.</p>
        
        <div id="companionsList"></div>
        <button class="btn btn-sm btn-outline" style="margin-top:10px;width:100%" onclick="addCompanionRow()">+ Añadir Acompañante a esta habitación</button>
    </div>
  </div>
  <div class="modal-footer">
    <button class="btn btn-outline" onclick="closeModal()">Cancelar</button>
    <button class="btn btn-success" onclick="processCheckinFlow(${resId}, ${guestId})">🛎️ Confirmar Check-in</button>
  </div>`);
}

function addCompanionRow() {
    const div = document.createElement('div');
    div.className = 'companion-row';
    div.style = 'display:grid;grid-template-columns:1fr 1fr 100px 100px 40px;gap:10px;margin-bottom:10px;align-items:end;background:#f9fafb;padding:10px;border-radius:var(--radius-md);border:1px solid var(--border-light);';
    div.innerHTML = `
        <div class="form-group" style="margin:0"><label style="font-size:0.75rem">Nombres</label><input type="text" class="form-control comp-fn" placeholder="Juan"></div>
        <div class="form-group" style="margin:0"><label style="font-size:0.75rem">Apellidos</label><input type="text" class="form-control comp-ln" placeholder="Pérez"></div>
        <div class="form-group" style="margin:0"><label style="font-size:0.75rem">Documento</label><select class="form-control comp-dt"><option value="DNI">DNI</option><option value="PASSPORT">Pasaporte</option></select></div>
        <div class="form-group" style="margin:0"><label style="font-size:0.75rem">Número</label><input type="text" class="form-control comp-dn"></div>
        <button class="btn btn-sm btn-danger" style="margin:0;height:42px" onclick="this.parentElement.remove()" title="Quitar">✕</button>
    `;
    document.getElementById('companionsList').appendChild(div);
}

async function processCheckinFlow(resId, guestId) {
    const rows = document.querySelectorAll('.companion-row');
    const companions = [];
    rows.forEach(r => {
        const fn = r.querySelector('.comp-fn').value.trim();
        const ln = r.querySelector('.comp-ln').value.trim();
        const dt = r.querySelector('.comp-dt').value;
        const dn = r.querySelector('.comp-dn').value.trim();
        if(fn && ln) {
            companions.push({
                first_name: fn,
                last_name: ln,
                document_type: dt || "DNI",
                document_number: dn || null
            });
        }
    });
    
    try {
        if(companions.length > 0) {
            await POST(`/reservations/${resId}/guests`, companions);
        }
        await POST(`/checkin/${resId}`);
        toast('Check-in completado exitosamente con acompañantes registrados');
        closeModal();
        loadCheckin();
        if (typeof loadDashboard === 'function') loadDashboard();
    } catch(e) {
        toast(e.message, 'error');
    }
}

function confirmCheckout(id, code) {
  showConfirm('Confirmar Check-out', `¿Realizar check-out de la reserva ${code}?`, '🛫 Check-out', 'btn-warning', async () => {
    try { await POST(`/checkin/checkout/${id}`); toast('Check-out realizado exitosamente'); loadCheckin(); } catch (e) { toast(e.message, 'error'); }
  });
}

// ══════════════ PAYMENTS ══════════════
// Global temporary state to calculate pricing
window.currentPaymentPricing = null;
window.currentResData = null;
window.currentSummary = null;

window.updatePaymentFormPricing = function() {
    if(!window.currentPaymentPricing || !window.currentSummary) return;
    const method = document.getElementById('payMethod').value;
    let key = method;
    if(key === 'bank_transfer') key = 'transfer';
    if(key === 'mercado_pago') key = 'mercadopago';
    
    const dynPrice = window.currentPaymentPricing['price_' + key];
    let newTotal = window.currentSummary.total_amount;
    let usedOverride = false;
    
    if(dynPrice && dynPrice > 0) {
        newTotal = dynPrice * window.currentResData.nights;
        usedOverride = true;
    }
    
    const newBalance = Math.max(0, newTotal - window.currentSummary.amount_paid);
    
    // Update visual values safely if they exist
    const elReq = document.getElementById('dynaRequired');
    if(elReq) elReq.textContent = fmtMoney(newTotal);
    const elBal = document.getElementById('dynaBalance');
    if(elBal) elBal.textContent = fmtMoney(newBalance);
    
    const badge = document.getElementById('dynaTariffBadge');
    if(badge) {
        if(usedOverride) {
            badge.innerHTML = `<span class="badge badge-info">💰 Tarifa ${method.toUpperCase()}: ${fmtMoney(dynPrice)}/noche</span>`;
        } else {
            badge.innerHTML = '';
        }
    }
    
    const payType = document.getElementById('payType').value;
    const amountInput = document.getElementById('payAmount');
    if(amountInput && (payType === 'full_payment' || payType === 'balance' || payType === 'deposit')) {
        amountInput.value = newBalance;
    }
};

async function searchPayment() {
  const q = document.getElementById('paySearch').value.trim();
  if (!q) return;
  const all = _allReservations.length ? _allReservations : await GET('/reservations/');
  const res = all.find(r => r.confirmation_code.toLowerCase().includes(q.toLowerCase()));
  if (!res) { document.getElementById('paymentDetail').innerHTML = '<div class="empty-state"><div class="empty-icon">🔍</div><h3>No encontrada</h3><p>No se encontró una reserva con ese código</p></div>'; return; }
  
  try {
    window.currentResData = res;
    // Fetch pricing configs
    try { window.currentPaymentPricing = await GET(`/rooms/categories/${res.category_id}/pricing`); } 
    catch(e) { window.currentPaymentPricing = null; }
    
    const summary = await GET(`/payments/summary/${res.id}`);
    window.currentSummary = summary;
    
    const g = _allGuests.find(x => x.id === res.guest_id);
    const gn = g ? g.first_name + ' ' + g.last_name : '--';
    let txHtml = summary.transactions.length ? '<table><thead><tr><th>Monto</th><th>Método</th><th>Tipo</th><th>Estado</th><th>Fecha</th></tr></thead><tbody>' +
      summary.transactions.map(t => `<tr><td>${fmtMoney(t.amount)}</td><td>${t.method}</td><td>${t.type}</td><td><span class="badge badge-${t.status === 'completed' ? 'checked_in' : 'pending'}">${t.status}</span></td><td>${t.created_at ? new Date(t.created_at).toLocaleString('es-AR') : '-'}</td></tr>`).join('') +
      '</tbody></table>' : '<p style="color:var(--text-muted)">Sin pagos registrados</p>';
    
    let payForm = '';
    if (summary.balance_due > 0) {
      payForm = `<div style="margin-top:20px;padding:20px;background:var(--bg-body);border-radius:var(--radius-md)"><h4 style="margin-bottom:12px;display:flex;align-items:center;">💳 Registrar Pago <span id="dynaTariffBadge" style="margin-left:15px"></span></h4>
        <div class="form-row-3"><div class="form-group"><label>Monto</label><input type="number" class="form-control" id="payAmount" value="${summary.balance_due}" step="0.01" min="0.01"></div>
        <div class="form-group"><label>Método</label><select class="form-control" id="payMethod" onchange="window.updatePaymentFormPricing()"><option value="cash">Efectivo</option><option value="credit_card">Tarjeta Crédito</option><option value="debit_card">Tarjeta Débito</option><option value="mercado_pago">MercadoPago</option><option value="paypal">PayPal</option><option value="bank_transfer">Transferencia</option></select></div>
        <div class="form-group"><label>Tipo</label><select class="form-control" id="payType" onchange="window.updatePaymentFormPricing()"><option value="deposit">Seña</option><option value="balance">Saldo</option><option value="full_payment">Pago Total</option></select></div></div>
        <button class="btn btn-success" onclick="submitPayment(${res.id})">💰 Registrar Pago</button></div>`;
    }
    
    document.getElementById('paymentDetail').innerHTML = `<div class="card"><div class="card-header"><h3>Reserva ${summary.confirmation_code} · ${gn}</h3>${fmtStatus(summary.status)}</div><div class="card-body">
      <div class="stats-grid" style="margin-bottom:20px"><div class="stat-card accent"><div class="stat-value" id="dynaRequired">${fmtMoney(summary.total_amount)}</div><div class="stat-label">Total</div></div><div class="stat-card success"><div class="stat-value">${fmtMoney(summary.amount_paid)}</div><div class="stat-label">Pagado</div></div><div class="stat-card ${summary.balance_due > 0 ? 'warning' : 'teal'}"><div class="stat-value" id="dynaBalance">${fmtMoney(summary.balance_due)}</div><div class="stat-label">Saldo</div></div><div class="stat-card info"><div class="stat-value">${fmtMoney(summary.deposit_required)}</div><div class="stat-label">Seña Requerida</div></div></div>
      <h4 style="margin-bottom:12px">📋 Historial de Transacciones</h4>${txHtml}${payForm}</div></div>`;
      
    // Trigger it initially to show any defaults (most likely cash if first)
    if(summary.balance_due > 0) window.updatePaymentFormPricing();
  } catch (e) { toast(e.message, 'error'); }
}
async function submitPayment(resId) {
  try {
    await POST('/payments/', { reservation_id: resId, amount: parseFloat(document.getElementById('payAmount').value), payment_method: document.getElementById('payMethod').value, transaction_type: document.getElementById('payType').value });
    toast('Pago registrado exitosamente'); searchPayment(); loadDashboard();
  } catch (e) { toast(e.message, 'error'); }
}

// ══════════════ HOUSEKEEPING ══════════════
async function loadHousekeeping() {
  try {
    const data = await GET('/rooms/housekeeping/summary');
    let html = `<div class="hk-stats">
      <div class="hk-stat s-available">🟢 Disponibles: ${data.available}</div>
      <div class="hk-stat s-occupied">🔵 Ocupadas: ${data.occupied}</div>
      <div class="hk-stat s-cleaning" style="background:#fff3cd;color:#856404;border-color:#ffc107">🧹 Limpieza: ${data.cleaning || 0}</div>
      <div class="hk-stat s-maintenance">🔴 Mantenimiento: ${data.maintenance}</div>
      <div class="hk-stat s-blocked">⚫ Bloqueadas: ${data.blocked}</div>
    </div>
    <div style="margin-bottom:16px;text-align:right">
      <button class="btn btn-primary" onclick="triggerReallocation()">🔄 Reasignar Habitaciones (Motor IA)</button>
    </div>
    <div class="hk-grid">`;
    data.rooms.sort((a,b) => parseInt(a.room_number) - parseInt(b.room_number)).forEach(r => {
      let cls = 's-' + r.status;
      let extraStyle = '';
      if (r.status === 'cleaning') {
        extraStyle = 'background:#fff3cd;border-color:#ffc107;';
      }
      html += `<div class="hk-room ${cls}" style="${extraStyle}" onclick="openRoomStatusModal(${r.id}, '${r.status}', '${r.room_number}')">
        ${r.has_guest ? '<div class="hk-guest-dot" title="Huésped alojado"></div>' : ''}
        <div class="hk-number">${r.room_number}</div>
        <div class="hk-label">${fmtRoomStatus(r.status)}</div>
        ${r.notes ? '<div style="font-size:0.65rem;color:var(--text-muted);margin-top:4px">'+r.notes+'</div>' : ''}
      </div>`;
    });
    html += '</div>';
    document.getElementById('housekeepingGrid').innerHTML = html;
  } catch (e) { toast(e.message, 'error'); }
}

function openRoomStatusModal(roomId, currentStatus, roomNum) {
  const statuses = [
    {val: 'available', label: '🟢 Disponible'},
    {val: 'occupied', label: '🔵 Ocupada'},
    {val: 'cleaning', label: '🧹 Limpieza'},
    {val: 'maintenance', label: '🔴 Mantenimiento'},
    {val: 'blocked', label: '⚫ Bloqueada'}
  ];
  const opts = statuses.map(s => `<option value="${s.val}" ${s.val === currentStatus ? 'selected' : ''}>${s.label}</option>`).join('');
  
  openModal(`<div class="modal-header"><h2>Estado - Habitación ${roomNum}</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
  <div class="modal-body">
    <div class="form-group">
      <label>Nuevo Estado</label>
      <select class="form-control" id="editRoomStatus">${opts}</select>
    </div>
  </div>
  <div class="modal-footer">
    <button class="btn btn-outline" onclick="closeModal()">Cancelar</button>
    <button class="btn btn-primary" onclick="submitRoomStatus(${roomId})">Guardar Cambios</button>
  </div>`);
}

async function submitRoomStatus(roomId) {
  const next = document.getElementById('editRoomStatus').value;
  try {
    const resp = await PATCH(`/rooms/${roomId}/status`, { status: next });
    let msg = `Estado cambiado a ${fmtRoomStatus(next)}`;
    if (resp.reallocation && resp.reallocation.moved > 0) {
      msg += ` · ${resp.reallocation.moved} reserva(s) reubicadas`;
    }
    if (resp.reallocation && resp.reallocation.unassigned > 0) {
      msg += ` · ⚠️ ${resp.reallocation.unassigned} sin asignar`;
    }
    toast(msg);
    closeModal();
    loadHousekeeping();
  } catch (e) { toast(e.message, 'error'); }
}

async function triggerReallocation() {
  try {
    const resp = await POST('/rooms/reallocate', {});
    let msg = `✅ Reasignación completada: ${resp.assignments} asignadas`;
    if (resp.moved_count > 0) msg += `, ${resp.moved_count} reubicadas`;
    if (resp.unassigned_count > 0) msg += `, ⚠️ ${resp.unassigned_count} sin habitación (ver en amarillo)`;
    toast(msg);
    loadHousekeeping();
    if (typeof loadReservations === 'function') loadReservations();
  } catch(e) { toast(e.message, 'error'); }
}

// ══════════════ ROOMS ══════════════
async function loadRooms() {
  const cats = _categories.length ? _categories : await GET('/rooms/categories');
  const rooms = await GET('/rooms/');
  const reservations = await GET('/reservations/');
  let pricings = [];
  try { pricings = await GET('/rooms/categories/pricing/all'); } catch(e) {}
  
  const catColors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
  let html = '';
  const order = ['DBC', 'DBP', 'TBC', 'TBP', 'CBC', 'CBP'];
  cats.sort((a, b) => {
    let ia = order.indexOf(a.code); let ib = order.indexOf(b.code);
    if(ia === -1) ia = 99; if(ib === -1) ib = 99;
    return ia - ib;
  }).forEach((cat, i) => {
    const catRooms = rooms.filter(r => r.category_id === cat.id).sort((a,b) => parseInt(a.room_number) - parseInt(b.room_number));
    
    // Calculate occupied rooms
    let occCount = 0;
    catRooms.forEach(room => {
       if(reservations.some(r => r.room_id === room.id && r.status === 'checked_in')) {
           occCount++;
       }
    });
    const availCount = catRooms.length - occCount;
    
    // Choose pricing strategy
    const pr = pricings.find(p => p.category_id === cat.id);
    const priEfectivo = pr && pr.price_cash ? pr.price_cash : cat.base_price_per_night;
    const priStr = `<strong>Efectivo: ${fmtMoney(priEfectivo)}/noche</strong>`;

    html += `<div class="card" style="margin-bottom:24px"><div class="card-header"><div style="display:flex;justify-content:space-between;align-items:center;width:100%"><div><h3><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${catColors[i % catColors.length]}"></span> ${cat.name} <span style="font-weight:400;color:var(--text-muted)">(${cat.code})</span></h3><span style="color:var(--text-secondary);font-size:0.85rem">${priStr} <br>Máx ${cat.max_occupancy} personas · <span style="color:var(--accent);font-weight:600">${availCount} de ${catRooms.length} disponibles</span></span></div><button class="btn btn-sm btn-outline" onclick="openPricingModal(${cat.id}, '${cat.name}')">⚙️ Tarifas y Precios</button></div></div><div class="card-body"><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px">`;
    catRooms.forEach(room => {
      const isOcc = reservations.some(r => r.room_id === room.id && r.status === 'checked_in');
      html += `<div style="position:relative;padding:14px;text-align:center;border:1.5px ${isOcc ? 'solid var(--success)' : 'dashed var(--border)'};border-radius:var(--radius-md);background:${isOcc ? 'var(--success-light)' : 'var(--bg-body)'}">
        <div style="font-weight:700;font-size:1.1rem">${room.room_number}</div>
        <div style="font-size:0.75rem;color:var(--text-muted)">Piso ${room.floor}</div>
        <div style="font-size:0.72rem;color:${isOcc ? 'var(--success)' : 'var(--text-muted)'}">● ${isOcc ? 'Ocupada' : 'Libre'}</div>
        <button class="btn btn-sm btn-outline" style="position:absolute;top:4px;right:4px;padding:2px 6px;font-size:0.6rem" onclick="openEditRoomModal(${room.id}, ${room.category_id}, '${room.room_number}')" title="Editar Categoría">✏️</button>
      </div>`;
    });
    html += '</div></div></div>';
  });
  document.getElementById('roomsGrid').innerHTML = html;
}

function openEditRoomModal(roomId, currentCatId, roomNum) {
  const cOpts = _categories.map(c => `<option value="${c.id}" ${c.id === currentCatId ? 'selected' : ''}>${c.name} (${c.code})</option>`).join('');
  openModal(`<div class="modal-header"><h2>Editar Habitación ${roomNum}</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
  <div class="modal-body">
    <div class="form-group">
      <label>Cambiar Categoría</label>
      <select class="form-control" id="editRoomCat">${cOpts}</select>
    </div>
    <p style="font-size:0.85rem;color:var(--text-muted)">Nota: Asegúrese de que no haya una reserva activa conflictiva al cambiar la categoría de esta habitación.</p>
  </div>
  <div class="modal-footer"><button class="btn btn-outline" onclick="closeModal()">Cancelar</button><button class="btn btn-primary" onclick="submitEditRoom(${roomId})">Guardar Cambios</button></div>`);
}

async function submitEditRoom(roomId) {
  const newCatId = document.getElementById('editRoomCat').value;
  try {
    await PATCH(`/rooms/${roomId}/category`, { category_id: parseInt(newCatId) });
    toast('Categoría cambiada exitosamente');
    closeModal();
    loadRooms(); // reload categories and rooms
  } catch(e) { toast(e.message, 'error'); }
}

async function openPricingModal(catId, catName) {
  let p = {};
  try {
    p = await GET(`/rooms/categories/${catId}/pricing`);
  } catch(e) { /* Not found means default is used, form fields empty */ }
  
  openModal(`<div class="modal-header"><h2>Configuración de Tarifas: ${catName}</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
  <div class="modal-body">
    <div style="background:var(--bg-body);padding:15px;border-radius:var(--radius-md);margin-bottom:20px;border:1px solid var(--border-light)">
        <h3 style="margin-bottom:12px;color:var(--accent);font-size:1.1rem">🏢 Venta Directa (Tarifarios Internos)</h3>
        <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:15px">Establezca los precios por noche para cada medio de pago. Si deja un campo vacío, el sistema utilizará la tarifa base de la categoría.</p>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
            <div class="form-group"><label>💵 Efectivo</label><div style="display:flex;align-items:center;gap:8px">$ <input type="number" step="0.01" class="form-control" id="p_cash" value="${p.price_cash||''}"></div></div>
            <div class="form-group"><label>🏦 Transferencia</label><div style="display:flex;align-items:center;gap:8px">$ <input type="number" step="0.01" class="form-control" id="p_transfer" value="${p.price_transfer||''}"></div></div>
            <div class="form-group"><label>🟦 MercadoPago</label><div style="display:flex;align-items:center;gap:8px">$ <input type="number" step="0.01" class="form-control" id="p_mp" value="${p.price_mercadopago||''}"></div></div>
            <div class="form-group"><label>🅿️ PayPal</label><div style="display:flex;align-items:center;gap:8px">$ <input type="number" step="0.01" class="form-control" id="p_pp" value="${p.price_paypal||''}"></div></div>
            <div class="form-group"><label>💳 Tarjeta de Crédito</label><div style="display:flex;align-items:center;gap:8px">$ <input type="number" step="0.01" class="form-control" id="p_cc" value="${p.price_credit_card||''}"></div></div>
            <div class="form-group"><label>💳 Tarjeta de Débito</label><div style="display:flex;align-items:center;gap:8px">$ <input type="number" step="0.01" class="form-control" id="p_dc" value="${p.price_debit_card||''}"></div></div>
        </div>
    </div>
    
    <div style="background:var(--bg-body);padding:15px;border-radius:var(--radius-md);border:1px solid var(--border-light)">
        <h3 style="margin-bottom:12px;color:var(--info);font-size:1.1rem">🌐 Canales de Venta (OTAs)</h3>
        <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:15px">Configure las tarifas netas o finales sincronizadas con el motor de reservas y canales de distribución.</p>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
            <div class="form-group"><label>🔵 Booking.com (Tarifa Host)</label><div style="display:flex;align-items:center;gap:8px">$ <input type="number" step="0.01" class="form-control" id="p_booking" value="${p.price_booking||''}"></div></div>
            <div class="form-group"><label>🟡 Expedia (Tarifa Externa)</label><div style="display:flex;align-items:center;gap:8px">$ <input type="number" step="0.01" class="form-control" id="p_expedia" value="${p.price_expedia||''}"></div></div>
        </div>
    </div>
  </div>
  <div class="modal-footer"><button class="btn btn-outline" onclick="closeModal()">Cancelar</button><button class="btn btn-primary" onclick="savePricing(${catId})">💾 Guardar Tarifas</button></div>`);
}

async function savePricing(catId) {
    const payload = {
        price_cash: parseFloat(document.getElementById('p_cash').value) || null,
        price_transfer: parseFloat(document.getElementById('p_transfer').value) || null,
        price_mercadopago: parseFloat(document.getElementById('p_mp').value) || null,
        price_paypal: parseFloat(document.getElementById('p_pp').value) || null,
        price_credit_card: parseFloat(document.getElementById('p_cc').value) || null,
        price_debit_card: parseFloat(document.getElementById('p_dc').value) || null,
        price_booking: parseFloat(document.getElementById('p_booking').value) || null,
        price_expedia: parseFloat(document.getElementById('p_expedia').value) || null,
    };
    try {
        await POST(`/rooms/categories/${catId}/pricing`, payload);
        toast('Tarifas actualizadas correctamente');
        closeModal();
    } catch(e) {
        toast(e.message, 'error');
    }
}

// ══════════════ REPORTS ══════════════
async function loadDailyReport() {
  const d = document.getElementById('reportDate')?.value || todayStr();
  try {
    const rpt = await GET(`/reports/daily?report_date=${d}`);
    const o = rpt.occupancy;
    const rev = rpt.revenue;
    const methodLabels = {cash:'Efectivo',credit_card:'T. Crédito',debit_card:'T. Débito',mercado_pago:'MercadoPago',paypal:'PayPal',bank_transfer:'Transferencia'};
    let revenueDetail = Object.entries(rev.by_method || {}).map(([k, v]) => `<li>💳 ${methodLabels[k] || k}: <strong>${fmtMoney(v)}</strong></li>`).join('') || '<li>Sin transacciones</li>';
    let arrivalsList = rpt.arrivals.reservations.map(r => `<li>${fmtStatus(r.status)} <strong>${r.confirmation_code}</strong> — Hab. ${r.room_id || '--'} — Saldo: ${fmtMoney(r.balance_due)}</li>`).join('') || '<li>Sin llegadas</li>';
    let departuresList = rpt.departures.reservations.map(r => `<li>${fmtStatus(r.status)} <strong>${r.confirmation_code}</strong> — Hab. ${r.room_id || '--'}</li>`).join('') || '<li>Sin salidas</li>';

    document.getElementById('reportsContent').innerHTML = `
      <div class="report-section"><h3>📊 Resumen del Día — ${fmtDate(d)}</h3>
        <div class="report-metrics">
          <div class="report-metric"><div class="rm-value" style="color:var(--accent)">${o.total_rooms}</div><div class="rm-label">Total Hab.</div></div>
          <div class="report-metric"><div class="rm-value" style="color:var(--success)">${o.occupied}</div><div class="rm-label">Ocupadas</div></div>
          <div class="report-metric"><div class="rm-value" style="color:var(--info)">${o.available}</div><div class="rm-label">Libres</div></div>
          <div class="report-metric"><div class="rm-value" style="color:var(--teal)">${o.occupancy_rate}%</div><div class="rm-label">Ocupación</div></div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="report-section"><h3>🛬 Llegadas (${rpt.arrivals.count})</h3><ul class="report-list">${arrivalsList}</ul></div>
        <div class="report-section"><h3>🛫 Salidas (${rpt.departures.count})</h3><ul class="report-list">${departuresList}</ul></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="report-section"><h3>💰 Ingresos del Día</h3>
          <div class="report-metrics"><div class="report-metric"><div class="rm-value" style="color:var(--success)">${fmtMoney(rev.total)}</div><div class="rm-label">Total Cobrado</div></div><div class="report-metric"><div class="rm-value">${rev.transactions_count}</div><div class="rm-label">Transacciones</div></div></div>
          <ul class="report-list" style="margin-top:12px">${revenueDetail}</ul>
        </div>
        <div class="report-section"><h3>⚠️ Pendientes</h3>
          <div class="report-metrics"><div class="report-metric"><div class="rm-value" style="color:var(--danger)">${fmtMoney(rpt.pending_payments.total_balance)}</div><div class="rm-label">Saldo Total Pendiente</div></div><div class="report-metric"><div class="rm-value">${rpt.pending_payments.count}</div><div class="rm-label">Reservas c/ Saldo</div></div></div>
          ${rpt.no_shows.count > 0 ? '<p style="margin-top:12px;color:var(--danger)"><strong>🚫 No-Shows: ' + rpt.no_shows.count + '</strong></p>' : ''}
        </div>
      </div>`;
  } catch (e) { document.getElementById('reportsContent').innerHTML = '<div class="empty-state"><p>Error cargando reporte</p></div>'; console.error(e); }
}

// ══════════════ CONFIG ══════════════
async function loadConfig() {
  _config = await GET('/config/');
  const c = _config;
  const toggle = (id, val, label, desc) => `<div class="config-item"><div><div class="config-item-label">${label}</div><div class="config-item-desc">${desc}</div></div><label class="toggle-switch"><input type="checkbox" id="${id}" ${val ? 'checked' : ''}><span class="toggle-slider"></span></label></div>`;
  document.getElementById('configPanel').innerHTML = `<div class="config-grid">
    <div class="config-card"><h3>💰 Políticas Financieras</h3>
      <div class="config-item"><div><div class="config-item-label">Porcentaje de Seña</div><div class="config-item-desc">% del total requerido como anticipo</div></div><div style="display:flex;align-items:center;gap:8px"><input type="number" class="form-control" id="cfgDeposit" value="${c.deposit_percentage}" style="width:80px" min="0" max="100"> %</div></div>
      ${toggle('cfgFullPay', c.enable_full_payment, 'Permitir Pago Total', 'Clientes pueden pagar el 100% al reservar')}
      ${toggle('cfgDepPay', c.enable_deposit_payment, 'Permitir Pago de Seña', 'Clientes pueden pagar solo el depósito')}
    </div>
    <div class="config-card"><h3>💳 Pasarelas de Pago</h3>
      ${toggle('cfgCash', c.enable_cash, '💵 Efectivo', '')}
      ${toggle('cfgMP', c.enable_mercado_pago, '🟦 MercadoPago', '')}
      ${toggle('cfgPP', c.enable_paypal, '🅿️ PayPal', '')}
      ${toggle('cfgCC', c.enable_credit_card, '💳 Tarjeta Crédito', '')}
      ${toggle('cfgDC', c.enable_debit_card, '💳 Tarjeta Débito', '')}
      ${toggle('cfgBT', c.enable_bank_transfer, '🏦 Transferencia Bancaria', '')}
    </div>
    <div class="config-card"><h3>🛎️ Políticas de Check-in</h3>
      ${toggle('cfgDoc', c.require_document_for_checkin, 'Requerir Documento', 'DNI/Pasaporte obligatorio para check-in')}
      ${toggle('cfgTerms', c.require_terms_acceptance, 'Aceptación de Términos', 'Huésped debe aceptar T&C para check-in')}
    </div>
    <div class="config-card"><h3>🌐 Cancelación y OTA</h3>
      <div class="config-item"><div><div class="config-item-label">Horas de Cancelación Gratis</div><div class="config-item-desc">Tiempo para cancelar sin cargo</div></div><div style="display:flex;align-items:center;gap:8px"><input type="number" class="form-control" id="cfgCancelHrs" value="${c.free_cancellation_hours}" style="width:80px" min="0"> hrs</div></div>
      ${toggle('cfgBooking', c.enable_booking_sync, 'Sync Booking.com', '')}
      ${toggle('cfgExpedia', c.enable_expedia_sync, 'Sync Expedia', '')}
    </div>
  </div>
  <div style="text-align:right;margin-top:24px"><button class="btn btn-primary btn-lg" onclick="saveConfig()">💾 Guardar Configuración</button></div>`;
}
async function saveConfig() {
  try {
    await PATCH('/config/', { deposit_percentage: parseFloat(document.getElementById('cfgDeposit').value), enable_full_payment: document.getElementById('cfgFullPay').checked, enable_deposit_payment: document.getElementById('cfgDepPay').checked, enable_cash: document.getElementById('cfgCash').checked, enable_mercado_pago: document.getElementById('cfgMP').checked, enable_paypal: document.getElementById('cfgPP').checked, enable_credit_card: document.getElementById('cfgCC').checked, enable_debit_card: document.getElementById('cfgDC').checked, enable_bank_transfer: document.getElementById('cfgBT').checked, require_document_for_checkin: document.getElementById('cfgDoc').checked, require_terms_acceptance: document.getElementById('cfgTerms').checked, free_cancellation_hours: parseInt(document.getElementById('cfgCancelHrs').value), enable_booking_sync: document.getElementById('cfgBooking').checked, enable_expedia_sync: document.getElementById('cfgExpedia').checked });
    toast('Configuración guardada exitosamente');
  } catch (e) { toast(e.message, 'error'); }
}
