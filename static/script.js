const state = { students: {}, teachers: {}, vans: {} };
let currentPeriod = 'AM';
let sortables = [];
let isDragging = false;
let lastStateJSON = null;
let pollTimer = null;
const POLL_INTERVAL_MS = 3000;

function periodKey() {
  return currentPeriod === 'AM' ? 'am_van' : 'pm_van';
}

async function api(endpoint, body) {
  const res = await fetch(`/api/${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}

async function fetchState() {
  const res = await fetch('/api/state');
  return res.json();
}

function showMessage(msg, isError) {
  const banner = document.getElementById('banner');
  banner.textContent = msg;
  banner.hidden = false;
  banner.classList.toggle('banner--error', !!isError);
}

function looksLikeError(msg) {
  const m = msg.toLowerCase();
  return (
    m.includes('cannot') ||
    m.includes('not ') ||
    m.includes('does not') ||
    m.includes('already') ||
    m.includes('blank') ||
    m.includes('must')
  );
}

function destroySortables() {
  sortables.forEach((s) => s.destroy());
  sortables = [];
}

function makeChip(name, opts) {
  const li = document.createElement('li');
  li.className = 'chip';
  li.dataset.name = name;
  if (opts.absent) li.classList.add('chip--absent');

  const label = document.createElement('span');
  label.textContent = name;
  li.appendChild(label);

  const actions = document.createElement('div');
  actions.className = 'chip__actions';

  if (opts.onToggle) {
    const toggle = document.createElement('button');
    toggle.className = 'chip__toggle';
    toggle.type = 'button';
    toggle.textContent = opts.toggleLabel;
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      opts.onToggle();
    });
    actions.appendChild(toggle);
  }

  const del = document.createElement('button');
  del.className = 'chip__del';
  del.type = 'button';
  del.title = opts.delTitle;
  del.textContent = '\u00d7';
  del.addEventListener('click', (e) => {
    e.stopPropagation();
    opts.onDelete();
  });
  actions.appendChild(del);
  li.appendChild(actions);

  return li;
}

function seatDots(periodData, capacity) {
  const dots = [];
  for (let i = 0; i < periodData.teachers.length; i++) dots.push('teacher');
  for (let i = 0; i < periodData.students.length; i++) dots.push('student');
  const empty = Math.max(0, capacity - dots.length);
  for (let i = 0; i < empty; i++) dots.push('empty');
  return dots;
}

// applyState() records new data from the server. renderUI() rebuilds the
// DOM from whatever's currently in `state`, for the currently-selected
// period. Keeping these separate means switching AM/PM doesn't need a
// server round trip — both periods are always present in `state` already.

function applyState(newState) {
  Object.assign(state, newState);
  lastStateJSON = JSON.stringify(state);
}

function render(newState) {
  applyState(newState);
  renderUI();
}

function renderUI() {
  destroySortables();

  const pKey = periodKey();

  // ── Roster: students ──
  const studentList = document.getElementById('roster-students-list');
  studentList.innerHTML = '';
  let studentCount = 0;
  Object.entries(state.students).forEach(([name, data]) => {
    if (data[pKey]) return; // assigned in the period currently being viewed
    studentCount++;
    studentList.appendChild(
      makeChip(name, {
        absent: !data.present,
        delTitle: 'Delete student',
        toggleLabel: data.present ? 'Mark absent' : 'Mark present',
        onToggle: async () => {
          const res = await api('toggle_attendance', { name });
          showMessage(res.message, looksLikeError(res.message));
          render(res.state);
        },
        onDelete: async () => {
          const res = await api('delete_student', { name });
          showMessage(res.message, looksLikeError(res.message));
          render(res.state);
        },
      })
    );
  });
  document.getElementById('studentCount').textContent = studentCount;

  // ── Roster: teachers ──
  const teacherList = document.getElementById('roster-teachers-list');
  teacherList.innerHTML = '';
  let teacherCount = 0;
  Object.entries(state.teachers).forEach(([name, data]) => {
    if (data[pKey]) return;
    teacherCount++;
    teacherList.appendChild(
      makeChip(name, {
        delTitle: 'Delete teacher',
        onDelete: async () => {
          const res = await api('delete_teacher', { name });
          showMessage(res.message, looksLikeError(res.message));
          render(res.state);
        },
      })
    );
  });
  document.getElementById('teacherCount').textContent = teacherCount;

  // ── Vans ──
  const grid = document.getElementById('vanGrid');
  grid.innerHTML = '';
  Object.entries(state.vans).forEach(([vanName, van], idx) => {
    const periodData = currentPeriod === 'AM' ? van.am : van.pm;

    const card = document.createElement('div');
    card.className = 'van-card';
    card.dataset.van = vanName;

    const header = document.createElement('div');
    header.className = 'van-card__header';

    const title = document.createElement('div');
    title.className = 'van-card__title';
    const handle = document.createElement('span');
    handle.className = 'van-card__handle';
    handle.title = 'Drag to reorder';
    handle.textContent = '\u283F';
    title.appendChild(handle);
    const nameEl = document.createElement('span');
    nameEl.className = 'van-card__name';
    nameEl.textContent = vanName;
    title.appendChild(nameEl);
    header.appendChild(title);

    const headerRight = document.createElement('div');
    headerRight.className = 'van-card__header-right';
    const occ = document.createElement('span');
    occ.className =
      'van-card__occupancy' +
      (periodData.occupants >= van.capacity ? ' van-card__occupancy--full' : '');
    occ.textContent = `${periodData.occupants}/${van.capacity}`;
    headerRight.appendChild(occ);
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'van-card__delete';
    deleteBtn.type = 'button';
    deleteBtn.title = 'Delete van';
    deleteBtn.textContent = '\u00d7';
    deleteBtn.addEventListener('click', async () => {
      const totalOccupants = van.am.occupants + van.pm.occupants;
      const confirmMsg =
        totalOccupants > 0
          ? `Delete ${vanName}? ${totalOccupants} AM/PM assignment(s) will be cleared.`
          : `Delete ${vanName}?`;
      if (!confirm(confirmMsg)) return;
      const res = await api('delete_van', { name: vanName });
      showMessage(res.message, looksLikeError(res.message));
      render(res.state);
    });
    headerRight.appendChild(deleteBtn);
    header.appendChild(headerRight);

    card.appendChild(header);

    const strip = document.createElement('div');
    strip.className = 'seat-strip';
    seatDots(periodData, van.capacity).forEach((kind) => {
      const dot = document.createElement('span');
      dot.className = 'seat-dot' + (kind !== 'empty' ? ` seat-dot--${kind}` : '');
      strip.appendChild(dot);
    });
    card.appendChild(strip);

    const teacherLabel = document.createElement('div');
    teacherLabel.className = 'van-card__section-label';
    teacherLabel.textContent = 'Teachers';
    card.appendChild(teacherLabel);

    const teacherZone = document.createElement('ul');
    teacherZone.className = 'van-card__dropzone';
    teacherZone.id = `van-${idx}-teachers`;
    teacherZone.dataset.context = 'van';
    teacherZone.dataset.van = vanName;
    teacherZone.dataset.type = 'teacher';
    periodData.teachers.forEach((name) => {
      teacherZone.appendChild(
        makeChip(name, {
          delTitle: 'Remove from van',
          onDelete: async () => {
            const res = await api('remove_teacher', { teacher: name, period: currentPeriod });
            showMessage(res.message, looksLikeError(res.message));
            render(res.state);
          },
        })
      );
    });
    card.appendChild(teacherZone);

    const studentLabel = document.createElement('div');
    studentLabel.className = 'van-card__section-label';
    studentLabel.textContent = 'Students';
    card.appendChild(studentLabel);

    const studentZone = document.createElement('ul');
    studentZone.className = 'van-card__dropzone';
    studentZone.id = `van-${idx}-students`;
    studentZone.dataset.context = 'van';
    studentZone.dataset.van = vanName;
    studentZone.dataset.type = 'student';
    periodData.students.forEach((name) => {
      studentZone.appendChild(
        makeChip(name, {
          delTitle: 'Remove from van',
          onDelete: async () => {
            const res = await api('remove_student', { student: name, period: currentPeriod });
            showMessage(res.message, looksLikeError(res.message));
            render(res.state);
          },
        })
      );
    });
    card.appendChild(studentZone);

    grid.appendChild(card);
  });

  initSortables();
}

function initSortables() {
  const lists = document.querySelectorAll('[data-type]');
  lists.forEach((list) => {
    const type = list.dataset.type;
    const s = new Sortable(list, {
      group: { name: type, pull: true, put: true },
      animation: 150,
      // forceFallback gives identical, touch-friendly behavior on phones/tablets
      // as well as desktop mouse, instead of relying on native HTML5 DnD
      // (which does not support touch at all).
      forceFallback: true,
      fallbackTolerance: 3,
      onStart: () => {
        isDragging = true;
      },
      onEnd: (evt) => {
        isDragging = false;
        handleMove(evt, type);
      },
    });
    sortables.push(s);
  });

  // Reordering the vans themselves is a separate Sortable instance, scoped
  // to only start dragging from the ⠿ handle — otherwise it would conflict
  // with dragging student/teacher chips around inside each card.
  const grid = document.getElementById('vanGrid');
  const gridSortable = new Sortable(grid, {
    handle: '.van-card__handle',
    animation: 150,
    forceFallback: true,
    fallbackTolerance: 3,
    onStart: () => {
      isDragging = true;
    },
    onEnd: async (evt) => {
      isDragging = false;
      if (evt.oldIndex === evt.newIndex) return;
      const order = Array.from(grid.children).map((card) => card.dataset.van);
      const res = await api('reorder_vans', { order });
      render(res.state);
    },
  });
  sortables.push(gridSortable);
}

async function handleMove(evt, personType) {
  if (evt.from === evt.to) return; // reordered in place, nothing to persist

  const name = evt.item.dataset.name;
  const fromCtx = evt.from.dataset.context;
  const toCtx = evt.to.dataset.context;
  const toVan = evt.to.dataset.van;

  let result;
  if (fromCtx === 'van') {
    result = await api(`remove_${personType}`, { [personType]: name, period: currentPeriod });
  }
  if (toCtx === 'van') {
    result = await api(`assign_${personType}`, {
      [personType]: name,
      van: toVan,
      period: currentPeriod,
    });
  }
  if (result) {
    showMessage(result.message, looksLikeError(result.message));
    render(result.state);
  }
}

// ── AM/PM period switch ──

document.querySelectorAll('.period-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    if (btn.dataset.period === currentPeriod) return;
    currentPeriod = btn.dataset.period;
    document.querySelectorAll('.period-btn').forEach((b) => {
      const active = b === btn;
      b.classList.toggle('period-btn--active', active);
      b.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    document.getElementById('periodLabel').textContent = currentPeriod;
    renderUI();
  });
});

// ── Forms & buttons ──

document.getElementById('addStudentForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('studentNameInput');
  const present = document.getElementById('studentPresentInput').checked;
  const name = input.value.trim();
  if (!name) return;
  const res = await api('add_student', { name, present });
  showMessage(res.message, looksLikeError(res.message));
  if (!looksLikeError(res.message)) input.value = '';
  render(res.state);
});

document.getElementById('addTeacherForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('teacherNameInput');
  const name = input.value.trim();
  if (!name) return;
  const res = await api('add_teacher', { name });
  showMessage(res.message, looksLikeError(res.message));
  if (!looksLikeError(res.message)) input.value = '';
  render(res.state);
});

document.getElementById('addVanForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const nameInput = document.getElementById('vanNameInput');
  const capacityInput = document.getElementById('vanCapacityInput');
  const name = nameInput.value.trim();
  const capacity = capacityInput.value;
  if (!name || !capacity) return;
  const res = await api('add_van', { name, capacity });
  showMessage(res.message, looksLikeError(res.message));
  if (!looksLikeError(res.message)) {
    nameInput.value = '';
    capacityInput.value = '';
  }
  render(res.state);
});

document.getElementById('resetBtn').addEventListener('click', async () => {
  if (!confirm('Clear ALL van assignments for both AM and PM? Students and teachers stay in the roster.')) return;
  const res = await api('reset', {});
  showMessage(res.message, false);
  render(res.state);
});

// ── Live sync (polling) ──
//
// Multiple people can have this page open on different devices at once.
// Every few seconds, each open tab quietly checks the server for changes
// and updates itself if anything moved — no manual refresh needed.
// This intentionally skips WebSockets in favor of simple polling, since
// changes only need to show up within a few seconds, not instantly.

function setSyncStatus(status) {
  const indicator = document.getElementById('syncIndicator');
  const label = document.getElementById('syncLabel');
  indicator.classList.remove('sync-indicator--paused', 'sync-indicator--error');
  if (status === 'paused') {
    indicator.classList.add('sync-indicator--paused');
    label.textContent = 'Paused';
  } else if (status === 'error') {
    indicator.classList.add('sync-indicator--error');
    label.textContent = 'Offline';
  } else {
    label.textContent = 'Live';
  }
}

async function pollState() {
  if (isDragging) return; // don't yank a list out from under an active drag

  try {
    const newState = await fetchState();
    const newJSON = JSON.stringify(newState);
    if (newJSON !== lastStateJSON) {
      render(newState);
      showMessage('Updated with changes from another device.', false);
    }
    setSyncStatus('live');
  } catch (err) {
    setSyncStatus('error');
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(pollState, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

// Pause polling when the tab isn't visible (saves requests/battery), and
// catch up immediately the moment it becomes visible again.
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    stopPolling();
    setSyncStatus('paused');
  } else {
    setSyncStatus('live');
    pollState();
    startPolling();
  }
});

// ── Print / export ──
// Builds ONE document containing both AM and PM assignments, regardless
// of which period is currently being viewed on screen.

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function buildPeriodSection(periodName, periodKeyName) {
  let html = `<h1 class="print-period-heading">${periodName}</h1>`;

  Object.entries(state.vans).forEach(([vanName, van]) => {
    const periodData = van[periodKeyName];
    html += `<div class="print-van">`;
    html += `<h2>${escapeHtml(vanName)} <span class="print-occ">(${periodData.occupants}/${van.capacity})</span></h2>`;

    html += `<h3>Teachers</h3><ul>`;
    html += periodData.teachers.length
      ? periodData.teachers.map((n) => `<li>${escapeHtml(n)}</li>`).join('')
      : `<li class="print-empty">None assigned</li>`;
    html += `</ul>`;

    html += `<h3>Students</h3><ul>`;
    html += periodData.students.length
      ? periodData.students.map((n) => `<li>${escapeHtml(n)}</li>`).join('')
      : `<li class="print-empty">None assigned</li>`;
    html += `</ul></div>`;
  });

  const dataKey = periodKeyName === 'am' ? 'am_van' : 'pm_van';
  const unassignedStudents = Object.entries(state.students).filter(([, d]) => !d[dataKey]);
  const unassignedTeachers = Object.entries(state.teachers).filter(([, d]) => !d[dataKey]);

  html += `<div class="print-van"><h2>Not Yet Assigned (${periodName})</h2>`;
  html += `<h3>Students</h3><ul>`;
  html += unassignedStudents.length
    ? unassignedStudents
        .map(
          ([n, d]) =>
            `<li>${escapeHtml(n)}${d.present ? '' : ' <span class="print-absent">(absent)</span>'}</li>`
        )
        .join('')
    : `<li class="print-empty">None</li>`;
  html += `</ul>`;

  html += `<h3>Teachers</h3><ul>`;
  html += unassignedTeachers.length
    ? unassignedTeachers.map(([n]) => `<li>${escapeHtml(n)}</li>`).join('')
    : `<li class="print-empty">None</li>`;
  html += `</ul></div>`;

  return html;
}

function buildPrintReport() {
  const el = document.getElementById('printReport');
  const generated = new Date().toLocaleString();

  let html = `<h1>Dispatch — Van Assignments</h1>`;
  html += `<p class="print-meta">Generated ${generated}</p>`;

  html += buildPeriodSection('AM', 'am');
  html += `<div class="print-page-break"></div>`;
  html += buildPeriodSection('PM', 'pm');

  el.innerHTML = html;
}

document.getElementById('printBtn').addEventListener('click', () => {
  buildPrintReport();
  window.print();
});

// ── Init ──

fetchState().then((initialState) => {
  render(initialState);
  startPolling();
});
