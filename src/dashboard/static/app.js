/* MISSION_CONTROL — IDE-style frontend. Vanilla JS, no build step. */
'use strict';

const $ = (s) => document.querySelector(s);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};
const fmt = (v, d = 2) => (v === null || v === undefined) ? '—' : Number(v).toFixed(d);

async function getJSON(url) {
  const r = await fetch(url);
  const data = await r.json().catch(() => ({}));
  if (!r.ok || (data && data.error)) throw new Error(data.detail || data.error || ('HTTP ' + r.status));
  return data;
}

/* ================= TAB SYSTEM ================= */
const tabs = {};
let activeTab = null;

function openTab(id, title, build, opts = {}) {
  if (tabs[id]) { activateTab(id); return tabs[id]; }
  const pane = el('div', 'pane');
  $('#content').appendChild(pane);
  const tabEl = el('div', 'tab');
  tabEl.innerHTML = `<span class="ttl">${title}</span><span class="x">✕</span>`;
  $('#tabbar').appendChild(tabEl);
  const t = { id, title, paneEl: pane, tabEl, ...opts };
  tabs[id] = t;
  tabEl.addEventListener('click', (e) => {
    if (e.target.classList.contains('x')) closeTab(id); else activateTab(id);
  });
  build(pane, t);
  activateTab(id);
  return t;
}

function activateTab(id) {
  Object.values(tabs).forEach(t => { t.tabEl.classList.remove('active'); t.paneEl.classList.remove('active'); });
  const t = tabs[id];
  if (!t) return;
  activeTab = id;
  t.tabEl.classList.add('active'); t.paneEl.classList.add('active');
  if (t.onShow) t.onShow();
}

function closeTab(id) {
  const t = tabs[id];
  if (!t) return;
  if (t.dirty && !confirm(`"${t.title}" ha modifiche non salvate. Chiudere comunque?`)) return;
  if (t.onClose) t.onClose();
  t.paneEl.remove(); t.tabEl.remove();
  delete tabs[id];
  if (activeTab === id) {
    const left = Object.keys(tabs);
    if (left.length) activateTab(left[left.length - 1]);
    else activeTab = null;
  }
}

function setDirty(id, dirty) {
  const t = tabs[id];
  if (!t) return;
  t.dirty = dirty;
  t.tabEl.querySelector('.ttl').innerHTML = (dirty ? '<span class="dirty">●</span> ' : '') + t.title;
}

/* ================= SORTABLE / FILTERABLE TABLE ================= */
/* makeTable(container, cols, rows, opts)
   - click intestazione: ordina (1° click discendente, 2° ascendente)
   - search box: filtra su tutte le colonne
   - opts.controls: [{el, test(row)}] filtri custom (select/checkbox)
   - opts.sortKey/sortDir: ordinamento iniziale                         */
function makeTable(container, cols, rows, opts = {}) {
  const state = { sortKey: opts.sortKey || null, sortDir: opts.sortDir || -1, query: '' };
  container.innerHTML = '';
  const bar = el('div', 'table-toolbar');
  const inp = el('input', 'tbl-search');
  inp.type = 'search'; inp.placeholder = '⌕ filtra…';
  inp.oninput = () => { state.query = inp.value.toLowerCase(); draw(); };
  bar.appendChild(inp);
  (opts.controls || []).forEach(c => { bar.appendChild(c.el); c.onChange = draw; });
  const count = el('span', 'tbl-count');
  bar.appendChild(count);
  container.appendChild(bar);
  const wrap = el('div', 'table-wrap');
  const table = el('table');
  wrap.appendChild(table);
  container.appendChild(wrap);

  function visibleRows() {
    let out = rows;
    if (state.query) {
      out = out.filter(r => cols.some(c => String(r[c.key] ?? '').toLowerCase().includes(state.query)));
    }
    (opts.controls || []).forEach(c => { if (c.test) out = out.filter(c.test); });
    if (state.sortKey) {
      const k = state.sortKey, dir = state.sortDir;
      out = [...out].sort((a, b) => {
        const va = a[k], vb = b[k];
        if (va == null && vb == null) return 0;
        if (va == null) return 1;
        if (vb == null) return -1;
        const na = Number(va), nb = Number(vb);
        if (Number.isFinite(na) && Number.isFinite(nb)) return (na - nb) * dir;
        return String(va).localeCompare(String(vb)) * dir;
      });
    }
    return out;
  }

  function draw() {
    const data = visibleRows();
    count.textContent = `${data.length}/${rows.length} righe`;
    if (!rows.length) { table.innerHTML = '<tr><td class="dim">nessun dato</td></tr>'; return; }
    const head = '<tr>' + cols.map(c => {
      const sorted = state.sortKey === c.key;
      const arrow = sorted ? (state.sortDir === 1 ? ' ▲' : ' ▼') : '';
      return `<th data-key="${c.key}" class="${sorted ? 'sorted' : ''}">${c.label}${arrow}</th>`;
    }).join('') + '</tr>';
    const body = data.map(r => '<tr>' + cols.map(c => {
      let v = r[c.key];
      if (c.fmt) v = c.fmt(v, r);
      const cls = opts.cellClass ? (opts.cellClass(c.key, r) || '') : '';
      return `<td class="${cls}">${v === null || v === undefined ? '—' : v}</td>`;
    }).join('') + '</tr>').join('');
    table.innerHTML = head + body;
  }

  table.addEventListener('click', (e) => {
    const th = e.target.closest('th');
    if (!th || !th.dataset.key) return;
    if (state.sortKey === th.dataset.key) state.sortDir *= -1;
    else { state.sortKey = th.dataset.key; state.sortDir = -1; }  // primo click: decrescente
    draw();
  });

  draw();
  return { redraw: draw, state };
}

function makeCheck(label, test) {
  const lab = el('label', 'tbl-check', `<input type="checkbox"> ${label}`);
  const box = lab.querySelector('input');
  const ctl = { el: lab, test: null };
  box.onchange = () => { ctl.test = box.checked ? test : null; if (ctl.onChange) ctl.onChange(); };
  return ctl;
}

function makeSelect(options, testFactory) {
  const sel = el('select', 'tbl-select');
  sel.innerHTML = options.map(([v, lbl]) => `<option value="${v}">${lbl}</option>`).join('');
  const ctl = { el: sel, test: null };
  sel.onchange = () => { ctl.test = sel.value ? testFactory(sel.value) : null; if (ctl.onChange) ctl.onChange(); };
  return ctl;
}

const dt = v => v ? String(v).slice(0, 16).replace('T', ' ') : '—';

/* ================= COCKPIT PANELS ================= */
const CHART_FONT = { family: 'IBM Plex Mono, monospace', size: 10 };

/* ---- temi: i colori dei grafici seguono le CSS var del tema attivo ---- */
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
let INK, CLAY, GRASS, SUN, DIM;
function refreshThemeColors() {
  INK = cssVar('--ink'); CLAY = cssVar('--accent-2'); GRASS = cssVar('--accent');
  SUN = cssVar('--highlight'); DIM = cssVar('--ink-faint');
  if (window.Chart) { Chart.defaults.color = INK; Chart.defaults.borderColor = cssVar('--line'); }
}

const THEMES = [
  ['hermes', '🎾 Hermes'], ['onepiece', '⚓ One Piece'], ['matrix', '▮ Matrix'],
  ['batman', '🦇 Batman'], ['hitman', '♠ Hitman'], ['diablo', '🔥 Diablo IV'],
];

function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem('mc-theme', t);
  refreshThemeColors();
  // terminali aperti: aggiorna i colori al volo
  Object.values(terms).forEach(x => {
    x.term.options.theme = { background: cssVar('--term-bg'), foreground: cssVar('--term-fg'), cursor: cssVar('--highlight') };
  });
  // pannello attivo: ri-renderizza coi colori nuovi
  if (activeTab && activeTab.startsWith('panel:')) {
    const name = activeTab.split(':')[1];
    if (PANELS[name]) { closeTab(activeTab); openPanel(name); }
  }
}

function blk(k, v, cls = '', sub = '') {
  return `<div class="blk ${cls}"><div class="k">${k}</div><div class="v">${v}</div>` +
         (sub ? `<div class="s">${sub}</div>` : '') + '</div>';
}

const PANELS = {
  overview: { title: 'Overview', render: async (pane) => {
    const [d, mo, dec, odds] = await Promise.all([
      getJSON('/api/overview'), getJSON('/api/model'),
      getJSON('/api/decisions?limit=500'), getJSON('/api/odds'),
    ]);
    const c = mo.current || {};
    pane.innerHTML = `<div class="pane-pad dash">
      <div class="section-bar">Banca <small>betanalytix.db</small></div>
      <div class="blk-row">
        ${blk('Bankroll', d.bankroll !== null ? '€' + fmt(d.bankroll, 0) : '—', 'ink')}
        ${blk('Profit', '€' + fmt(d.total_profit, 0), d.total_profit < 0 ? 'alarm' : 'grass')}
        ${blk('ROI', d.roi_pct !== null ? fmt(d.roi_pct, 1) + '%' : '—', '')}
        ${blk('Win rate', d.win_rate !== null ? fmt(d.win_rate, 0) + '%' : '—', '')}
        ${blk('Bet aperte', d.bets_open, 'sun')}
        ${blk('Decisioni', d.decisions, '', 'ultimo scan ' + dt(d.last_scan))}
      </div>
      <div class="section-bar">Modello <small>${c.best_model || '—'} · test 2025+</small></div>
      <div class="blk-row">
        ${blk('Accuracy', c.accuracy ? (c.accuracy * 100).toFixed(1) + '%' : '—', 'grass', 'onesta, leak-free')}
        ${blk('vs Mercato', (mo.market_baseline * 100).toFixed(1) + '%', 'clay', 'favorito B365 — da battere')}
        ${blk('Log loss', c.log_loss ? c.log_loss.toFixed(3) : '—', 'ink')}
        ${blk('ROC AUC', c.roc_auc ? c.roc_auc.toFixed(3) : '—', '')}
        ${blk('Train', c.trained_at ? dt(c.trained_at) : '—', '', 'TennisLoopNightly 07:13')}
      </div>
      <div class="chart-grid">
        <div class="chart-box"><h4>Distribuzione edge — ultime ${dec.length} decisioni</h4>
          <canvas id="ch-edge"></canvas></div>
        <div class="chart-box"><h4>Match nel feed (ultimo snapshot)</h4>
          <div class="today-list" id="today-list"></div></div>
      </div>
      <div class="chart-grid">
        <div class="chart-box"><h4>Traiettoria modello — accuracy & log loss per training</h4>
          <canvas id="ch-hist"></canvas></div>
        <div class="chart-box"><h4>Accuracy per modello (run corrente)</h4>
          <canvas id="ch-models"></canvas></div>
      </div>
    </div>`;

    Chart.defaults.font = CHART_FONT;
    Chart.defaults.color = INK;

    // edge histogram
    const edges = dec.map(r => r.edge).filter(e => e !== null && isFinite(e));
    const bins = [-0.3, -0.2, -0.1, -0.05, 0, 0.05, 0.1, 0.2, 0.3, 0.5];
    const counts = new Array(bins.length - 1).fill(0);
    edges.forEach(e => { for (let i = 0; i < bins.length - 1; i++) if (e >= bins[i] && e < bins[i + 1]) { counts[i]++; break; } });
    new Chart($('#ch-edge'), {
      type: 'bar',
      data: { labels: bins.slice(0, -1).map((b, i) => `${b}–${bins[i + 1]}`),
              datasets: [{ data: counts, backgroundColor: bins.slice(0, -1).map(b => b >= 0 ? GRASS : CLAY), borderColor: INK, borderWidth: 1.5 }] },
      options: { plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: 'rgba(26,26,18,0.1)' } } } },
    });

    // today's matches with best legal price (top 8)
    const tl = $('#today-list');
    const matches = (odds.matches || []).slice(0, 8);
    if (!matches.length) tl.innerHTML = '<div class="sb-note">nessuno snapshot — lancia ⚡ scan dalla Pipeline</div>';
    matches.forEach(async m => {
      const row = el('div', 'today-row', `<span class="t-m">${m}</span><span class="t-o">…</span>`);
      tl.appendChild(row);
      try {
        const dd = await getJSON('/api/odds?match=' + encodeURIComponent(m));
        const best1 = Math.max(...dd.rows.map(r => r.price_1 || 0));
        const best2 = Math.max(...dd.rows.map(r => r.price_2 || 0));
        row.querySelector('.t-o').textContent = `${best1.toFixed(2)} / ${best2.toFixed(2)}`;
      } catch (e) { row.querySelector('.t-o').textContent = '—'; }
    });

    // metrics history
    const hist = mo.history || [];
    new Chart($('#ch-hist'), {
      type: 'line',
      data: { labels: hist.map(h => String(h.trained_at).slice(5, 16).replace('T', ' ')),
        datasets: [
          { label: 'accuracy', data: hist.map(h => +h.accuracy * 100), borderColor: GRASS, backgroundColor: GRASS, yAxisID: 'y', tension: 0.25, pointRadius: 4 },
          { label: 'log loss', data: hist.map(h => +h.log_loss), borderColor: CLAY, backgroundColor: CLAY, yAxisID: 'y2', tension: 0.25, pointRadius: 4 },
        ] },
      options: { plugins: { legend: { labels: { boxWidth: 10 } } },
        scales: { y: { position: 'left', title: { display: true, text: 'acc %' }, grid: { color: 'rgba(26,26,18,0.1)' } },
                  y2: { position: 'right', title: { display: true, text: 'log loss' }, grid: { display: false } },
                  x: { grid: { display: false } } } },
    });

    // per-model accuracy
    const models = Object.entries(c.models || {}).filter(([k]) => k.startsWith('target_'));
    new Chart($('#ch-models'), {
      type: 'bar',
      data: { labels: models.map(([k]) => k.replace('target_', '')),
              datasets: [{ data: models.map(([, v]) => v.accuracy * 100), backgroundColor: models.map(([k]) => k === c.best_model ? SUN : INK), borderColor: INK, borderWidth: 1.5 }] },
      options: { indexAxis: 'y', plugins: { legend: { display: false } },
        scales: { x: { min: 60, max: 70, grid: { color: 'rgba(26,26,18,0.1)' }, title: { display: true, text: 'accuracy %' } }, y: { grid: { display: false } } } },
    });
  }},
  segnali: { title: 'Segnali', render: async (pane) => {
    const rows = await getJSON('/api/decisions?limit=500');
    pane.innerHTML = '<div class="pane-pad" style="height:100%"><div class="tbl-host" style="height:100%"></div></div>';
    makeTable(pane.querySelector('.tbl-host'), [
      { key: 'timestamp', label: 'Quando', fmt: dt },
      { key: 'match_str', label: 'Match' }, { key: 'tournament', label: 'Torneo' },
      { key: 'surface', label: 'Sup.' },
      { key: 'odds_1', label: 'Q1', fmt: v => fmt(v) }, { key: 'odds_2', label: 'Q2', fmt: v => fmt(v) },
      { key: 'ml_prob_1', label: 'ML p1', fmt: v => fmt(v, 3) }, { key: 'ml_prob_2', label: 'ML p2', fmt: v => fmt(v, 3) },
      { key: 'edge', label: 'Edge', fmt: v => fmt(v, 3) }, { key: 'value_side', label: 'Side' },
      { key: 'kelly_fraction', label: 'Kelly', fmt: v => fmt(v, 4) },
      { key: 'low_confidence', label: 'Conf.', fmt: v => v ? 'LOW' : 'ok' },
    ], rows, {
      sortKey: 'timestamp', sortDir: -1,
      controls: [makeCheck('solo edge > 0', r => r.edge > 0),
                 makeCheck('escludi low-conf', r => !r.low_confidence)],
      cellClass: (k, r) => k === 'edge' ? (r.edge > 0 ? 'pos' : 'neg')
                         : k === 'low_confidence' ? (r.low_confidence ? 'neg' : 'dim') : '',
    });
  }},
  bet: { title: 'Bet', render: async (pane) => {
    const rows = await getJSON('/api/bets');
    const settled = rows.filter(r => r.status === 'won' || r.status === 'lost');
    const staked = settled.reduce((s, r) => s + (r.stake || 0), 0);
    const profit = settled.reduce((s, r) => s + (r.profit || 0), 0);
    const won = settled.filter(r => r.status === 'won').length;
    const bank = rows.filter(r => r.bankroll_after !== null)
                     .sort((a, b) => (a.resolved_at || '').localeCompare(b.resolved_at || ''));

    pane.innerHTML = `<div class="pane-pad dash" style="height:100%; overflow:auto">
      <div class="blk-row">
        ${blk('Bankroll', bank.length ? '€' + fmt(bank[bank.length - 1].bankroll_after, 0) : '—', 'ink')}
        ${blk('Profit', '€' + fmt(profit, 1), profit < 0 ? 'alarm' : 'grass')}
        ${blk('Yield', staked ? (profit / staked * 100).toFixed(1) + '%' : '—', '', 'profit / volume puntato')}
        ${blk('Record', `${won}–${settled.length - won}`, 'sun', rows.filter(r => r.status === 'pending').length + ' pending')}
      </div>
      <div class="chart-grid">
        <div class="chart-box"><h4>Equity curve — bankroll dopo ogni bet risolta</h4><canvas id="ch-bank"></canvas></div>
        <div class="chart-box"><h4>Registra una bet</h4>
          <form id="bet-form" class="bet-form">
            <input name="match_str" placeholder="Match (es. Sinner vs Alcaraz)" required>
            <input name="side_name" placeholder="Puntata su (giocatore)" required>
            <div class="bet-form-row">
              <input name="odds" type="number" step="0.01" min="1.01" placeholder="Quota" required>
              <input name="stake" type="number" step="0.5" min="0.5" placeholder="Stake €" required>
            </div>
            <input name="notes" placeholder="Note / bookmaker (opzionale)">
            <button class="btn primary" type="submit">+ registra</button>
            <span class="panel-note" id="bet-form-status"></span>
          </form></div>
      </div>
      <div class="tbl-host"></div></div>`;

    new Chart($('#ch-bank'), {
      type: 'line',
      data: { labels: bank.map(b => dt(b.resolved_at)),
        datasets: [{ label: 'bankroll €', data: bank.map(b => b.bankroll_after),
                     borderColor: INK, backgroundColor: SUN, pointRadius: 4, tension: 0.15, fill: false }] },
      options: { plugins: { legend: { display: false } },
        scales: { y: { grid: { color: 'rgba(26,26,18,0.1)' } }, x: { grid: { display: false } } } },
    });

    $('#bet-form').onsubmit = async (e) => {
      e.preventDefault();
      const f = new FormData(e.target), st = $('#bet-form-status');
      st.textContent = '…';
      try {
        const r = await fetch('/api/bet', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(Object.fromEntries(f.entries())) });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || d.error);
        toast('bet registrata');
        delete tabs['panel:bet']; closeTab('panel:bet'); openPanel('bet');
      } catch (err) { st.textContent = 'ERRORE: ' + err.message; }
    };

    const host = pane.querySelector('.tbl-host');
    makeTable(host, [
      { key: 'timestamp', label: 'Quando', fmt: dt }, { key: 'match_str', label: 'Match' },
      { key: 'side_name', label: 'Puntata su' }, { key: 'odds', label: 'Quota', fmt: v => fmt(v) },
      { key: 'stake', label: 'Stake €', fmt: v => fmt(v) },
      { key: 'status', label: 'Status' },
      { key: 'profit', label: 'Profit €', fmt: v => v === null ? '—' : fmt(v) },
      { key: 'bankroll_after', label: 'Bankroll €', fmt: v => v === null ? '—' : fmt(v) },
      { key: 'id', label: 'Esito', fmt: (v, r) => r.status === 'pending'
          ? `<button class="row-act win" data-id="${v}" data-do="won">✓ vinta</button>
             <button class="row-act lose" data-id="${v}" data-do="lost">✗ persa</button>`
          : `<button class="row-act" data-id="${v}" data-do="undo">↩</button>` },
    ], rows, {
      sortKey: 'timestamp', sortDir: -1,
      controls: [makeSelect([['', 'tutti gli status'], ['pending', 'pending'], ['won', 'won'], ['lost', 'lost']],
                            v => r => r.status === v)],
      cellClass: (k, r) => k === 'status' ? (r.status === 'won' ? 'pos' : (r.status === 'lost' ? 'neg' : 'dim'))
                         : (k === 'profit' && r.profit !== null) ? (r.profit > 0 ? 'pos' : 'neg') : '',
    });
    host.addEventListener('click', async (e) => {
      const b = e.target.closest('.row-act');
      if (!b) return;
      const url = b.dataset.do === 'undo' ? `/api/bet/${b.dataset.id}/undo` : `/api/bet/${b.dataset.id}/resolve`;
      try {
        const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ won: b.dataset.do === 'won' }) });
        if (!r.ok) throw new Error((await r.json()).detail);
        toast(b.dataset.do === 'undo' ? 'esito annullato' : 'esito registrato: ' + b.dataset.do);
        closeTab('panel:bet'); openPanel('bet');
      } catch (err) { toast('errore: ' + err.message, true); }
    });
  }},
  clv: { title: 'CLV', render: async (pane) => {
    const d = await getJSON('/api/clv');
    pane.innerHTML = `<div class="pane-pad" style="height:100%">
      <div class="panel-note">${d.note || ''}${d.mean_clv !== null ? ' · CLV medio: ' + (d.mean_clv * 100).toFixed(2) + '%' : ''}</div>
      <canvas id="clv-chart" width="960" height="240"></canvas>
      <div class="tbl-host"></div></div>`;
    const vals = (d.rows || []).filter(r => r.clv !== null && r.clv !== undefined).map(r => r.clv);
    drawClv(pane.querySelector('#clv-chart'), vals);
    makeTable(pane.querySelector('.tbl-host'), [
      { key: 'ts', label: 'Quando', fmt: dt }, { key: 'match', label: 'Match' },
      { key: 'side', label: 'Side' }, { key: 'bookmaker', label: 'Book' },
      { key: 'odds', label: 'Quota presa', fmt: v => fmt(v) },
      { key: 'clv', label: 'CLV', fmt: v => v === null ? '—' : (v * 100).toFixed(2) + '%' },
    ], d.rows || [], {
      sortKey: 'clv', sortDir: -1,
      controls: [makeCheck('solo CLV positivo', r => r.clv !== null && r.clv > 0)],
      cellClass: (k, r) => k === 'clv' && r.clv !== null ? (r.clv > 0 ? 'pos' : 'neg') : '',
    });
  }},
  quote: { title: 'Quote', render: async (pane) => {
    const d = await getJSON('/api/odds');
    pane.innerHTML = `<div class="pane-pad" style="height:100%">
      <div class="toolbar"><select class="match-sel"></select>
        <span class="panel-note">${d.snapshot_ts ? 'snapshot: ' + d.snapshot_ts : 'nessuno snapshot'}</span></div>
      <div class="tbl-host"></div></div>`;
    const sel = pane.querySelector('.match-sel');
    sel.innerHTML = '<option value="">— scegli match —</option>' + (d.matches || []).map(m => `<option>${m}</option>`).join('');
    sel.onchange = async () => {
      if (!sel.value) return;
      const dd = await getJSON('/api/odds?match=' + encodeURIComponent(sel.value));
      makeTable(pane.querySelector('.tbl-host'), [
        { key: 'bookmaker', label: 'Bookmaker' }, { key: 'p1', label: 'Giocatore 1' },
        { key: 'price_1', label: 'Quota 1', fmt: v => fmt(v) },
        { key: 'p2', label: 'Giocatore 2' }, { key: 'price_2', label: 'Quota 2', fmt: v => fmt(v) },
      ], dd.rows, { sortKey: 'price_1', sortDir: -1 });   // default: quota 1 decrescente
    };
  }},
};

function drawClv(cv, vals) {
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.font = '12px IBM Plex Mono, monospace';
  if (!vals.length) { ctx.fillStyle = '#8C8470'; ctx.fillText('Nessun dato CLV — accumula snapshot', 20, 40); return; }
  const pad = 30, W = cv.width - pad * 2, H = cv.height - pad * 2;
  const mx = Math.max(0.01, Math.max(...vals.map(Math.abs)));
  const y = v => pad + H / 2 - (v / mx) * (H / 2);
  const x = i => pad + (vals.length === 1 ? W / 2 : i * W / (vals.length - 1));
  ctx.strokeStyle = 'rgba(26,26,18,0.35)'; ctx.beginPath(); ctx.moveTo(pad, y(0)); ctx.lineTo(pad + W, y(0)); ctx.stroke();
  ctx.strokeStyle = '#C75A2A'; ctx.lineWidth = 2; ctx.beginPath();
  vals.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v)));
  ctx.stroke();
  vals.forEach((v, i) => {
    ctx.fillStyle = v >= 0 ? '#2E6B3F' : '#C0392B';
    ctx.beginPath(); ctx.arc(x(i), y(v), 3, 0, Math.PI * 2); ctx.fill();
  });
}

function openPanel(name) {
  const p = PANELS[name];
  openTab('panel:' + name, p.title, async (pane) => {
    try { await p.render(pane); }
    catch (err) { pane.innerHTML = `<div class="pane-pad"><div class="banner">ERRORE: ${err.message}</div></div>`; }
  });
}

/* ================= EDITOR ================= */
const MODES = { py: 'python', yaml: 'yaml', yml: 'yaml', js: 'javascript', json: { name: 'javascript', json: true },
                md: 'markdown', markdown: 'markdown', sh: 'shell', ps1: 'shell', bat: 'shell',
                css: 'css', html: 'htmlmixed', txt: null, csv: null, log: null };

const IMG_EXT = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico'];
const VID_EXT = ['mp4', 'webm', 'mov', 'mkv', 'm4v'];
const AUD_EXT = ['mp3', 'wav', 'ogg', 'm4a'];

function openMedia(path) {
  const id = 'media:' + path;
  if (tabs[id]) { activateTab(id); return; }
  const name = path.split('/').pop();
  const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
  const src = '/api/media?path=' + encodeURIComponent(path);
  let inner;
  if (IMG_EXT.includes(ext)) inner = `<img src="${src}" alt="${name}">`;
  else if (VID_EXT.includes(ext)) inner = `<video src="${src}" controls autoplay></video>`;
  else if (AUD_EXT.includes(ext)) inner = `<audio src="${src}" controls autoplay></audio>`;
  else if (ext === 'pdf') inner = `<iframe src="${src}" style="width:100%;height:100%;border:none"></iframe>`;
  else inner = `<div class="panel-note">anteprima non disponibile per .${ext}</div>`;
  openTab(id, name, (pane) => {
    pane.innerHTML = `<div class="media-host">${inner}</div>`;
  });
}

async function openFile(path, readonly = false) {
  const name0 = path.split('/').pop();
  const ext0 = name0.includes('.') ? name0.split('.').pop().toLowerCase() : '';
  if ([...IMG_EXT, ...VID_EXT, ...AUD_EXT, 'pdf'].includes(ext0)) { openMedia(path); return; }
  const id = 'file:' + path;
  if (tabs[id]) { activateTab(id); return; }
  let data;
  try { data = await getJSON('/api/file?path=' + encodeURIComponent(path)); }
  catch (err) { alert('Impossibile aprire ' + path + ': ' + err.message); return; }
  const name = path.split('/').pop();
  openTab(id, name, (pane, t) => {
    pane.innerHTML = `<div class="editor-host">
      <div class="editor-toolbar">
        <span>${path}${readonly ? ' · sola lettura' : ''}</span>
        ${readonly ? '' : '<button class="btn primary save">Salva (Ctrl+S)</button>'}
        <span class="status"></span>
      </div>
      <div class="editor-cm"></div></div>`;
    const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
    const cm = CodeMirror(pane.querySelector('.editor-cm'), {
      value: data.content, mode: MODES[ext] ?? null, lineNumbers: true,
      readOnly: readonly, lineWrapping: ['md', 'txt', 'log'].includes(ext), viewportMargin: 50,
    });
    t.cm = cm;
    t.onShow = () => setTimeout(() => cm.refresh(), 10);
    if (!readonly) {
      cm.on('change', () => setDirty(id, true));
      const save = async () => {
        const st = pane.querySelector('.status');
        st.textContent = 'salvataggio…';
        try {
          if (path === 'config/config.yaml') {
            const r = await fetch('/api/config', { method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ content: cm.getValue() }) });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || d.error);
            st.textContent = 'salvato ✓ (backup .bak)';
          } else {
            const r = await fetch('/api/file', { method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ path, content: cm.getValue() }) });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || d.error);
            st.textContent = 'salvato ✓';
          }
          setDirty(id, false);
        } catch (err) { st.textContent = 'ERRORE: ' + err.message; }
      };
      pane.querySelector('.save').onclick = save;
      cm.setOption('extraKeys', { 'Ctrl-S': save });
    }
  });
}

/* ================= SIDEBAR / ACTIVITIES ================= */
const ACTS = {
  cockpit: { title: 'Cockpit', render: (body) => {
    ['overview', 'segnali', 'bet', 'clv', 'quote'].forEach(name => {
      const b = el('button', 'sb-item', '◧ ' + PANELS[name].title);
      b.onclick = () => openPanel(name);
      body.appendChild(b);
    });
    body.appendChild(el('div', 'sb-note', 'Dati live da betanalytix.db e odds_history.csv. Click sulle intestazioni per ordinare (1° click: decrescente).'));
  }},
  chat: { title: 'UnaBettingOS', render: (body) => {
    body.appendChild(el('div', 'sb-note',
      `<b>UnaBettingOS</b> — centro di memoria agentica. Modello locale <b>qwen3.5:9b</b> via Ollama. ` +
      `Collegato a: dati live, vault Obsidian, knowledge graph, memoria persistente.`));
    body.appendChild(el('div', 'sb-section', 'Dati & azioni'));
    ['quali sono i match di oggi?', 'ultimi segnali del modello?',
     'com’è messo il modello?', 'stato del bankroll?'].forEach(q => {
      const b = el('button', 'sb-item', '✦ ' + q);
      b.onclick = () => { openChat(); const inp = $('#chat-input'); if (inp) { inp.value = q; inp.focus(); } };
      body.appendChild(b);
    });
    body.appendChild(el('div', 'sb-section', 'Memoria & conoscenza'));
    ['cerca nel vault: perché il backtest dava 85%?',
     'interroga il grafo: EloRating',
     'ricorda che: ', 'cosa ti ho chiesto di ricordare?'].forEach(q => {
      const b = el('button', 'sb-item', '🧠 ' + q);
      b.onclick = () => { openChat(); const inp = $('#chat-input'); if (inp) { inp.value = q; inp.focus(); } };
      body.appendChild(b);
    });
    body.appendChild(el('div', 'sb-note', 'La memoria vive in docs/obsidian/UnaBettingOS_Memoria.md — versionata con git come tutto il resto.'));
    openChat();
  }},
  browser: { title: 'Browser web', render: (body) => {
    body.appendChild(el('div', 'sb-note',
      'Browser agentico: apri URL, leggi il contenuto, segui i link. Anche l\'agente UnaBettingOS può navigare (tool browse_web).'));
    body.appendChild(el('div', 'sb-section', 'Scorciatoie'));
    [['Sofascore tennis', 'https://www.sofascore.com/tennis'],
     ['ATP Tour', 'https://www.atptour.com'],
     ['Tennis Abstract', 'http://www.tennisabstract.com'],
     ['the-odds-api', 'https://the-odds-api.com']].forEach(([label, url]) => {
      const b = el('button', 'sb-item', '🌐 ' + label);
      b.onclick = () => openBrowser(url);
      body.appendChild(b);
    });
    openBrowser('https://www.sofascore.com/tennis');
  }},
  graph: { title: 'Knowledge graph', render: (body) => {
    body.appendChild(el('div', 'sb-note',
      'Il grafo del progetto (graphify): nodi-stella colorati per community, 3D. Trascina per ruotare, scroll per zoom, click su un nodo per il focus.'));
    const b = el('button', 'sb-item', '❂ apri il grafo 3D');
    b.onclick = openGraph3D;
    body.appendChild(b);
    openGraph3D();
  }},
  explorer: { title: 'Esplora progetto', render: (body) => { body.appendChild(buildTree('')); } },
  pipeline: { title: 'Pipeline', render: (body) => {
    body.appendChild(el('div', 'sb-section', 'Live'));
    const scan = el('button', 'sb-cmd', '⚡ scan match live');
    scan.dataset.cmd = 'scan';
    scan.onclick = () => runCommand('scan');
    body.appendChild(scan);
    body.appendChild(el('div', 'sb-note', 'scarica quote fresche (the-odds-api, consuma crediti) e ci fa girare modello + news. Risultati nel tab Segnali.'));
    body.appendChild(el('div', 'sb-section', 'Pipeline dati/modello'));
    ['download', 'clean', 'features', 'train', 'backtest', 'inference', 'signals'].forEach(cmd => {
      const b = el('button', 'sb-cmd', '▶ ' + cmd);
      b.dataset.cmd = cmd;
      b.onclick = () => runCommand(cmd);
      body.appendChild(b);
    });
    const stop = el('button', 'sb-cmd stop', '■ stop');
    stop.onclick = () => { if (runWs && runWs.readyState === 1) runWs.send(JSON.stringify({ type: 'stop' })); };
    body.appendChild(stop);
    body.appendChild(el('div', 'sb-note', 'Output nel tab "Pipeline". Solo comandi whitelisted: il resto passa dai terminali.'));
  }},
  loops: { title: 'Loop autoevolutivi', render: async (body) => {
    body.appendChild(el('div', 'sb-section', 'Cervello'));
    [['EXPERIMENTS.md', 'EXPERIMENTS.md'],
     ['loop notturno', 'scripts/loops/nightly_maintenance.md'],
     ['loop settimanale', 'scripts/loops/weekly_evolution.md'],
     ['storico metriche', 'reports/metrics_history.csv']].forEach(([label, p]) => {
      const b = el('button', 'sb-item', '¶ ' + label);
      b.onclick = () => openFile(p);
      body.appendChild(b);
    });
    body.appendChild(el('div', 'sb-section', 'Log run (reports/loops)'));
    try {
      const logs = await getJSON('/api/loops');
      if (!logs.length) body.appendChild(el('div', 'sb-note', 'nessuna run ancora — nightly 07:13, weekly dom 09:23'));
      logs.slice(0, 25).forEach(l => {
        const b = el('button', 'sb-item', '≡ ' + l.name);
        b.onclick = () => openFile(l.path, true);
        body.appendChild(b);
      });
    } catch (err) { body.appendChild(el('div', 'sb-note', 'errore: ' + err.message)); }
  }},
  docs: { title: 'Documentazione', render: async (body) => {
    body.appendChild(el('div', 'sb-section', 'Radice'));
    ['README.md', 'EXPERIMENTS.md', 'DATA_SOURCES.md', 'docs/ALPHA_FINDINGS.md', 'docs/PROJECT_EVALUATION.md'].forEach(p => {
      const b = el('button', 'sb-item', '¶ ' + p);
      b.onclick = () => openFile(p);
      body.appendChild(b);
    });
    body.appendChild(el('div', 'sb-section', 'Obsidian'));
    try {
      (await getJSON('/api/tree?path=docs/obsidian')).filter(i => !i.dir).forEach(i => {
        const b = el('button', 'sb-item', '¶ ' + i.name);
        b.onclick = () => openFile(i.path);
        body.appendChild(b);
      });
    } catch (err) { body.appendChild(el('div', 'sb-note', 'errore: ' + err.message)); }
  }},
  config: { title: 'Config', render: (body) => {
    const b = el('button', 'sb-item', '⚙ config/config.yaml');
    b.onclick = () => openFile('config/config.yaml');
    body.appendChild(b);
    const b2 = el('button', 'sb-item', '⚙ selected_features_atp.txt');
    b2.onclick = () => openFile('config/selected_features_atp.txt');
    body.appendChild(b2);
    body.appendChild(el('div', 'sb-note', 'config.yaml viene salvato con backup .bak automatico'));
    openFile('config/config.yaml');
  }},
};

function buildTree(path) {
  const wrap = el('div');
  getJSON('/api/tree?path=' + encodeURIComponent(path)).then(items => {
    items.forEach(item => {
      if (item.dir) {
        const dir = el('div', 'tree-dir');
        const btn = el('button', 'sb-item', `<span class="tw">▸</span>🗀 ${item.name}`);
        const children = el('div', 'tree-children');
        children.style.paddingLeft = '14px';
        let loaded = false;
        btn.onclick = () => {
          dir.classList.toggle('open');
          btn.querySelector('.tw').textContent = dir.classList.contains('open') ? '▾' : '▸';
          if (!loaded) { children.appendChild(buildTree(item.path)); loaded = true; }
        };
        dir.appendChild(btn); dir.appendChild(children); wrap.appendChild(dir);
      } else {
        const btn = el('button', 'sb-item', `<span class="tw"></span>· ${item.name}`);
        btn.onclick = () => openFile(item.path);
        wrap.appendChild(btn);
      }
    });
  }).catch(err => wrap.appendChild(el('div', 'sb-note', 'errore: ' + err.message)));
  return wrap;
}

$('#activitybar').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;
  document.querySelectorAll('#activitybar button').forEach(b => b.classList.toggle('active', b === btn));
  const act = ACTS[btn.dataset.act];
  $('#sb-title').textContent = act.title.toUpperCase();
  const body = $('#sb-body');
  body.innerHTML = '';
  act.render(body);
});

/* ================= PIPELINE RUNNER ================= */
let runWs = null;

function pipelinePane() {
  return openTab('panel:pipeline', 'Pipeline', (pane) => {
    pane.innerHTML = `<div class="pane-pad" style="height:100%">
      <div class="toolbar">
        <span class="panel-note" id="pl-status" style="margin:0">pronto</span>
        <button class="btn" id="pl-copy">copia output</button>
      </div>
      <pre class="cli-box" id="pl-out"></pre></div>`;
    pane.querySelector('#pl-copy').onclick = async () => {
      try {
        await navigator.clipboard.writeText($('#pl-out').textContent);
        toast('output copiato negli appunti');
      } catch (err) { toast('copia fallita: ' + err.message, true); }
    };
  });
}

function runCommand(cmd) {
  pipelinePane();
  activateTab('panel:pipeline');
  const out = $('#pl-out'), status = $('#pl-status');
  const send = () => runWs.send(JSON.stringify({ cmd }));
  if (!runWs || runWs.readyState !== 1) {
    runWs = new WebSocket(`ws://${location.host}/ws/run`);
    runWs.onopen = send;
    runWs.onerror = () => { status.textContent = 'errore connessione'; };
    runWs.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === 'start') {
        out.textContent = `$ ${m.cmd}\n`;
        status.textContent = 'in esecuzione: ' + m.cmd;
        document.querySelectorAll('.sb-cmd').forEach(b => b.classList.toggle('running', b.dataset.cmd === m.cmd));
      } else if (m.type === 'line') {
        out.textContent += m.text + '\n'; out.scrollTop = out.scrollHeight;
      } else if (m.type === 'exit') {
        out.textContent += `\n[exit ${m.code}]\n`;
        status.textContent = 'terminato (exit ' + m.code + ')';
        document.querySelectorAll('.sb-cmd').forEach(b => b.classList.remove('running'));
      } else if (m.type === 'error') {
        out.textContent += '[ERRORE] ' + m.detail + '\n'; status.textContent = 'errore';
      }
    };
  } else send();
}

/* ================= TERMINALS ================= */
let termCount = 0;
const terms = {};

$('#term-new-ps').onclick = () => newTerminal('powershell');
$('#term-new-wsl').onclick = () => newTerminal('wsl');

/* --- vibe coding: menu di scelta agente (tmux su WSL) --- */
const VIBE_AGENTS = [
  { id: 'claude',   label: 'Claude Code', color: '#D97757', glyph: '✳' },
  { id: 'opencode', label: 'OpenCode',    color: '#1A1A12', glyph: '>_' },
  { id: 'codex',    label: 'Codex',       color: '#000000', glyph: '⬡' },
  { id: 'hermes',   label: 'Hermes',      color: '#8B6F47', glyph: '⚚' },
  { id: 'agy',      label: 'Antigravity', color: '#FF5A00', glyph: '⊼' },
];

$('#term-new-vibe').onclick = (e) => {
  e.stopPropagation();
  const old = $('.vibe-menu');
  if (old) { old.remove(); return; }
  const menu = el('div', 'vibe-menu');
  VIBE_AGENTS.forEach(a => {
    const item = el('button', 'vibe-item',
      `<span class="vibe-badge" style="background:${a.color}">${a.glyph}</span>
       <span>${a.label}</span><span class="vibe-tmux">tmux:vibe-${a.id}</span>`);
    item.onclick = () => { menu.remove(); newTerminal('wsl', { agent: a.id, label: a.label }); };
    menu.appendChild(item);
  });
  const btn = $('#term-new-vibe').getBoundingClientRect();
  menu.style.left = btn.left + 'px';
  menu.style.bottom = (window.innerHeight - btn.top + 6) + 'px';
  document.body.appendChild(menu);
  const closeOnce = (ev) => {
    if (menu.contains(ev.target)) return;  // click su una voce: lascia arrivare il click
    menu.remove();
    window.removeEventListener('mousedown', closeOnce, true);
  };
  setTimeout(() => window.addEventListener('mousedown', closeOnce, true), 0);
};
$('#term-toggle').onclick = () => {
  $('#termpanel').classList.toggle('collapsed');
  $('#term-toggle').textContent = $('#termpanel').classList.contains('collapsed') ? '▴' : '▾';
  fitActiveTerm();
};

/* --- drag resize del pannello terminale --- */
(() => {
  const resizer = $('#term-resizer'), panel = $('#termpanel');
  let dragging = false;
  resizer.addEventListener('mousedown', (e) => {
    dragging = true;
    resizer.classList.add('dragging');
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'ns-resize';
    e.preventDefault();
  });
  window.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const h = Math.min(Math.max(window.innerHeight - e.clientY, 110), window.innerHeight * 0.85);
    panel.style.flex = `0 0 ${h}px`;
    fitActiveTerm();
  });
  window.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    resizer.classList.remove('dragging');
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    fitActiveTerm();
  });
})();

function newTerminal(shell, opts = {}) {
  $('#termpanel').classList.remove('collapsed');
  const id = 't' + (++termCount);
  const label = opts.agent ? `⚡ ${opts.label || opts.agent}` : `${shell} #${termCount}`;
  const tab = el('div', 'ttab');
  tab.innerHTML = `<span>${label}</span><span class="x">✕</span>`;
  $('#term-tabs').appendChild(tab);
  const pane = el('div', 'tpane');
  pane.innerHTML = '<div style="height:100%"></div>';
  $('#term-panes').appendChild(pane);

  const term = new Terminal({
    fontFamily: '"IBM Plex Mono", "Cascadia Code", monospace', fontSize: 13, cursorBlink: true,
    theme: { background: cssVar('--term-bg'), foreground: cssVar('--term-fg'), cursor: cssVar('--highlight') },
  });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open(pane.firstChild);

  const ws = new WebSocket(`ws://${location.host}/ws/term?shell=${shell}` +
                           (opts.agent ? `&agent=${encodeURIComponent(opts.agent)}` : ''));
  ws.onmessage = (ev) => term.write(ev.data);
  ws.onclose = () => term.write('\r\n[connessione chiusa' +
    (opts.agent ? ` — la sessione tmux vibe-${opts.agent} resta viva in WSL` : '') + ']\r\n');
  term.onData(d => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'input', data: d })); });
  term.onResize(({ cols, rows }) => {
    if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'resize', cols, rows }));
  });
  // copia/incolla: Ctrl+Shift+C copia la selezione, Ctrl+Shift+V incolla
  term.attachCustomKeyEventHandler((ev) => {
    if (ev.type !== 'keydown' || !ev.ctrlKey || !ev.shiftKey) return true;
    if (ev.code === 'KeyC' && term.hasSelection()) {
      navigator.clipboard.writeText(term.getSelection()).then(() => toast('selezione copiata'));
      return false;
    }
    if (ev.code === 'KeyV') {
      navigator.clipboard.readText().then(t => {
        if (t && ws.readyState === 1) ws.send(JSON.stringify({ type: 'input', data: t }));
      });
      return false;
    }
    return true;
  });

  terms[id] = { term, fit, ws, tab, pane };
  tab.addEventListener('click', (e) => {
    if (e.target.classList.contains('x')) closeTerminal(id); else activateTerminal(id);
  });
  activateTerminal(id);
}

function activateTerminal(id) {
  Object.values(terms).forEach(t => { t.tab.classList.remove('active'); t.pane.classList.remove('active'); });
  const t = terms[id];
  if (!t) return;
  t.tab.classList.add('active'); t.pane.classList.add('active');
  requestAnimationFrame(() => { t.fit.fit(); t.term.focus(); });
}

function closeTerminal(id) {
  const t = terms[id];
  if (!t) return;
  try { t.ws.close(); } catch (e) { /* già chiusa */ }
  t.term.dispose(); t.tab.remove(); t.pane.remove();
  delete terms[id];
  const left = Object.keys(terms);
  if (left.length) activateTerminal(left[left.length - 1]);
}

function fitActiveTerm() {
  Object.values(terms).forEach(t => { if (t.pane.classList.contains('active')) t.fit.fit(); });
}
window.addEventListener('resize', fitActiveTerm);

/* ================= BROWSER AGENTICO ================= */
function openBrowser(url) {
  openTab('panel:browser', '🌐 Browser', (pane) => {
    pane.innerHTML = `<div class="browser-host">
      <form class="browser-bar" id="browser-bar">
        <button type="button" class="btn" id="br-back" title="indietro">←</button>
        <input id="br-url" placeholder="url o dominio…" value="${url || ''}">
        <button class="btn primary" type="submit">vai</button>
      </form>
      <div class="browser-view" id="br-view"><div class="panel-note">carico…</div></div>
    </div>`;
    const hist = [];
    const go = async (u) => {
      const view = $('#br-view');
      view.innerHTML = '<div class="panel-note">carico ' + escHtml(u) + '…</div>';
      try {
        const d = await getJSON('/api/browse?url=' + encodeURIComponent(u));
        $('#br-url').value = d.url;
        hist.push(d.url);
        const links = (d.links || []).map(l =>
          `<a href="#" data-href="${escHtml(l.href)}" class="br-link">${escHtml(l.text)}</a>`).join('');
        view.innerHTML = `<h2 class="br-title">${escHtml(d.title)}</h2>
          <div class="br-src">${escHtml(d.url)}</div>
          <pre class="br-text">${escHtml(d.text)}</pre>
          ${links ? '<div class="br-links"><b>Link:</b>' + links + '</div>' : ''}`;
        view.querySelectorAll('.br-link').forEach(a =>
          a.onclick = (e) => { e.preventDefault(); go(a.dataset.href); });
        view.scrollTop = 0;
      } catch (err) {
        view.innerHTML = '<div class="banner">errore: ' + escHtml(err.message) + '</div>';
      }
    };
    $('#browser-bar').onsubmit = (e) => { e.preventDefault(); go($('#br-url').value.trim()); };
    $('#br-back').onclick = () => { hist.pop(); const p = hist.pop(); if (p) go(p); };
    if (url) go(url);
  });
  activateTab('panel:browser');
}

/* ================= GRAPH 3D ================= */
function openGraph3D() {
  openTab('panel:graph3d', '❂ Grafo 3D', (pane) => {
    pane.innerHTML = '<iframe src="/static/graph3d.html" style="width:100%;height:100%;border:none;display:block"></iframe>';
  });
  activateTab('panel:graph3d');
}

/* ================= CHAT AGENT ================= */
let chatWs = null;

function openChat() {
  openTab('panel:chat', '✦ Chat', (pane) => {
    pane.innerHTML = `<div class="chat-host">
      <div class="chat-msgs" id="chat-msgs">
        <div class="chat-msg bot">Sono <b>UnaBettingOS</b> — memoria e intelligenza agentica dell'app (qwen3.5:9b, locale).
Dati live, vault Obsidian, knowledge graph e memoria persistente: chiedimi dei match, del modello, della storia del progetto — o dimmi "ricorda che…".</div>
      </div>
      <form class="chat-form" id="chat-form">
        <input id="chat-input" autocomplete="off" placeholder="scrivi… (Invio per inviare)">
        <button class="btn primary" type="submit">▶</button>
      </form></div>`;
    $('#chat-form').onsubmit = (e) => { e.preventDefault(); sendChat(); };
  });
  activateTab('panel:chat');
}

const escHtml = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/* template strutturati per i risultati dei tool (card animate) */
function chatTemplates(data) {
  let html = '';
  const tm = data.get_today_matches;
  if (tm && tm.matches && tm.matches.length) {
    html += '<div class="chat-cards">' + tm.matches.slice(0, 10).map(m =>
      `<div class="chat-card"><span class="cc-main">🎾 ${escHtml(m.match)}</span>
       <span class="cc-badge">${m.best_quota_p1} / ${m.best_quota_p2}</span></div>`).join('') + '</div>';
  }
  const sg = data.get_signals;
  if (Array.isArray(sg) && sg.length) {
    html += '<div class="chat-cards">' + sg.slice(0, 8).map(s =>
      `<div class="chat-card"><span class="cc-main">${escHtml(s.match)}</span>
       <span class="cc-badge ${s.edge > 0 ? 'pos' : 'neg'}">edge ${(s.edge * 100).toFixed(1)}%</span></div>`).join('') + '</div>';
  }
  const mm = data.get_model_metrics;
  if (mm && mm.current) {
    const c = mm.current;
    html += `<div class="chat-kpis">
      <div class="chat-kpi"><div class="k">Accuracy</div><div class="v">${(c.accuracy * 100).toFixed(1)}%</div></div>
      <div class="chat-kpi"><div class="k">Log loss</div><div class="v">${c.log_loss.toFixed(3)}</div></div>
      <div class="chat-kpi"><div class="k">ROC AUC</div><div class="v">${c.roc_auc.toFixed(3)}</div></div>
      <div class="chat-kpi"><div class="k">vs Mercato</div><div class="v">${(mm.market_baseline * 100).toFixed(1)}%</div></div></div>`;
  }
  const bk = data.get_bankroll;
  if (bk && (bk.bankroll !== undefined)) {
    html += `<div class="chat-kpis">
      <div class="chat-kpi"><div class="k">Bankroll</div><div class="v">${bk.bankroll !== null ? '€' + Number(bk.bankroll).toFixed(0) : '—'}</div></div>
      <div class="chat-kpi"><div class="k">Profit</div><div class="v">€${Number(bk.total_profit || 0).toFixed(1)}</div></div>
      <div class="chat-kpi"><div class="k">Pending</div><div class="v">${bk.bets_open}</div></div>
      <div class="chat-kpi"><div class="k">Decisioni</div><div class="v">${bk.decisions}</div></div></div>`;
  }
  return html;
}

function chatMsg(cls, text, data) {
  const m = el('div', 'chat-msg ' + cls);
  if (cls === 'wait') {
    m.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
  } else if (cls === 'bot') {
    // markdown leggero e sicuro + template card dai dati dei tool
    m.innerHTML = escHtml(text)
      .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      + (data ? chatTemplates(data) : '');
  } else {
    m.textContent = text;
  }
  $('#chat-msgs').appendChild(m);
  $('#chat-msgs').scrollTop = $('#chat-msgs').scrollHeight;
  return m;
}

function ensureChatWs() {
  if (chatWs && chatWs.readyState === 1) return Promise.resolve();
  return new Promise((resolve, reject) => {
    chatWs = new WebSocket(`ws://${location.host}/ws/chat`);
    chatWs.onopen = resolve;
    chatWs.onerror = () => reject(new Error('connessione chat fallita'));
    let pending = null;
    chatWs.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === 'tool') {
        if (m.status === 'start') pending = chatMsg('tool', `⚙ ${m.name} in esecuzione…`);
        else if (pending) { pending.textContent = `⚙ ${m.name} ✓`; pending = null; }
      } else if (m.type === 'reply') {
        document.querySelectorAll('.chat-msg.wait').forEach(x => x.remove());
        chatMsg('bot', m.text, m.data);
      } else if (m.type === 'refresh') {
        toast('dati aggiornati dallo scan — riapri i pannelli per vederli');
        delete loadedPanels['panel:overview'];
      } else if (m.type === 'error') {
        document.querySelectorAll('.chat-msg.wait').forEach(x => x.remove());
        chatMsg('err', 'Errore: ' + m.detail +
          (String(m.detail).includes('11434') ? ' — Ollama è acceso? (ollama serve)' : ''));
      }
    };
    chatWs.onclose = () => { chatWs = null; };
  });
}

async function sendChat() {
  const inp = $('#chat-input');
  const text = inp.value.trim();
  if (!text) return;
  inp.value = '';
  chatMsg('me', text);
  chatMsg('wait', '…');
  try {
    await ensureChatWs();
    chatWs.send(JSON.stringify({ text }));
  } catch (err) {
    document.querySelectorAll('.chat-msg.wait').forEach(x => x.remove());
    chatMsg('err', err.message);
  }
}
const loadedPanels = {};

/* ================= TOAST ================= */
function toast(msg, isErr = false) {
  const t = el('div', 'toast' + (isErr ? ' err' : ''), msg);
  document.body.appendChild(t);
  requestAnimationFrame(() => t.classList.add('show'));
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 400); }, 3500);
}

/* ================= SCREENSHOT (click rotella + selezione) ================= */
let shotActive = false;

window.addEventListener('mousedown', (e) => {
  if (e.button !== 1 || shotActive) return;   // 1 = rotella
  e.preventDefault(); e.stopPropagation();
  startShot(e.clientX, e.clientY);
}, true);
window.addEventListener('auxclick', (e) => { if (e.button === 1) e.preventDefault(); }, true);

function startShot(sx, sy) {
  shotActive = true;
  const ov = el('div', 'shot-overlay');
  const rect = el('div', 'shot-rect');
  const hint = el('div', 'shot-hint', 'trascina per selezionare · Esc annulla');
  ov.appendChild(rect); ov.appendChild(hint);
  document.body.appendChild(ov);
  let cur = { x: sx, y: sy, w: 0, h: 0 };

  const update = (ex, ey) => {
    cur = { x: Math.min(sx, ex), y: Math.min(sy, ey), w: Math.abs(ex - sx), h: Math.abs(ey - sy) };
    rect.style.left = cur.x + 'px'; rect.style.top = cur.y + 'px';
    rect.style.width = cur.w + 'px'; rect.style.height = cur.h + 'px';
  };
  update(sx, sy);

  const onMove = (e) => update(e.clientX, e.clientY);
  const onUp = () => { cleanup(); captureShot(cur); };
  const onKey = (e) => { if (e.key === 'Escape') { cleanup(); shotActive = false; } };
  function cleanup() {
    window.removeEventListener('mousemove', onMove, true);
    window.removeEventListener('mouseup', onUp, true);
    window.removeEventListener('keydown', onKey, true);
    ov.remove();
  }
  window.addEventListener('mousemove', onMove, true);
  window.addEventListener('mouseup', onUp, true);
  window.addEventListener('keydown', onKey, true);
}

async function captureShot(r) {
  if (r.w < 3 || r.h < 3) { shotActive = false; return; }
  // wait two frames so the overlay is really gone before the screen grab
  await new Promise(res => requestAnimationFrame(() => requestAnimationFrame(res)));
  await new Promise(res => setTimeout(res, 80));
  try {
    const resp = await fetch('/api/screenshot', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ x: r.x, y: r.y, w: r.w, h: r.h, dpr: window.devicePixelRatio }),
    });
    const d = await resp.json();
    if (!resp.ok) throw new Error(d.detail || d.error);
    toast(`screenshot ${d.clipboard ? 'copiato negli appunti' : 'salvato'} · ${d.path}`);
  } catch (err) {
    toast('screenshot fallito: ' + err.message, true);
  } finally {
    shotActive = false;
  }
}

/* ================= BOOT ================= */
const themeSel = $('#theme-sel');
themeSel.innerHTML = THEMES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
themeSel.onchange = () => applyTheme(themeSel.value);
const savedTheme = localStorage.getItem('mc-theme') || 'hermes';
themeSel.value = savedTheme;
document.documentElement.dataset.theme = savedTheme;
refreshThemeColors();

ACTS.cockpit.render($('#sb-body'));
openPanel('overview');
