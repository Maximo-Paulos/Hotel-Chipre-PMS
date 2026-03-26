/* ═══ SECTIONS PART 1: Dashboard, Calendar, Reservations, Guests ═══ */

// ══════════════ DASHBOARD ══════════════
async function loadDashboard() {
  const d = document.getElementById('dashDateLabel');
  d.textContent = new Date().toLocaleDateString('es-AR',{weekday:'long',year:'numeric',month:'long',day:'numeric'});
  try {
    const [reservations, rooms] = await Promise.all([GET('/reservations/'), GET('/rooms/')]);
    _allReservations = reservations;
    const today = todayStr();
    const totalRooms = rooms.length;
    const checkedIn = reservations.filter(r=>r.status==='checked_in').length;
    const arrivals = reservations.filter(r=>r.check_in_date===today && r.status!=='cancelled').length;
    const departures = reservations.filter(r=>r.check_out_date===today).length;
    const occRate = totalRooms ? Math.round(checkedIn/totalRooms*100) : 0;
    const revenue = reservations.reduce((s,r)=>s+r.amount_paid,0);
    document.getElementById('dashStats').innerHTML = [
      {icon:'🏨',val:totalRooms,label:'Habitaciones Totales',cls:'accent'},
      {icon:'🛏️',val:checkedIn,label:'Ocupadas Ahora',cls:'success'},
      {icon:'🛬',val:arrivals,label:'Llegadas Hoy',cls:'info'},
      {icon:'🛫',val:departures,label:'Salidas Hoy',cls:'warning'},
      {icon:'📊',val:occRate+'%',label:'Ocupación',cls:'teal'},
      {icon:'💰',val:fmtMoney(revenue),label:'Ingresos Cobrados',cls:'purple'}
    ].map(s=>`<div class="stat-card ${s.cls}"><div class="stat-icon">${s.icon}</div><div class="stat-value">${s.val}</div><div class="stat-label">${s.label}</div></div>`).join('');
    // Arrivals & Departures
    const arrList = reservations.filter(r=>r.check_in_date===today&&r.status!=='cancelled');
    const depList = reservations.filter(r=>r.check_out_date===today);
    document.getElementById('dashArrivals').innerHTML = arrList.length ? arrList.map(r=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border-light)"><div><strong>${r.confirmation_code}</strong>${r.additional_guests && r.additional_guests.length ? ' <span style="font-size:0.8rem;color:var(--text-muted)">(+'+r.additional_guests.length+' acomp.)</span>' : ''}<br><small>Hab. ${r.room_id||'--'}</small></div>${fmtStatus(r.status)}</div>`).join('') : '<div class="empty-state"><div class="empty-icon">🛬</div><p>No hay llegadas programadas para hoy</p></div>';
    document.getElementById('dashDepartures').innerHTML = depList.length ? depList.map(r=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border-light)"><div><strong>${r.confirmation_code}</strong>${r.additional_guests && r.additional_guests.length ? ' <span style="font-size:0.8rem;color:var(--text-muted)">(+'+r.additional_guests.length+' acomp.)</span>' : ''}<br><small>Hab. ${r.room_id||'--'}</small></div>${fmtStatus(r.status)}</div>`).join('') : '<div class="empty-state"><div class="empty-icon">🛫</div><p>No hay salidas programadas para hoy</p></div>';
    // Badge
    const pending = reservations.filter(r=>r.status==='pending').length;
    const badge = document.getElementById('pendingBadge');
    if(pending>0){badge.textContent=pending;badge.style.display='inline';}else{badge.style.display='none';}
  } catch(e) { console.error(e); }
}

// ══════════════ CALENDAR ══════════════
let calStart = new Date(); calStart.setDate(calStart.getDate() - calStart.getDay() + 1);
function calendarPrev() { calStart.setDate(calStart.getDate()-14); loadCalendar(); }
function calendarNext() { calStart.setDate(calStart.getDate()+14); loadCalendar(); }
function calendarToday() { calStart = new Date(); calStart.setDate(calStart.getDate()-calStart.getDay()+1); loadCalendar(); }

async function loadCalendar() {
  const days = 14, today = todayStr();
  const dates = []; for(let i=0;i<days;i++){const d=new Date(calStart);d.setDate(d.getDate()+i);dates.push(d);}
  const rooms = _rooms.length ? _rooms : await GET('/rooms/');
  const reservations = await GET('/reservations/');
  const cols = days+1;
  let html = `<div class="calendar-grid" style="grid-template-columns: 140px repeat(${days}, 1fr)">`;
  html += `<div class="calendar-header-cell"></div>`;
  dates.forEach(d => {
    const ds = d.toISOString().split('T')[0];
    const isToday = ds===today;
    html += `<div class="calendar-header-cell${isToday?' today':''}">${d.toLocaleDateString('es-AR',{weekday:'short'})}<br>${d.getDate()}/${d.getMonth()+1}</div>`;
  });
  const catColors = ['#6366f1','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899'];
  const catMap = {}; 
  let legendHtml = '<div style="display:flex;gap:15px;margin-bottom:15px;flex-wrap:wrap;padding:10px;background:var(--bg-body);border-radius:var(--radius-md);border:1px solid var(--border-light)">';
  _categories.forEach((c,i) => {
    catMap[c.id]=catColors[i%catColors.length];
    legendHtml += `<div style="display:flex;align-items:center;font-size:0.85rem;"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${catColors[i%catColors.length]};margin-right:6px;"></span><strong>${c.code}</strong> <span style="color:var(--text-muted);margin-left:4px">- ${c.name}</span></div>`;
  });
  legendHtml += '</div>';

  rooms.sort((a,b) => parseInt(a.room_number) - parseInt(b.room_number)).forEach(room => {
    const cat = _categories.find(c=>c.id===room.category_id);
    const isCleaning = room.status === 'cleaning';
    const cleaningIcon = isCleaning ? `<span title="En Limpieza" style="color:#f59e0b; margin-left:4px; font-size:0.9em">🧹</span>` : '';
    html += `<div class="calendar-room-label"><span class="room-cat-dot" style="background:${catMap[room.category_id]||'#999'}"></span><strong style="font-size:1.1em">${room.room_number}</strong>${cleaningIcon} <span style="font-size:0.75rem;color:var(--text-secondary);font-weight:normal;margin-left:6px">(${cat ? cat.code : ''})</span></div>`;
    dates.forEach(d => {
      const ds = d.toISOString().split('T')[0];
      const res = reservations.find(r => r.room_id===room.id && r.check_in_date<=ds && r.check_out_date>ds && r.status!=='cancelled');
      if(res) {
        let ex = res.additional_guests && res.additional_guests.length ? ` (+${res.additional_guests.length})` : '';
        html += `<div class="calendar-cell occupied"><div class="calendar-booking status-${res.status}" title="${res.confirmation_code}${ex}" onclick="showReservationDetail(${res.id})">${res.confirmation_code.slice(-4)}${ex}</div></div>`;
      } else {
        html += `<div class="calendar-cell"></div>`;
      }
    });
  });
  html += '</div>';
  document.getElementById('calendarGrid').innerHTML = legendHtml + html;
}

// ══════════════ RESERVATIONS ══════════════
async function loadReservations() {
  _allReservations = await GET('/reservations/');
  _allGuests = await GET('/guests/');
  renderReservations(_allReservations);
}
function filterReservations() {
  const q = document.getElementById('resSearch').value.toLowerCase();
  const s = document.getElementById('resStatusFilter').value;
  let list = _allReservations;
  if(s) list = list.filter(r=>r.status===s);
  if(q) list = list.filter(r=>{
    const g = _allGuests.find(g=>g.id===r.guest_id);
    const gn = g ? (g.first_name+' '+g.last_name).toLowerCase() : '';
    return r.confirmation_code.toLowerCase().includes(q) || gn.includes(q);
  });
  renderReservations(list);
}
function renderReservations(list) {
  const tb = document.getElementById('resTbody');
  if(!list.length){ tb.innerHTML='<tr><td colspan="9"><div class="empty-state"><p>No hay reservas</p></div></td></tr>'; return; }
  tb.innerHTML = list.map(r=>{
    const g = _allGuests.find(g=>g.id===r.guest_id);
    const gn = g?g.first_name+' '+g.last_name:'--';
    const room = _rooms.find(rm=>rm.id===r.room_id);
    const rn = room?room.room_number:'--';
    let actions = `<button class="btn btn-sm btn-outline" onclick="showReservationDetail(${r.id})" title="Ver detalle">👁️</button>`;
    if(r.status==='pending'||r.status==='deposit_paid')
      actions += ` <button class="btn btn-sm btn-warning" onclick="navigate('payments');document.getElementById('paySearch').value='${r.confirmation_code}';searchPayment()" title="Cobrar">💰</button>`;
    if(r.status!=='cancelled')
      actions += ` <button class="btn btn-sm btn-danger" onclick="confirmCancelReservation(${r.id},'${r.confirmation_code}','${r.status}')" title="Cancelar">✕</button>`;
    return `<tr><td><strong style="color:var(--accent)">${r.confirmation_code}</strong></td><td>${gn}</td><td>${rn}</td><td>${fmtDate(r.check_in_date)}</td><td>${fmtDate(r.check_out_date)}</td><td>${fmtMoney(r.total_amount)}</td><td style="color:${r.balance_due>0?'var(--danger)':'var(--success)'}"><strong>${fmtMoney(r.balance_due)}</strong></td><td>${fmtStatus(r.status)}</td><td><div class="btn-group">${actions}</div></td></tr>`;
  }).join('');
}
function confirmCancelReservation(id, code, status) {
  if (status === 'checked_in' || status === 'checked_out') {
    showConfirm('Reembolso Premium', `¿Cancelar/Reembolsar ${code}? Esta acción liberará la habitación y requiere PIN de autorización del dueño.`, '💰 Autorizar Reembolso', 'btn-danger', async()=>{
      const pin = prompt('Ingrese PIN de Dueño para reembolsar:');
      if(pin===null) return;
      try { await POST(`/reservations/${id}/cancel?manager_pin=${pin}`); toast('Reembolso Autorizado','warning'); loadReservations(); loadDashboard(); } catch(e){ toast(e.message,'error'); }
    });
  } else {
    showConfirm('Cancelar Reserva', `¿Estás seguro de cancelar ${code}? Esta acción no se puede deshacer.`, '❌ Cancelar Reserva', 'btn-danger', async()=>{
      try { await POST(`/reservations/${id}/cancel`); toast('Reserva cancelada','warning'); loadReservations(); loadDashboard(); } catch(e){ toast(e.message,'error'); }
    });
  }
}
async function showReservationDetail(id) {
  try {
    const r = await GET(`/reservations/${id}`);
    const g = _allGuests.find(g=>g.id===r.guest_id) || await GET(`/guests/${r.guest_id}`);
    const room = _rooms.find(rm=>rm.id===r.room_id);
    const cat = _categories.find(c=>c.id===r.category_id);
    const gn = g?g.first_name+' '+g.last_name:'--';
    let actionsHtml = '';
    if(r.status!=='cancelled')
      actionsHtml += `<button class="btn btn-danger btn-sm" onclick="confirmCancelReservation(${r.id},'${r.confirmation_code}','${r.status}');closeModal()">❌ Cancelar</button>`;
    if(r.status==='pending'||r.status==='deposit_paid')
      actionsHtml += ` <button class="btn btn-warning btn-sm" onclick="closeModal();navigate('payments');document.getElementById('paySearch').value='${r.confirmation_code}';searchPayment()">💰 Cobrar</button>`;
    if(r.status==='pending'||r.status==='deposit_paid')
      actionsHtml += ` <button class="btn btn-sm btn-outline" onclick="confirmNoShow(${r.id},'${r.confirmation_code}')">🚫 No-Show</button>`;
    if(r.status==='checked_in'||r.status==='fully_paid')
      actionsHtml += ` <button class="btn btn-sm btn-primary" onclick="openExtendModal(${r.id})">📅 Extender</button>`;
    openModal(`<div class="modal-header"><h2>Reserva ${r.confirmation_code}</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
    <div class="modal-body">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div><h4 style="margin-bottom:12px">🏷️ Información</h4>
          <p><strong>Titular:</strong> ${gn}</p>
          ${r.additional_guests && r.additional_guests.length ? `<p><strong>Acompañantes en la Habitación:</strong><br>` + r.additional_guests.map(ag => `• ${ag.first_name} ${ag.last_name}`).join('<br>') + `</p>` : ''}
          <p><strong>Habitación:</strong> ${room?room.room_number:'--'} (${cat?cat.name:'--'})</p>
          <p><strong>Check-in:</strong> ${fmtDate(r.check_in_date)}</p><p><strong>Check-out:</strong> ${fmtDate(r.check_out_date)}</p>
          <p><strong>Noches:</strong> ${r.nights}</p><p><strong>Adultos:</strong> ${r.num_adults} / Niños: ${r.num_children}</p>
          <p><strong>Fuente:</strong> ${r.source}</p>${r.notes?'<p><strong>Notas:</strong> '+r.notes+'</p>':''}
        </div>
        <div><h4 style="margin-bottom:12px">💰 Finanzas</h4>
          <p><strong>Total:</strong> ${fmtMoney(r.total_amount)}</p><p><strong>Seña:</strong> ${fmtMoney(r.deposit_amount)}</p>
          <p><strong>Pagado:</strong> ${fmtMoney(r.amount_paid)}</p>
          <p style="font-size:1.2rem"><strong>Saldo:</strong> <span style="color:${r.balance_due>0?'var(--danger)':'var(--success)'}"><strong>${fmtMoney(r.balance_due)}</strong></span></p>
          <p><strong>Estado:</strong> ${fmtStatus(r.status)}</p>
        </div>
      </div>
    </div>
    <div class="modal-footer">${actionsHtml} <button class="btn btn-outline" onclick="closeModal()">Cerrar</button></div>`);
  } catch(e){ toast(e.message,'error'); }
}
function confirmNoShow(id, code) {
  showConfirm('Marcar No-Show', `¿Marcar ${code} como no-show? El huésped no se presentó.`, '🚫 Confirmar No-Show', 'btn-warning', async()=>{
    try { await POST(`/reservations/${id}/noshow`); toast('Reserva marcada como No-Show','warning'); closeModal(); loadReservations(); } catch(e){ toast(e.message,'error'); }
  });
}
function openExtendModal(id) {
  closeModal();
  openModal(`<div class="modal-header"><h2>📅 Extender Estadía</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
  <div class="modal-body"><div class="form-group"><label>Nueva fecha de check-out</label><input type="date" class="form-control" id="extendDate" min="${tomorrowStr()}"></div></div>
  <div class="modal-footer"><button class="btn btn-outline" onclick="closeModal()">Cancelar</button><button class="btn btn-primary" onclick="doExtend(${id})">Confirmar Extensión</button></div>`);
}
async function doExtend(id) {
  const d = document.getElementById('extendDate').value;
  if(!d){toast('Seleccione una fecha','error');return;}
  try { await POST(`/reservations/${id}/extend?new_checkout=${d}`); toast('Estadía extendida exitosamente'); closeModal(); } catch(e){ toast(e.message,'error'); }
}

// ══════════════ NEW RESERVATION MODAL ══════════════
async function openNewReservationModal() {
  if(!_allGuests.length) _allGuests = await GET('/guests/');
  if(!_categories.length) _categories = await GET('/rooms/categories');
  if(!_pricings.length) try{_pricings = await GET('/rooms/categories/pricing/all');}catch(e){}
  const gOpts = _allGuests.map(g=>`<option value="${g.id}">${g.first_name} ${g.last_name} (${g.document_type||''}:${g.document_number||''})</option>`).join('');
  const cOpts = _categories.map(c=>{
    const p = _pricings.find(x=>x.category_id===c.id);
    const pri = p && p.price_cash ? p.price_cash : c.base_price_per_night;
    return `<option value="${c.id}">${c.name} - ${fmtMoney(pri)}/noche</option>`;
  }).join('');
  openModal(`<div class="modal-header"><h2>Nueva Reserva</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
  <div class="modal-body"><form id="resForm">
    <div class="form-group"><label>Titular de la Reserva <span class="required">*</span></label><select class="form-control" id="resGuest" required>${gOpts}</select></div>
    <div class="form-group"><label>Categoría de Habitación <span class="required">*</span></label><select class="form-control" id="resCat" required>${cOpts}</select></div>
    <div class="form-row"><div class="form-group"><label>Check-in</label><input type="date" class="form-control" id="resCheckin" value="${todayStr()}" required></div>
    <div class="form-group"><label>Check-out</label><input type="date" class="form-control" id="resCheckout" value="${tomorrowStr()}" required></div></div>
    
    <div class="form-row"><div class="form-group"><label>Adultos</label><input type="number" class="form-control" id="resAdults" value="1" min="1" onchange="renderCompanionsForm()"></div>
    <div class="form-group"><label>Niños</label><input type="number" class="form-control" id="resChildren" value="0" min="0" onchange="renderCompanionsForm()"></div></div>
    
    <div id="companionsContainer" style="margin-top:10px;margin-bottom:15px;padding:10px;background:var(--bg-body);border-radius:var(--radius-md);display:none;"></div>
    
    <div class="form-group"><label>Notas</label><textarea class="form-control" id="resNotes" rows="2"></textarea></div>
  </form></div>
  <div class="modal-footer"><button class="btn btn-outline" onclick="closeModal()">Cancelar</button><button class="btn btn-primary" onclick="submitReservation()">Crear Reserva</button></div>`);
  // Initialize in case it is somehow > 1
  renderCompanionsForm();
}

function renderCompanionsForm() {
    const adults = parseInt(document.getElementById('resAdults').value) || 1;
    const children = parseInt(document.getElementById('resChildren').value) || 0;
    const totalPeople = adults + children;
    const container = document.getElementById('companionsContainer');
    if (totalPeople <= 1) {
        container.style.display = 'none';
        container.innerHTML = '';
        return;
    }
    container.style.display = 'block';
    const companionsNeeded = totalPeople - 1; // 1 is the titular
    let html = `<h4 style="margin-bottom:10px">👥 Pasajeros Acompañantes (${companionsNeeded})</h4>`;
    for(let i=0; i<companionsNeeded; i++) {
        html += `<div style="padding:10px;border:1px solid var(--border-light);border-radius:4px;margin-bottom:10px;background:#fff">
            <strong>Pasajero ${i+1}</strong>
            <div class="form-row">
                <div class="form-group" style="margin-bottom:8px"><input type="text" class="form-control comp-fname" placeholder="Nombre" required></div>
                <div class="form-group" style="margin-bottom:8px"><input type="text" class="form-control comp-lname" placeholder="Apellido" required></div>
            </div>
            <div class="form-row">
                <div class="form-group" style="margin-bottom:0"><input type="text" class="form-control comp-doctype" placeholder="Tipo Doc (DNI/Pasaporte)"></div>
                <div class="form-group" style="margin-bottom:0"><input type="text" class="form-control comp-docnum" placeholder="Número Documento"></div>
            </div>
        </div>`;
    }
    container.innerHTML = html;
}

async function submitReservation() {
  try {
    const guestId = +document.getElementById('resGuest').value;
    // Gather companions if any
    const compFnames = document.querySelectorAll('.comp-fname');
    const compLnames = document.querySelectorAll('.comp-lname');
    const compDtypes = document.querySelectorAll('.comp-doctype');
    const compDnums = document.querySelectorAll('.comp-docnum');
    const companions = [];
    for(let i=0; i<compFnames.length; i++) {
        if(compFnames[i].value.trim() && compLnames[i].value.trim()) {
            companions.push({
                first_name: compFnames[i].value.trim(),
                last_name: compLnames[i].value.trim(),
                document_type: compDtypes[i].value.trim() || null,
                document_number: compDnums[i].value.trim() || null
            });
        }
    }
    
    // Create reservation
    const r = await POST('/reservations/', { 
        guest_id: guestId, 
        category_id: +document.getElementById('resCat').value, 
        check_in_date: document.getElementById('resCheckin').value, 
        check_out_date: document.getElementById('resCheckout').value, 
        num_adults: +document.getElementById('resAdults').value, 
        num_children: +document.getElementById('resChildren').value, 
        notes: document.getElementById('resNotes').value || null 
    });
    
    // Add companions to the reservation (if any)
    if (companions.length > 0) {
        await POST(`/reservations/${r.id}/guests`, companions);
    }
    
    toast(`Reserva ${r.confirmation_code} creada exitosamente`);
    closeModal(); loadReservations(); loadDashboard();
  } catch(e){ toast(e.message, 'error'); }
}

// ══════════════ GUESTS ══════════════
async function loadGuests() {
  const q = document.getElementById('guestSearch')?.value || '';
  _allGuests = await GET('/guests/?search=' + encodeURIComponent(q));
  const tb = document.getElementById('guestsTbody');
  if(!_allGuests.length){ tb.innerHTML='<tr><td colspan="7"><div class="empty-state"><p>No hay huéspedes registrados</p></div></td></tr>'; return; }
  tb.innerHTML = _allGuests.map(g=>`<tr><td>${g.first_name} ${g.last_name}</td><td>${g.document_type||''}${g.document_number?': '+g.document_number:''}</td><td>${g.nationality||'-'}</td><td>${g.email||'-'}</td><td>${g.phone||'-'}</td><td>${g.terms_accepted?'<span style="color:var(--success)">✅ Sí</span>':'<span style="color:var(--danger)">❌ No</span>'}</td><td><button class="btn btn-sm btn-outline" onclick="openEditGuestModal(${g.id})">✏️ Editar</button></td></tr>`).join('');
}
async function openNewGuestModal() {
  openModal(`<div class="modal-header"><h2>Nuevo Huésped</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
  <div class="modal-body"><form id="guestForm">
    <div class="form-row"><div class="form-group"><label>Nombre <span class="required">*</span></label><input type="text" class="form-control" id="gFname" required></div>
    <div class="form-group"><label>Apellido <span class="required">*</span></label><input type="text" class="form-control" id="gLname" required></div></div>
    <div class="form-row"><div class="form-group"><label>Tipo Documento</label><select class="form-control" id="gDocType"><option value="">--</option><option value="DNI">DNI</option><option value="Passport">Pasaporte</option><option value="CUIT">CUIT</option></select></div>
    <div class="form-group"><label>Nro Documento</label><input type="text" class="form-control" id="gDocNum"></div></div>
    <div class="form-row"><div class="form-group"><label>Nacionalidad</label><input type="text" class="form-control" id="gNat"></div>
    <div class="form-group"><label>Email</label><input type="email" class="form-control" id="gEmail"></div></div>
    <div class="form-row"><div class="form-group"><label>Teléfono</label><input type="tel" class="form-control" id="gPhone"></div>
    <div class="form-group" style="display:flex;align-items:center;gap:10px;padding-top:22px"><label class="toggle-switch"><input type="checkbox" id="gTerms"><span class="toggle-slider"></span></label><span>Acepta términos y condiciones</span></div></div>
    <div class="form-group"><label>Solicitudes especiales</label><textarea class="form-control" id="gSpecial" rows="2"></textarea></div>
  </form></div>
  <div class="modal-footer"><button class="btn btn-outline" onclick="closeModal()">Cancelar</button><button class="btn btn-primary" onclick="submitGuest()">Guardar Huésped</button></div>`);
}
async function submitGuest() {
  try {
    await POST('/guests/', { first_name: document.getElementById('gFname').value, last_name: document.getElementById('gLname').value, document_type: document.getElementById('gDocType').value||null, document_number: document.getElementById('gDocNum').value||null, nationality: document.getElementById('gNat').value||null, email: document.getElementById('gEmail').value||null, phone: document.getElementById('gPhone').value||null, terms_accepted: document.getElementById('gTerms').checked, special_requests: document.getElementById('gSpecial').value||null, companions: [] });
    toast('Huésped creado exitosamente'); closeModal(); loadGuests();
  } catch(e){ toast(e.message,'error'); }
}
async function openEditGuestModal(id) {
  const g = await GET(`/guests/${id}`);
  openModal(`<div class="modal-header"><h2>Editar Huésped</h2><button class="modal-close" onclick="closeModal()">✕</button></div>
  <div class="modal-body"><form>
    <div class="form-row"><div class="form-group"><label>Nombre</label><input type="text" class="form-control" id="egFname" value="${g.first_name}"></div>
    <div class="form-group"><label>Apellido</label><input type="text" class="form-control" id="egLname" value="${g.last_name}"></div></div>
    <div class="form-row"><div class="form-group"><label>Tipo Doc</label><select class="form-control" id="egDocType"><option value="">--</option><option value="DNI" ${g.document_type==='DNI'?'selected':''}>DNI</option><option value="Passport" ${g.document_type==='Passport'?'selected':''}>Pasaporte</option><option value="CUIT" ${g.document_type==='CUIT'?'selected':''}>CUIT</option></select></div>
    <div class="form-group"><label>Nro Doc</label><input type="text" class="form-control" id="egDocNum" value="${g.document_number||''}"></div></div>
    <div class="form-row"><div class="form-group"><label>Email</label><input type="email" class="form-control" id="egEmail" value="${g.email||''}"></div>
    <div class="form-group"><label>Teléfono</label><input type="text" class="form-control" id="egPhone" value="${g.phone||''}"></div></div>
    <div class="form-group"><label>Nacionalidad</label><input type="text" class="form-control" id="egNat" value="${g.nationality||''}"></div>
    <div class="form-group" style="display:flex;align-items:center;gap:10px"><label class="toggle-switch"><input type="checkbox" id="egTerms" ${g.terms_accepted?'checked':''}><span class="toggle-slider"></span></label><span>Acepta T&C</span></div>
  </form></div>
  <div class="modal-footer"><button class="btn btn-outline" onclick="closeModal()">Cancelar</button><button class="btn btn-primary" onclick="submitEditGuest(${id})">Guardar Cambios</button></div>`);
}
async function submitEditGuest(id) {
  try {
    await PATCH(`/guests/${id}`, { first_name: document.getElementById('egFname').value, last_name: document.getElementById('egLname').value, document_type: document.getElementById('egDocType').value||null, document_number: document.getElementById('egDocNum').value||null, email: document.getElementById('egEmail').value||null, phone: document.getElementById('egPhone').value||null, nationality: document.getElementById('egNat').value||null, terms_accepted: document.getElementById('egTerms').checked });
    toast('Huésped actualizado'); closeModal(); loadGuests();
  } catch(e){ toast(e.message,'error'); }
}
