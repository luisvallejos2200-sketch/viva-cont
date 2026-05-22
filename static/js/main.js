/* ── VIVA CONT – Core JS ─────────────────────────────────── */

// ── SIDEBAR ────────────────────────────────────────────────
const sidebar       = document.getElementById('sidebar');
const mainWrapper   = document.getElementById('mainWrapper');
const sidebarToggle = document.getElementById('sidebarToggle');
const mobileToggle  = document.getElementById('mobileToggle');

(function initSidebar() {
  const collapsed = localStorage.getItem('vivaCollapsed') === '1';
  if (collapsed) {
    sidebar.classList.add('collapsed');
    mainWrapper.classList.add('collapsed');
  }
})();

sidebarToggle?.addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
  mainWrapper.classList.toggle('collapsed');
  localStorage.setItem('vivaCollapsed', sidebar.classList.contains('collapsed') ? '1' : '0');
});

mobileToggle?.addEventListener('click', () => {
  sidebar.classList.toggle('mobile-open');
});

document.addEventListener('click', (e) => {
  if (window.innerWidth <= 900 &&
      sidebar.classList.contains('mobile-open') &&
      !sidebar.contains(e.target) && e.target !== mobileToggle) {
    sidebar.classList.remove('mobile-open');
  }
});

// ── DATE ────────────────────────────────────────────────────
(function updateDate() {
  const el = document.getElementById('currentDate');
  if (!el) return;
  const now = new Date();
  const opts = { weekday:'long', year:'numeric', month:'long', day:'numeric' };
  el.textContent = now.toLocaleDateString('es-PE', opts);
})();

// ── TOAST ────────────────────────────────────────────────────
const ICONS = {
  success: 'fa-circle-check',
  error:   'fa-circle-xmark',
  info:    'fa-circle-info',
  warning: 'fa-triangle-exclamation',
};

function showToast(type, title, message, duration = 4000) {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <i class="fa-solid ${ICONS[type]} toast-icon"></i>
    <div class="toast-content">
      <div class="toast-title">${title}</div>
      ${message ? `<div class="toast-msg">${message}</div>` : ''}
    </div>
    <button onclick="this.parentElement.remove()" style="background:none;border:none;cursor:pointer;color:var(--text-muted);font-size:14px;padding:2px 4px;">
      <i class="fa-solid fa-xmark"></i>
    </button>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), duration);
}

// ── MODAL ────────────────────────────────────────────────────
function openModal(title, bodyHTML, footerHTML = '', size = '') {
  const overlay = document.getElementById('modalOverlay');
  const box     = document.getElementById('modalBox');
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalBody').innerHTML  = bodyHTML;
  document.getElementById('modalFooter').innerHTML = footerHTML;
  box.className = 'modal-box' + (size ? ` ${size}` : '');
  overlay.style.display = 'flex';
}

function closeModal() {
  document.getElementById('modalOverlay').style.display = 'none';
}

document.getElementById('modalOverlay')?.addEventListener('click', (e) => {
  if (e.target === document.getElementById('modalOverlay')) closeModal();
});

// ── TABS ─────────────────────────────────────────────────────
function initTabs(containerSelector) {
  document.querySelectorAll(containerSelector + ' .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      const parent = btn.closest(containerSelector) || document;
      parent.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      parent.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(tab)?.classList.add('active');
    });
  });
}

// ── API HELPERS ───────────────────────────────────────────────
// Fetch con timeout configurable — evita spinners colgados indefinidamente
function _fetchWithTimeout(url, options = {}, timeoutMs = 20000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  return fetch(url, { ...options, signal: ctrl.signal })
    .finally(() => clearTimeout(timer));
}

function _handleApiError(e, context = '') {
  if (e.name === 'AbortError') {
    showToast('warning', 'Tiempo agotado', 'La solicitud tardó demasiado. Intenta nuevamente.');
  } else if (e.message === '401' || e.message === '302') {
    showToast('error', 'Sesión expirada', 'Recarga la página e inicia sesión nuevamente.');
  } else {
    showToast('error', 'Error de conexión', e.message || 'Verifica tu conexión e intenta de nuevo.');
  }
}

async function apiGet(url) {
  try {
    const res = await _fetchWithTimeout(url, {}, 20000);
    if (!res.ok && (res.status === 401 || res.redirected)) {
      _handleApiError({ message: '401' });
      return null;
    }
    return await res.json();
  } catch (e) {
    _handleApiError(e);
    return null;
  }
}

async function apiPost(url, data) {
  try {
    const res = await _fetchWithTimeout(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }, 25000);
    if (!res.ok && res.status === 401) { _handleApiError({ message: '401' }); return null; }
    return await res.json();
  } catch (e) {
    _handleApiError(e);
    return null;
  }
}

async function apiPut(url, data) {
  try {
    const res = await _fetchWithTimeout(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }, 20000);
    if (!res.ok && res.status === 401) { _handleApiError({ message: '401' }); return null; }
    return await res.json();
  } catch (e) {
    _handleApiError(e);
    return null;
  }
}

async function apiDelete(url) {
  try {
    const res = await _fetchWithTimeout(url, { method: 'DELETE' }, 20000);
    if (!res.ok && res.status === 401) { _handleApiError({ message: '401' }); return null; }
    return await res.json();
  } catch (e) {
    _handleApiError(e);
    return null;
  }
}

// ── FORMATTERS ────────────────────────────────────────────────
function fmtMoney(val, currency = 'PEN') {
  const n = parseFloat(val) || 0;
  const sym = currency === 'USD' ? '$' : 'S/';
  return sym + ' ' + Math.abs(n).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(str) {
  if (!str) return '—';
  // Parse ISO date (YYYY-MM-DD) manually to avoid UTC→local timezone shift.
  // new Date('2025-04-30') = UTC midnight → shows Apr 29 in Peru (UTC-5).
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(str);
  if (iso) return `${iso[3]}/${iso[2]}/${iso[1]}`;
  try {
    const d = new Date(str);
    if (isNaN(d)) return str;
    return d.toLocaleDateString('es-PE', { day:'2-digit', month:'2-digit', year:'numeric' });
  } catch { return str; }
}

function badgeTipo(tipo) {
  const map = {
    'TRANSFERENCIA': 'badge-info',
    'COBRO':         'badge-warning',
    'PAGO':          'badge-danger',
    'ABONO':         'badge-success',
    'OTRO':          'badge-default',
  };
  return `<span class="badge ${map[tipo] || 'badge-default'}">${tipo || '—'}</span>`;
}

function badgeEstado(estado) {
  const map = {
    'BORRADOR': 'badge-default',
    'EMITIDA':  'badge-success',
    'ANULADA':  'badge-danger',
  };
  return `<span class="badge ${map[estado] || 'badge-default'}">${estado || '—'}</span>`;
}

// ── DRAG & DROP UPLOAD ────────────────────────────────────────
function initUploadZone(zoneId, inputId, onFile) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;

  zone.addEventListener('click', () => input.click());
  input.addEventListener('change', () => {
    if (input.files[0]) {
      const file = input.files[0];
      input.value = '';   // reset so same file can be re-uploaded
      onFile(file);
    }
  });
  zone.addEventListener('dragover', (e) => {
    e.preventDefault(); zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault(); zone.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  });
}

// ── EXPORT TABLE TO EXCEL ─────────────────────────────────────
function exportTableToExcel(tableId, filename) {
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.table_to_sheet(document.getElementById(tableId));
  XLSX.utils.book_append_sheet(wb, ws, 'Datos');
  XLSX.writeFile(wb, filename + '.xlsx');
}

// ── PAGINATION HELPER ─────────────────────────────────────────
function renderPagination(containerId, total, page, perPage, onPage) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const totalPages = Math.ceil(total / perPage);
  if (totalPages <= 1) { container.innerHTML = ''; return; }

  let html = `<button class="page-btn" ${page===1?'disabled':''} onclick="(${onPage})(${page-1})">
    <i class="fa-solid fa-chevron-left"></i></button>`;

  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= page-2 && i <= page+2)) {
      html += `<button class="page-btn ${i===page?'active':''}" onclick="(${onPage})(${i})">${i}</button>`;
    } else if (i === page-3 || i === page+3) {
      html += '<span class="page-info">…</span>';
    }
  }

  html += `<button class="page-btn" ${page===totalPages?'disabled':''} onclick="(${onPage})(${page+1})">
    <i class="fa-solid fa-chevron-right"></i></button>`;
  html += `<span class="page-info">${total.toLocaleString()} registros</span>`;
  container.innerHTML = html;
}

// ── LOADING STATE ─────────────────────────────────────────────
function setLoading(btnId, loading, text = '') {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  if (loading) {
    btn._originalHTML = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> ${text || 'Procesando...'}`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn._originalHTML || text;
    btn.disabled = false;
  }
}

// ══ SPA NAVIGATION ═══════════════════════════════════════════
(function initSPA() {
  const _cache    = new Map();
  const _inflight = new Map();
  const NAV_PATHS = ['/', '/estados-cuenta', '/analisis-bancario',
                     '/estados-resultados', '/balance-general',
                     '/facturador', '/configuracion', '/usuarios',
                     '/empresas', '/api/docs'];

  // Rutas con estado client-side pesado: no cachear para evitar pérdida de datos
  const NO_CACHE = new Set(['/analisis-bancario']);

  /* ── Progress bar ── */
  const _bar = document.createElement('div');
  _bar.id = 'viva-npbar';
  document.body.prepend(_bar);

  let _barTimer;
  function npStart() {
    clearTimeout(_barTimer);
    _bar.style.transition = 'none';
    _bar.style.width = '0';
    _bar.classList.add('active');
    requestAnimationFrame(() => {
      _bar.style.transition = 'width .35s ease, opacity .25s ease';
      _bar.style.width = '65%';
    });
  }
  function npDone() {
    _bar.style.width = '100%';
    _barTimer = setTimeout(() => {
      _bar.style.opacity = '0';
      setTimeout(() => { _bar.classList.remove('active'); _bar.style.width = '0'; _bar.style.opacity = '1'; }, 280);
    }, 200);
  }

  /* ── Fetch with dedup + AbortController timeout (15s) ── */
  function fetchPage(url) {
    if (!NO_CACHE.has(url) && _cache.has(url)) return Promise.resolve(_cache.get(url));
    if (_inflight.has(url)) return _inflight.get(url);

    const ctrl  = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 15000);

    const p = fetch(url, { headers: { 'X-VIVA-SPA': '1' }, signal: ctrl.signal })
      .then(r => {
        clearTimeout(timer);
        if (!r.ok) throw new Error(r.status);
        return r.text();
      })
      .then(html => {
        if (!NO_CACHE.has(url)) _cache.set(url, html);
        _inflight.delete(url);
        return html;
      })
      .catch(e => { clearTimeout(timer); _inflight.delete(url); throw e; });
    _inflight.set(url, p);
    return p;
  }

  function prefetch(url) {
    if (!NAV_PATHS.includes(url) || NO_CACHE.has(url) || _cache.has(url) || _inflight.has(url)) return;
    fetchPage(url).catch(() => {});
  }

  /* ── Parse fetched HTML ── */
  function parsePage(html) {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    // Collect page-specific inline <style> blocks from <head> (from {% block head %})
    const headStyles = [...doc.querySelectorAll('head style')].map(s => s.textContent);
    return {
      content:    doc.querySelector('.page-content')?.innerHTML || '',
      title:      doc.title,
      breadcrumb: doc.querySelector('.breadcrumb-current')?.textContent?.trim() || '',
      scripts:    [...doc.querySelectorAll('body script:not([src])')].map(s => s.textContent),
      headStyles,
    };
  }

  /* ── Inject / replace page-specific head styles ── */
  function applyHeadStyles(styles) {
    document.querySelectorAll('style[data-spa]').forEach(el => el.remove());
    styles.forEach(css => {
      const el = document.createElement('style');
      el.setAttribute('data-spa', '1');
      el.textContent = css;
      document.head.appendChild(el);
    });
  }

  /* ── Destroy active Chart.js instances ── */
  function destroyCharts() {
    if (!window.Chart) return;
    document.querySelectorAll('canvas').forEach(c => {
      try { const ch = Chart.getChart(c); if (ch) ch.destroy(); } catch (e) {}
    });
  }

  /* ── Execute scripts in new content ── */
  function runScripts(scripts) {
    scripts.forEach(code => {
      try {
        const el = document.createElement('script');
        el.textContent = code;
        document.body.appendChild(el);
        document.body.removeChild(el);
      } catch (e) {}
    });
  }

  /* ── Core navigate ── */
  async function navigate(url, push = true) {
    if (url === window.location.pathname) return;
    npStart();
    try {
      const html = await fetchPage(url);
      const { content, title, breadcrumb, scripts, headStyles } = parsePage(html);

      destroyCharts();

      // Apply styles BEFORE content is visible — eliminates flash of unstyled content
      applyHeadStyles(headStyles);

      const mainEl = document.querySelector('.page-content');
      mainEl.classList.add('leaving');
      await new Promise(r => setTimeout(r, 100));

      mainEl.innerHTML = content;
      mainEl.classList.remove('leaving');

      document.title = title;
      const bc = document.querySelector('.breadcrumb-current');
      if (bc) bc.textContent = breadcrumb;

      document.querySelectorAll('.nav-item[href]').forEach(a => {
        a.classList.toggle('active', a.getAttribute('href') === url);
      });

      if (push) history.pushState({ url }, title, url);
      window.scrollTo(0, 0);
      npDone();
      runScripts(scripts);
    } catch (e) {
      npDone();
      window.location.href = url;
    }
  }

  /* ── Intercept nav clicks ── */
  document.addEventListener('click', e => {
    const link = e.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href');
    if (!NAV_PATHS.includes(href)) return;
    e.preventDefault();
    navigate(href);
  });

  /* ── Prefetch on hover ── */
  document.querySelectorAll('.nav-item[href]').forEach(a => {
    a.addEventListener('mouseenter', () => prefetch(a.getAttribute('href')));
  });

  /* ── Back / Forward ── */
  window.addEventListener('popstate', e => {
    const url = e.state?.url || window.location.pathname;
    navigate(url, false);
  });

  /* ── Seed current state ── */
  history.replaceState({ url: window.location.pathname }, document.title, window.location.pathname);
})();
