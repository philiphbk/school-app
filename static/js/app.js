/* ═══════════════════════════════════════════════════════
   GISL Schools Management System — Frontend Application
   ═══════════════════════════════════════════════════════ */

const API = '';  // same-origin
let currentUser = null;
let appData = { classes: [], terms: [], subjects: [], pupils: [] };
let _marksheetData = null;

const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

// ─── SCHOOL CONSTANTS ────────────────────────────────────────────────────────
const SCHOOL = {
  name: 'GISL SCHOOLS',
  fullName: 'GISL Daycare Nursery & Primary School',
  tagline: 'Light of Knowledge',
  address: '3 Oludemi Adeniba St. Alarere Layout. Opp Temidire Mrk, New Ife Road.',
  address2: 'P.O. Box 19707 UI, Ibadan, Oyo State.',
  phones: '+2348033299074, +23409151404619, +2348033295403',
  email: 'gislschools@gmail.com',
  motto: '"TRAIN UP YOUR CHILD IN THE WAY HE SHOULD GO WHEN HE IS OLD, HE SHALL NOT DEPART FROM IT. PROV 22:6"',
  logo: '/gisl_logo.png'  // served from /static/gisl_logo.png
};

// ─── SECURITY ─────────────────────────────────────────────────────────────────
function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ─── SESSION TIMEOUT ──────────────────────────────────────────────────────────
let _sessionTimer = null;
let _sessionWarnTimer = null;

function resetSessionTimers() {
  clearTimeout(_sessionTimer);
  clearTimeout(_sessionWarnTimer);
  // Warn 5 minutes before 24-hour session expires (at 23h55m)
  _sessionWarnTimer = setTimeout(showSessionWarning, (23 * 60 + 55) * 60 * 1000);
  _sessionTimer = setTimeout(() => logout(), 24 * 60 * 60 * 1000);
}

function showSessionWarning() {
  showToast('Your session expires in 5 minutes. Save your work or click to stay logged in.', 'warning', 0);
  document.getElementById('toast').onclick = async () => {
    try { await apiFetch('/api/auth/me'); resetSessionTimers(); hideToast(); } catch {}
  };
}

function hideToast() {
  const toast = document.getElementById('toast');
  if (toast) { toast.classList.add('hidden'); toast.onclick = null; }
}

// ─── AUTH ─────────────────────────────────────────────────────────────────────

function showLoginPage() {
  localStorage.removeItem('token');
  currentUser = null;
  document.getElementById('app').classList.add('hidden');
  document.getElementById('login-page').classList.remove('hidden');
  const btn = document.getElementById('login-btn');
  btn.textContent = 'Sign In';
  btn.disabled = false;
  document.getElementById('login-error').classList.add('hidden');
}

async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(API + path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && path !== '/api/auth/login') {
    showLoginPage();
    throw new Error('Session expired. Please sign in again.');
  }
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const errEl = document.getElementById('login-error');
  errEl.classList.add('hidden');
  btn.textContent = 'Signing in…';
  btn.disabled = true;
  try {
    const data = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: document.getElementById('login-email').value,
        password: document.getElementById('login-password').value
      })
    });
    localStorage.setItem('token', data.token);
    currentUser = data.user;
    if (data.user.must_change_password) {
      showForcePasswordChange();
      return;
    }
    startApp();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
    btn.textContent = 'Sign In';
    btn.disabled = false;
  }
});

async function logout() {
  clearTimeout(_sessionTimer);
  clearTimeout(_sessionWarnTimer);
  try { await apiFetch('/api/auth/logout', { method: 'POST' }); } catch {}
  showLoginPage();
  document.getElementById('login-password').value = '';
}

async function initAuth() {
  const token = localStorage.getItem('token');
  if (!token) return;
  try {
    currentUser = await apiFetch('/api/auth/me');
    if (currentUser.must_change_password) {
      showForcePasswordChange();
      return;
    }
    startApp();
  } catch {
    localStorage.removeItem('token');
  }
}

function showForcePasswordChange() {
  document.getElementById('login-page').classList.add('hidden');
  document.getElementById('app').classList.add('hidden');
  const overlay = document.getElementById('force-pw-overlay');
  if (overlay) overlay.classList.remove('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('force-pw-form');
  if (!form) return;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pw = document.getElementById('force-new-pw').value;
    const confirm = document.getElementById('force-confirm-pw').value;
    const errEl = document.getElementById('force-pw-error');
    const btn = document.getElementById('force-pw-btn');
    errEl.classList.add('hidden');
    if (pw !== confirm) {
      errEl.textContent = 'Passwords do not match.';
      errEl.classList.remove('hidden');
      return;
    }
    if (pw.length < 6) {
      errEl.textContent = 'Password must be at least 6 characters.';
      errEl.classList.remove('hidden');
      return;
    }
    btn.disabled = true;
    btn.textContent = 'Saving…';
    try {
      await apiFetch('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ new_password: pw })
      });
      currentUser.must_change_password = false;
      startApp();
    } catch (err) {
      errEl.textContent = err.message || 'Failed to change password.';
      errEl.classList.remove('hidden');
      btn.disabled = false;
      btn.textContent = 'Set Password';
    }
  });
});

// ─── APP START ────────────────────────────────────────────────────────────────

async function startApp() {
  resetSessionTimers();
  applyStoredTheme();
  registerServiceWorker();
  // Hide force-password-change overlay if shown
  const forcePw = document.getElementById('force-pw-overlay');
  if (forcePw) forcePw.classList.add('hidden');
  document.getElementById('login-page').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');

  // Set user info in sidebar
  document.getElementById('user-name').textContent = currentUser.name;
  document.getElementById('user-email').textContent = currentUser.email;
  document.getElementById('user-avatar').textContent = currentUser.name.charAt(0).toUpperCase();

  const isParent = currentUser.role === 'parent';
  const isAdmin = currentUser.role === 'admin';

  // Reset all nav visibility from any previous session
  document.querySelectorAll('.admin-only').forEach(el => el.classList.remove('hidden'));
  document.querySelectorAll('.parent-only').forEach(el => el.classList.remove('hidden'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('hidden'));

  document.getElementById('sidebar-role').textContent =
    isAdmin ? 'Administrator' : isParent ? 'Parent' : 'Teacher';

  // Show/hide role-specific nav
  if (!isAdmin) {
    document.querySelectorAll('.admin-only').forEach(el => el.classList.add('hidden'));
  }
  if (!isParent) {
    document.querySelectorAll('.parent-only').forEach(el => el.classList.add('hidden'));
  }
  if (isParent) {
    // Hide all staff-only nav
    document.querySelectorAll('.nav-item:not(.parent-only)').forEach(el => el.classList.add('hidden'));
  }

  if (isParent) {
    // Parent portal — no need to load all reference data
    try {
      const terms = await apiFetch('/api/terms');
      appData.terms = terms;
      const current = terms.find(t => t.is_current) || terms[0];
      if (current) {
        const badge = document.getElementById('parent-term-badge');
        if (badge) badge.textContent = `${current.academic_year} — Term ${current.term_number}`;
      }
    } catch {}
    await processPaymentCallback();
    navigate('parent-home');
  } else {
    // Staff portal
    await loadReferenceData();
    await processPaymentCallback();
    navigate('dashboard');
  }
}

async function processPaymentCallback() {
  try {
    const params = new URLSearchParams(window.location.search);
    const reference = params.get('reference') || params.get('trxref');
    if (!reference) return;

    const alreadyHandled = sessionStorage.getItem(`verified_payment_${reference}`);
    if (alreadyHandled) {
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }

    const res = await apiFetch('/api/fees/payments/verify', {
      method: 'POST',
      body: JSON.stringify({ reference })
    });

    sessionStorage.setItem(`verified_payment_${reference}`, '1');
    window.history.replaceState({}, document.title, window.location.pathname);
    showToast(res.message || 'Payment verified successfully', 'success', 5000);

    if (currentUser?.role === 'parent' && _parentCurrentTab === 'fees' && _parentCurrentChild) {
      const currentTerm = appData.terms.find(t => t.is_current) || appData.terms[0];
      if (currentTerm) {
        loadParentChildFees(currentTerm);
      }
    }
  } catch (err) {
    const params = new URLSearchParams(window.location.search);
    if (params.get('reference') || params.get('trxref')) {
      showToast(`Payment verification failed: ${err.message}`, 'error', 6000);
    }
  }
}

async function loadReferenceData() {
  try {
    const [classes, terms, subjects] = await Promise.all([
      apiFetch('/api/classes'),
      apiFetch('/api/terms'),
      apiFetch('/api/subjects')
    ]);
    appData.classes = classes;
    appData.terms = terms;
    appData.subjects = subjects;

    // Populate class filter on pupils page
    const classFilter = document.getElementById('pupil-class-filter');
    if (classFilter) {
      classFilter.innerHTML = '<option value="">All Classes</option>' +
        classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    }

    // Populate results selects
    populateResultsSelects();
  } catch (err) {
    console.error('Error loading reference data:', err);
  }
}

// ─── NAVIGATION ───────────────────────────────────────────────────────────────

function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const pageEl = document.getElementById(`page-${page}`);
  if (pageEl) pageEl.classList.add('active');

  const navEl = document.querySelector(`[data-page="${page}"]`);
  if (navEl) navEl.classList.add('active');

  // Close mobile sidebar
  document.getElementById('sidebar').classList.remove('open');

  // Load page data
  switch (page) {
    case 'dashboard': loadDashboard(); break;
    case 'pupils': loadPupils(); break;
    case 'teachers': loadTeachers(); break;
    case 'classes': loadClasses(); break;
    case 'results': loadResultsPage(); break;
    case 'attendance': loadAttendancePage(); break;
    case 'fees': loadFees(); break;
    case 'archive': loadArchive('archived'); break;
    case 'settings': loadSettings(); break;
    case 'parent-home': loadParentHome(); break;
    case 'parent-notices': loadParentNotices(); break;
    case 'parent-child': /* loaded explicitly */ break;
  }
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// ─── DASHBOARD ────────────────────────────────────────────────────────────────

async function loadDashboard() {
  try {
    const [stats, analytics] = await Promise.all([
      apiFetch('/api/stats'),
      apiFetch('/api/analytics').catch(() => ({ subject_averages: [], fee_collection: [], top_performers: [], bottom_performers: [] }))
    ]);
    document.getElementById('stat-pupils').textContent = stats.total_pupils;
    document.getElementById('stat-teachers').textContent = stats.total_teachers;
    document.getElementById('stat-classes').textContent = stats.total_classes;
    document.getElementById('stat-archived').textContent = stats.archived + stats.graduated;

    const tb = document.getElementById('current-term-badge');
    if (stats.current_term) {
      tb.textContent = `${stats.current_term.academic_year} — Term ${stats.current_term.term_number}`;
    } else {
      tb.textContent = 'No current term set';
    }

    const breakdownEl = document.getElementById('class-breakdown-table');
    breakdownEl.innerHTML = `
      <table class="class-breakdown-table">
        <thead><tr>
          <th>Class</th><th>Teacher</th><th>Pupils</th><th>Actions</th>
        </tr></thead>
        <tbody>${stats.class_breakdown.map(c => `
          <tr>
            <td><strong>${c.name}</strong></td>
            <td>${c.teacher_name || '<span class="text-muted">Unassigned</span>'}</td>
            <td><span class="badge badge-active">${c.count}</span></td>
            <td>
              <button class="btn btn-sm btn-secondary" onclick="document.getElementById('pupil-class-filter').value='${c.id}'; navigate('pupils')">
                View Pupils
              </button>
            </td>
          </tr>
        `).join('')}</tbody>
      </table>`;

    const analyticsEl = document.getElementById('dashboard-analytics');
    if (analyticsEl) {
      const subjectRows = (analytics.subject_averages || []).slice(0, 8).map(r => {
        const width = Math.max(6, Math.min(100, Number(r.average_score || 0)));
        return `
          <div class="mini-bar-row">
            <div class="mini-bar-label">${esc(r.class_name)} · ${esc(r.subject_name)}</div>
            <div class="mini-bar-track"><div class="mini-bar-fill" style="width:${width}%"></div></div>
            <div class="mini-bar-value">${Number(r.average_score || 0).toFixed(1)}</div>
          </div>`;
      }).join('') || '<div class="empty-state">No analytics yet.</div>';
      const feeRows = (analytics.fee_collection || []).map(r => {
        const expected = Number(r.expected_total || 0);
        const collected = Number(r.collected_total || 0);
        const pct = expected ? Math.min(100, (collected / expected) * 100) : 0;
        return `
          <div class="mini-bar-row">
            <div class="mini-bar-label">${esc(r.class_name)}</div>
            <div class="mini-bar-track success"><div class="mini-bar-fill success" style="width:${pct}%"></div></div>
            <div class="mini-bar-value">₦${collected.toLocaleString()}</div>
          </div>`;
      }).join('') || '<div class="empty-state">No fee data yet.</div>';
      const top = (analytics.top_performers || []).map(p => `<li>${esc(p.first_name)} ${esc(p.last_name)} <strong>${Number(p.average_score || 0).toFixed(1)}</strong></li>`).join('') || '<li>No scores yet</li>';
      const bottom = (analytics.bottom_performers || []).map(p => `<li>${esc(p.first_name)} ${esc(p.last_name)} <strong>${Number(p.average_score || 0).toFixed(1)}</strong></li>`).join('') || '<li>No scores yet</li>';
      analyticsEl.innerHTML = `
        <div class="analytics-grid">
          <div class="analytics-card">
            <h4>Subject Averages</h4>
            ${subjectRows}
          </div>
          <div class="analytics-card">
            <h4>Fee Collection Rate</h4>
            ${feeRows}
          </div>
          <div class="analytics-card">
            <h4>Top Performers</h4>
            <ol class="analytics-list">${top}</ol>
          </div>
          <div class="analytics-card">
            <h4>Needs Attention</h4>
            <ol class="analytics-list">${bottom}</ol>
          </div>
        </div>
        <div class="analytics-summary-grid">
          <div class="summary-chip">Attendance Today: Present ${stats.attendance_today?.present || 0}, Late ${stats.attendance_today?.late || 0}, Absent ${stats.attendance_today?.absent || 0}</div>
          <div class="summary-chip">Fees Collected Today: ₦${Number(stats.fee_collection_today || 0).toLocaleString()}</div>
          <div class="summary-chip">Active Homework: ${stats.active_homework || 0}</div>
          <div class="summary-chip">Upcoming Events: ${stats.upcoming_events || 0}</div>
        </div>`;
    }
  } catch (err) {
    showToast('Failed to load dashboard: ' + err.message, 'error');
  }
}

async function loadAttendancePage() {
  const classSelect = document.getElementById('attendance-class-select');
  const dateInput = document.getElementById('attendance-date');
  if (!classSelect || !dateInput) return;
  const previousClassId = classSelect.value;

  if (!dateInput.value) dateInput.value = new Date().toISOString().split('T')[0];
  if (currentUser.role === 'teacher' && currentUser.class) {
    const teacherClass = appData.classes.find(c => c.id === currentUser.class.id) || currentUser.class;
    const pupilCount = Number(teacherClass?.pupil_count || 0);
    classSelect.innerHTML = `<option value="${currentUser.class.id}">${currentUser.class.name}${pupilCount ? ` (${pupilCount})` : ''}</option>`;
    classSelect.disabled = true;
  } else {
    classSelect.disabled = false;
    classSelect.innerHTML = '<option value="">— Select Class —</option>' +
      appData.classes.map(c => `<option value="${c.id}">${c.name}${Number(c.pupil_count || 0) ? ` (${c.pupil_count})` : ''}</option>`).join('');

    if (previousClassId && appData.classes.some(c => c.id === previousClassId)) {
      classSelect.value = previousClassId;
    } else {
      const defaultClass = appData.classes.find(c => Number(c.pupil_count || 0) > 0) || appData.classes[0];
      if (defaultClass) classSelect.value = defaultClass.id;
    }
  }

  const classId = classSelect.value;
  if (!classId) {
    document.getElementById('attendance-register').innerHTML = '<div class="empty">Select a class to load attendance.</div>';
    return;
  }
  try {
    const data = await apiFetch(`/api/attendance?class_id=${classId}&date=${dateInput.value}`);
    renderAttendanceRegister(data);
  } catch (err) {
    document.getElementById('attendance-register').innerHTML = `<div class="empty">${err.message}</div>`;
  }
}

function renderAttendanceRegister(data) {
  const container = document.getElementById('attendance-register');
  const badge = document.getElementById('attendance-summary-badge');
  if (badge) badge.textContent = `${data.date} · P:${data.summary.present || 0} L:${data.summary.late || 0} A:${data.summary.absent || 0}`;
  const rows = (data.records || []).map((p, idx) => {
    const current = p.attendance_status || 'present';
    return `
      <tr>
        <td>${idx + 1}</td>
        <td><strong>${esc(p.last_name)}, ${esc(p.first_name)}</strong></td>
        <td>${esc(p.parent_name || '—')}</td>
        <td>
          <select class="attendance-status" data-pupil-id="${p.id}">
            <option value="present" ${current === 'present' ? 'selected' : ''}>Present</option>
            <option value="late" ${current === 'late' ? 'selected' : ''}>Late</option>
            <option value="absent" ${current === 'absent' ? 'selected' : ''}>Absent</option>
          </select>
        </td>
        <td><input class="attendance-notes" data-pupil-id="${p.id}" value="${esc(p.attendance_notes || '')}" placeholder="Optional note" /></td>
      </tr>`;
  }).join('');
  const selectedClass = appData.classes.find(c => c.id === data.class_id);
  const otherClassesWithPupils = appData.classes.filter(c => c.id !== data.class_id && Number(c.pupil_count || 0) > 0);
  container.innerHTML = rows ? `
    <table class="data-table">
      <thead><tr><th>#</th><th>Pupil</th><th>Parent</th><th>Status</th><th>Notes</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>` : `<div class="empty">${esc(selectedClass?.name || 'This class')} has no active pupils.${otherClassesWithPupils.length ? ` Try ${esc(otherClassesWithPupils[0].name)} or another class with pupils.` : ''}</div>`;
}

async function saveAttendanceRegister() {
  const classId = document.getElementById('attendance-class-select')?.value;
  const date = document.getElementById('attendance-date')?.value;
  if (!classId || !date) return showToast('Select a class and date first', 'error');
  const statuses = [...document.querySelectorAll('.attendance-status')].map(sel => ({
    pupil_id: sel.dataset.pupilId,
    status: sel.value,
    notes: document.querySelector(`.attendance-notes[data-pupil-id="${sel.dataset.pupilId}"]`)?.value || ''
  }));
  try {
    const res = await apiFetch('/api/attendance', {
      method: 'POST',
      body: JSON.stringify({ class_id: classId, date, records: statuses })
    });
    showToast(`${res.message}${res.alerts_sent ? ` • ${res.alerts_sent} absence alerts sent` : ''}`, 'success');
    loadAttendancePage();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function publishCurrentResults() {
  const termId = document.getElementById('results-term-select')?.value;
  const classId = document.getElementById('results-class-select')?.value;
  if (!termId) return showToast('Select a term first', 'error');
  if (!confirm('Publish these results to parents via WhatsApp/SMS/email notifications?')) return;
  try {
    const res = await apiFetch('/api/results/publish', {
      method: 'POST',
      body: JSON.stringify({ term_id: termId, class_id: classId || null })
    });
    showToast(res.message, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ─── PUPILS ───────────────────────────────────────────────────────────────────

async function loadPupils() {
  const container = document.getElementById('pupils-list');
  container.innerHTML = '<div class="loading">Loading pupils…</div>';
  try {
    const classId = document.getElementById('pupil-class-filter').value;
    const search = document.getElementById('pupil-search').value;
    let url = '/api/pupils?status=active';
    if (classId) url += `&class_id=${classId}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    const pupils = await apiFetch(url);
    appData.pupils = pupils;
    renderPupilsTable(pupils);
  } catch (err) {
    container.innerHTML = `<div class="empty">Failed to load: ${err.message}</div>`;
  }
}

function filterPupils() {
  clearTimeout(filterPupils._timer);
  filterPupils._timer = setTimeout(loadPupils, 300);
}

function renderPupilsTable(pupils) {
  const container = document.getElementById('pupils-list');
  if (!pupils.length) {
    container.innerHTML = '<div class="empty">No pupils found.</div>';
    return;
  }
  const isAdmin = currentUser.role === 'admin';
  container.innerHTML = `
    <table class="data-table">
      <thead><tr>
        <th>Pupil</th><th>Admission No.</th><th>Class</th><th>Gender</th><th>Parent Contact</th><th>Actions</th>
      </tr></thead>
      <tbody>${pupils.map(p => `
        <tr>
          <td>
            <div class="pupil-info">
              ${p.photo
                ? `<div class="pupil-avatar"><img src="${p.photo}" alt="photo"/></div>`
                : `<div class="pupil-avatar">${esc(p.first_name).charAt(0)}${esc(p.last_name).charAt(0)}</div>`}
              <div>
                <div class="pupil-name">${esc(p.last_name)}, ${esc(p.first_name)} ${esc(p.other_name || '')}</div>
                <div class="pupil-adm">${esc(p.admission_number || '')}</div>
              </div>
            </div>
          </td>
          <td>${esc(p.admission_number || '—')}</td>
          <td>${p.class_name ? esc(p.class_name) : '<span class="text-muted">—</span>'}</td>
          <td><span class="badge badge-${p.gender}">${p.gender || '—'}</span></td>
          <td>${p.parent_phone ? esc(p.parent_phone) : '<span class="text-muted">—</span>'}</td>
          <td>
            <div class="actions">
              <button class="btn-icon" title="View Profile" onclick="viewPupil('${p.id}')">👁️</button>
              ${isAdmin ? `<button class="btn-icon" title="Edit" onclick="editPupil('${p.id}')">✏️</button>` : ''}
              ${isAdmin ? `<button class="btn-icon" title="Archive" onclick="archivePupil('${p.id}', '${p.first_name} ${p.last_name}')">📦</button>` : ''}
            </div>
          </td>
        </tr>
      `).join('')}</tbody>
    </table>`;
}

function showAddPupil() {
  openModal('Add New Pupil', pupilForm(null));
}

function editPupil(id) {
  const pupilId = String(id);
  const pupil = appData.pupils.find(p => String(p.id) === pupilId);
  if (pupil) {
    openModal('Edit Pupil', pupilForm(pupil));
    return;
  }

  // Keep UX responsive when list cache is cold/mismatched
  openModal('Edit Pupil', '<div class="loading">Loading pupil…</div>');
  apiFetch(`/api/pupils/${encodeURIComponent(pupilId)}`)
    .then(p => openModal('Edit Pupil', pupilForm(p)))
    .catch(err => {
      closeModal();
      showToast('Error loading pupil: ' + err.message, 'error');
    });
}

function editPupilFromProfile(id) {
  // Close profile modal first, then open edit modal on next tick.
  // Prevents openModal->closeModal race from inline chained calls.
  closeModal();
  setTimeout(() => editPupil(id), 0);
}

function pupilForm(pupil) {
  const classes = appData.classes;
  const isEdit = !!pupil;
  return `
    <form id="pupil-form" onsubmit="savePupil(event, '${isEdit ? pupil.id : ''}')">
      <div class="form-section">
        <h4>Personal Information</h4>
        <div class="photo-upload-area" onclick="document.getElementById('photo-input').click()" id="photo-area">
          ${pupil && pupil.photo
            ? `<img src="${pupil.photo}" class="photo-preview" id="photo-preview" />`
            : `<div class="photo-placeholder">📷</div>`}
          <div class="text-sm text-muted">Click to upload photo</div>
          <input type="file" id="photo-input" accept="image/*" style="display:none" onchange="handlePhotoUpload(event)" />
        </div>
        <input type="hidden" id="f-photo" value="${pupil ? (pupil.photo || '') : ''}" />
        <div class="form-grid">
          <div class="form-group">
            <label>First Name *</label>
            <input type="text" name="first_name" value="${pupil ? pupil.first_name : ''}" required />
          </div>
          <div class="form-group">
            <label>Last Name *</label>
            <input type="text" name="last_name" value="${pupil ? pupil.last_name : ''}" required />
          </div>
          <div class="form-group">
            <label>Other Name</label>
            <input type="text" name="other_name" value="${pupil ? (pupil.other_name || '') : ''}" />
          </div>
          <div class="form-group">
            <label>Admission Number</label>
            <input type="text" name="admission_number" value="${pupil ? (pupil.admission_number || '') : ''}" placeholder="Auto-generated if empty" />
          </div>
          <div class="form-group">
            <label>Date of Birth</label>
            <input type="date" name="date_of_birth" value="${pupil ? (pupil.date_of_birth || '') : ''}" />
          </div>
          <div class="form-group">
            <label>Gender</label>
            <select name="gender">
              <option value="">— Select —</option>
              <option value="male" ${pupil && pupil.gender === 'male' ? 'selected' : ''}>Male</option>
              <option value="female" ${pupil && pupil.gender === 'female' ? 'selected' : ''}>Female</option>
            </select>
          </div>
          <div class="form-group">
            <label>Class</label>
            <select name="class_id">
              <option value="">— Select Class —</option>
              ${classes.map(c => `<option value="${c.id}" ${pupil && pupil.class_id === c.id ? 'selected' : ''}>${c.name}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label>Blood Group</label>
            <select name="blood_group">
              <option value="">— Select —</option>
              ${['A+','A-','B+','B-','AB+','AB-','O+','O-'].map(b => `<option ${pupil && pupil.blood_group === b ? 'selected' : ''}>${b}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label>Religion</label>
            <select name="religion">
              <option value="">— Select —</option>
              <option value="Christianity" ${pupil && pupil.religion === 'Christianity' ? 'selected' : ''}>Christianity</option>
              <option value="Islam" ${pupil && pupil.religion === 'Islam' ? 'selected' : ''}>Islam</option>
              <option value="Other" ${pupil && pupil.religion === 'Other' ? 'selected' : ''}>Other</option>
            </select>
          </div>
        </div>
      </div>
      <div class="form-section">
        <h4>Parent / Guardian Information</h4>
        <div class="form-grid">
          <div class="form-group">
            <label>Parent/Guardian Name</label>
            <input type="text" name="parent_name" value="${pupil ? (pupil.parent_name || '') : ''}" />
          </div>
          <div class="form-group">
            <label>Relationship</label>
            <select name="parent_relationship">
              <option value="">— Select —</option>
              ${['Father','Mother','Guardian','Uncle','Aunt','Grandparent'].map(r =>
                `<option ${pupil && pupil.parent_relationship === r ? 'selected' : ''}>${r}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label>Phone Number</label>
            <input type="tel" name="parent_phone" value="${pupil ? (pupil.parent_phone || '') : ''}" />
          </div>
          <div class="form-group">
            <label>Email Address</label>
            <input type="email" name="parent_email" value="${pupil ? (pupil.parent_email || '') : ''}" />
          </div>
        </div>
        <div class="form-group">
          <label>Home Address</label>
          <textarea name="parent_address" rows="2">${pupil ? (pupil.parent_address || '') : ''}</textarea>
        </div>
      </div>
      <div class="form-section">
        <h4>Emergency Contact</h4>
        <div class="form-grid">
          <div class="form-group">
            <label>Emergency Contact Name</label>
            <input type="text" name="emergency_name" value="${pupil ? (pupil.emergency_name || '') : ''}" />
          </div>
          <div class="form-group">
            <label>Emergency Contact Phone</label>
            <input type="tel" name="emergency_phone" value="${pupil ? (pupil.emergency_phone || '') : ''}" />
          </div>
        </div>
      </div>
      <div class="form-section">
        <h4>Medical Record</h4>
        <div class="form-grid">
          <div class="form-group">
            <label>Allergies</label>
            <input type="text" name="allergies" value="${pupil ? (pupil.allergies || '') : ''}" />
          </div>
          <div class="form-group">
            <label>Medical Conditions</label>
            <input type="text" name="medical_conditions" value="${pupil ? (pupil.medical_conditions || '') : ''}" />
          </div>
          <div class="form-group">
            <label>Doctor's Name</label>
            <input type="text" name="doctor_name" value="${pupil ? (pupil.doctor_name || '') : ''}" />
          </div>
          <div class="form-group">
            <label>Doctor's Phone</label>
            <input type="tel" name="doctor_phone" value="${pupil ? (pupil.doctor_phone || '') : ''}" />
          </div>
        </div>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">${isEdit ? 'Save Changes' : 'Add Pupil'}</button>
      </div>
    </form>`;
}

function handlePhotoUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const dataUrl = e.target.result;
    document.getElementById('f-photo').value = dataUrl;
    const area = document.getElementById('photo-area');
    area.innerHTML = `<img src="${dataUrl}" class="photo-preview" /><div class="text-sm text-muted">Click to change</div><input type="file" id="photo-input" accept="image/*" style="display:none" onchange="handlePhotoUpload(event)" />`;
  };
  reader.readAsDataURL(file);
}

async function savePupil(e, pupilId) {
  e.preventDefault();
  const form = e.target;
  const data = {};
  new FormData(form).forEach((v, k) => { data[k] = v; });
  data.photo = document.getElementById('f-photo').value;

  try {
    if (pupilId) {
      await apiFetch(`/api/pupils/${pupilId}`, { method: 'PUT', body: JSON.stringify(data) });
      showToast('Pupil updated successfully', 'success');
    } else {
      await apiFetch('/api/pupils', { method: 'POST', body: JSON.stringify(data) });
      showToast('Pupil added successfully', 'success');
    }
    closeModal();
    loadPupils();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function archivePupil(id, name) {
  if (!confirm(`Archive ${name}? They can be restored from the Archive section.`)) return;
  try {
    await apiFetch(`/api/pupils/${id}`, { method: 'DELETE' });
    showToast('Pupil archived', 'success');
    loadPupils();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function viewPupil(id) {
  try {
    const pupil = await apiFetch(`/api/pupils/${id}`);
    const terms = appData.terms;
    openModal(`${pupil.first_name} ${pupil.last_name}`, pupilProfile(pupil, terms));
  } catch (err) {
    showToast('Error loading pupil: ' + err.message, 'error');
  }
}

function pupilProfile(p, terms) {
  const isAdmin = currentUser.role === 'admin';
  return `
    <div class="profile-header" style="background:var(--gray-50);border-radius:8px;padding:16px;display:flex;align-items:center;gap:16px;margin-bottom:16px;flex-wrap:wrap">
      <div class="profile-photo">
        ${p.photo ? `<img src="${p.photo}" />` : p.first_name.charAt(0) + p.last_name.charAt(0)}
      </div>
      <div>
        <div class="profile-name">${esc(p.last_name)}, ${esc(p.first_name)} ${esc(p.other_name || '')}</div>
        <div class="profile-meta">${esc(p.admission_number || '')} · ${esc(p.class_name || 'No class')}</div>
        <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">
          <span class="badge badge-${p.gender}">${p.gender || '—'}</span>
          <span class="badge badge-active">Active</span>
          ${p.blood_group ? `<span class="badge" style="background:#fef2f2;color:#dc2626">${p.blood_group}</span>` : ''}
        </div>
      </div>
      ${isAdmin ? `<div style="margin-left:auto;display:flex;gap:8px">
        <button class="btn btn-secondary btn-sm" onclick="editPupilFromProfile('${p.id}')">✏️ Edit</button>
      </div>` : ''}
    </div>
    <div class="profile-sections" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px">
      <div class="info-card">
        <h4>Personal Details</h4>
        ${infoRow('Date of Birth', p.date_of_birth || '—')}
        ${infoRow('Religion', p.religion || '—')}
        ${infoRow('Blood Group', p.blood_group || '—')}
      </div>
      <div class="info-card">
        <h4>Parent / Guardian</h4>
        ${infoRow('Name', esc(p.parent_name || '—'))}
        ${infoRow('Relationship', esc(p.parent_relationship || '—'))}
        ${infoRow('Phone', esc(p.parent_phone || '—'))}
        ${infoRow('Email', esc(p.parent_email || '—'))}
      </div>
    </div>
    <div style="margin-top:12px;background:white;border:1px solid var(--gray-200);border-radius:8px;padding:16px">
      <!-- Row 1: Term selector + results/report actions -->
      <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px">
        <span style="font-size:13px;font-weight:600;color:var(--gray-700);white-space:nowrap">Results</span>
        <select id="profile-term-select" style="font-size:12px;padding:4px 8px;border:1px solid var(--gray-300);border-radius:6px">
          ${terms.map(t => `<option value="${t.id}">${t.academic_year} Term ${t.term_number}${t.is_current?' (Current)':''}</option>`).join('')}
        </select>
        <button class="btn btn-sm btn-secondary" onclick="viewPupilResults('${p.id}')">View</button>
        ${p.class_type === 'lower'
          ? `<button class="btn btn-sm btn-secondary" onclick="openSkillEntry('${p.id}')">📋 Skills</button>
             <button class="btn btn-sm btn-primary" onclick="generateLowerSchoolReport('${p.id}')">📄 Report Card</button>`
          : `<button class="btn btn-sm btn-secondary" onclick="openConductEntry('${p.id}')">✏️ Conduct</button>
             <button class="btn btn-sm btn-primary" onclick="generateReport('${p.id}')">📄 Report Card</button>`
        }
        <button class="btn btn-sm" style="background:#7B1D1D;color:white" onclick="generatePupilIDCard('${p.id}')">🪪 ID Card</button>
      </div>
      <!-- Row 2: Parent acknowledgments (visually separated) -->
      <div style="border-top:1px solid var(--gray-100);padding-top:9px;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <span style="font-size:12px;font-weight:600;color:var(--gray-600)">Parent Sign-off:</span>
        <button class="btn btn-sm"
          style="background:#15803d;color:white;display:inline-flex;align-items:center;gap:5px"
          onclick="viewPupilAcknowledgments('${p.id}')">
          ✅ View Acknowledgments
        </button>
        <span style="font-size:11px;color:var(--gray-400);font-style:italic">Shows when parent confirmed seeing results</span>
      </div>
      <div id="pupil-results-preview" class="text-muted text-sm" style="padding:20px;text-align:center;margin-top:8px">Select a term and click View to see results</div>
    </div>`;
}

function infoRow(label, value) {
  return `<div class="info-row"><span class="info-label">${label}</span><span class="info-value">${value}</span></div>`;
}

async function viewPupilResults(pupilId) {
  const termId = document.getElementById('profile-term-select').value;
  if (!termId) return;
  try {
    const results = await apiFetch(`/api/results?pupil_id=${pupilId}&term_id=${termId}`);
    const el = document.getElementById('pupil-results-preview');
    if (!results.length) {
      el.innerHTML = '<div style="text-align:center;padding:20px;color:var(--gray-400)">No results recorded for this term</div>';
      return;
    }
    const rows = results.map(r => {
      const total = (r.ca_score || 0) + (r.exam_score || 0);
      return `<tr>
        <td>${esc(r.subject_name)}</td>
        <td style="text-align:center">${r.ca_score || 0}</td>
        <td style="text-align:center">${r.exam_score || 0}</td>
        <td style="text-align:center;font-weight:700">${total}</td>
      </tr>`;
    }).join('');
    const grandTotal = results.reduce((s, r) => s + (r.ca_score || 0) + (r.exam_score || 0), 0);
    const avg = (grandTotal / results.length).toFixed(1);
    el.innerHTML = `
      <table class="data-table" style="font-size:13px">
        <thead><tr><th>Subject</th><th style="text-align:center">CA/40</th><th style="text-align:center">Exam/60</th><th style="text-align:center">Total/100</th></tr></thead>
        <tbody>${rows}</tbody>
        <tfoot><tr style="background:var(--gray-50)">
          <td colspan="3" style="padding:10px 14px;font-weight:700">Average</td>
          <td style="padding:10px 14px;font-weight:700;text-align:center;color:var(--primary)">${avg}</td>
        </tr></tfoot>
      </table>`;
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ─── VIEW ACKNOWLEDGMENTS ─────────────────────────────────────────────────────

async function viewPupilAcknowledgments(pupilId) {
  const el = document.getElementById('pupil-results-preview');
  el.innerHTML = '<div class="loading">Loading acknowledgments…</div>';
  try {
    const acks = await apiFetch(`/api/acknowledgments?pupil_id=${pupilId}`);
    if (!acks.length) {
      el.innerHTML = '<div style="text-align:center;padding:20px;color:var(--gray-400)">No parent acknowledgments recorded for this pupil yet.</div>';
      return;
    }
    const rows = acks.map(a => {
      const term = appData.terms.find(t => t.id === a.term_id);
      const termLabel = term ? `${term.academic_year} Term ${term.term_number}` : a.term_id;
      const date = new Date(a.acknowledged_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
      return `<tr>
        <td>${termLabel}</td>
        <td><span class="badge badge-active">✅ Acknowledged</span></td>
        <td>${date}</td>
        <td style="font-style:italic;color:var(--gray-500)">${esc(a.parent_comment || '—')}</td>
      </tr>`;
    }).join('');
    el.innerHTML = `
      <div style="text-align:left;margin-bottom:8px">
        <h4 style="font-size:14px;font-weight:600;color:#15803d">✅ Parent Acknowledgments</h4>
      </div>
      <table class="data-table" style="font-size:13px">
        <thead><tr>
          <th>Term</th><th>Status</th><th>Date</th><th>Parent Comment</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (err) {
    el.innerHTML = `<div style="text-align:center;padding:20px;color:#dc2626">Error: ${err.message}</div>`;
  }
}

// ─── CONDUCT ENTRY ────────────────────────────────────────────────────────────

async function openConductEntry(pupilId) {
  const termSelect = document.getElementById('profile-term-select');
  const termId = termSelect ? termSelect.value : null;
  if (!termId) return showToast('Please select a term first', 'error');

  let existing = {};
  try { existing = await apiFetch(`/api/conduct/${pupilId}/term/${termId}`); } catch {}

  const ratingField = (fieldId, label, val) => {
    const opts = ['E','VG','G','F','P'];
    const btns = opts.map(r => {
      const sel = (val||'').toUpperCase() === r;
      return `<label style="cursor:pointer;display:inline-flex;align-items:center;gap:3px;margin-right:6px">
        <input type="radio" name="${fieldId}" value="${r}" ${sel?'checked':''} style="margin:0" />
        <span style="font-size:12px">${r}</span>
      </label>`;
    }).join('');
    return `<div style="display:flex;align-items:center;justify-content:space-between;padding:5px 0;border-bottom:1px solid #f3f4f6">
      <span style="font-size:13px;min-width:120px">${label}</span>
      <span>${btns}</span>
    </div>`;
  };

  const body = `
    <div style="max-height:70vh;overflow-y:auto;padding:4px">
      <p style="font-size:12px;color:#6b7280;margin-bottom:12px">Rate each trait: E=Excellent, VG=Very Good, G=Good, F=Fair, P=Poor</p>
      <div style="font-weight:700;font-size:13px;color:#7B1D1D;margin-bottom:6px">Conduct Observations</div>
      ${ratingField('conduct_punctuality','Punctuality',existing.punctuality)}
      ${ratingField('conduct_honesty','Honesty',existing.honesty)}
      ${ratingField('conduct_cleanliness','Cleanliness',existing.cleanliness)}
      ${ratingField('conduct_leadership','Leadership',existing.leadership)}
      ${ratingField('conduct_politeness','Politeness',existing.politeness)}
      ${ratingField('conduct_attentiveness','Attentiveness',existing.attentiveness)}
      <div style="font-weight:700;font-size:13px;color:#7B1D1D;margin:12px 0 6px">Physical / Skills</div>
      ${ratingField('conduct_writing','H/Writing',existing.writing)}
      ${ratingField('conduct_handwork','Handwork',existing.handwork)}
      ${ratingField('conduct_verbal_fluency','Verbal Fluency',existing.verbal_fluency)}
      ${ratingField('conduct_drama','Drama',existing.drama)}
      ${ratingField('conduct_sports','Sports',existing.sports)}
      <div style="margin-top:14px">
        <div style="font-weight:700;font-size:13px;color:#7B1D1D;margin-bottom:5px">Class Teacher's Comment</div>
        <textarea id="conduct_teacher_comment" rows="2" style="width:100%;font-size:13px;padding:7px;border:1px solid #d1d5db;border-radius:5px;resize:vertical;box-sizing:border-box">${existing.teacher_comment||''}</textarea>
      </div>
      <div style="margin-top:10px">
        <div style="font-weight:700;font-size:13px;color:#7B1D1D;margin-bottom:5px">Administrator's Comment</div>
        <textarea id="conduct_admin_comment" rows="2" style="width:100%;font-size:13px;padding:7px;border:1px solid #d1d5db;border-radius:5px;resize:vertical;box-sizing:border-box">${existing.admin_comment||''}</textarea>
      </div>
      <div style="margin-top:16px;display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="saveConductEntry('${pupilId}','${termId}')">Save Conduct</button>
      </div>
    </div>`;

  openModal('Conduct & Skills Ratings', body);
}

async function saveConductEntry(pupilId, termId) {
  const get = (name) => {
    const el = document.querySelector(`input[name="${name}"]:checked`);
    return el ? el.value : '';
  };
  const payload = {
    punctuality: get('conduct_punctuality'),
    honesty: get('conduct_honesty'),
    cleanliness: get('conduct_cleanliness'),
    leadership: get('conduct_leadership'),
    politeness: get('conduct_politeness'),
    attentiveness: get('conduct_attentiveness'),
    writing: get('conduct_writing'),
    handwork: get('conduct_handwork'),
    verbal_fluency: get('conduct_verbal_fluency'),
    drama: get('conduct_drama'),
    sports: get('conduct_sports'),
    teacher_comment: document.getElementById('conduct_teacher_comment').value.trim(),
    admin_comment: document.getElementById('conduct_admin_comment').value.trim()
  };
  try {
    await apiFetch(`/api/conduct/${pupilId}/term/${termId}`, { method: 'POST', body: JSON.stringify(payload) });
    showToast('Conduct ratings saved!', 'success');
    closeModal();
  } catch (err) {
    showToast('Error saving: ' + err.message, 'error');
  }
}

// ─── TEACHERS ─────────────────────────────────────────────────────────────────

async function loadTeachers() {
  const container = document.getElementById('teachers-list');
  container.innerHTML = '<div class="loading">Loading teachers…</div>';
  try {
    const teachers = await apiFetch('/api/teachers');
    if (!teachers.length) {
      container.innerHTML = '<div class="empty">No teachers registered yet.</div>';
      return;
    }
    container.innerHTML = `
      <table class="data-table">
        <thead><tr>
          <th>Name</th><th>Email</th><th>Phone</th><th>Assigned Class</th><th>Actions</th>
        </tr></thead>
        <tbody>${teachers.map(t => `
          <tr>
            <td>
              <div style="display:flex;align-items:center;gap:10px">
                <div class="user-avatar" style="width:32px;height:32px;font-size:13px">${esc(t.name).charAt(0)}</div>
                <strong>${esc(t.name)}</strong>
              </div>
            </td>
            <td>${esc(t.email)}</td>
            <td>${t.phone ? esc(t.phone) : '—'}</td>
            <td>${t.class_name ? `<span class="badge badge-active">${esc(t.class_name)}</span>` : '<span class="text-muted">Unassigned</span>'}</td>
            <td>
              <div class="actions">
                <button class="btn-icon" title="Edit" onclick="editTeacher(${JSON.stringify(t).replace(/"/g, '&quot;')})">✏️</button>
                <button class="btn-icon" title="ID Card" onclick="generateTeacherIDCard('${t.id}', '${t.name.replace(/'/g, "\\'")}')">🪪</button>
                <button class="btn-icon" title="Remove" onclick="deleteTeacher('${t.id}', '${t.name}')">🗑️</button>
              </div>
            </td>
          </tr>
        `).join('')}</tbody>
      </table>`;
  } catch (err) {
    container.innerHTML = `<div class="empty">Failed to load: ${err.message}</div>`;
  }
}

function showAddTeacher() {
  openModal('Add New Teacher', teacherForm(null));
}

function editTeacher(teacher) {
  openModal('Edit Teacher', teacherForm(teacher));
}

function teacherForm(t) {
  const classes = appData.classes;
  const isEdit = !!t;
  return `
    <form id="teacher-form" onsubmit="saveTeacher(event, '${isEdit ? t.id : ''}')">
      <div class="form-grid">
        <div class="form-group">
          <label>Full Name *</label>
          <input type="text" name="name" value="${t ? t.name : ''}" required />
        </div>
        <div class="form-group">
          <label>Email Address *</label>
          <input type="email" name="email" value="${t ? t.email : ''}" ${isEdit ? 'readonly' : 'required'} />
        </div>
        <div class="form-group">
          <label>Phone Number</label>
          <input type="tel" name="phone" value="${t ? (t.phone || '') : ''}" />
        </div>
        <div class="form-group">
          <label>Assign to Class</label>
          <select name="class_id">
            <option value="">— Unassigned —</option>
            ${classes.map(c => `<option value="${c.id}" ${t && t.class_id === c.id ? 'selected' : ''}>${c.name}</option>`).join('')}
          </select>
        </div>
        <div class="form-group">
          <label>${isEdit ? 'New Password (leave blank to keep)' : 'Password *'}</label>
          <input type="password" name="password" ${isEdit ? '' : 'required'} minlength="6" placeholder="${isEdit ? 'Leave blank to keep current' : 'Minimum 6 characters'}" />
        </div>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">${isEdit ? 'Save Changes' : 'Add Teacher'}</button>
      </div>
    </form>`;
}

async function saveTeacher(e, teacherId) {
  e.preventDefault();
  const data = {};
  new FormData(e.target).forEach((v, k) => { if (v) data[k] = v; });
  try {
    if (teacherId) {
      await apiFetch(`/api/teachers/${teacherId}`, { method: 'PUT', body: JSON.stringify(data) });
      showToast('Teacher updated', 'success');
    } else {
      await apiFetch('/api/teachers', { method: 'POST', body: JSON.stringify(data) });
      showToast('Teacher added', 'success');
    }
    closeModal();
    loadTeachers();
    loadReferenceData();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function deleteTeacher(id, name) {
  if (!confirm(`Remove ${name} as a teacher? This cannot be undone.`)) return;
  try {
    await apiFetch(`/api/teachers/${id}`, { method: 'DELETE' });
    showToast('Teacher removed', 'success');
    loadTeachers();
    loadReferenceData();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ─── CLASSES ──────────────────────────────────────────────────────────────────

async function loadClasses() {
  const container = document.getElementById('classes-grid');
  container.innerHTML = '<div class="loading">Loading classes…</div>';
  try {
    const classes = await apiFetch('/api/classes');
    const teachers = await apiFetch('/api/teachers');
    appData.classes = classes;
    container.innerHTML = classes.map(c => `
      <div class="class-card">
        <div class="class-card-title">${c.name}</div>
        <div class="class-card-info">
          ${c.teacher_name
            ? `<span style="color:var(--success)">👩‍🏫 ${esc(c.teacher_name)}</span>`
            : `<span style="color:var(--gray-400)">No teacher assigned</span>`}
        </div>
        <div style="display:flex;gap:8px;align-items:center;background:var(--gray-50);border-radius:6px;padding:10px">
          <span style="font-size:24px;font-weight:700;color:var(--primary)">${c.pupil_count}</span>
          <span style="font-size:12px;color:var(--gray-500)">Active Pupils</span>
        </div>
        <div style="margin-bottom:8px">
          <button class="btn btn-sm btn-secondary" style="width:100%" onclick="document.getElementById('pupil-class-filter').value='${c.id}'; navigate('pupils')">
            👀 View Pupils
          </button>
        </div>
        <div class="class-card-footer">
          <select id="assign-${c.id}" style="font-size:12px;flex:1;margin-right:8px">
            <option value="">— No Teacher —</option>
            ${teachers.map(t => `<option value="${t.id}" ${c.teacher_id === t.id ? 'selected' : ''}>${t.name}</option>`).join('')}
          </select>
          <button class="btn btn-sm btn-secondary" onclick="assignTeacher('${c.id}')">Assign</button>
        </div>
        ${currentUser.role === 'admin' ? `
        <div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--gray-100)">
          <button class="btn btn-sm btn-warning" style="width:100%" onclick="promoteClass('${c.id}')">
            🎓 ${getPromotionActionText(c)}
          </button>
        </div>` : ''}
      </div>`).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty">Failed to load: ${err.message}</div>`;
  }
}

function getPromotionTargetClass(cls) {
  if (!cls) return null;
  const classType = cls.class_type || 'primary';
  const level = Number(cls.level || 0);
  if (classType === 'primary') {
    if (level >= 6) return null;
    return (appData.classes || []).find(c => (c.class_type || 'primary') === 'primary' && Number(c.level) === level + 1) || null;
  }
  if (classType === 'lower') {
    if (level >= 3) {
      return (appData.classes || []).find(c => (c.class_type || 'primary') === 'primary' && Number(c.level) === 1) || null;
    }
    return (appData.classes || []).find(c => (c.class_type || 'primary') === 'lower' && Number(c.level) === level + 1) || null;
  }
  return (appData.classes || []).find(c => Number(c.level) === level + 1) || null;
}

function getPromotionActionText(cls) {
  const nextClass = getPromotionTargetClass(cls);
  return nextClass ? `Promote to ${nextClass.name}` : 'Graduate Class';
}

function updatePromotionSelectionState() {
  const checkboxes = [...document.querySelectorAll('.promotion-pupil-checkbox')];
  const selected = checkboxes.filter(cb => cb.checked).length;
  const total = checkboxes.length;
  const label = document.getElementById('promotion-selected-count');
  const button = document.getElementById('promotion-submit-btn');
  const selectAll = document.getElementById('promotion-select-all');
  if (label) label.textContent = `${selected} of ${total} pupil${total === 1 ? '' : 's'} selected`;
  if (button) button.disabled = selected === 0;
  if (selectAll) selectAll.checked = total > 0 && selected === total;
}

function togglePromotionSelectionAll(checked) {
  document.querySelectorAll('.promotion-pupil-checkbox').forEach(cb => { cb.checked = checked; });
  updatePromotionSelectionState();
}

async function refreshPromotionViews() {
  await loadReferenceData();
  const refreshTasks = [loadClasses(), loadDashboard()];
  if (document.getElementById('page-pupils')?.classList.contains('active')) refreshTasks.push(loadPupils());
  if (document.getElementById('page-settings')?.classList.contains('active')) refreshTasks.push(loadSettings());
  await Promise.all(refreshTasks.map(task => Promise.resolve(task).catch(() => null)));
}

async function assignTeacher(classId) {
  const teacherId = document.getElementById(`assign-${classId}`).value;
  try {
    await apiFetch(`/api/classes/${classId}/assign`, {
      method: 'POST',
      body: JSON.stringify({ teacher_id: teacherId || null })
    });
    showToast('Teacher assigned', 'success');
    loadClasses();
    loadReferenceData();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function promoteClass(classId) {
  const cls = (appData.classes || []).find(c => c.id === classId);
  if (!cls) return showToast('Class information is unavailable. Please reload the page.', 'error');
  const nextClass = getPromotionTargetClass(cls);
  const pupils = await apiFetch(`/api/pupils?status=active&class_id=${classId}`);
  if (!pupils.length) return showToast(`No active pupils found in ${cls.name}`, 'error');

  openModal(nextClass ? `Promote ${cls.name}` : `Graduate ${cls.name}`, `
    <div>
      <p style="margin-bottom:12px;color:var(--gray-600)">
        ${nextClass
          ? `Select the pupils you want to promote from <strong>${cls.name}</strong> to <strong>${nextClass.name}</strong>.`
          : `Select the pupils you want to graduate from <strong>${cls.name}</strong>.`}
      </p>
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap">
        <label style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:var(--gray-700)">
          <input type="checkbox" id="promotion-select-all" checked onchange="togglePromotionSelectionAll(this.checked)" />
          Select all
        </label>
        <span id="promotion-selected-count" style="font-size:12px;color:var(--gray-500)"></span>
      </div>
      <div style="max-height:320px;overflow:auto;border:1px solid var(--gray-200);border-radius:8px;padding:8px;background:var(--gray-50)">
        ${pupils.map((p, index) => `
          <label style="display:flex;align-items:center;gap:10px;padding:10px 8px;border-bottom:${index < pupils.length - 1 ? '1px solid var(--gray-200)' : 'none'};cursor:pointer;background:white;border-radius:6px;margin-bottom:6px">
            <input type="checkbox" class="promotion-pupil-checkbox" value="${p.id}" checked onchange="updatePromotionSelectionState()" />
            <div style="flex:1">
              <div style="font-size:13px;font-weight:600;color:#1f2937">${esc(p.last_name)}, ${esc(p.first_name)} ${esc(p.other_name || '')}</div>
              <div style="font-size:11px;color:var(--gray-500)">${esc(p.admission_number || 'No admission number')}</div>
            </div>
          </label>
        `).join('')}
      </div>
      <div style="margin-top:14px;display:flex;justify-content:flex-end;gap:8px">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="button" class="btn btn-warning" id="promotion-submit-btn" onclick="submitPromotionSelection('${classId}')">
          ${nextClass ? `🎓 Promote Selected` : '🎓 Graduate Selected'}
        </button>
      </div>
    </div>
  `);
  updatePromotionSelectionState();
}

async function submitPromotionSelection(classId) {
  const cls = (appData.classes || []).find(c => c.id === classId);
  const nextClass = getPromotionTargetClass(cls);
  const selectedIds = [...document.querySelectorAll('.promotion-pupil-checkbox:checked')].map(cb => cb.value);
  if (!selectedIds.length) return showToast('Select at least one pupil to continue', 'error');
  const msg = nextClass
    ? `Promote ${selectedIds.length} selected pupil${selectedIds.length === 1 ? '' : 's'} from ${cls.name} to ${nextClass.name}?`
    : `Graduate ${selectedIds.length} selected pupil${selectedIds.length === 1 ? '' : 's'} from ${cls.name}?`;
  if (!confirm(msg)) return;
  try {
    const result = await apiFetch(`/api/pupils/${classId}/promote`, {
      method: 'POST',
      body: JSON.stringify({ pupil_ids: selectedIds })
    });
    showToast(result.message, 'success');
    closeModal();
    await refreshPromotionViews();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ─── RESULTS ──────────────────────────────────────────────────────────────────

function populateResultsSelects() {
  const classes = appData.classes;
  const terms = appData.terms;

  const classSelect = document.getElementById('results-class-select');
  const termSelect = document.getElementById('results-term-select');
  if (!classSelect || !termSelect) return;

  // For teachers, pre-select their class
  if (currentUser.role === 'teacher' && currentUser.class) {
    classSelect.innerHTML = `<option value="${currentUser.class.id}">${currentUser.class.name}</option>`;
    classSelect.disabled = true;
  } else {
    classSelect.innerHTML = '<option value="">— Select Class —</option>' +
      classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  }

  const currentTerm = terms.find(t => t.is_current);
  termSelect.innerHTML = '<option value="">— Select Term —</option>' +
    terms.map(t => `<option value="${t.id}" ${t.is_current ? 'selected' : ''}>${t.academic_year} Term ${t.term_number}${t.is_current ? ' (Current)' : ''}</option>`).join('');

  if (currentTerm) loadResultsGrid();
}

async function loadResultsPage() {
  if (currentUser.role === 'teacher') {
    try {
      const me = await apiFetch('/api/auth/me');
      currentUser = me;
    } catch {}
  }
  populateResultsSelects();
}

// ── SCORE CLAMP ────────────────────────────────────────────────────────────────
function clampScore(input, max) {
  let v = parseFloat(input.value);
  if (isNaN(v) || v < 0) v = 0;
  if (v > max) v = max;
  input.value = v === 0 && input.value === '' ? '' : v;
  return v;
}

// ── MARKSHEET GRID: class × term → all pupils × all subjects ──────────────────
async function loadResultsGrid() {
  const classId = document.getElementById('results-class-select').value;
  const termId = document.getElementById('results-term-select').value;
  const container = document.getElementById('results-grid-container');

  if (!classId || !termId) {
    container.innerHTML = '<div style="text-align:center;padding:60px;color:var(--gray-400)">📋 Select a class and term above to load the marksheet</div>';
    return;
  }

  container.innerHTML = '<div class="loading">Loading marksheet…</div>';
  try {
    const [pupils, existingResults] = await Promise.all([
      apiFetch(`/api/pupils?class_id=${classId}&status=active`),
      apiFetch(`/api/results?class_id=${classId}&term_id=${termId}`)
    ]);

    if (!pupils.length) {
      container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--gray-400)">No active pupils in this class</div>';
      return;
    }

    const subjects = appData.subjects;
    const term = appData.terms.find(t => t.id === termId);
    const cls = appData.classes.find(c => c.id === classId);

    // Build lookup: resultMap[pupil_id][subject_id] = {ca_score, exam_score}
    const resultMap = {};
    existingResults.forEach(r => {
      if (!resultMap[r.pupil_id]) resultMap[r.pupil_id] = {};
      resultMap[r.pupil_id][r.subject_id] = r;
    });

    // Store for saving
    _marksheetData = { pupils, subjects, classId, termId };

    // Build header rows — two-level: subject name spans 2 cols (CA|Exam), then Total col
    const subjectHeaders = subjects.map(s =>
      `<th colspan="2" style="text-align:center;background:#7B1D1D;color:white;border:1px solid #9B2D2D;white-space:nowrap;padding:6px 10px;font-size:12px">${s.name}</th>`
    ).join('');
    const subjectSubHeaders = subjects.map(() =>
      `<th style="text-align:center;background:#f9f5f5;font-size:11px;padding:4px;border:1px solid #e5e7eb;color:#7B1D1D;font-weight:600">CA<br><span style="font-weight:400;color:#9ca3af">/40</span></th>
       <th style="text-align:center;background:#f9f5f5;font-size:11px;padding:4px;border:1px solid #e5e7eb;color:#7B1D1D;font-weight:600">Exam<br><span style="font-weight:400;color:#9ca3af">/60</span></th>`
    ).join('');

    // Build rows
    const rows = pupils.map((p, i) => {
      const pResults = resultMap[p.id] || {};
      const cells = subjects.map((s, sIdx) => {
        const r = pResults[s.id];
        const ca = r != null && r.ca_score != null ? r.ca_score : '';
        const exam = r != null && r.exam_score != null ? r.exam_score : '';
        const tabIdx = (i * subjects.length * 2) + (sIdx * 2) + 1;
        return `
          <td style="padding:3px;border:1px solid #e5e7eb">
            <input type="number" class="ms-input" id="ms-ca-${p.id}-${s.id}"
              min="0" max="40" step="0.5" value="${ca}" tabindex="${tabIdx}"
              placeholder="—"
              oninput="msClampAndTotal('${p.id}',40,this)"
              onblur="msClampAndTotal('${p.id}',40,this)"
              style="width:44px;text-align:center;border:1px solid #d1d5db;border-radius:4px;padding:4px;font-size:13px;background:#fffdf9" />
          </td>
          <td style="padding:3px;border:1px solid #e5e7eb">
            <input type="number" class="ms-input" id="ms-exam-${p.id}-${s.id}"
              min="0" max="60" step="0.5" value="${exam}" tabindex="${tabIdx+1}"
              placeholder="—"
              oninput="msClampAndTotal('${p.id}',60,this)"
              onblur="msClampAndTotal('${p.id}',60,this)"
              style="width:44px;text-align:center;border:1px solid #d1d5db;border-radius:4px;padding:4px;font-size:13px;background:#fffdf9" />
          </td>`;
      }).join('');

      // Compute current grand total
      const gt = subjects.reduce((sum, s) => {
        const r = pResults[s.id];
        return sum + (r ? ((r.ca_score||0)+(r.exam_score||0)) : 0);
      }, 0);
      const gtDisplay = existingResults.some(r => r.pupil_id === p.id) ? gt : '—';

      return `<tr id="ms-row-${p.id}" style="background:${i%2===0?'white':'#fafafa'}">
        <td style="padding:6px 10px;border:1px solid #e5e7eb;text-align:center;color:#9ca3af;font-size:12px">${i+1}</td>
        <td style="padding:6px 10px;border:1px solid #e5e7eb;white-space:nowrap;font-weight:600;font-size:13px;min-width:140px">${esc(p.last_name)}, ${esc(p.first_name)}</td>
        ${cells}
        <td id="ms-total-${p.id}" style="padding:6px 10px;border:1px solid #e5e7eb;text-align:center;font-weight:700;font-size:14px;color:#7B1D1D;background:#fff5f5;white-space:nowrap">${gtDisplay}</td>
        <td style="padding:4px;border:1px solid #e5e7eb">
          <button class="btn btn-sm btn-success" onclick="saveOnePupilResults('${p.id}')" title="Save this pupil's results" style="white-space:nowrap;font-size:11px;padding:4px 8px">💾</button>
        </td>
      </tr>`;
    }).join('');

    container.innerHTML = `
      <div style="background:white;border-radius:8px;box-shadow:var(--shadow-sm);overflow:hidden">
        <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid var(--gray-200);flex-wrap:wrap;gap:8px">
          <div>
            <span style="font-weight:700;font-size:15px">${cls ? cls.name : ''}</span>
            <span style="color:var(--gray-400);margin-left:8px;font-size:13px">${term ? `${term.academic_year} — Term ${term.term_number}` : ''}</span>
            <span style="margin-left:10px;font-size:12px;color:#7B1D1D;background:#fff5f5;padding:2px 8px;border-radius:10px">${pupils.length} pupils · ${subjects.length} subjects</span>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <span style="font-size:11px;color:var(--gray-400)">💾 = save one row &nbsp;|&nbsp; Tab = move between cells</span>
            <button class="btn btn-success" onclick="saveAllMarksheetResults()" style="font-size:13px">💾 Save All</button>
          </div>
        </div>
        <div style="overflow-x:auto">
          <table style="border-collapse:collapse;width:100%;min-width:${120 + 90*subjects.length}px">
            <thead>
              <tr>
                <th style="padding:6px 10px;background:#374151;color:white;border:1px solid #4b5563;font-size:11px" rowspan="2">#</th>
                <th style="padding:6px 10px;background:#374151;color:white;border:1px solid #4b5563;font-size:11px;min-width:140px" rowspan="2">Pupil Name</th>
                ${subjectHeaders}
                <th style="padding:6px 10px;background:#374151;color:white;border:1px solid #4b5563;font-size:11px;text-align:center" rowspan="2">Total</th>
                <th style="padding:6px 10px;background:#374151;color:white;border:1px solid #4b5563;font-size:11px;text-align:center" rowspan="2">Save</th>
              </tr>
              <tr>${subjectSubHeaders}</tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
        <div style="padding:12px 18px;background:var(--gray-50);border-top:1px solid var(--gray-200);display:flex;justify-content:flex-end;gap:10px;align-items:center">
          <span style="font-size:12px;color:var(--gray-400)">CA max 40 · Exam max 60 · Values auto-capped when you move away</span>
          <button class="btn btn-success" onclick="saveAllMarksheetResults()">💾 Save All Results</button>
        </div>
      </div>`;

  } catch (err) {
    container.innerHTML = `<div class="empty">Error: ${err.message}</div>`;
  }
}

function msClampAndTotal(pupilId, maxVal, input) {
  // Clamp value to allowed max
  let v = parseFloat(input.value);
  if (!isNaN(v) && v > maxVal) {
    input.value = maxVal;
    v = maxVal;
    input.style.background = '#fef2f2';
    input.style.borderColor = '#ef4444';
    setTimeout(() => { input.style.background = '#fffdf9'; input.style.borderColor = '#d1d5db'; }, 800);
  }
  if (!isNaN(v) && v < 0) { input.value = 0; v = 0; }
  // Recompute grand total for this pupil's row
  msRecomputeTotal(pupilId);
}

function msRecomputeTotal(pupilId) {
  const { subjects } = _marksheetData || {};
  if (!subjects) return;
  let total = 0;
  let hasAny = false;
  subjects.forEach(s => {
    const caEl = document.getElementById(`ms-ca-${pupilId}-${s.id}`);
    const examEl = document.getElementById(`ms-exam-${pupilId}-${s.id}`);
    if (caEl && caEl.value !== '') { total += parseFloat(caEl.value) || 0; hasAny = true; }
    if (examEl && examEl.value !== '') { total += parseFloat(examEl.value) || 0; hasAny = true; }
  });
  const el = document.getElementById(`ms-total-${pupilId}`);
  if (el) el.textContent = hasAny ? total : '—';
}

function collectPupilResults(pupilId, classId, termId) {
  const { subjects } = _marksheetData || {};
  if (!subjects) return [];
  const results = [];
  subjects.forEach(s => {
    const caEl = document.getElementById(`ms-ca-${pupilId}-${s.id}`);
    const examEl = document.getElementById(`ms-exam-${pupilId}-${s.id}`);
    if (!caEl || !examEl) return;
    const caVal = caEl.value.trim();
    const examVal = examEl.value.trim();
    if (caVal !== '' || examVal !== '') {
      results.push({
        pupil_id: pupilId,
        subject_id: s.id,
        term_id: termId,
        ca_score: Math.min(parseFloat(caVal) || 0, 40),
        exam_score: Math.min(parseFloat(examVal) || 0, 60)
      });
    }
  });
  return results;
}

async function saveOnePupilResults(pupilId) {
  const { classId, termId } = _marksheetData || {};
  if (!classId || !termId) return;
  const results = collectPupilResults(pupilId, classId, termId);
  if (!results.length) return showToast('No scores entered for this pupil', 'error');
  try {
    const res = await apiFetch('/api/results/batch', { method: 'POST', body: JSON.stringify({ results }) });
    // Flash the row green
    const row = document.getElementById(`ms-row-${pupilId}`);
    if (row) { row.style.background = '#f0fdf4'; setTimeout(() => row.style.background = '', 1200); }
    showToast('Saved!', 'success');
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function saveAllMarksheetResults() {
  const { pupils, classId, termId } = _marksheetData || {};
  if (!pupils || !classId || !termId) return;
  const results = [];
  pupils.forEach(p => {
    results.push(...collectPupilResults(p.id, classId, termId));
  });
  if (!results.length) return showToast('No scores to save', 'error');
  try {
    const res = await apiFetch('/api/results/batch', { method: 'POST', body: JSON.stringify({ results }) });
    showToast(res.message || `Saved ${results.length} scores!`, 'success');
  } catch (err) {
    showToast('Error saving: ' + err.message, 'error');
  }
}


// ─── ARCHIVE ──────────────────────────────────────────────────────────────────

async function loadArchive(status) {
  // Update tab buttons — scoped to archive page, driven by status param (not global event)
  document.querySelectorAll('#page-archive .tab-btn').forEach(b => b.classList.remove('active'));
  const tabIndex = status === 'graduated' ? 1 : 0;
  const tabs = document.querySelectorAll('#page-archive .tab-btn');
  if (tabs[tabIndex]) tabs[tabIndex].classList.add('active');

  const container = document.getElementById('archive-list');
  container.innerHTML = '<div class="loading">Loading…</div>';
  try {
    const pupils = await apiFetch(`/api/pupils?status=${status}`);
    if (!pupils.length) {
      container.innerHTML = `<div class="empty">No ${status} pupils.</div>`;
      return;
    }
    container.innerHTML = `
      <table class="data-table">
        <thead><tr>
          <th>Pupil</th><th>Admission No.</th><th>Last Class</th><th>Status</th><th>Actions</th>
        </tr></thead>
        <tbody>${pupils.map(p => `
          <tr>
            <td>
              <div class="pupil-info">
                <div class="pupil-avatar">${esc(p.first_name).charAt(0)}${esc(p.last_name).charAt(0)}</div>
                <div>
                  <div class="pupil-name">${esc(p.last_name)}, ${esc(p.first_name)}</div>
                </div>
              </div>
            </td>
            <td>${p.admission_number || '—'}</td>
            <td>${p.class_name || '—'}</td>
            <td><span class="badge badge-${status}">${status}</span></td>
            <td>
              ${status === 'archived' ? `<button class="btn btn-sm btn-success" onclick="restorePupil('${p.id}', '${p.first_name} ${p.last_name}')">Restore</button>` : ''}
            </td>
          </tr>
        `).join('')}</tbody>
      </table>`;
  } catch (err) {
    container.innerHTML = `<div class="empty">Error: ${err.message}</div>`;
  }
}

async function restorePupil(id, name) {
  if (!confirm(`Restore ${name} as an active pupil?`)) return;
  try {
    await apiFetch(`/api/pupils/${id}/restore`, { method: 'POST' });
    showToast(`${name} restored`, 'success');
    loadArchive('archived');
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ─── SETTINGS ─────────────────────────────────────────────────────────────────

async function loadSettings() {
  try {
    const [terms, subjects] = await Promise.all([
      apiFetch('/api/terms'),
      apiFetch('/api/subjects')
    ]);

    // Terms
    const termsEl = document.getElementById('terms-list');
    termsEl.innerHTML = terms.map(t => `
      <div class="term-item ${t.is_current ? 'term-current' : ''}">
        <div>
          <strong>${t.academic_year} — Term ${t.term_number}</strong>
          ${t.is_current ? '<span class="badge badge-active" style="margin-left:8px">Current</span>' : ''}
        </div>
        ${!t.is_current ? `<button class="btn btn-sm btn-secondary" onclick="setCurrentTerm('${t.id}')">Set Current</button>` : ''}
      </div>`).join('');

    // Subjects
    const subjectsEl = document.getElementById('subjects-list');
    subjectsEl.innerHTML = subjects.map(s => `
      <div class="subject-item">
        <span>${s.name}</span>
        <button class="btn btn-sm ${s.is_active ? 'btn-secondary' : 'btn-success'}" onclick="toggleSubject('${s.id}', ${!s.is_active})">
          ${s.is_active ? 'Disable' : 'Enable'}
        </button>
      </div>`).join('');


    // Admin-only extras
    if (currentUser.role === 'admin') {
      loadParentAccountsList();
      loadNoticesAdminList();
      loadAuditLog();
      loadReadinessStatus();
      loadBackupList();
      loadEventsList();
      loadHomeworkAdminList();
      loadTimetableAdminList();
      loadPayrollList();
      populateClassDropdown('broadcast-class', true);
      const darkToggle = document.getElementById('dark-mode-toggle');
      if (darkToggle) darkToggle.checked = document.body.classList.contains('dark-mode');
    }
  } catch (err) {
    showToast('Error loading settings: ' + err.message, 'error');
  }
}

function showAddTerm() {
  const year = new Date().getFullYear();
  openModal('Add New Term', `
    <form onsubmit="addTerm(event)">
      <div class="form-group">
        <label>Academic Year</label>
        <input type="text" id="term-year" value="${year}/${year+1}" placeholder="e.g. 2025/2026" required />
      </div>
      <div class="form-group">
        <label>Term Number</label>
        <select id="term-num" required>
          <option value="1">Term 1</option>
          <option value="2">Term 2</option>
          <option value="3">Term 3</option>
        </select>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Add Term</button>
      </div>
    </form>`);
}

async function addTerm(e) {
  e.preventDefault();
  try {
    await apiFetch('/api/terms', {
      method: 'POST',
      body: JSON.stringify({
        academic_year: document.getElementById('term-year').value,
        term_number: parseInt(document.getElementById('term-num').value)
      })
    });
    showToast('Term added', 'success');
    closeModal();
    loadSettings();
    loadReferenceData();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function setCurrentTerm(id) {
  try {
    await apiFetch(`/api/terms/${id}/set-current`, { method: 'POST' });
    showToast('Current term updated', 'success');
    loadSettings();
    loadReferenceData();
    loadDashboard();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

function showAddSubject() {
  openModal('Add Subject', `
    <form onsubmit="addSubject(event)">
      <div class="form-group">
        <label>Subject Name</label>
        <input type="text" id="subject-name" required placeholder="e.g. Home Economics" />
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Add Subject</button>
      </div>
    </form>`);
}

async function addSubject(e) {
  e.preventDefault();
  try {
    await apiFetch('/api/subjects', {
      method: 'POST',
      body: JSON.stringify({ name: document.getElementById('subject-name').value })
    });
    showToast('Subject added', 'success');
    closeModal();
    loadSettings();
    loadReferenceData();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function toggleSubject(id, active) {
  try {
    await apiFetch(`/api/subjects/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ is_active: active })
    });
    showToast('Subject updated', 'success');
    loadSettings();
    loadReferenceData();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function changePassword(e) {
  e.preventDefault();
  const pw = document.getElementById('new-password').value;
  const confirm = document.getElementById('confirm-password').value;
  if (pw !== confirm) return showToast('Passwords do not match', 'error');
  if (pw.length < 6) return showToast('Password must be at least 6 characters', 'error');
  try {
    await apiFetch('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ new_password: pw })
    });
    showToast('Password updated', 'success');
    e.target.reset();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ─── REPORT CARD ──────────────────────────────────────────────────────────────

async function generateReport(pupilId) {
  const termSelect = document.getElementById('profile-term-select');
  const termId = termSelect ? termSelect.value : null;
  const currentTermId = termId || appData.terms.find(t => t.is_current)?.id;
  if (!currentTermId) return showToast('No term selected', 'error');

  try {
    const data = await apiFetch(`/api/report/pupil/${pupilId}/term/${currentTermId}`);
    renderReportCard(data);
  } catch (err) {
    showToast('Error generating report: ' + err.message, 'error');
  }
}

function reportGrade(total) {
  if (total >= 85) return 'A';
  if (total >= 75) return 'B+';
  if (total >= 60) return 'B';
  if (total >= 50) return 'C';
  if (total >= 40) return 'D';
  return 'E';
}

function reportRatingBadge(val) {
  const ratings = ['E','VG','G','F','P'];
  return ratings.map(r => {
    const active = (val || '').toUpperCase() === r;
    const bg = active ? '#7B1D1D' : '#f3f4f6';
    const color = active ? 'white' : '#6b7280';
    return `<span style="display:inline-block;padding:1px 5px;margin:1px;border-radius:3px;font-size:10px;font-weight:${active?700:400};background:${bg};color:${color}">${r}</span>`;
  }).join('');
}

function renderReportCard(data) {
  const {
    pupil, term, results, grand_total, max_total, percentage, avg_per_subject,
    position, total_in_class, least_class_avg, max_class_avg, num_subjects, age, conduct,
    prev_term_results, is_cumulative
  } = data;
  const pupilName = `${pupil.last_name}, ${pupil.first_name}${pupil.other_name ? ' ' + pupil.other_name : ''}`;
  const c = conduct || {};
  const prev = prev_term_results || {};
  const ordinals = {1:'1ST', 2:'2ND', 3:'3RD'};
  const curOrd = term ? (ordinals[term.term_number] || `${term.term_number}TH`) : '';

  // Build results rows based on whether this is a cumulative (Term 3) view
  const resultRows = results.map(r => {
    const curTotal = (r.ca_score || 0) + (r.exam_score || 0);
    const pos = r.position_in_subject || '—';
    const classAvg = r.class_subject_average != null ? Number(r.class_subject_average).toFixed(1) : '—';
    const TD = 'padding:2px 5px;text-align:center;border:1px solid #e5e7eb;font-size:9px';
    const TDS = 'padding:2px 5px;border:1px solid #e5e7eb;font-size:9px';

    if (is_cumulative) {
      const sid = r.subject_id;
      const t1 = prev['1'] && prev['1'][sid] != null ? prev['1'][sid] : null;
      const t2 = prev['2'] && prev['2'][sid] != null ? prev['2'][sid] : null;
      const vals = [t1, t2, curTotal].filter(v => v != null);
      const avgTotal = vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2) : null;
      const grade = reportGrade(avgTotal != null ? Number(avgTotal) : curTotal);
      return `<tr>
        <td style="${TDS}">${r.subject_name}</td>
        <td style="${TD}">${r.ca_score != null ? r.ca_score : '—'}</td>
        <td style="${TD}">${r.exam_score != null ? r.exam_score : '—'}</td>
        <td style="${TD};font-weight:700">${curTotal || '—'}</td>
        <td style="${TD}">${t2 != null ? t2 : '—'}</td>
        <td style="${TD}">${t1 != null ? t1 : '—'}</td>
        <td style="${TD};font-weight:700;color:#7B1D1D">${avgTotal != null ? avgTotal : '—'}</td>
        <td style="${TD}">${pos}</td>
        <td style="${TD};font-weight:700;color:#7B1D1D">${grade}</td>
        <td style="${TD}">${classAvg}</td>
      </tr>`;
    } else {
      const grade = reportGrade(curTotal);
      return `<tr>
        <td style="${TDS}">${r.subject_name}</td>
        <td style="${TD}">${r.ca_score != null ? r.ca_score : '—'}</td>
        <td style="${TD}">${r.exam_score != null ? r.exam_score : '—'}</td>
        <td style="${TD};font-weight:700">${curTotal || '—'}</td>
        <td style="${TD}">${pos}</td>
        <td style="${TD};font-weight:700;color:#7B1D1D">${grade}</td>
        <td style="${TD}">${classAvg}</td>
      </tr>`;
    }
  }).join('');

  const conductItems = [
    ['Punctuality', c.punctuality], ['Honesty', c.honesty], ['Cleanliness', c.cleanliness],
    ['Leadership', c.leadership], ['Politeness', c.politeness], ['Attentiveness', c.attentiveness]
  ];
  const skillItems = [
    ['H/Writing', c.writing], ['Handwork', c.handwork], ['Verbal Fluency', c.verbal_fluency],
    ['Drama', c.drama], ['Sports', c.sports]
  ];

  function conductRow([label, val]) {
    return `<tr>
      <td style="padding:4px 8px;border:1px solid #d1d5db;width:40%">${label}</td>
      <td style="padding:4px 8px;border:1px solid #d1d5db">${reportRatingBadge(val)}</td>
    </tr>`;
  }

  const html = `
  <style>
    @media print {
      @page { size: A4 portrait; margin: 7mm; }
      .report-toolbar { display: none !important; }
      .report-content { padding: 0 !important; background: white !important; overflow: visible !important; }
      .report-page { box-shadow: none !important; margin: 0 !important; padding: 0 !important; max-width: 100% !important; }
    }
  </style>
  <div class="report-page" style="background:white;max-width:780px;margin:0 auto;padding:14px;font-family:'Segoe UI',Arial,sans-serif;font-size:10px;color:#1f2937;line-height:1.3">

    <!-- HEADER -->
    <div style="border:2px solid #7B1D1D;border-radius:5px;padding:7px 12px;margin-bottom:6px;display:flex;align-items:center;gap:10px">
      <img src="${SCHOOL.logo}" style="width:55px;height:55px;object-fit:contain;flex-shrink:0" />
      <div style="flex:1;text-align:center">
        <div style="font-size:14px;font-weight:800;color:#7B1D1D;text-transform:uppercase;letter-spacing:.8px;line-height:1.2">${SCHOOL.fullName}</div>
        <div style="font-size:8.5px;color:#6b7280;margin-top:1px">${SCHOOL.address} ${SCHOOL.address2}</div>
        <div style="font-size:8.5px;color:#6b7280">Tel: ${SCHOOL.phones}</div>
        <div style="font-size:8.5px;font-style:italic;color:#7B1D1D;margin-top:2px">${SCHOOL.motto}</div>
      </div>
      <div style="text-align:center;flex-shrink:0">
        <div style="font-size:10px;font-weight:700;color:#7B1D1D;text-transform:uppercase;border:2px solid #7B1D1D;padding:3px 7px;border-radius:3px">REPORT CARD</div>
        <div style="font-size:9px;margin-top:4px;color:#374151">${term ? term.academic_year : ''}</div>
        <div style="font-size:9px;color:#374151">Term ${term ? term.term_number : ''}</div>
      </div>
    </div>

    <!-- STUDENT INFO + PHOTO -->
    <div style="display:flex;gap:8px;margin-bottom:6px;align-items:stretch">
      <div style="flex:1;border:1px solid #d1d5db;border-radius:4px;padding:6px 8px">
        <table style="width:100%;border-collapse:collapse">
          ${[
            ['Student\'s Name', `<strong style="text-transform:uppercase">${pupilName}</strong>`],
            ['Admission No.', `<strong>${pupil.admission_number || '—'}</strong>`],
            ['Class', `<strong>${pupil.class_name || '—'}</strong>`],
            ['Gender', pupil.gender || '—'],
            ['Age', age || '—'],
            ['No. in Class', total_in_class || '—'],
          ].map(([l,v]) => `<tr>
            <td style="padding:2px 5px;color:#6b7280;width:36%;white-space:nowrap">${l}:</td>
            <td style="padding:2px 5px">${v}</td>
          </tr>`).join('')}
        </table>
      </div>
      <div style="flex-shrink:0;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center">
        ${pupil.photo
          ? `<img src="${pupil.photo}" style="width:72px;height:88px;object-fit:cover;border:2px solid #7B1D1D;border-radius:3px;display:block" />`
          : `<div style="width:72px;height:88px;border:2px solid #7B1D1D;border-radius:3px;background:#fff5f5;display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:700;color:#7B1D1D">${pupil.first_name.charAt(0)}${pupil.last_name.charAt(0)}</div>`
        }
        <div style="font-size:7.5px;color:#9ca3af;margin-top:2px">PASSPORT</div>
      </div>
    </div>

    <!-- RESULTS TABLE -->
    <div style="margin-bottom:6px">
      <div style="background:#7B1D1D;color:white;padding:3px 8px;font-weight:700;font-size:9px;text-transform:uppercase;letter-spacing:.5px;border-radius:3px 3px 0 0">Academic Performance</div>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:#f9f5f5">
            <th style="padding:3px 6px;text-align:left;border:1px solid #d1d5db;font-size:9px">Subject</th>
            <th style="padding:3px 6px;text-align:center;border:1px solid #d1d5db;font-size:9px">Test(40)</th>
            <th style="padding:3px 6px;text-align:center;border:1px solid #d1d5db;font-size:9px">Exam(60)</th>
            <th style="padding:3px 6px;text-align:center;border:1px solid #d1d5db;font-size:9px">${curOrd} Total(%)</th>
            ${is_cumulative ? `
            <th style="padding:3px 6px;text-align:center;border:1px solid #d1d5db;font-size:9px">2ND Total(%)</th>
            <th style="padding:3px 6px;text-align:center;border:1px solid #d1d5db;font-size:9px">1ST Total(%)</th>
            <th style="padding:3px 6px;text-align:center;border:1px solid #d1d5db;font-size:9px">Total Avg(%)</th>
            ` : ''}
            <th style="padding:3px 6px;text-align:center;border:1px solid #d1d5db;font-size:9px">Pos.</th>
            <th style="padding:3px 6px;text-align:center;border:1px solid #d1d5db;font-size:9px">Grade</th>
            <th style="padding:3px 6px;text-align:center;border:1px solid #d1d5db;font-size:9px">Cls Avg(%)</th>
          </tr>
        </thead>
        <tbody>${resultRows}</tbody>
      </table>
    </div>

    <!-- SUMMARY + CONDUCT + SKILLS: all in one row to save vertical space -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px">

      <!-- Left: Summary -->
      <div style="border:1px solid #d1d5db;border-radius:3px;overflow:hidden">
        <div style="background:#7B1D1D;color:white;padding:3px 8px;font-weight:700;font-size:9px;text-transform:uppercase;letter-spacing:.5px">Summary</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0">
          ${[
            ['Student Avg', avg_per_subject != null ? Number(avg_per_subject).toFixed(1) : '—'],
            ['Least Cls Avg', least_class_avg != null ? Number(least_class_avg).toFixed(1) : '—'],
            ['Max Cls Avg', max_class_avg != null ? Number(max_class_avg).toFixed(1) : '—'],
            ['Subjects', num_subjects || '—'],
            ['Obtainable', max_total || '—'],
            ['Obtained', grand_total || '—'],
            ['% Score', percentage != null ? percentage + '%' : '—'],
            ['Position', position && total_in_class ? position + '/' + total_in_class : '—'],
          ].map(([label, val]) => `
            <div style="padding:3px 6px;border:1px solid #f0f0f0;text-align:center">
              <div style="font-size:11px;font-weight:700;color:#7B1D1D;line-height:1.2">${val}</div>
              <div style="font-size:7.5px;color:#6b7280;text-transform:uppercase">${label}</div>
            </div>`).join('')}
        </div>
      </div>

      <!-- Right: Conduct + Skills stacked -->
      <div style="display:flex;flex-direction:column;gap:4px">
        <div>
          <div style="background:#7B1D1D;color:white;padding:3px 8px;font-weight:700;font-size:9px;text-transform:uppercase;letter-spacing:.5px;border-radius:3px 3px 0 0">Conduct</div>
          <table style="width:100%;border-collapse:collapse">
            ${conductItems.map(([label, val]) => `<tr>
              <td style="padding:2px 5px;border:1px solid #e5e7eb;font-size:9px;width:42%">${label}</td>
              <td style="padding:1px 4px;border:1px solid #e5e7eb">${reportRatingBadge(val)}</td>
            </tr>`).join('')}
          </table>
        </div>
        <div>
          <div style="background:#7B1D1D;color:white;padding:3px 8px;font-weight:700;font-size:9px;text-transform:uppercase;letter-spacing:.5px;border-radius:3px 3px 0 0">Skills</div>
          <table style="width:100%;border-collapse:collapse">
            ${skillItems.map(([label, val]) => `<tr>
              <td style="padding:2px 5px;border:1px solid #e5e7eb;font-size:9px;width:42%">${label}</td>
              <td style="padding:1px 4px;border:1px solid #e5e7eb">${reportRatingBadge(val)}</td>
            </tr>`).join('')}
          </table>
          <div style="padding:2px 5px;font-size:7.5px;color:#6b7280;border:1px solid #e5e7eb;border-top:none">
            E=Excellent &nbsp; VG=Very Good &nbsp; G=Good &nbsp; F=Fair &nbsp; P=Poor
          </div>
        </div>
      </div>
    </div>

    <!-- COMMENTS -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px">
      <div style="border:1px solid #d1d5db;border-radius:3px;overflow:hidden">
        <div style="background:#f9f5f5;padding:2px 6px;font-weight:700;font-size:9px;color:#7B1D1D;border-bottom:1px solid #d1d5db">Class Teacher's Comment</div>
        <div style="padding:4px 6px;min-height:22px;font-size:9px;color:#374151">${c.teacher_comment || '<span style="color:#9ca3af;font-style:italic">—</span>'}</div>
        <div style="margin:0 6px;border-top:1px solid #374151;padding:2px 0">
          <div style="font-size:7.5px;color:#6b7280">Signature &amp; Date</div>
        </div>
      </div>
      <div style="border:1px solid #d1d5db;border-radius:3px;overflow:hidden">
        <div style="background:#f9f5f5;padding:2px 6px;font-weight:700;font-size:9px;color:#7B1D1D;border-bottom:1px solid #d1d5db">Administrator's Comment</div>
        <div style="padding:4px 6px;min-height:22px;font-size:9px;color:#374151">${c.admin_comment || '<span style="color:#9ca3af;font-style:italic">—</span>'}</div>
        <div style="margin:0 6px;border-top:1px solid #374151;padding:2px 0">
          <div style="font-size:7.5px;color:#6b7280">Signature &amp; Date</div>
        </div>
      </div>
    </div>

    <!-- GRADING SCALE + GOVT APPROVED + FOOTER all in one line -->
    <div style="display:flex;justify-content:space-between;align-items:center;border:1px solid #d1d5db;border-radius:3px;padding:4px 10px;background:#fafafa">
      <div>
        <div style="font-size:8px;font-weight:700;color:#374151;margin-bottom:2px">GRADING SCALE</div>
        <div style="display:flex;gap:8px">
          ${[['A','85–100'],['B+','75–84'],['B','60–74'],['C','50–59'],['D','40–49'],['E','0–39']].map(([g,r]) =>
            `<span style="font-size:8px"><strong style="color:#7B1D1D">${g}</strong>=${r}%</span>`
          ).join('')}
        </div>
      </div>
      <div style="font-size:7.5px;color:#9ca3af;text-align:center">
        Generated ${new Date().toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})} · ${SCHOOL.name}
      </div>
      <div style="text-align:center;border:2px solid #7B1D1D;border-radius:50%;width:46px;height:46px;display:flex;flex-direction:column;align-items:center;justify-content:center;transform:rotate(-10deg);flex-shrink:0">
        <div style="font-size:6.5px;font-weight:800;color:#7B1D1D;text-align:center;line-height:1.3">GOVT.<br/>APPROVED</div>
      </div>
    </div>

  </div>`;

  document.getElementById('report-content').innerHTML = html;
  document.getElementById('report-overlay').classList.remove('hidden');
  closeModal();
}

function closeReport() {
  document.getElementById('report-overlay').classList.add('hidden');
}

// ─── LOWER SCHOOL REPORT CARD ────────────────────────────────────────────────

const LOWER_SCHOOL_SKILLS = [
  { key: 'books_pictures',   label: 'I love books and pictures',         emoji: '📚' },
  { key: 'relate_well',      label: 'I can relate well with others',     emoji: '🤝' },
  { key: 'share_cooperate',  label: 'I can share and cooperate',         emoji: '🎁' },
  { key: 'use_pencil',       label: 'I can use a pencil',                emoji: '✏️' },
  { key: 'write_name',       label: 'I can write my name',               emoji: '📝' },
  { key: 'count_10',         label: 'I can count to 10',                 emoji: '🔢' },
  { key: 'recognise_shapes', label: 'I can recognise basic shapes',      emoji: '🔷' },
  { key: 'recognise_colours',label: 'I can recognise colours',           emoji: '🎨' },
  { key: 'cut_paste',        label: 'I can cut and paste',               emoji: '✂️' },
  { key: 'sing_rhyme',       label: 'I can sing and recite rhymes',      emoji: '🎵' },
  { key: 'follow_rules',     label: 'I can follow rules and instructions',emoji: '📋' },
  { key: 'self_care',        label: 'I can take care of myself',         emoji: '🌟' }
];

function gradeColor(g) {
  return { A: '#15803d', B: '#1d4ed8', C: '#b45309', D: '#dc2626', E: '#6b7280' }[g] || '#374151';
}

async function generateLowerSchoolReport(pupilId) {
  const termId = document.getElementById('profile-term-select')?.value;
  if (!termId) { showToast('Please select a term first', 'error'); return; }
  try {
    const data = await apiFetch(`/api/report/lower/${pupilId}/term/${termId}`);
    renderLowerSchoolReport(data);
  } catch (err) {
    showToast('Error generating report: ' + err.message, 'error');
  }
}

function renderLowerSchoolReport(data) {
  const p = data.pupil;
  const t = data.term;
  const skills = data.skills || {};
  const name = `${p.first_name} ${p.other_name ? p.other_name + ' ' : ''}${p.last_name}`;

  const skillRows = LOWER_SCHOOL_SKILLS.map(s => {
    const g = (typeof skills[s.key] === 'string' ? skills[s.key] : (skills[s.key]?.grade || ''));
    const color = gradeColor(g);
    return `
      <tr>
        <td style="padding:4px 8px;font-size:11px;border:1px solid #e5e7eb">
          <span style="margin-right:4px">${s.emoji}</span>${s.label}
        </td>
        ${['A','B','C','D','E'].map(grade =>
          `<td style="padding:4px 6px;text-align:center;border:1px solid #e5e7eb;font-size:11px">
            ${g === grade ? `<strong style="color:${color}">${grade}</strong>` : '<span style="color:#d1d5db">·</span>'}
          </td>`
        ).join('')}
      </tr>`;
  }).join('');

  const html = `
  <style>
    @media print {
      @page { size: A4 portrait; margin: 10mm; }
      body * { visibility: hidden; }
      #report-content, #report-content * { visibility: visible; }
      #report-content { position: fixed; top: 0; left: 0; width: 100%; }
      .report-toolbar { display: none !important; }
    }
  </style>
  <div style="font-family:Arial,sans-serif;font-size:11px;color:#1f2937;max-width:650px;margin:0 auto;padding:10px">

    <!-- Header -->
    <div style="text-align:center;border-bottom:3px solid #7B1D1D;padding-bottom:10px;margin-bottom:12px">
      <img src="${SCHOOL.logo}" style="height:55px;margin-bottom:4px" onerror="this.style.display='none'" />
      <div style="font-size:16px;font-weight:800;color:#7B1D1D;letter-spacing:1px">${SCHOOL.name}</div>
      <div style="font-size:11px;color:#374151;font-style:italic">${SCHOOL.fullName}</div>
      <div style="font-size:10px;color:#6b7280">${SCHOOL.address}</div>
      <div style="font-size:13px;font-weight:700;color:#374151;margin-top:6px;text-transform:uppercase;letter-spacing:1px">
        Playgroup / Nursery Progress Report
      </div>
    </div>

    <!-- Pupil Info -->
    <div style="display:flex;gap:12px;margin-bottom:12px;background:#fafafa;border:1px solid #e5e7eb;border-radius:6px;padding:10px;align-items:center">
      ${p.photo
        ? `<img src="${p.photo}" style="width:65px;height:75px;object-fit:cover;border-radius:4px;border:2px solid #7B1D1D" />`
        : `<div style="width:65px;height:75px;background:#7B1D1D;border-radius:4px;display:flex;align-items:center;justify-content:center;color:white;font-size:22px;font-weight:700">${p.first_name.charAt(0)}${p.last_name.charAt(0)}</div>`
      }
      <div style="flex:1;display:grid;grid-template-columns:1fr 1fr;gap:4px">
        <div><span style="font-size:9px;color:#6b7280;text-transform:uppercase">Pupil Name</span><br/><strong>${name}</strong></div>
        <div><span style="font-size:9px;color:#6b7280;text-transform:uppercase">Admission No.</span><br/><strong>${p.admission_number || '—'}</strong></div>
        <div><span style="font-size:9px;color:#6b7280;text-transform:uppercase">Class</span><br/><strong>${p.class_name || '—'}</strong></div>
        <div><span style="font-size:9px;color:#6b7280;text-transform:uppercase">Term</span><br/><strong>${t.academic_year} — Term ${t.term_number}</strong></div>
        <div><span style="font-size:9px;color:#6b7280;text-transform:uppercase">Age</span><br/><strong>${data.age || '—'}</strong></div>
        <div><span style="font-size:9px;color:#6b7280;text-transform:uppercase">Gender</span><br/><strong>${p.gender || '—'}</strong></div>
      </div>
    </div>

    <!-- Skills Assessment Table -->
    <div style="margin-bottom:12px">
      <div style="font-size:12px;font-weight:700;color:#7B1D1D;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;border-bottom:2px solid #7B1D1D;padding-bottom:3px">
        Skills Assessment
      </div>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:#7B1D1D;color:white">
            <th style="padding:5px 8px;text-align:left;font-size:10px;font-weight:600;border:1px solid #7B1D1D">Skill / Activity</th>
            <th style="padding:5px 6px;text-align:center;font-size:10px;font-weight:600;border:1px solid #7B1D1D;width:32px">A</th>
            <th style="padding:5px 6px;text-align:center;font-size:10px;font-weight:600;border:1px solid #7B1D1D;width:32px">B</th>
            <th style="padding:5px 6px;text-align:center;font-size:10px;font-weight:600;border:1px solid #7B1D1D;width:32px">C</th>
            <th style="padding:5px 6px;text-align:center;font-size:10px;font-weight:600;border:1px solid #7B1D1D;width:32px">D</th>
            <th style="padding:5px 6px;text-align:center;font-size:10px;font-weight:600;border:1px solid #7B1D1D;width:32px">E</th>
          </tr>
        </thead>
        <tbody>${skillRows}</tbody>
      </table>
    </div>

    <!-- Grading Key -->
    <div style="display:flex;gap:16px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:4px;padding:6px 10px;margin-bottom:10px;flex-wrap:wrap">
      <div style="font-size:9px;font-weight:700;color:#374151;text-transform:uppercase">Grading Key:</div>
      ${[['A','Excellent'],['B','Very Good'],['C','Good'],['D','Fair'],['E','Needs Improvement']].map(([g,l]) =>
        `<span style="font-size:9px"><strong style="color:${gradeColor(g)}">${g}</strong> = ${l}</span>`
      ).join('')}
    </div>

    <!-- Teacher Comment -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">
      <div style="border:1px solid #e5e7eb;border-radius:4px;padding:8px">
        <div style="font-size:9px;font-weight:700;color:#7B1D1D;text-transform:uppercase;margin-bottom:4px">Class Teacher's Comment</div>
        <div style="font-size:11px;min-height:30px;color:#374151">${data.teacher_comment || '<span style="color:#9ca3af;font-style:italic">—</span>'}</div>
        <div style="margin-top:8px;border-top:1px solid #e5e7eb;padding-top:4px;font-size:9px;color:#6b7280">
          Signature: _________________________
        </div>
      </div>
      <div style="border:1px solid #e5e7eb;border-radius:4px;padding:8px">
        <div style="font-size:9px;font-weight:700;color:#7B1D1D;text-transform:uppercase;margin-bottom:4px">Head Teacher's Remark</div>
        <div style="font-size:11px;min-height:30px;color:#374151">${data.admin_comment || '<span style="color:#9ca3af;font-style:italic">—</span>'}</div>
        <div style="margin-top:8px;border-top:1px solid #e5e7eb;padding-top:4px;font-size:9px;color:#6b7280">
          Signature: _________________________
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div style="display:flex;justify-content:space-between;align-items:center;border-top:1px solid #e5e7eb;padding-top:6px">
      <div style="font-size:9px;color:#6b7280">Generated ${new Date().toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})}</div>
      <div style="text-align:center;border:2px solid #7B1D1D;border-radius:50%;width:44px;height:44px;display:flex;flex-direction:column;align-items:center;justify-content:center;transform:rotate(-10deg)">
        <div style="font-size:6px;font-weight:800;color:#7B1D1D;text-align:center;line-height:1.3">GOVT.<br/>APPROVED</div>
      </div>
      <div style="font-size:9px;color:#6b7280">${SCHOOL.address2}</div>
    </div>

  </div>`;

  document.getElementById('report-content').innerHTML = html;
  document.getElementById('report-overlay').classList.remove('hidden');
  closeModal();
}

async function openSkillEntry(pupilId) {
  const termId = document.getElementById('profile-term-select')?.value;
  if (!termId) { showToast('Please select a term first', 'error'); return; }
  try {
    // API returns flat dict: { skill_name: grade, __teacher_comment: '...', __admin_comment: '...' }
    const existing = await apiFetch(`/api/skills/${pupilId}/term/${termId}`);

    const rows = LOWER_SCHOOL_SKILLS.map(s => {
      const g = existing[s.key] || '';
      const sel = `<select name="grade_${s.key}" style="font-size:12px;padding:2px 4px;border:1px solid #e5e7eb;border-radius:3px">
        <option value="">—</option>
        ${['A','B','C','D','E'].map(x => `<option value="${x}" ${g===x?'selected':''}>${x}</option>`).join('')}
      </select>`;
      return `<tr>
        <td style="padding:5px 8px;font-size:12px">${s.emoji} ${s.label}</td>
        <td style="padding:5px 8px">${sel}</td>
      </tr>`;
    }).join('');

    const tc = existing.__teacher_comment || '';
    const ac = existing.__admin_comment || '';

    openModal('📋 Skill Assessment', `
      <form id="skill-form" onsubmit="saveSkillEntry(event,'${pupilId}','${termId}')">
        <table style="width:100%;border-collapse:collapse;margin-bottom:12px">
          <thead><tr style="background:#f3f4f6">
            <th style="padding:6px 8px;text-align:left;font-size:12px">Skill</th>
            <th style="padding:6px 8px;text-align:left;font-size:12px">Grade</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <div class="form-grid">
          <div class="form-group">
            <label>Teacher's Comment</label>
            <textarea name="teacher_comment" rows="2" style="width:100%;font-size:12px;padding:6px;border:1px solid #e5e7eb;border-radius:4px">${tc}</textarea>
          </div>
          <div class="form-group">
            <label>Head Teacher's Remark</label>
            <textarea name="admin_comment" rows="2" style="width:100%;font-size:12px;padding:6px;border:1px solid #e5e7eb;border-radius:4px">${ac}</textarea>
          </div>
        </div>
        <button type="submit" class="btn btn-primary">💾 Save Assessment</button>
      </form>`);
  } catch (err) {
    showToast('Error loading skills: ' + err.message, 'error');
  }
}

async function saveSkillEntry(event, pupilId, termId) {
  event.preventDefault();
  const form = document.getElementById('skill-form');
  const fd = new FormData(form);
  // API expects flat dict: { skill_name: grade, __teacher_comment: '...', __admin_comment: '...' }
  const payload = {};
  LOWER_SCHOOL_SKILLS.forEach(s => { payload[s.key] = fd.get(`grade_${s.key}`) || ''; });
  payload.__teacher_comment = fd.get('teacher_comment') || '';
  payload.__admin_comment = fd.get('admin_comment') || '';
  try {
    await apiFetch(`/api/skills/${pupilId}/term/${termId}`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    showToast('Skills assessment saved!');
    closeModal();
  } catch (err) {
    showToast('Error saving: ' + err.message, 'error');
  }
}

// ─── FEE MANAGEMENT ──────────────────────────────────────────────────────────

let _feeTab = 'structure';

async function loadFees() {
  _feeTab = 'structure';
  await loadFeeStructure();
}

async function loadFeesTab(tab) {
  _feeTab = tab;
  document.querySelectorAll('#page-fees .tab-btn').forEach((b, i) => {
    b.classList.toggle('active', (i === 0 && tab === 'structure') || (i === 1 && tab === 'bill'));
  });
  if (tab === 'structure') await loadFeeStructure();
  else await loadFeeBillUI();
}

async function loadFeeStructure() {
  const container = document.getElementById('fees-content');
  // Read year BEFORE clearing container — the select lives inside container
  const currentTerm = appData.terms.find(t => t.is_current) || appData.terms[0];
  const defaultYear = currentTerm ? currentTerm.academic_year : new Date().getFullYear() + '/' + (new Date().getFullYear()+1);
  const yearSelect = document.getElementById('fee-year-select');
  const year = yearSelect ? yearSelect.value : defaultYear;
  container.innerHTML = '<div class="loading">Loading fee structure…</div>';
  try {
    const data = await apiFetch(`/api/fees/structures?year=${encodeURIComponent(year)}`);
    const items = data.fee_structures || [];

    const grouped = {};
    items.forEach(item => {
      const key = item.class_id || '__all__';
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(item);
    });

    const allClasses = [{ id: '', name: 'All Classes (General)' }, ...appData.classes];
    const classOptions = allClasses.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    const yearOptions = (() => {
      const now = new Date().getFullYear();
      return [now-1, now, now+1].map(y => {
        const label = `${y}/${y+1}`;
        return `<option value="${label}" ${label===year?'selected':''}>${label}</option>`;
      }).join('');
    })();

    let html = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap">
        <div class="form-group" style="margin:0;flex:1;min-width:160px">
          <label style="font-size:12px">Academic Year</label>
          <select id="fee-year-select" onchange="loadFeeStructure()" style="width:100%">${yearOptions}</select>
        </div>
      </div>`;

    allClasses.forEach(cls => {
      const feeItems = grouped[cls.id] || [];
      html += `
        <div class="settings-card" style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <h3 style="margin:0">${cls.name}</h3>
            <button class="btn btn-sm btn-primary" onclick="openFeeStructureModal('','${cls.id}','${year}')">+ Add Fee</button>
          </div>`;

      if (!feeItems.length) {
        html += `<div class="empty" style="font-size:12px;padding:10px">No fee items. Click "+ Add Fee" to add.</div>`;
      } else {
        html += `<table class="data-table" style="font-size:12px">
          <thead><tr>
            <th>Fee Name</th><th>Term</th><th>New Pupil (₦)</th><th>Returning (₦)</th><th>Optional</th><th></th>
          </tr></thead><tbody>`;
        feeItems.forEach(item => {
          html += `<tr>
            <td><strong>${item.fee_name}</strong></td>
            <td>Term ${item.term_number}</td>
            <td>₦${Number(item.new_pupil_amount).toLocaleString()}</td>
            <td>₦${Number(item.returning_pupil_amount).toLocaleString()}</td>
            <td>${item.is_optional ? '<span class="badge">Optional</span>' : '—'}</td>
            <td>
              <button class="btn-icon" onclick="openFeeStructureModal('${item.id}','${cls.id}','${year}')" title="Edit">✏️</button>
              <button class="btn-icon" onclick="deleteFeeItem('${item.id}')" title="Delete">🗑️</button>
            </td>
          </tr>`;
        });
        html += `</tbody></table>`;
      }
      html += `</div>`;
    });

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="empty">Failed to load: ${err.message}</div>`;
  }
}

function openFeeStructureModal(feeId = '', classId = '', year = '') {
  const currentTerm = appData.terms.find(t => t.is_current);
  const defaultTerm = currentTerm ? currentTerm.term_number : 1;

  apiFetch(`/api/fees/structures?year=${encodeURIComponent(year)}`)
    .then(data => {
      const existing = (data.fee_structures || []).find(f => f.id === feeId);
      const classOptions = [{ id: '', name: 'All Classes (General)' }, ...appData.classes]
        .map(c => `<option value="${c.id}" ${(existing?existing.class_id:classId)===c.id?'selected':''}>${c.name}</option>`).join('');
      const termOptions = [1,2,3].map(n =>
        `<option value="${n}" ${(existing?existing.term_number:defaultTerm)===n?'selected':''}>${n}</option>`).join('');

      openModal(feeId ? 'Edit Fee Item' : 'Add Fee Item', `
        <form id="fee-struct-form" onsubmit="saveFeeItem(event,'${feeId}','${year}')">
          <div class="form-grid">
            <div class="form-group">
              <label>Class</label>
              <select name="class_id">${classOptions}</select>
            </div>
            <div class="form-group">
              <label>Term</label>
              <select name="term_number">${termOptions}</select>
            </div>
          </div>
          <div class="form-group">
            <label>Fee Name *</label>
            <input type="text" name="fee_name" value="${existing ? existing.fee_name : ''}" required placeholder="e.g. School Fees, PTA Levy…" />
          </div>
          <div class="form-grid">
            <div class="form-group">
              <label>New Pupil Amount (₦) *</label>
              <input type="number" name="new_pupil_amount" value="${existing ? existing.new_pupil_amount : ''}" min="0" step="0.01" required />
            </div>
            <div class="form-group">
              <label>Returning Pupil Amount (₦) *</label>
              <input type="number" name="returning_pupil_amount" value="${existing ? existing.returning_pupil_amount : ''}" min="0" step="0.01" required />
            </div>
          </div>
          <div class="form-group">
            <label><input type="checkbox" name="is_optional" style="margin-right:6px" ${existing&&existing.is_optional?'checked':''}> Optional fee</label>
          </div>
          <button type="submit" class="btn btn-primary">💾 Save</button>
        </form>`);
    }).catch(() => openModal('Error', '<p>Failed to load fee data</p>'));
}

async function saveFeeItem(event, feeId, year) {
  event.preventDefault();
  const form = document.getElementById('fee-struct-form');
  const fd = new FormData(form);
  const payload = {
    class_id: fd.get('class_id') || null,
    academic_year: year || appData.terms.find(t=>t.is_current)?.academic_year || '',
    term_number: parseInt(fd.get('term_number')),
    fee_name: fd.get('fee_name'),
    new_pupil_amount: parseFloat(fd.get('new_pupil_amount')) || 0,
    returning_pupil_amount: parseFloat(fd.get('returning_pupil_amount')) || 0,
    is_optional: fd.has('is_optional') ? 1 : 0
  };
  try {
    if (feeId) {
      await apiFetch(`/api/fees/structures/${feeId}`, { method: 'PUT', body: JSON.stringify(payload) });
    } else {
      await apiFetch('/api/fees/structures', { method: 'POST', body: JSON.stringify(payload) });
    }
    showToast('Fee item saved!');
    closeModal();
    loadFeeStructure();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function deleteFeeItem(feeId) {
  if (!confirm('Delete this fee item?')) return;
  try {
    await apiFetch(`/api/fees/structures/${feeId}`, { method: 'DELETE' });
    showToast('Fee item deleted');
    loadFeeStructure();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function loadFeeBillUI() {
  const container = document.getElementById('fees-content');
  const classOptions = appData.classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  const termOptions = appData.terms.map(t =>
    `<option value="${t.id}" ${t.is_current?'selected':''}>${t.academic_year} Term ${t.term_number}</option>`).join('');

  container.innerHTML = `
    <div class="settings-card" style="margin-bottom:16px">
      <h3>Generate Fee Bills</h3>
      <div class="form-row" style="align-items:flex-end;gap:12px">
        <div class="form-group" style="flex:1;min-width:160px">
          <label>Class</label>
          <select id="bill-class-select">${classOptions}</select>
        </div>
        <div class="form-group" style="flex:1;min-width:160px">
          <label>Term</label>
          <select id="bill-term-select">${termOptions}</select>
        </div>
        <button class="btn btn-primary" onclick="loadClassBills()" style="height:40px;margin-bottom:0">🔄 Load</button>
      </div>
    </div>
    <div id="bills-list"></div>`;
}

async function loadClassBills() {
  const classId = document.getElementById('bill-class-select').value;
  const termId = document.getElementById('bill-term-select').value;
  if (!classId || !termId) return;

  const container = document.getElementById('bills-list');
  container.innerHTML = '<div class="loading">Loading…</div>';
  try {
    const pupils = await apiFetch(`/api/pupils?status=active&class_id=${classId}`);
    if (!pupils.length) {
      container.innerHTML = '<div class="empty">No active pupils in this class</div>';
      return;
    }

    let html = `<table class="data-table" style="font-size:13px">
      <thead><tr>
        <th>Pupil</th><th>Adm No.</th><th>Actions</th>
      </tr></thead><tbody>`;
    pupils.forEach(p => {
      html += `<tr>
        <td><strong>${esc(p.last_name)}, ${esc(p.first_name)}</strong></td>
        <td>${esc(p.admission_number || '—')}</td>
        <td>
          <button class="btn btn-sm btn-primary" onclick="printBillForPupil('${p.id}','${termId}')">🖨️ Print Bill</button>
          <button class="btn btn-sm btn-secondary" onclick="recordFeePayment('${p.id}','${termId}')">💰 Record Payment</button>
        </td>
      </tr>`;
    });
    html += `</tbody></table>`;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div class="empty">Error: ${err.message}</div>`;
  }
}

async function printBillForPupil(pupilId, termId) {
  try {
    const data = await apiFetch(`/api/fees/bill/${pupilId}/term/${termId}`);
    renderSchoolBill(data);
  } catch (err) {
    showToast('Error generating bill: ' + err.message, 'error');
  }
}

async function recordFeePayment(pupilId, termId) {
  try {
    const data = await apiFetch(`/api/fees/bill/${pupilId}/term/${termId}`);
    const p = data.pupil;
    const t = data.term;
    const items = data.fee_items || [];
    const payments = data.payments || [];
    const isNew = data.is_new_pupil;
    const pupilName = `${p.first_name} ${p.last_name}`;

    if (!items.length) {
      return showToast('No fee items set up for this term. Add fee items in Fee Structure first.', 'error');
    }

    const rows = items.map(item => {
      const amt = isNew ? item.new_pupil_amount : item.returning_pupil_amount;
      const existingPayment = payments.find(pay => pay.fee_structure_id === item.id);
      const alreadyPaid = existingPayment ? existingPayment.amount_paid : 0;
      const balance = Math.max(0, amt - alreadyPaid);
      const balColor = balance > 0 ? '#dc2626' : '#15803d';
      // Input starts at 0 (this is the NEW additional payment, not the total).
      // The server accumulates: DB amount_paid += submitted value.
      return `<tr data-amt="${amt}" data-paid="${alreadyPaid}">
        <td style="font-size:13px">${item.fee_name}</td>
        <td style="text-align:right;font-size:13px">₦${Number(amt).toLocaleString()}</td>
        <td style="text-align:right;font-size:13px;color:#15803d">₦${Number(alreadyPaid).toLocaleString()}</td>
        <td>
          <input type="number" class="fee-pay-input" data-fee-id="${item.id}"
                 data-max-new="${balance}"
                 value="0" min="0" max="${balance}" step="0.01"
                 oninput="updatePaymentBalance(this)"
                 style="width:110px;font-size:13px;padding:4px 8px;border:1px solid var(--gray-200);border-radius:4px;text-align:right" />
        </td>
        <td class="pay-balance-cell" style="text-align:right;font-size:13px;font-weight:600;color:${balColor}">₦${balance.toLocaleString()}</td>
      </tr>`;
    }).join('');

    const body = `
      <div style="margin-bottom:12px">
        <div style="font-size:14px;font-weight:600">${pupilName}</div>
        <div style="font-size:12px;color:var(--gray-500)">${p.admission_number || ''} · ${p.class_name || ''} · ${t.academic_year} Term ${t.term_number}</div>
      </div>
      <p style="font-size:12px;color:var(--gray-500);margin-bottom:8px">
        ℹ️ Enter the <strong>new payment amount</strong> for each fee item. Leave at 0 to skip.
      </p>
      <form id="payment-form" onsubmit="submitFeePayments(event,'${pupilId}','${termId}')">
        <table class="data-table" style="font-size:13px">
          <thead><tr>
            <th>Fee Item</th>
            <th style="text-align:right">Amount Due</th>
            <th style="text-align:right">Already Paid</th>
            <th>New Payment (₦)</th>
            <th style="text-align:right">Remaining</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <div style="margin-top:8px;display:flex;gap:8px;align-items:center">
          <div class="form-group" style="flex:1;margin:0">
            <label style="font-size:12px">Payment Reference <span style="color:var(--gray-400);font-weight:400">(optional)</span></label>
            <input type="text" id="pay-ref" placeholder="e.g. Bank teller no., receipt no." style="font-size:12px;padding:6px 8px" />
          </div>
          <div class="form-group" style="margin:0">
            <label style="font-size:12px">Date</label>
            <input type="date" id="pay-date" value="${new Date().toISOString().split('T')[0]}" style="font-size:12px;padding:6px 8px" />
          </div>
        </div>
        <div style="margin-top:12px;display:flex;gap:8px;justify-content:flex-end">
          <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary">💾 Save Payments</button>
        </div>
      </form>`;

    openModal(`Record Payment — ${pupilName}`, body);
  } catch (err) {
    showToast('Error loading fee data: ' + err.message, 'error');
  }
}

// Live balance update: called when user changes a fee-pay-input value
function updatePaymentBalance(input) {
  const row = input.closest('tr');
  if (!row) return;
  const amt      = parseFloat(row.dataset.amt)  || 0;
  const paid     = parseFloat(row.dataset.paid) || 0;
  const newAmt   = parseFloat(input.value)      || 0;
  const maxNew   = parseFloat(input.dataset.maxNew) || 0;

  // Clamp to maximum payable
  if (newAmt > maxNew) {
    input.value = maxNew;
  }

  const remaining = Math.max(0, amt - paid - Math.min(newAmt, maxNew));
  const cell = row.querySelector('.pay-balance-cell');
  if (cell) {
    cell.textContent = `₦${remaining.toLocaleString()}`;
    cell.style.color = remaining > 0 ? '#dc2626' : '#15803d';
  }
}

async function submitFeePayments(event, pupilId, termId) {
  event.preventDefault();
  const inputs = document.querySelectorAll('.fee-pay-input');
  const payRef = document.getElementById('pay-ref').value.trim();
  const payDate = document.getElementById('pay-date').value;

  if (!payDate) {
    showToast('Please enter a payment date.', 'error');
    return;
  }

  let saved = 0;

  for (const input of inputs) {
    const feeId  = input.dataset.feeId;
    const amount = parseFloat(input.value) || 0;
    if (amount <= 0) continue;
    // Guard: never submit more than the remaining balance
    const maxNew = parseFloat(input.dataset.maxNew) || 0;
    const safeAmount = Math.min(amount, maxNew);
    if (safeAmount <= 0) continue;
    try {
      await apiFetch('/api/fees/payments', {
        method: 'POST',
        body: JSON.stringify({
          pupil_id: pupilId,
          term_id: termId,
          fee_structure_id: feeId,
          amount_paid: safeAmount,
          payment_date: payDate,
          payment_reference: payRef
        })
      });
      saved++;
    } catch (err) {
      showToast(`Error saving payment: ${err.message}`, 'error');
      return;
    }
  }

  if (saved === 0) {
    showToast('No payment amounts entered. Please enter at least one amount.', 'error');
    return;
  }

  showToast(`${saved} payment(s) recorded successfully!`, 'success');
  closeModal();
  loadClassBills(); // Refresh the bills list
}

function renderSchoolBill(data) {
  const p = data.pupil;
  const t = data.term;
  const items = data.fee_items || [];
  const payments = data.payments || [];
  const isNew = data.is_new_pupil;
  const name = `${p.first_name} ${p.other_name ? p.other_name + ' ' : ''}${p.last_name}`;

  const totalDue = items.reduce((sum, item) =>
    sum + (isNew ? item.new_pupil_amount : item.returning_pupil_amount), 0);
  const totalPaid = payments.reduce((sum, pay) => sum + (pay.amount_paid || 0), 0);
  const balance = totalDue - totalPaid;

  const feeRows = items.map(item => {
    const amt = isNew ? item.new_pupil_amount : item.returning_pupil_amount;
    const paid = payments.filter(pay => pay.fee_structure_id === item.id)
      .reduce((s, pay) => s + pay.amount_paid, 0);
    return `<tr>
      <td style="padding:6px 10px;border:1px solid #e5e7eb;font-size:12px">${item.fee_name}${item.is_optional?' <span style="font-size:10px;color:#6b7280">(Optional)</span>':''}</td>
      <td style="padding:6px 10px;border:1px solid #e5e7eb;font-size:12px;text-align:right">₦${amt.toLocaleString()}</td>
      <td style="padding:6px 10px;border:1px solid #e5e7eb;font-size:12px;text-align:right">₦${paid.toLocaleString()}</td>
      <td style="padding:6px 10px;border:1px solid #e5e7eb;font-size:12px;text-align:right;color:${amt-paid>0?'#dc2626':'#15803d'}">₦${(amt-paid).toLocaleString()}</td>
    </tr>`;
  }).join('');

  const html = `
  <style>
    @media print {
      @page { size: A4 portrait; margin: 12mm; }
      body * { visibility: hidden; }
      #report-content, #report-content * { visibility: visible; }
      #report-content { position: fixed; top: 0; left: 0; width: 100%; }
      .report-toolbar { display: none !important; }
    }
  </style>
  <div style="font-family:Arial,sans-serif;font-size:12px;color:#1f2937;max-width:650px;margin:0 auto;padding:10px">

    <!-- School Header -->
    <div style="text-align:center;border-bottom:3px solid #7B1D1D;padding-bottom:10px;margin-bottom:14px">
      <img src="${SCHOOL.logo}" style="height:55px;margin-bottom:4px" onerror="this.style.display='none'" />
      <div style="font-size:18px;font-weight:800;color:#7B1D1D;letter-spacing:1px">${SCHOOL.name}</div>
      <div style="font-size:11px;color:#374151">${SCHOOL.fullName}</div>
      <div style="font-size:10px;color:#6b7280">${SCHOOL.address}</div>
      <div style="font-size:10px;color:#6b7280">${SCHOOL.address2}</div>
      <div style="font-size:10px;color:#6b7280">Tel: ${SCHOOL.phones}</div>
      <div style="font-size:14px;font-weight:700;color:#374151;margin-top:8px;text-transform:uppercase;letter-spacing:1px;border:2px solid #7B1D1D;display:inline-block;padding:3px 16px;border-radius:2px">
        School Fee Bill — ${t.academic_year} Term ${t.term_number}
      </div>
    </div>

    <!-- Pupil Info -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;background:#fafafa;border:1px solid #e5e7eb;border-radius:6px;padding:10px;margin-bottom:14px">
      <div><span style="font-size:9px;color:#6b7280;text-transform:uppercase">Pupil Name</span><br/><strong>${name}</strong></div>
      <div><span style="font-size:9px;color:#6b7280;text-transform:uppercase">Admission No.</span><br/><strong>${p.admission_number || '—'}</strong></div>
      <div><span style="font-size:9px;color:#6b7280;text-transform:uppercase">Class</span><br/><strong>${p.class_name || '—'}</strong></div>
      <div><span style="font-size:9px;color:#6b7280;text-transform:uppercase">Pupil Type</span><br/><strong style="color:${isNew?'#7B1D1D':'#374151'}">${isNew ? 'New Pupil' : 'Returning Pupil'}</strong></div>
    </div>

    <!-- Fee Table -->
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px">
      <thead>
        <tr style="background:#7B1D1D;color:white">
          <th style="padding:6px 10px;text-align:left;font-size:11px;border:1px solid #7B1D1D">Fee Description</th>
          <th style="padding:6px 10px;text-align:right;font-size:11px;border:1px solid #7B1D1D;width:100px">Amount Due</th>
          <th style="padding:6px 10px;text-align:right;font-size:11px;border:1px solid #7B1D1D;width:100px">Paid</th>
          <th style="padding:6px 10px;text-align:right;font-size:11px;border:1px solid #7B1D1D;width:100px">Balance</th>
        </tr>
      </thead>
      <tbody>${feeRows}</tbody>
      <tfoot>
        <tr style="background:#f3f4f6;font-weight:700">
          <td style="padding:7px 10px;border:1px solid #e5e7eb;font-size:12px">TOTAL</td>
          <td style="padding:7px 10px;border:1px solid #e5e7eb;font-size:12px;text-align:right">₦${totalDue.toLocaleString()}</td>
          <td style="padding:7px 10px;border:1px solid #e5e7eb;font-size:12px;text-align:right;color:#15803d">₦${totalPaid.toLocaleString()}</td>
          <td style="padding:7px 10px;border:1px solid #e5e7eb;font-size:12px;text-align:right;color:${balance>0?'#dc2626':'#15803d'}">₦${balance.toLocaleString()}</td>
        </tr>
      </tfoot>
    </table>

    <!-- Bank Details -->
    <div style="background:#fef9f0;border:1px solid #fcd34d;border-radius:4px;padding:10px;margin-bottom:12px">
      <div style="font-size:10px;font-weight:700;color:#92400e;text-transform:uppercase;margin-bottom:4px">Payment Details</div>
      <div style="font-size:11px;color:#374151">All fees should be paid via bank transfer or directly at the school bursary.</div>
      <div style="font-size:11px;color:#374151;margin-top:4px">Please present this bill when making payment at the school office.</div>
    </div>

    <!-- Signature Area -->
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-top:20px">
      <div style="text-align:center">
        <div style="border-top:1px solid #374151;padding-top:4px;font-size:10px;color:#6b7280">Parent / Guardian Signature</div>
      </div>
      <div style="text-align:center">
        <div style="border-top:1px solid #374151;padding-top:4px;font-size:10px;color:#6b7280">Bursary Stamp</div>
      </div>
      <div style="text-align:center">
        <div style="border-top:1px solid #374151;padding-top:4px;font-size:10px;color:#6b7280">Date Paid</div>
      </div>
    </div>

    <!-- Footer -->
    <div style="text-align:center;margin-top:16px;font-size:9px;color:#9ca3af;border-top:1px solid #e5e7eb;padding-top:8px">
      Generated ${new Date().toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric'})} · ${SCHOOL.email}
    </div>
  </div>`;

  document.getElementById('report-content').innerHTML = html;
  document.getElementById('report-overlay').classList.remove('hidden');
}

// ─── ID CARDS ─────────────────────────────────────────────────────────────────

function idCardFront(name, role, photoUrl, initials) {
  const photoHtml = photoUrl
    ? `<img src="${photoUrl}" />`
    : `<div class="id-card-photo-initials">${initials}</div>`;
  return `
    <div class="id-card">
      <div class="id-card-bg"></div>
      <div class="id-card-inner">
        <img src="${SCHOOL.logo}" class="id-card-logo" />
        <div class="id-card-school-name">${SCHOOL.name}</div>
        <div class="id-card-motto-line">${SCHOOL.tagline}</div>
        <div class="id-card-photo-wrap">${photoHtml}</div>
        <div class="id-card-name">${name}</div>
        <div class="id-card-divider"></div>
        <div class="id-card-role">${role}</div>
      </div>
    </div>`;
}

function idCardBack(certText) {
  return `
    <div class="id-card id-card-back">
      <div class="id-card-bg"></div>
      <div class="id-card-inner">
        <div class="id-card-back-cert">${certText}</div>
        <div class="id-card-contact-row">
          <span class="id-card-contact-icon">📞</span>
          <span class="id-card-contact-text">${SCHOOL.phones}</span>
        </div>
        <div class="id-card-contact-row">
          <span class="id-card-contact-icon">✉️</span>
          <span class="id-card-contact-text">${SCHOOL.email}</span>
        </div>
        <div class="id-card-contact-row">
          <span class="id-card-contact-icon">📍</span>
          <span class="id-card-contact-text">${SCHOOL.address}<br/>${SCHOOL.address2}</span>
        </div>
        <div class="id-card-back-motto">${SCHOOL.motto}</div>
      </div>
    </div>`;
}

async function generatePupilIDCard(pupilId) {
  try {
    const pupil = await apiFetch(`/api/pupils/${pupilId}`);
    const name = `${pupil.first_name} ${pupil.other_name ? pupil.other_name + ' ' : ''}${pupil.last_name}`;
    const initials = `${pupil.first_name.charAt(0)}${pupil.last_name.charAt(0)}`;
    const certText = `This is to certify that the child whose photograph appears on this card is a registered pupil of this school. Please come with this ID anytime you want to pick this child. If found, drop in any mail box or return to the school.`;
    const front = idCardFront(name, 'Pupil', pupil.photo || '', initials);
    const back = idCardBack(certText);
    renderIDCard([[front, back]]);
  } catch (err) {
    showToast('Error generating ID card: ' + err.message, 'error');
  }
}

async function generateTeacherIDCard(teacherId, teacherName) {
  const initials = (teacherName || 'ST').split(' ').filter(w => w.length > 0).map(w => w[0]).join('').substring(0, 2).toUpperCase() || 'ST';
  const certText = `This is to certify that the person whose photograph appears on this card is a registered staff of this school. Please come with this ID when resuming at work. If found, drop in any mailbox or return to the school.`;
  const front = idCardFront(teacherName, 'Staff', '', initials);
  const back = idCardBack(certText);
  renderIDCard([[front, back]]);
}

async function generateAllPupilIDCards(classId) {
  try {
    const url = classId ? `/api/pupils?class_id=${classId}&status=active` : `/api/pupils?status=active`;
    const pupils = await apiFetch(url);
    if (!pupils.length) return showToast('No pupils found', 'error');
    const certText = `This is to certify that the child whose photograph appears on this card is a registered pupil of this school. Please come with this ID anytime you want to pick this child. If found, drop in any mail box or return to the school.`;
    const pairs = pupils.map(p => {
      const name = `${p.first_name} ${p.other_name ? p.other_name + ' ' : ''}${p.last_name}`;
      const initials = `${p.first_name.charAt(0)}${p.last_name.charAt(0)}`;
      return [idCardFront(name, 'Pupil', p.photo || '', initials), idCardBack(certText)];
    });
    renderIDCard(pairs);
    closeModal();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

function renderIDCard(pairs) {
  const content = pairs.map(([front, back]) => `
    <div class="id-card-pair">
      <div>
        <div class="id-card-label">FRONT</div>
        ${front}
      </div>
      <div>
        <div class="id-card-label">BACK</div>
        ${back}
      </div>
    </div>`).join('');
  document.getElementById('idcard-content').innerHTML = content;
  document.getElementById('idcard-overlay').classList.remove('hidden');
  closeModal();
}

function closeIDCard() {
  document.getElementById('idcard-overlay').classList.add('hidden');
}

function showBulkIDCardModal() {
  const classes = appData.classes;
  openModal('Generate ID Cards', `
    <div style="padding-bottom:8px">
      <p style="color:var(--gray-600);margin-bottom:16px">Generate ID cards for all pupils in a class, or for all pupils in the school.</p>
      <div class="form-group">
        <label>Select Class (or leave blank for all)</label>
        <select id="bulk-id-class">
          <option value="">All Classes (entire school)</option>
          ${classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('')}
        </select>
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="generateAllPupilIDCards(document.getElementById('bulk-id-class').value)">
          🪪 Generate ID Cards
        </button>
      </div>
    </div>`);
}

// ─── PARENT EXPORT ────────────────────────────────────────────────────────────

async function exportParents() {
  try {
    showToast('Preparing export…', 'success');
    const pupils = await apiFetch('/api/pupils?status=active');
    if (!pupils.length) return showToast('No active pupils found', 'error');

    const headers = ['Pupil Name', 'Admission No.', 'Class', 'Parent/Guardian Name',
                     'Relationship', 'Phone Number', 'Email Address', 'Home Address'];

    const rows = pupils.map(p => [
      `${p.last_name}, ${p.first_name} ${p.other_name || ''}`.trim(),
      p.admission_number || '',
      p.class_name || '',
      p.parent_name || '',
      p.parent_relationship || '',
      p.parent_phone || '',
      p.parent_email || '',
      (p.parent_address || '').replace(/\n/g, ' ')
    ]);

    // Build CSV
    const csvLines = [headers, ...rows].map(row =>
      row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
    );
    const csv = '\ufeff' + csvLines.join('\r\n');  // BOM for Excel compatibility

    // Download
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `GISL_Schools_Parent_Contacts_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`Exported ${pupils.length} parent contacts`, 'success');
  } catch (err) {
    showToast('Export failed: ' + err.message, 'error');
  }
}

// ─── CSV EXPORTS ──────────────────────────────────────────────────────────────

async function exportPupilsCSV() {
  try {
    const token = localStorage.getItem('token');
    const res = await fetch('/api/export/pupils', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) { showToast('Export failed', 'error'); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'pupils.csv';
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) { showToast('Export failed: ' + err.message, 'error'); }
}

async function exportResultsCSV() {
  const termId = document.getElementById('results-term-select')?.value;
  if (!termId) { showToast('Please select a term first', 'error'); return; }
  try {
    const token = localStorage.getItem('token');
    const res = await fetch(`/api/export/results?term_id=${termId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) { showToast('Export failed', 'error'); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'results.csv';
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) { showToast('Export failed: ' + err.message, 'error'); }
}

async function exportFeesCSV() {
  const termSelect = document.getElementById('bill-term-select');
  const termId = termSelect ? termSelect.value : (appData.terms.find(t => t.is_current) || appData.terms[0])?.id;
  if (!termId) { showToast('Please select a term first', 'error'); return; }
  try {
    const token = localStorage.getItem('token');
    const res = await fetch(`/api/export/fees?term_id=${termId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) { showToast('Export failed', 'error'); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'fees.csv';
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) { showToast('Export failed: ' + err.message, 'error'); }
}

// ─── BULK RESULTS IMPORT ──────────────────────────────────────────────────────

function showBulkResultsImport() {
  const { classId, termId, subjects } = _marksheetData || {};
  if (!classId || !termId) {
    showToast('Please load a marksheet first (select class and term)', 'error');
    return;
  }
  openModal('📥 Import Results CSV', `
    <div>
      <p style="font-size:13px;color:var(--gray-600);margin-bottom:8px">
        Upload a CSV file to pre-fill scores. The file must have these columns:<br/>
        <code style="background:var(--gray-50);padding:2px 6px;border-radius:4px">admission_number, subject_name, ca_score, exam_score</code>
      </p>
      <div class="form-group">
        <label>Select CSV File</label>
        <input type="file" id="import-csv-input" accept=".csv" onchange="previewImportCSV(event)" />
      </div>
      <div id="import-csv-preview"></div>
      <div id="import-csv-actions" class="hidden" style="margin-top:12px;display:flex;gap:8px">
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="applyImportedResults()">✅ Apply to Marksheet</button>
      </div>
    </div>`);
}

let _importedRows = [];

function previewImportCSV(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target.result;
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    if (lines.length < 2) {
      document.getElementById('import-csv-preview').innerHTML = '<div class="empty">File appears empty or has no data rows.</div>';
      return;
    }
    const headers = lines[0].split(',').map(h => h.replace(/^"|"$/g,'').trim().toLowerCase());
    const admIdx = headers.indexOf('admission_number');
    const subjIdx = headers.indexOf('subject_name');
    const caIdx = headers.indexOf('ca_score');
    const examIdx = headers.indexOf('exam_score');
    if (admIdx < 0 || subjIdx < 0 || caIdx < 0 || examIdx < 0) {
      document.getElementById('import-csv-preview').innerHTML =
        '<div class="empty" style="color:#dc2626">Missing required columns. Need: admission_number, subject_name, ca_score, exam_score</div>';
      return;
    }
    const { pupils, subjects } = _marksheetData || {};
    _importedRows = [];
    const rows = lines.slice(1).map(line => {
      const cols = line.split(',').map(c => c.replace(/^"|"$/g,'').trim());
      const admNo = cols[admIdx];
      const subjName = cols[subjIdx];
      const ca = parseFloat(cols[caIdx]) || 0;
      const exam = parseFloat(cols[examIdx]) || 0;
      const pupil = (pupils||[]).find(p => p.admission_number === admNo);
      const subject = (subjects||[]).find(s => s.name.toLowerCase() === subjName.toLowerCase());
      const status = !pupil ? 'Unknown pupil' : !subject ? 'Unknown subject' : 'OK';
      if (pupil && subject) _importedRows.push({ pupil, subject, ca, exam });
      return { admNo, subjName, ca, exam, status };
    });
    const preview = rows.map(r => `<tr>
      <td style="padding:4px 8px;font-size:12px">${esc(r.admNo)}</td>
      <td style="padding:4px 8px;font-size:12px">${esc(r.subjName)}</td>
      <td style="padding:4px 8px;font-size:12px;text-align:center">${r.ca}</td>
      <td style="padding:4px 8px;font-size:12px;text-align:center">${r.exam}</td>
      <td style="padding:4px 8px;font-size:12px;color:${r.status==='OK'?'#15803d':'#dc2626'}">${esc(r.status)}</td>
    </tr>`).join('');
    document.getElementById('import-csv-preview').innerHTML = `
      <div style="max-height:300px;overflow-y:auto;margin-top:10px">
        <table class="data-table" style="font-size:12px">
          <thead><tr>
            <th>Adm No</th><th>Subject</th><th>CA</th><th>Exam</th><th>Status</th>
          </tr></thead>
          <tbody>${preview}</tbody>
        </table>
      </div>
      <div style="margin-top:8px;font-size:12px;color:var(--gray-500)">${_importedRows.length} of ${rows.length} rows will be applied.</div>`;
    document.getElementById('import-csv-actions').classList.remove('hidden');
  };
  reader.readAsText(file);
}

function applyImportedResults() {
  if (!_importedRows.length) { showToast('No valid rows to apply', 'error'); return; }
  let applied = 0;
  _importedRows.forEach(({ pupil, subject, ca, exam }) => {
    const caEl = document.getElementById(`ms-ca-${pupil.id}-${subject.id}`);
    const examEl = document.getElementById(`ms-exam-${pupil.id}-${subject.id}`);
    if (caEl) { caEl.value = Math.min(ca, 40); }
    if (examEl) { examEl.value = Math.min(exam, 60); }
    if (caEl || examEl) { msRecomputeTotal(pupil.id); applied++; }
  });
  closeModal();
  showToast(`Applied ${applied} scores to marksheet. Review and save.`, 'success');
}

// ─── AUDIT LOG ────────────────────────────────────────────────────────────────

async function loadAuditLog() {
  const el = document.getElementById('audit-log-list');
  if (!el) return;
  try {
    const logs = await apiFetch('/api/audit-log');
    if (!logs.length) {
      el.innerHTML = '<div class="empty" style="font-size:12px;padding:8px">No audit entries yet.</div>';
      return;
    }
    el.innerHTML = `<div style="overflow-x:auto;max-height:300px;overflow-y:auto">
      <table class="data-table" style="font-size:11px">
        <thead><tr>
          <th>Date/Time</th><th>User</th><th>Action</th><th>Details</th>
        </tr></thead>
        <tbody>${logs.map(l => `<tr>
          <td style="white-space:nowrap">${new Date(l.created_at).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'})}</td>
          <td>${esc(l.user_email || '—')}</td>
          <td><span class="badge" style="background:#f3f4f6;color:#374151">${esc(l.action)}</span></td>
          <td style="color:var(--gray-500)">${esc(l.details || l.target_id || '—')}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>`;
  } catch (err) {
    el.innerHTML = `<div class="empty" style="font-size:12px">Error: ${esc(err.message)}</div>`;
  }
}

// ─── MODAL ────────────────────────────────────────────────────────────────────

function openModal(title, html) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = html;
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal(event) {
  if (event && event.target !== document.getElementById('modal-overlay')) return;
  document.getElementById('modal-overlay').classList.add('hidden');
  document.getElementById('modal-body').innerHTML = '';
}

// ─── PARENT PORTAL ───────────────────────────────────────────────────────────

let _parentCurrentChild = null;
let _parentCurrentChildType = 'primary'; // 'lower' or 'primary'
let _parentCurrentTab = 'results';

async function loadParentHome() {
  const grid = document.getElementById('parent-children-grid');
  grid.innerHTML = '<div class="loading">Loading your children…</div>';
  try {
    const children = await apiFetch('/api/parent/children');
    if (!children.length) {
      grid.innerHTML = `<div class="empty" style="grid-column:1/-1">
        <p>No children found linked to your account.</p>
        <p style="font-size:13px;color:var(--gray-400)">Please contact the school office to link your email to your child's record.</p>
      </div>`;
      return;
    }
    grid.innerHTML = children.map(c => {
      const name = `${c.first_name} ${c.other_name ? c.other_name + ' ' : ''}${c.last_name}`;
      const photo = c.photo
        ? `<img src="${c.photo}" style="width:70px;height:80px;object-fit:cover;border-radius:6px;border:2px solid #7B1D1D" />`
        : `<div style="width:70px;height:80px;background:#7B1D1D;border-radius:6px;display:flex;align-items:center;justify-content:center;color:white;font-size:24px;font-weight:700">${c.first_name.charAt(0)}${c.last_name.charAt(0)}</div>`;
      const classType = c.class_type || 'primary';
      return `
        <div class="settings-card" style="cursor:pointer;transition:box-shadow 0.15s" onmouseenter="this.style.boxShadow='0 4px 16px rgba(123,29,29,0.15)'" onmouseleave="this.style.boxShadow=''" onclick="openParentChild('${c.id}','${name.replace(/'/g,"\\'")}','${classType}')">
          <div style="display:flex;gap:14px;align-items:center">
            ${photo}
            <div>
              <div style="font-size:15px;font-weight:700;color:#1f2937;margin-bottom:4px">${esc(name)}</div>
              <div style="font-size:12px;color:#6b7280;margin-bottom:6px">${esc(c.class_name || 'No class assigned')}</div>
              <div style="font-size:12px;color:#6b7280">Adm: <strong>${esc(c.admission_number || '—')}</strong></div>
              <div style="margin-top:8px">
                <span class="badge badge-${c.gender}">${c.gender || '—'}</span>
                ${c.class_type === 'lower' ? '<span class="badge" style="background:#fef9c3;color:#78350f;margin-left:4px">Nursery/KG</span>' : ''}
              </div>
            </div>
          </div>
          <div style="margin-top:12px;border-top:1px solid var(--gray-100);padding-top:10px;display:flex;gap:8px">
            <button class="btn btn-primary btn-sm" style="flex:1" onclick="event.stopPropagation();openParentChild('${c.id}','${name.replace(/'/g,"\\'")}','${classType}')">
              View Details →
            </button>
          </div>
        </div>`;
    }).join('');
  } catch (err) {
    grid.innerHTML = `<div class="empty">Failed to load: ${err.message}</div>`;
  }
}

function openParentChild(childId, childName, classType) {
  _parentCurrentChild = childId;
  _parentCurrentChildType = classType || 'primary';
  _parentCurrentTab = 'results';
  document.getElementById('parent-child-title').textContent = childName;
  // Reset tab buttons
  document.querySelectorAll('#parent-child-tabs .tab-btn').forEach((b, i) => b.classList.toggle('active', i === 0));
  // Navigate
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-parent-child').classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  loadParentChildTab('results');
}

function loadParentChildTab(tab) {
  _parentCurrentTab = tab;
  const buttons = document.querySelectorAll('#parent-child-tabs .tab-btn');
  const tabNames = ['results', 'fees', 'report', 'homework', 'timetable', 'acknowledge'];
  buttons.forEach((b, i) => b.classList.toggle('active', tabNames[i] === tab));
  const content = document.getElementById('parent-child-content');

  const terms = appData.terms;
  if (!terms.length) {
    content.innerHTML = '<div class="empty">No terms available. Please contact the school.</div>';
    return;
  }

  // Build term selector
  const existingSelect = document.getElementById('parent-term-select');
  const selectedTermId = existingSelect ? existingSelect.value : (terms.find(t => t.is_current) || terms[0]).id;
  const termSelectHtml = `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <label style="font-size:12px;font-weight:600;color:var(--gray-600)">Term:</label>
      <select id="parent-term-select" onchange="loadParentChildTab('${tab}')" style="font-size:13px;padding:4px 10px;border:1px solid var(--gray-200);border-radius:6px">
        ${terms.map(t => `<option value="${t.id}" ${t.id===selectedTermId?'selected':''}>${t.academic_year} Term ${t.term_number}${t.is_current?' (Current)':''}</option>`).join('')}
      </select>
    </div>`;

  content.innerHTML = termSelectHtml + '<div id="parent-child-data"><div class="loading">Loading…</div></div>';

  const termSel = document.getElementById('parent-term-select');
  const chosenTermId = termSel ? termSel.value : selectedTermId;
  const selectedTerm = terms.find(t => t.id === chosenTermId) || terms[0];

  if (tab === 'results') loadParentChildResults(selectedTerm);
  else if (tab === 'fees') loadParentChildFees(selectedTerm);
  else if (tab === 'report') loadParentChildReport(selectedTerm);
  else if (tab === 'homework') loadParentChildHomework(selectedTerm);
  else if (tab === 'timetable') loadParentChildTimetable(selectedTerm);
  else if (tab === 'acknowledge') loadParentChildAcknowledge(selectedTerm);
}

async function loadParentChildResults(term) {
  const content = document.getElementById('parent-child-data');
  try {
    const data = await apiFetch(`/api/parent/child/${_parentCurrentChild}/results?term_id=${term.id}`);
    const results = data.results || [];
    const ack = data.acknowledgment;

    if (!results.length) {
      content.innerHTML = `
        <div style="background:white;border:1px solid var(--gray-200);border-radius:8px;padding:24px;text-align:center;color:var(--gray-400)">
          <div style="font-size:32px;margin-bottom:8px">📝</div>
          <div>No results recorded yet for <strong>${term.academic_year} Term ${term.term_number}</strong></div>
          <div style="font-size:13px;margin-top:4px">Check back after results are entered by the school.</div>
        </div>`;
      return;
    }

    let totalCA = 0, totalExam = 0, totalObtained = 0, totalMax = results.length * 100;
    const rows = results.map(r => {
      const ca = r.ca_score || 0, exam = r.exam_score || 0, total = ca + exam;
      const grade = reportGrade(total);
      totalCA += ca; totalExam += exam; totalObtained += total;
      return `<tr>
        <td style="padding:6px 10px;border-bottom:1px solid var(--gray-100)"><strong>${esc(r.subject_name)}</strong></td>
        <td style="padding:6px 10px;border-bottom:1px solid var(--gray-100);text-align:center">${ca}<span style="color:var(--gray-400);font-size:11px">/40</span></td>
        <td style="padding:6px 10px;border-bottom:1px solid var(--gray-100);text-align:center">${exam}<span style="color:var(--gray-400);font-size:11px">/60</span></td>
        <td style="padding:6px 10px;border-bottom:1px solid var(--gray-100);text-align:center;font-weight:700">${total}</td>
        <td style="padding:6px 10px;border-bottom:1px solid var(--gray-100);text-align:center">
          <span style="background:${gradeColor(grade)};color:white;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:700">${grade}</span>
        </td>
      </tr>`;
    }).join('');

    const pct = totalMax > 0 ? ((totalObtained / totalMax) * 100).toFixed(1) : 0;
    const ackBanner = ack
      ? `<div style="background:#dcfce7;border:1px solid #86efac;border-radius:6px;padding:10px 14px;margin-bottom:14px;font-size:13px;color:#15803d">
           ✅ You acknowledged these results on <strong>${new Date(ack.acknowledged_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})}</strong>
           ${ack.parent_comment ? `<div style="margin-top:4px;font-style:italic">"${ack.parent_comment}"</div>` : ''}
         </div>`
      : `<div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:10px 14px;margin-bottom:14px;font-size:13px;color:#78350f">
           ⏳ You have not yet acknowledged this term's results. Go to the <strong>Acknowledge</strong> tab to confirm you've seen them.
         </div>`;

    content.innerHTML = `
      <div style="margin-bottom:12px">
        <h4 style="font-size:14px;font-weight:600;color:var(--gray-600);margin-bottom:6px">${term.academic_year} — Term ${term.term_number} Results</h4>
        ${ackBanner}
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:14px">
          ${[['Total Obtained', totalObtained], ['Max Score', totalMax], ['Percentage', pct+'%'], ['Subjects', results.length]].map(([l,v]) =>
            `<div style="background:white;border:1px solid var(--gray-200);border-radius:8px;padding:10px 14px;text-align:center">
              <div style="font-size:18px;font-weight:700;color:#7B1D1D">${v}</div>
              <div style="font-size:11px;color:var(--gray-400)">${l}</div>
            </div>`
          ).join('')}
        </div>
        <div style="background:white;border:1px solid var(--gray-200);border-radius:8px;overflow:hidden">
          <table style="width:100%;border-collapse:collapse">
            <thead><tr style="background:var(--gray-50)">
              <th style="padding:8px 10px;text-align:left;font-size:12px">Subject</th>
              <th style="padding:8px 10px;text-align:center;font-size:12px">Test</th>
              <th style="padding:8px 10px;text-align:center;font-size:12px">Exam</th>
              <th style="padding:8px 10px;text-align:center;font-size:12px">Total</th>
              <th style="padding:8px 10px;text-align:center;font-size:12px">Grade</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  } catch (err) {
    content.innerHTML = `<div class="empty">Failed to load: ${err.message}</div>`;
  }
}

async function loadParentChildFees(term) {
  const content = document.getElementById('parent-child-data');
  try {
    const data = await apiFetch(`/api/parent/child/${_parentCurrentChild}/fees/term/${term.id}`);
    const items = data.fee_items || [];
    const payments = data.payments || [];
    const isNew = data.is_new_pupil;
    const totalDue = items.reduce((s, i) => s + (isNew ? i.new_pupil_amount : i.returning_pupil_amount), 0);
    const totalPaid = payments.reduce((s, p) => s + p.amount_paid, 0);
    const balance = totalDue - totalPaid;

    if (!items.length) {
      content.innerHTML = `<div class="empty">No fee structure set up yet for this term. Please contact the school office.</div>`;
      return;
    }

    const rows = items.map(item => {
      const due = isNew ? item.new_pupil_amount : item.returning_pupil_amount;
      const paid = payments.filter(p => p.fee_structure_id === item.id).reduce((s, p) => s + p.amount_paid, 0);
      return `<tr>
        <td style="padding:8px 12px;border-bottom:1px solid var(--gray-100)">${item.fee_name}${item.is_optional?' <span style="font-size:11px;color:var(--gray-400)">(Optional)</span>':''}</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--gray-100);text-align:right">₦${due.toLocaleString()}</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--gray-100);text-align:right;color:#15803d">₦${paid.toLocaleString()}</td>
        <td style="padding:8px 12px;border-bottom:1px solid var(--gray-100);text-align:right;color:${due-paid>0?'#dc2626':'#15803d'};font-weight:${due-paid>0?'700':'400'}">₦${(due-paid).toLocaleString()}</td>
      </tr>`;
    }).join('');

    content.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-bottom:14px">
        ${[['Total Due', '₦'+totalDue.toLocaleString(), '#374151'], ['Amount Paid', '₦'+totalPaid.toLocaleString(), '#15803d'], ['Balance Owed', '₦'+balance.toLocaleString(), balance>0?'#dc2626':'#15803d']].map(([l,v,c]) =>
          `<div style="background:white;border:1px solid var(--gray-200);border-radius:8px;padding:12px 14px;text-align:center">
            <div style="font-size:18px;font-weight:700;color:${c}">${v}</div>
            <div style="font-size:11px;color:var(--gray-400)">${l}</div>
          </div>`
        ).join('')}
      </div>
      <div style="background:white;border:1px solid var(--gray-200);border-radius:8px;overflow:hidden;margin-bottom:12px">
        <table style="width:100%;border-collapse:collapse">
          <thead><tr style="background:var(--gray-50)">
            <th style="padding:8px 12px;text-align:left;font-size:12px">Description</th>
            <th style="padding:8px 12px;text-align:right;font-size:12px">Amount</th>
            <th style="padding:8px 12px;text-align:right;font-size:12px">Paid</th>
            <th style="padding:8px 12px;text-align:right;font-size:12px">Balance</th>
          </tr></thead>
          <tbody>${rows}</tbody>
          <tfoot><tr style="background:var(--gray-50);font-weight:700">
            <td style="padding:8px 12px">TOTAL</td>
            <td style="padding:8px 12px;text-align:right">₦${totalDue.toLocaleString()}</td>
            <td style="padding:8px 12px;text-align:right;color:#15803d">₦${totalPaid.toLocaleString()}</td>
            <td style="padding:8px 12px;text-align:right;color:${balance>0?'#dc2626':'#15803d'}">₦${balance.toLocaleString()}</td>
          </tr></tfoot>
        </table>
      </div>
      ${balance > 0 ? `<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:10px 14px;font-size:13px;color:#dc2626">
        ⚠️ You have an outstanding balance of <strong>₦${balance.toLocaleString()}</strong>. Please make payment at the school bursary.
      </div>` : `<div style="background:#dcfce7;border:1px solid #86efac;border-radius:6px;padding:10px 14px;font-size:13px;color:#15803d">
        ✅ All fees for this term are fully paid. Thank you!
      </div>`}
      <div style="margin-top:12px">
        <button class="btn btn-primary" onclick="printBillForPupil('${_parentCurrentChild}','${term.id}')">🖨️ Print Fee Bill</button>
        ${balance > 0 ? `<button class="btn btn-success" onclick="startParentOnlinePayment('${_parentCurrentChild}','${term.id}')">💳 Pay Now</button>` : ''}
        <button class="btn btn-secondary" onclick="downloadFeeReceiptPdf('${_parentCurrentChild}','${term.id}')">📄 Receipt PDF</button>
      </div>`;
  } catch (err) {
    content.innerHTML = `<div class="empty">Failed to load: ${err.message}</div>`;
  }
}

async function loadParentChildReport(term) {
  const content = document.getElementById('parent-child-data');
  try {
    const isLower = _parentCurrentChildType === 'lower';
    content.innerHTML = `
      <div style="background:white;border:1px solid var(--gray-200);border-radius:8px;padding:24px;text-align:center">
        <div style="font-size:40px;margin-bottom:12px">📄</div>
        <h3 style="font-size:16px;font-weight:600;color:#1f2937;margin-bottom:8px">${term.academic_year} Term ${term.term_number} Report Card</h3>
        <p style="font-size:13px;color:var(--gray-500);margin-bottom:20px">Click below to generate and view the full report card for this term.</p>
        <button class="btn btn-primary" onclick="${isLower ? `_parentGenerateLowerReport('${term.id}')` : `_parentGenerateReport('${term.id}')`}">
          📄 Generate Report Card
        </button>
        <button class="btn btn-secondary" onclick="downloadReportPdf('${_parentCurrentChild}','${term.id}')">
          ⬇️ Download PDF
        </button>
      </div>`;
  } catch (err) {
    content.innerHTML = `<div class="empty">Failed: ${err.message}</div>`;
  }
}

async function loadParentChildHomework(term) {
  const content = document.getElementById('parent-child-data');
  try {
    const rows = await apiFetch(`/api/homework?pupil_id=${_parentCurrentChild}`);
    if (!rows.length) {
      content.innerHTML = '<div class="empty">No homework posted yet.</div>';
      return;
    }
    content.innerHTML = rows.map(row => `
      <div class="settings-card" style="margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
          <div>
            <div style="font-weight:700">${esc(row.title)}</div>
            <div class="text-sm text-muted">${esc(row.subject_name || 'General')} · Due ${esc(row.due_date || 'TBA')}</div>
          </div>
          <span class="badge ${row.is_done ? 'badge-active' : ''}" style="${row.is_done ? '' : 'background:#fef3c7;color:#92400e'}">${row.is_done ? 'Done' : 'Pending'}</span>
        </div>
        <div style="margin-top:8px;color:var(--gray-600)">${esc(row.description || 'No description provided.')}</div>
        <div style="margin-top:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <input id="hw-note-${row.id}" placeholder="Optional note" value="${esc(row.parent_note || '')}" style="flex:1;min-width:180px" />
          <button class="btn ${row.is_done ? 'btn-secondary' : 'btn-success'}" onclick="toggleHomeworkDone('${row.id}', '${_parentCurrentChild}', ${row.is_done ? 'false' : 'true'})">${row.is_done ? 'Mark Pending' : 'Mark Done'}</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    content.innerHTML = `<div class="empty">${err.message}</div>`;
  }
}

async function loadParentChildTimetable(term) {
  const content = document.getElementById('parent-child-data');
  try {
    const rows = await apiFetch(`/api/timetable?pupil_id=${_parentCurrentChild}`);
    if (!rows.length) return content.innerHTML = '<div class="empty">No timetable available yet.</div>';
    const grouped = {};
    rows.forEach(r => {
      grouped[r.day_of_week] = grouped[r.day_of_week] || [];
      grouped[r.day_of_week].push(r);
    });
    content.innerHTML = DAYS_OF_WEEK.map(day => `
      <div class="settings-card" style="margin-bottom:12px">
        <h4>${day}</h4>
        ${(grouped[day] || []).map(r => `<div class="timetable-row"><span>${esc(r.start_time || '--')} - ${esc(r.end_time || '--')}</span><strong>${esc(r.subject_name || r.period_name || 'Period')}</strong><span>${esc(r.teacher_name || '')}</span></div>`).join('') || '<div class="empty-state">No periods</div>'}
      </div>
    `).join('');
  } catch (err) {
    content.innerHTML = `<div class="empty">${err.message}</div>`;
  }
}

async function toggleHomeworkDone(homeworkId, pupilId, isDone) {
  try {
    await apiFetch(`/api/homework/${homeworkId}/complete`, {
      method: 'POST',
      body: JSON.stringify({
        pupil_id: pupilId,
        is_done: isDone,
        parent_note: document.getElementById(`hw-note-${homeworkId}`)?.value || ''
      })
    });
    showToast('Homework updated', 'success');
    loadParentChildTab('homework');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function startParentOnlinePayment(pupilId, termId) {
  try {
    const bill = await apiFetch(`/api/parent/child/${pupilId}/fees/term/${termId}`);
    const payments = bill.payments || [];
    const targetItem = (bill.fee_items || []).find(item => {
      const paid = payments.filter(p => p.fee_structure_id === item.id).reduce((s, p) => s + p.amount_paid, 0);
      const due = bill.is_new_pupil ? item.new_pupil_amount : item.returning_pupil_amount;
      return paid < due;
    });
    if (!targetItem) return showToast('No outstanding fee item found.', 'error');
    const res = await apiFetch('/api/fees/payments/initialize', {
      method: 'POST',
      body: JSON.stringify({ pupil_id: pupilId, term_id: termId, fee_structure_id: targetItem.id })
    });
    if (res.authorization_url) {
      window.open(res.authorization_url, '_blank');
      showToast('Payment window opened. After payment, the portal will try to confirm it automatically.', 'success');
    } else {
      await apiFetch('/api/fees/payments/verify', { method: 'POST', body: JSON.stringify({ reference: res.reference }) });
      showToast('Demo payment completed successfully.', 'success');
      loadParentChildFees(appData.terms.find(t => t.id === termId) || { id: termId });
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function populateClassDropdown(id, includeBlank = false) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = (includeBlank ? '<option value="">— Select Class —</option>' : '') +
    appData.classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
}

function populateTeacherDropdown(id) {
  const el = document.getElementById(id);
  if (!el) return apiFetch('/api/teachers').then(teachers => {
    el.innerHTML = teachers.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join('');
  });
}

async function loadEventsList() {
  const el = document.getElementById('events-list');
  if (!el) return;
  try {
    const events = await apiFetch('/api/events');
    el.innerHTML = events.length ? events.map(ev => `
      <div class="simple-list-row">
        <div><strong>${esc(ev.title)}</strong><div class="text-sm text-muted">${esc(ev.event_date)} · ${esc(ev.event_type || 'general')}</div></div>
        <div class="actions"><button class="btn-icon" onclick="openEventModal('${ev.id}')">✏️</button><button class="btn-icon" onclick="deleteEventItem('${ev.id}')">🗑️</button></div>
      </div>`).join('') : '<div class="empty-state">No events yet.</div>';
  } catch (err) { el.innerHTML = `<div class="empty-state">${esc(err.message)}</div>`; }
}

async function openEventModal(eventId = '') {
  let existing = null;
  if (eventId) existing = (await apiFetch('/api/events')).find(e => e.id === eventId);
  openModal(eventId ? 'Edit Event' : 'Add Event', `
    <form onsubmit="saveEventItem(event, '${eventId}')">
      <div class="form-group"><label>Title</label><input id="event-title" value="${existing ? esc(existing.title) : ''}" required /></div>
      <div class="form-grid">
        <div class="form-group"><label>Date</label><input type="date" id="event-date" value="${existing?.event_date || ''}" required /></div>
        <div class="form-group"><label>End Date</label><input type="date" id="event-end-date" value="${existing?.end_date || ''}" /></div>
      </div>
      <div class="form-grid">
        <div class="form-group"><label>Type</label><input id="event-type" value="${existing?.event_type || 'general'}" /></div>
        <div class="form-group"><label>Audience</label><select id="event-target"><option value="all">All</option><option value="parents">Parents</option><option value="teachers">Staff</option></select></div>
      </div>
      <div class="form-group"><label>Description</label><textarea id="event-description" rows="4">${existing?.description || ''}</textarea></div>
      <button class="btn btn-primary" type="submit">Save Event</button>
    </form>`);
  if (existing) document.getElementById('event-target').value = existing.target || 'all';
}

async function saveEventItem(event, eventId = '') {
  event.preventDefault();
  const payload = {
    title: document.getElementById('event-title').value,
    event_date: document.getElementById('event-date').value,
    end_date: document.getElementById('event-end-date').value,
    event_type: document.getElementById('event-type').value,
    target: document.getElementById('event-target').value,
    description: document.getElementById('event-description').value
  };
  try {
    await apiFetch(eventId ? `/api/events/${eventId}` : '/api/events', { method: eventId ? 'PUT' : 'POST', body: JSON.stringify(payload) });
    showToast('Event saved', 'success');
    closeModal();
    loadEventsList();
  } catch (err) { showToast(err.message, 'error'); }
}

async function deleteEventItem(eventId) {
  if (!confirm('Delete this event?')) return;
  try { await apiFetch(`/api/events/${eventId}`, { method: 'DELETE' }); showToast('Event deleted', 'success'); loadEventsList(); } catch (err) { showToast(err.message, 'error'); }
}

async function loadHomeworkAdminList() {
  const el = document.getElementById('homework-admin-list');
  if (!el) return;
  try {
    const items = await apiFetch('/api/homework');
    el.innerHTML = items.length ? items.slice(0, 10).map(item => `
      <div class="simple-list-row">
        <div><strong>${esc(item.title)}</strong><div class="text-sm text-muted">${esc(item.subject_name || 'General')} · Due ${esc(item.due_date || 'TBA')}</div></div>
        <div class="actions"><button class="btn-icon" onclick="openHomeworkModal('${item.id}')">✏️</button><button class="btn-icon" onclick="deleteHomeworkItem('${item.id}')">🗑️</button></div>
      </div>`).join('') : '<div class="empty-state">No homework posted.</div>';
  } catch (err) { el.innerHTML = `<div class="empty-state">${esc(err.message)}</div>`; }
}

async function openHomeworkModal(homeworkId = '') {
  let existing = null;
  if (homeworkId) existing = (await apiFetch('/api/homework')).find(h => h.id === homeworkId);
  populateClassDropdown('broadcast-class', true);
  openModal(homeworkId ? 'Edit Homework' : 'Add Homework', `
    <form onsubmit="saveHomeworkItem(event, '${homeworkId}')">
      <div class="form-group"><label>Title</label><input id="hw-title" value="${existing ? esc(existing.title) : ''}" required /></div>
      <div class="form-grid">
        <div class="form-group"><label>Class</label><select id="hw-class"></select></div>
        <div class="form-group"><label>Subject</label><select id="hw-subject"><option value="">General</option>${appData.subjects.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select></div>
      </div>
      <div class="form-group"><label>Due Date</label><input type="date" id="hw-due" value="${existing?.due_date || ''}" /></div>
      <div class="form-group"><label>Description</label><textarea id="hw-desc" rows="4">${existing?.description || ''}</textarea></div>
      <button class="btn btn-primary" type="submit">Save Homework</button>
    </form>`);
  populateClassDropdown('hw-class');
  if (existing) {
    document.getElementById('hw-class').value = existing.class_id || '';
    document.getElementById('hw-subject').value = existing.subject_id || '';
  }
}

async function saveHomeworkItem(event, homeworkId = '') {
  event.preventDefault();
  const payload = {
    title: document.getElementById('hw-title').value,
    class_id: document.getElementById('hw-class').value,
    subject_id: document.getElementById('hw-subject').value || null,
    due_date: document.getElementById('hw-due').value,
    description: document.getElementById('hw-desc').value
  };
  try {
    await apiFetch(homeworkId ? `/api/homework/${homeworkId}` : '/api/homework', { method: homeworkId ? 'PUT' : 'POST', body: JSON.stringify(payload) });
    showToast('Homework saved', 'success');
    closeModal();
    loadHomeworkAdminList();
  } catch (err) { showToast(err.message, 'error'); }
}

async function deleteHomeworkItem(homeworkId) {
  if (!confirm('Archive this homework item?')) return;
  try { await apiFetch(`/api/homework/${homeworkId}`, { method: 'DELETE' }); showToast('Homework archived', 'success'); loadHomeworkAdminList(); } catch (err) { showToast(err.message, 'error'); }
}

async function loadTimetableAdminList() {
  const el = document.getElementById('timetable-admin-list');
  if (!el) return;
  try {
    const cls = appData.classes[0];
    const rows = cls ? await apiFetch(`/api/timetable?class_id=${cls.id}`) : [];
    el.innerHTML = rows.length ? rows.slice(0, 10).map(r => `
      <div class="simple-list-row">
        <div><strong>${esc(r.day_of_week)} ${esc(r.start_time || '')}</strong><div class="text-sm text-muted">${esc(r.subject_name || r.period_name || 'Period')}</div></div>
        <div class="actions"><button class="btn-icon" onclick="openTimetableModal('${r.id}')">✏️</button><button class="btn-icon" onclick="deleteTimetableItem('${r.id}')">🗑️</button></div>
      </div>`).join('') : '<div class="empty-state">No timetable entries yet.</div>';
  } catch (err) { el.innerHTML = `<div class="empty-state">${esc(err.message)}</div>`; }
}

async function openTimetableModal(timetableId = '') {
  let existing = null;
  if (timetableId) {
    for (const cls of appData.classes) {
      const rows = await apiFetch(`/api/timetable?class_id=${cls.id}`);
      existing = rows.find(r => r.id === timetableId);
      if (existing) break;
    }
  }
  openModal(timetableId ? 'Edit Timetable Entry' : 'Add Timetable Entry', `
    <form onsubmit="saveTimetableItem(event, '${timetableId}')">
      <div class="form-grid">
        <div class="form-group"><label>Class</label><select id="tt-class"></select></div>
        <div class="form-group"><label>Day</label><select id="tt-day">${DAYS_OF_WEEK.map(d => `<option value="${d}">${d}</option>`).join('')}</select></div>
      </div>
      <div class="form-grid">
        <div class="form-group"><label>Subject</label><select id="tt-subject"><option value="">General</option>${appData.subjects.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select></div>
        <div class="form-group"><label>Period Name</label><input id="tt-period" value="${existing?.period_name || ''}" /></div>
      </div>
      <div class="form-grid">
        <div class="form-group"><label>Start Time</label><input type="time" id="tt-start" value="${existing?.start_time || ''}" /></div>
        <div class="form-group"><label>End Time</label><input type="time" id="tt-end" value="${existing?.end_time || ''}" /></div>
      </div>
      <div class="form-grid">
        <div class="form-group"><label>Teacher Name</label><input id="tt-teacher" value="${existing?.teacher_name || ''}" /></div>
        <div class="form-group"><label>Location</label><input id="tt-location" value="${existing?.location || ''}" /></div>
      </div>
      <button class="btn btn-primary" type="submit">Save Entry</button>
    </form>`);
  populateClassDropdown('tt-class');
  if (existing) {
    document.getElementById('tt-class').value = existing.class_id || '';
    document.getElementById('tt-day').value = existing.day_of_week || 'Monday';
    document.getElementById('tt-subject').value = existing.subject_id || '';
  }
}

async function saveTimetableItem(event, timetableId = '') {
  event.preventDefault();
  const payload = {
    class_id: document.getElementById('tt-class').value,
    day_of_week: document.getElementById('tt-day').value,
    subject_id: document.getElementById('tt-subject').value || null,
    period_name: document.getElementById('tt-period').value,
    start_time: document.getElementById('tt-start').value,
    end_time: document.getElementById('tt-end').value,
    teacher_name: document.getElementById('tt-teacher').value,
    location: document.getElementById('tt-location').value
  };
  try {
    await apiFetch(timetableId ? `/api/timetable/${timetableId}` : '/api/timetable', { method: timetableId ? 'PUT' : 'POST', body: JSON.stringify(payload) });
    showToast('Timetable saved', 'success');
    closeModal();
    loadTimetableAdminList();
  } catch (err) { showToast(err.message, 'error'); }
}

async function deleteTimetableItem(timetableId) {
  if (!confirm('Delete this timetable entry?')) return;
  try { await apiFetch(`/api/timetable/${timetableId}`, { method: 'DELETE' }); showToast('Timetable deleted', 'success'); loadTimetableAdminList(); } catch (err) { showToast(err.message, 'error'); }
}

async function loadPayrollList() {
  const el = document.getElementById('payroll-list');
  if (!el) return;
  try {
    const rows = await apiFetch('/api/payroll');
    el.innerHTML = rows.length ? rows.slice(0, 10).map(r => `
      <div class="simple-list-row">
        <div><strong>${esc(r.staff_name)}</strong><div class="text-sm text-muted">${r.month}/${r.year}</div></div>
        <div class="text-success">₦${Number(r.net_pay || 0).toLocaleString()}</div>
      </div>`).join('') : '<div class="empty-state">No payroll entries yet.</div>';
  } catch (err) { el.innerHTML = `<div class="empty-state">${esc(err.message)}</div>`; }
}

async function openPayrollModal() {
  const teachers = await apiFetch('/api/teachers');
  openModal('Add Payroll Entry', `
    <form onsubmit="savePayrollEntry(event)">
      <div class="form-grid">
        <div class="form-group"><label>Staff</label><select id="payroll-staff">${teachers.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join('')}</select></div>
        <div class="form-group"><label>Month</label><input type="number" id="payroll-month" min="1" max="12" value="${new Date().getMonth() + 1}" /></div>
      </div>
      <div class="form-grid">
        <div class="form-group"><label>Year</label><input type="number" id="payroll-year" value="${new Date().getFullYear()}" /></div>
        <div class="form-group"><label>Basic Salary</label><input type="number" id="payroll-basic" min="0" value="0" /></div>
      </div>
      <div class="form-grid">
        <div class="form-group"><label>Allowances</label><input type="number" id="payroll-allowances" min="0" value="0" /></div>
        <div class="form-group"><label>Deductions</label><input type="number" id="payroll-deductions" min="0" value="0" /></div>
      </div>
      <div class="form-group"><label>Notes</label><textarea id="payroll-notes" rows="3"></textarea></div>
      <button class="btn btn-primary" type="submit">Save Payroll</button>
    </form>`);
}

async function savePayrollEntry(event) {
  event.preventDefault();
  try {
    const res = await apiFetch('/api/payroll', {
      method: 'POST',
      body: JSON.stringify({
        staff_id: document.getElementById('payroll-staff').value,
        month: Number(document.getElementById('payroll-month').value),
        year: Number(document.getElementById('payroll-year').value),
        basic_salary: Number(document.getElementById('payroll-basic').value || 0),
        allowances: Number(document.getElementById('payroll-allowances').value || 0),
        deductions: Number(document.getElementById('payroll-deductions').value || 0),
        notes: document.getElementById('payroll-notes').value
      })
    });
    showToast(`Payroll saved • Net pay ₦${Number(res.net_pay || 0).toLocaleString()}`, 'success');
    closeModal();
    loadPayrollList();
  } catch (err) { showToast(err.message, 'error'); }
}

async function sendBroadcastMessage() {
  try {
    const res = await apiFetch('/api/broadcast', {
      method: 'POST',
      body: JSON.stringify({
        target: document.getElementById('broadcast-target')?.value,
        class_id: document.getElementById('broadcast-class')?.value || null,
        channel: document.getElementById('broadcast-channel')?.value,
        message: document.getElementById('broadcast-message')?.value
      })
    });
    showToast(res.message, 'success');
    if (document.getElementById('broadcast-message')) document.getElementById('broadcast-message').value = '';
  } catch (err) { showToast(err.message, 'error'); }
}

async function runAcademicRollover() {
  if (!confirm('Run the academic year rollover wizard? This promotes pupils and creates next year terms.')) return;
  try {
    const res = await apiFetch('/api/rollover', {
      method: 'POST',
      body: JSON.stringify({ next_academic_year: document.getElementById('rollover-year')?.value || '' })
    });
    showToast(`${res.message} • Promoted: ${res.promoted}, Graduated: ${res.graduated}`, 'success');
    loadSettings();
    loadClasses();
  } catch (err) { showToast(err.message, 'error'); }
}

async function downloadReportPdf(pupilId, termId) {
  const token = localStorage.getItem('token');
  const res = await fetch(`/api/pupils/${pupilId}/report-pdf/term/${termId}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) return showToast('Failed to download report PDF', 'error');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'report-card.pdf';
  a.click();
  URL.revokeObjectURL(url);
}

async function downloadFeeReceiptPdf(pupilId, termId) {
  const token = localStorage.getItem('token');
  const res = await fetch(`/api/pupils/${pupilId}/receipt-pdf/term/${termId}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) return showToast('Failed to download receipt PDF', 'error');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'fee-receipt.pdf';
  a.click();
  URL.revokeObjectURL(url);
}

function toggleDarkMode(enabled) {
  document.body.classList.toggle('dark-mode', enabled);
  localStorage.setItem('darkMode', enabled ? '1' : '0');
}

function applyStoredTheme() {
  const enabled = localStorage.getItem('darkMode') === '1';
  document.body.classList.toggle('dark-mode', enabled);
  const toggle = document.getElementById('dark-mode-toggle');
  if (toggle) toggle.checked = enabled;
}

function registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
}

async function _parentGenerateReport(termId) {
  // Temporarily set profile-term-select value (needed by generateReport)
  // We use the direct API instead
  try {
    const data = await apiFetch(`/api/report/pupil/${_parentCurrentChild}/term/${termId}`);
    renderReportCard(data);
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function _parentGenerateLowerReport(termId) {
  try {
    const data = await apiFetch(`/api/report/lower/${_parentCurrentChild}/term/${termId}`);
    renderLowerSchoolReport(data);
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function loadParentChildAcknowledge(term) {
  const content = document.getElementById('parent-child-data');
  try {
    const data = await apiFetch(`/api/parent/child/${_parentCurrentChild}/results?term_id=${term.id}`);
    const ack = data.acknowledgment;
    const results = data.results || [];

    content.innerHTML = `
      <div style="background:white;border:1px solid var(--gray-200);border-radius:8px;padding:20px">
        <h4 style="font-size:15px;font-weight:600;color:#1f2937;margin-bottom:8px">Acknowledge Results — ${term.academic_year} Term ${term.term_number}</h4>
        <p style="font-size:13px;color:var(--gray-500);margin-bottom:16px">
          Please confirm that you have reviewed your child's results for this term. You can also leave a comment for the school.
        </p>
        ${!results.length ? `<div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:10px 14px;font-size:13px;color:#78350f;margin-bottom:16px">
          ⚠️ No results have been entered yet for this term. You can still acknowledge when they are available.
        </div>` : ''}
        ${ack ? `<div style="background:#dcfce7;border:1px solid #86efac;border-radius:6px;padding:12px 14px;margin-bottom:16px">
          <div style="font-size:13px;font-weight:600;color:#15803d">✅ Acknowledged</div>
          <div style="font-size:12px;color:#166534;margin-top:4px">
            On ${new Date(ack.acknowledged_at).toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric'})}
          </div>
          ${ack.parent_comment ? `<div style="font-size:12px;color:#166534;margin-top:6px;font-style:italic">"${ack.parent_comment}"</div>` : ''}
          <div style="margin-top:10px;font-size:12px;color:#166534">You can update your comment below:</div>
        </div>` : `<div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:10px 14px;font-size:13px;color:#78350f;margin-bottom:16px">
          ⏳ Not yet acknowledged for this term
        </div>`}
        <form onsubmit="submitAcknowledgment(event,'${_parentCurrentChild}','${term.id}')">
          <div class="form-group">
            <label>Your Comment to the School <span style="color:var(--gray-400);font-weight:400">(optional)</span></label>
            <textarea id="ack-comment" rows="3" placeholder="e.g. We are happy with the progress shown. Please keep it up." style="width:100%;font-size:13px;padding:8px;border:1px solid var(--gray-200);border-radius:6px">${ack ? (ack.parent_comment || '') : ''}</textarea>
          </div>
          <button type="submit" class="btn btn-primary">
            ${ack ? '💾 Update Acknowledgment' : '✅ Acknowledge Results'}
          </button>
        </form>
      </div>`;
  } catch (err) {
    content.innerHTML = `<div class="empty">Failed: ${err.message}</div>`;
  }
}

async function submitAcknowledgment(event, pupilId, termId) {
  event.preventDefault();
  const comment = document.getElementById('ack-comment').value;
  try {
    await apiFetch('/api/parent/acknowledge', {
      method: 'POST',
      body: JSON.stringify({ pupil_id: pupilId, term_id: termId, comment })
    });
    showToast('Acknowledgment saved! Thank you.');
    loadParentChildAcknowledge(appData.terms.find(t => t.id === termId) || { id: termId });
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function loadParentNotices() {
  const el = document.getElementById('parent-notices-list');
  el.innerHTML = '<div class="loading">Loading notices…</div>';
  try {
    const notices = await apiFetch('/api/notices');
    if (!notices.length) {
      el.innerHTML = '<div class="empty">No notices at this time. Check back soon.</div>';
      return;
    }
    el.innerHTML = notices.map(n => `
      <div style="background:white;border:1px solid var(--gray-200);border-radius:8px;padding:16px 20px;margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
          <div>
            <div style="font-size:15px;font-weight:700;color:#1f2937">${esc(n.title)}</div>
            <div style="font-size:12px;color:var(--gray-400);margin-top:2px">
              Posted by ${esc(n.posted_by)} · ${new Date(n.posted_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})}
              ${n.target === 'parents' ? '<span class="badge" style="margin-left:6px;background:#fef9c3;color:#78350f">Parents</span>' : ''}
            </div>
          </div>
          <span style="font-size:24px">📢</span>
        </div>
        <div style="margin-top:10px;font-size:13px;color:#374151;line-height:1.6;border-top:1px solid var(--gray-100);padding-top:10px">${n.body.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br/>')}</div>
      </div>`).join('');
  } catch (err) {
    el.innerHTML = `<div class="empty">Failed to load: ${err.message}</div>`;
  }
}

// ─── ADMIN: PARENT ACCOUNTS ───────────────────────────────────────────────────

async function loadParentAccountsList() {
  const el = document.getElementById('parent-accounts-list');
  if (!el) return;
  try {
    const parents = await apiFetch('/api/parent-accounts');
    if (!parents.length) {
      el.innerHTML = '<div class="empty" style="font-size:12px;padding:8px">No parent accounts yet.</div>';
      return;
    }
    el.innerHTML = parents.map(p => `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--gray-100)">
        <div>
          <div style="font-size:13px;font-weight:600">${esc(p.name)}</div>
          <div style="font-size:11px;color:var(--gray-400)">${esc(p.email)}</div>
          <div style="font-size:11px;color:var(--gray-400)">${p.children.map(c=>esc(c.first_name)+' '+esc(c.last_name)).join(', ') || 'No linked children'}</div>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          <span class="badge ${p.is_active ? 'badge-active' : ''}" style="${!p.is_active?'background:#fee2e2;color:#dc2626':''}">
            ${p.is_active ? 'Active' : 'Inactive'}
          </span>
          <button class="btn-icon" onclick="openParentAccountModal('${p.id}')" title="Edit">✏️</button>
          <button class="btn-icon" onclick="deleteParentAccount('${p.id}')" title="Delete">🗑️</button>
        </div>
      </div>`).join('');
  } catch (err) {
    el.innerHTML = `<div class="empty" style="font-size:12px">Error: ${err.message}</div>`;
  }
}

async function loadReadinessStatus() {
  const el = document.getElementById('readiness-list');
  if (!el) return;
  try {
    const report = await apiFetch('/api/admin/readiness');
    const summary = report.summary || { ok: 0, warning: 0, error: 0 };
    const checks = report.checks || [];
    const pill = (label, value, color) => `
      <span style="display:inline-block;padding:4px 8px;border-radius:999px;font-size:12px;font-weight:600;background:${color};color:white">${label}: ${value}</span>`;
    el.innerHTML = `
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">
        ${pill('OK', summary.ok || 0, '#15803d')}
        ${pill('Warnings', summary.warning || 0, '#d97706')}
        ${pill('Errors', summary.error || 0, '#dc2626')}
      </div>
      <div style="font-size:12px;color:var(--gray-500);margin-bottom:10px">
        Environment: <strong>${esc(report.environment || 'unknown')}</strong>
        ${report.bootstrap?.message ? ` · ${esc(report.bootstrap.message)}` : ''}
      </div>
      <div style="max-height:260px;overflow:auto">
        ${(checks.length ? checks : []).map(check => {
          const tone = check.status === 'ok' ? '#15803d' : check.status === 'warning' ? '#d97706' : '#dc2626';
          return `
            <div style="border-bottom:1px solid var(--gray-100);padding:8px 0">
              <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
                <strong style="font-size:13px">${esc(check.label)}</strong>
                <span style="font-size:11px;font-weight:700;color:${tone};text-transform:uppercase">${esc(check.status)}</span>
              </div>
              <div style="font-size:12px;color:var(--gray-500);margin-top:4px">${esc(check.message)}</div>
            </div>`;
        }).join('') || '<div class="empty-state">No readiness information available.</div>'}
      </div>`;
  } catch (err) {
    el.innerHTML = `<div class="empty-state">${esc(err.message)}</div>`;
  }
}

async function loadBackupList() {
  const el = document.getElementById('backup-list');
  if (!el) return;
  try {
    const data = await apiFetch('/api/admin/backups');
    const backups = data.backups || [];
    el.innerHTML = backups.length ? `
      <div style="max-height:300px;overflow:auto">
        ${backups.map(item => `
          <div style="border-bottom:1px solid var(--gray-100);padding:8px 0;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <div style="flex:1;min-width:0">
              <div style="font-size:13px;font-weight:600;word-break:break-all">${esc(item.filename)}</div>
              <div style="font-size:12px;color:var(--gray-500)">${new Date(item.modified_at).toLocaleString()} &mdash; ${(Number(item.size || 0) / 1024).toFixed(1)} KB</div>
            </div>
            <button class="btn btn-sm btn-secondary" onclick="downloadBackup('${esc(item.filename)}')">Download</button>
            <button class="btn btn-sm btn-danger" onclick="restoreBackup('${esc(item.filename)}')">Restore</button>
          </div>`).join('')}
      </div>` : '<div class="empty-state">No backups created yet.</div>';
  } catch (err) {
    el.innerHTML = `<div class="empty-state">${esc(err.message)}</div>`;
  }
}

async function createSystemBackup() {
  try {
    const label = document.getElementById('backup-label')?.value || '';
    const res = await apiFetch('/api/admin/backups', {
      method: 'POST',
      body: JSON.stringify({ label })
    });
    showToast(res.message || 'Backup created', 'success');
    if (document.getElementById('backup-label')) document.getElementById('backup-label').value = '';
    loadBackupList();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function downloadBackup(filename) {
  try {
    const token = localStorage.getItem('token');
    const res = await fetch(`/api/admin/backups/${encodeURIComponent(filename)}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Download failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function restoreBackup(filename) {
  if (!confirm(`Restore database from "${filename}"?\n\nA safety backup of the current database will be created first.\nThe page will reload after the restore completes.`)) return;
  try {
    const res = await apiFetch(`/api/admin/backups/${encodeURIComponent(filename)}/restore`, { method: 'POST' });
    showToast((res.message || 'Database restored') + ' Reloading…', 'success', 0);
    setTimeout(() => window.location.reload(), 3000);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function restoreFromUpload() {
  const input = document.getElementById('restore-upload-input');
  if (!input || !input.files[0]) return showToast('Please select a .db file first', 'error');
  const file = input.files[0];
  if (!file.name.endsWith('.db')) return showToast('File must be a .db (SQLite) file', 'error');
  if (!confirm(`Restore database from "${file.name}"?\n\nA safety backup of the current database will be created first.\nThe page will reload after the restore completes.`)) return;
  try {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = '';
    const chunkSize = 8192;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
    }
    const res = await apiFetch('/api/admin/restore-upload', {
      method: 'POST',
      body: JSON.stringify({ data: btoa(binary) })
    });
    showToast((res.message || 'Database restored') + ' Reloading…', 'success', 0);
    setTimeout(() => window.location.reload(), 3000);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openParentAccountModal(parentId = '') {
  let existing = null;
  if (parentId) {
    const parents = await apiFetch('/api/parent-accounts');
    existing = parents.find(p => p.id === parentId);
  }
  openModal(parentId ? 'Edit Parent Account' : 'Add Parent Account', `
    <form onsubmit="saveParentAccount(event,'${parentId}')">
      <div class="form-grid">
        <div class="form-group">
          <label>Full Name *</label>
          <input type="text" name="name" value="${existing ? existing.name : ''}" required />
        </div>
        <div class="form-group">
          <label>Email Address * <span style="font-size:11px;color:var(--gray-400)">(must match parent email on pupil record)</span></label>
          <input type="email" name="email" value="${existing ? existing.email : ''}" ${existing ? 'readonly style="background:var(--gray-50)"' : ''} required />
        </div>
        <div class="form-group">
          <label>Phone</label>
          <input type="text" name="phone" value="${existing ? (existing.phone||'') : ''}" />
        </div>
        <div class="form-group">
          <label>${existing ? 'New Password' : 'Password *'} <span style="font-size:11px;color:var(--gray-400)">${existing ? '(leave blank to keep current)' : ''}</span></label>
          <input type="password" name="password" ${!existing ? 'required' : ''} minlength="6" />
        </div>
      </div>
      ${existing ? `<div class="form-group">
        <label><input type="checkbox" name="is_active" style="margin-right:6px" ${existing.is_active?'checked':''}> Account Active</label>
      </div>` : ''}
      <button type="submit" class="btn btn-primary">💾 Save Account</button>
    </form>`);
}

async function saveParentAccount(event, parentId) {
  event.preventDefault();
  const form = event.target;
  const fd = new FormData(form);
  const payload = {
    name: fd.get('name'),
    email: fd.get('email'),
    phone: fd.get('phone') || '',
    password: fd.get('password') || ''
  };
  if (parentId) {
    payload.is_active = fd.has('is_active') ? 1 : 0;
  }
  try {
    if (parentId) {
      await apiFetch(`/api/parent-accounts/${parentId}`, { method: 'PUT', body: JSON.stringify(payload) });
    } else {
      await apiFetch('/api/parent-accounts', { method: 'POST', body: JSON.stringify(payload) });
    }
    showToast('Parent account saved!');
    closeModal();
    loadParentAccountsList();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function deleteParentAccount(parentId) {
  if (!confirm('Delete this parent account? They will no longer be able to log in.')) return;
  try {
    await apiFetch(`/api/parent-accounts/${parentId}`, { method: 'DELETE' });
    showToast('Account deleted');
    loadParentAccountsList();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ─── ADMIN: SCHOOL NOTICES ────────────────────────────────────────────────────

async function loadNoticesAdminList() {
  const el = document.getElementById('notices-admin-list');
  if (!el) return;
  try {
    const notices = await apiFetch('/api/notices');
    if (!notices.length) {
      el.innerHTML = '<div class="empty" style="font-size:12px;padding:8px">No notices posted yet.</div>';
      return;
    }
    el.innerHTML = notices.map(n => `
      <div style="display:flex;align-items:flex-start;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--gray-100);gap:10px">
        <div style="flex:1">
          <div style="font-size:13px;font-weight:600">${esc(n.title)}</div>
          <div style="font-size:11px;color:var(--gray-400)">
            ${new Date(n.posted_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})} ·
            ${n.target === 'parents' ? 'Parents only' : n.target === 'teachers' ? 'Staff only' : 'Everyone'}
            · ${n.is_active ? '<span style="color:#15803d">Active</span>' : '<span style="color:#dc2626">Hidden</span>'}
          </div>
        </div>
        <div style="display:flex;gap:4px;flex-shrink:0">
          <button class="btn-icon" onclick="openNoticeModal('${n.id}')" title="Edit">✏️</button>
          <button class="btn-icon" onclick="deleteNotice('${n.id}')" title="Delete">🗑️</button>
        </div>
      </div>`).join('');
  } catch (err) {
    el.innerHTML = `<div class="empty" style="font-size:12px">Error: ${err.message}</div>`;
  }
}

async function openNoticeModal(noticeId = '') {
  let existing = null;
  if (noticeId) {
    const notices = await apiFetch('/api/notices');
    existing = notices.find(n => n.id === noticeId);
  }
  openModal(noticeId ? 'Edit Notice' : 'Post New Notice', `
    <form onsubmit="saveNotice(event,'${noticeId}')">
      <div class="form-group">
        <label>Title *</label>
        <input type="text" name="title" value="${existing ? existing.title : ''}" required placeholder="e.g. End of Term Party — Friday 20th" />
      </div>
      <div class="form-group">
        <label>Notice Body *</label>
        <textarea name="body" rows="5" required style="width:100%;font-size:13px;padding:8px;border:1px solid var(--gray-200);border-radius:6px" placeholder="Write the full notice here…">${existing ? existing.body : ''}</textarea>
      </div>
      <div class="form-grid">
        <div class="form-group">
          <label>Audience</label>
          <select name="target">
            <option value="all" ${(!existing||existing.target==='all')?'selected':''}>Everyone (Parents + Staff)</option>
            <option value="parents" ${existing&&existing.target==='parents'?'selected':''}>Parents Only</option>
            <option value="teachers" ${existing&&existing.target==='teachers'?'selected':''}>Staff Only</option>
          </select>
        </div>
        ${existing ? `<div class="form-group">
          <label>Visibility</label>
          <select name="is_active">
            <option value="1" ${existing.is_active?'selected':''}>Active (visible)</option>
            <option value="0" ${!existing.is_active?'selected':''}>Hidden</option>
          </select>
        </div>` : ''}
      </div>
      <button type="submit" class="btn btn-primary">📢 ${noticeId ? 'Update' : 'Post'} Notice</button>
    </form>`);
}

async function saveNotice(event, noticeId) {
  event.preventDefault();
  const form = event.target;
  const fd = new FormData(form);
  const payload = {
    title: fd.get('title'),
    body: fd.get('body'),
    target: fd.get('target') || 'all'
  };
  if (noticeId && fd.get('is_active') !== null) {
    payload.is_active = fd.get('is_active') === '1' ? 1 : 0;
  }
  try {
    if (noticeId) {
      await apiFetch(`/api/notices/${noticeId}`, { method: 'PUT', body: JSON.stringify(payload) });
    } else {
      await apiFetch('/api/notices', { method: 'POST', body: JSON.stringify(payload) });
    }
    showToast('Notice saved!');
    closeModal();
    loadNoticesAdminList();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function deleteNotice(noticeId) {
  if (!confirm('Delete this notice?')) return;
  try {
    await apiFetch(`/api/notices/${noticeId}`, { method: 'DELETE' });
    showToast('Notice deleted');
    loadNoticesAdminList();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ─── TOAST ────────────────────────────────────────────────────────────────────

function showToast(message, type = 'success', duration) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast toast-${type}`;
  toast.classList.remove('hidden');
  clearTimeout(showToast._timer);
  // duration=0 means stay until dismissed; omitted/undefined = 3500ms default
  const ms = duration === 0 ? null : (duration != null ? duration : 3500);
  if (ms != null) {
    showToast._timer = setTimeout(() => { toast.classList.add('hidden'); toast.onclick = null; }, ms);
  }
}

// ─── INIT ─────────────────────────────────────────────────────────────────────

initAuth();
