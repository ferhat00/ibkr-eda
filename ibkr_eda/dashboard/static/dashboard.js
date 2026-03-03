/* IBKR Trade Dashboard — Frontend Logic */

const DARK = {
  bg: '#0d1117',
  card: '#161b22',
  grid: '#21262d',
  text: '#c9d1d9',
  muted: '#8b949e',
  green: '#00c853',
  red: '#ff1744',
  blue: '#58a6ff',
};

const PLOTLY_LAYOUT = {
  paper_bgcolor: DARK.card,
  plot_bgcolor: DARK.card,
  font: { color: DARK.text, family: 'Inter, sans-serif', size: 12 },
  margin: { t: 10, r: 15, b: 40, l: 60 },
  xaxis: { gridcolor: DARK.grid, zerolinecolor: DARK.grid },
  yaxis: { gridcolor: DARK.grid, zerolinecolor: DARK.grid },
  showlegend: false,
};

const PLOTLY_CONFIG = { responsive: true, displayModeBar: false };

const state = {
  filters: {},
  tablePage: 1,
  tablePageSize: 50,
  tableSortBy: 'trade_time',
  tableSortDir: 'desc',
  symbolView: 'pnl',
  symbolData: null,
};

// ─── Utilities ────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

function fmt(v, prefix = '', suffix = '', decimals = 2) {
  if (v == null) return '--';
  const n = Number(v);
  if (isNaN(n)) return '--';
  const abs = Math.abs(n);
  let s;
  if (abs >= 1e6) s = (n / 1e6).toFixed(1) + 'M';
  else if (abs >= 1e3) s = n.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  else s = n.toFixed(decimals);
  return prefix + s + suffix;
}

function pnlClass(v) {
  if (v == null) return '';
  return v > 0 ? 'text-profit' : v < 0 ? 'text-loss' : '';
}

function showToast(msg, type = 'danger') {
  const c = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `alert alert-${type} alert-dismissible fade show`;
  el.style.minWidth = '300px';
  el.innerHTML = `${msg}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
  c.appendChild(el);
  setTimeout(() => el.remove(), 6000);
}

function makeLayout(overrides = {}) {
  return { ...PLOTLY_LAYOUT, ...overrides };
}

// ─── Filter UI ────────────────────────────────────────────────────────────

function populateCheckboxes(containerId, values, group) {
  const el = document.getElementById(containerId);
  el.innerHTML = values.map(v =>
    `<div class="form-check">
      <input class="form-check-input" type="checkbox" value="${v}" id="f-${group}-${v}" data-filter-group="${group}" checked>
      <label class="form-check-label" for="f-${group}-${v}">${v}</label>
    </div>`
  ).join('');
}

function populateFilters(opts) {
  if (!opts) return;
  populateCheckboxes('filter-sec-type', opts.sec_types || [], 'sec_type');
  populateCheckboxes('filter-country', opts.countries || [], 'country');
  populateCheckboxes('filter-currency', opts.currencies || [], 'currency');
  populateCheckboxes('filter-exchange', opts.exchanges || [], 'exchange');
  populateCheckboxes('filter-side', opts.sides || [], 'side');

  const dl = document.getElementById('symbol-list');
  dl.innerHTML = (opts.symbols || []).map(s => `<option value="${s}">`).join('');
}

function collectFilters() {
  const f = {};
  const start = document.getElementById('filter-start').value;
  const end = document.getElementById('filter-end').value;
  if (start) f.start_date = start;
  if (end) f.end_date = end;

  for (const group of ['sec_type', 'country', 'currency', 'exchange', 'side']) {
    const checked = [...document.querySelectorAll(`input[data-filter-group="${group}"]:checked`)].map(i => i.value);
    const all = [...document.querySelectorAll(`input[data-filter-group="${group}"]`)];
    if (checked.length > 0 && checked.length < all.length) {
      f[group] = checked.join(',');
    }
  }

  const sym = document.getElementById('filter-symbol').value.trim();
  if (sym) f.symbol = sym;

  state.filters = f;
  return f;
}

function buildParams() {
  const f = state.filters;
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) p.set(k, v);
  return '?' + p.toString();
}

function resetFilters() {
  document.getElementById('filter-start').value = '';
  document.getElementById('filter-end').value = '';
  document.getElementById('filter-symbol').value = '';
  document.querySelectorAll('.filter-group input[type="checkbox"], #filter-side input[type="checkbox"]').forEach(cb => cb.checked = true);
  state.filters = {};
  state.tablePage = 1;
  refreshAll();
}

// ─── Data Loading ─────────────────────────────────────────────────────────

async function reloadData() {
  const source = document.querySelector('input[name="data_source"]:checked').value;
  const btn = document.getElementById('btn-reload');
  const text = document.getElementById('reload-text');
  const spinner = document.getElementById('reload-spinner');

  btn.disabled = true;
  text.textContent = 'Loading...';
  spinner.classList.remove('d-none');

  try {
    const resp = await fetch('/api/reload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source }),
    });
    const data = await resp.json();
    if (data.ok) {
      showToast(data.message, 'success');
      await init();
    } else {
      showToast(data.error || 'Reload failed');
    }
  } catch (e) {
    showToast('Reload failed: ' + e.message);
  } finally {
    btn.disabled = false;
    text.textContent = 'Reload Data';
    spinner.classList.add('d-none');
  }
}

// ─── Summary Cards ────────────────────────────────────────────────────────

function renderSummary(d) {
  const set = (id, val, cls = '') => {
    const el = document.getElementById(id);
    el.textContent = val;
    el.className = 'metric-value ' + cls;
  };
  const sub = (id, val) => { document.getElementById(id).textContent = val; };

  set('mc-pnl', fmt(d.total_pnl, '$'), pnlClass(d.total_pnl));
  sub('mc-pnl-sub', `Comm: ${fmt(d.total_commission, '$')}`);

  set('mc-winrate', fmt(d.win_rate, '', '%', 1), d.win_rate > 50 ? 'text-profit' : 'text-loss');
  sub('mc-winrate-sub', `${d.buys} buys / ${d.sells} sells`);

  set('mc-pf', fmt(d.profit_factor, '', '', 2), d.profit_factor > 1 ? 'text-profit' : 'text-loss');
  sub('mc-pf-sub', `R/R: ${fmt(d.reward_risk, '', '', 2)}`);

  set('mc-sharpe', fmt(d.sharpe, '', '', 2));
  sub('mc-sharpe-sub', `Avg: ${fmt(d.avg_pnl_per_trade, '$')}/trade`);

  set('mc-dd', fmt(d.max_drawdown, '$'), 'text-loss');
  sub('mc-dd-sub', `Worst: ${fmt(d.largest_loss, '$')}`);

  set('mc-trades', d.total_trades != null ? d.total_trades.toLocaleString() : '--');
  sub('mc-trades-sub', `Best: ${fmt(d.largest_win, '$')}`);
}

// ─── Charts ───────────────────────────────────────────────────────────────

function renderCumPnl(data) {
  if (!data.timestamps.length) {
    Plotly.purge('chart-cum-pnl');
    document.getElementById('chart-cum-pnl').innerHTML = '<div class="loading-spinner">No data</div>';
    return;
  }
  const traces = [
    {
      x: data.timestamps, y: data.cum_pnl, type: 'scatter', mode: 'lines',
      name: 'Cumulative P&L', line: { color: DARK.green, width: 2 },
      xaxis: 'x', yaxis: 'y',
    },
    {
      x: data.timestamps, y: data.running_max, type: 'scatter', mode: 'lines',
      name: 'High Water Mark', line: { color: DARK.muted, width: 1, dash: 'dot' },
      xaxis: 'x', yaxis: 'y',
    },
    {
      x: data.timestamps, y: data.drawdown, type: 'scatter',
      fill: 'tozeroy', fillcolor: 'rgba(255,23,68,0.25)',
      line: { color: DARK.red, width: 1 },
      name: 'Drawdown', xaxis: 'x', yaxis: 'y2',
    },
  ];
  const layout = makeLayout({
    height: 380,
    grid: { rows: 2, columns: 1, pattern: 'independent', roworder: 'top to bottom' },
    xaxis: { gridcolor: DARK.grid, showgrid: false },
    yaxis: { gridcolor: DARK.grid, tickprefix: '$', tickformat: ',.0f', domain: [0.35, 1] },
    xaxis2: { gridcolor: DARK.grid, showgrid: false },
    yaxis2: { gridcolor: DARK.grid, tickprefix: '$', tickformat: ',.0f', domain: [0, 0.28] },
    showlegend: true,
    legend: { orientation: 'h', y: 1.06, font: { size: 10 } },
    margin: { t: 30, r: 15, b: 30, l: 70 },
  });
  Plotly.newPlot('chart-cum-pnl', traces, layout, PLOTLY_CONFIG);
}

function renderPnlDist(data) {
  if (!data.values.length) {
    Plotly.purge('chart-pnl-dist');
    document.getElementById('chart-pnl-dist').innerHTML = '<div class="loading-spinner">No data</div>';
    return;
  }
  const winners = data.values.filter(v => v >= 0);
  const losers = data.values.filter(v => v < 0);
  const traces = [
    { x: winners, type: 'histogram', name: 'Winners', marker: { color: DARK.green }, opacity: 0.85, nbinsx: 30 },
    { x: losers, type: 'histogram', name: 'Losers', marker: { color: DARK.red }, opacity: 0.85, nbinsx: 30 },
  ];
  const layout = makeLayout({
    height: 320, barmode: 'overlay',
    xaxis: { gridcolor: DARK.grid, tickprefix: '$' },
    yaxis: { gridcolor: DARK.grid, title: { text: 'Count', font: { size: 11 } } },
    showlegend: true,
    legend: { orientation: 'h', y: 1.08, font: { size: 10 } },
    margin: { t: 25, r: 10, b: 40, l: 50 },
  });
  Plotly.newPlot('chart-pnl-dist', traces, layout, PLOTLY_CONFIG);
}

function renderSymbol(data) {
  state.symbolData = data;
  _drawSymbol();
}

function _drawSymbol() {
  const data = state.symbolData;
  if (!data) return;
  const view = state.symbolView;
  const d = view === 'pnl' ? data.by_pnl : data.by_count;
  const values = view === 'pnl' ? d.pnl : d.counts;
  const colors = view === 'pnl'
    ? d.pnl.map(v => v >= 0 ? DARK.green : DARK.red)
    : d.counts.map(() => DARK.blue);

  const h = Math.max(320, d.symbols.length * 20);
  document.getElementById('chart-symbol').style.height = h + 'px';

  const traces = [{
    y: d.symbols, x: values, type: 'bar', orientation: 'h',
    marker: { color: colors },
    text: values.map(v => view === 'pnl' ? fmt(v, '$') : v),
    textposition: 'outside', textfont: { size: 10, color: DARK.muted },
  }];
  const layout = makeLayout({
    height: h,
    xaxis: { gridcolor: DARK.grid, tickprefix: view === 'pnl' ? '$' : '', tickformat: view === 'pnl' ? ',.0f' : '' },
    yaxis: { gridcolor: DARK.grid, autorange: view === 'pnl' ? true : 'reversed', tickfont: { size: 11 } },
    margin: { t: 5, r: 60, b: 30, l: 80 },
  });
  Plotly.newPlot('chart-symbol', traces, layout, PLOTLY_CONFIG);
}

window.switchSymbolView = function(view) {
  state.symbolView = view;
  document.getElementById('sym-btn-pnl').classList.toggle('active', view === 'pnl');
  document.getElementById('sym-btn-count').classList.toggle('active', view === 'count');
  _drawSymbol();
};

function renderBarChart(elId, labels, values, opts = {}) {
  const colors = opts.colorBySign
    ? values.map(v => v >= 0 ? DARK.green : DARK.red)
    : values.map(() => opts.color || DARK.blue);
  const traces = [{ x: labels, y: values, type: 'bar', marker: { color: colors } }];
  const layout = makeLayout({
    height: opts.height || 280,
    xaxis: { gridcolor: DARK.grid, tickfont: { size: 10 }, ...(opts.xaxis || {}) },
    yaxis: { gridcolor: DARK.grid, tickprefix: opts.tickprefix || '', tickformat: opts.tickformat || '', ...(opts.yaxis || {}) },
    margin: { t: 10, r: 10, b: 50, l: 55 },
  });
  Plotly.newPlot(elId, traces, layout, PLOTLY_CONFIG);
}

function renderTimePatterns(data) {
  renderBarChart('chart-hour', data.by_hour.hours, data.by_hour.pnl,
    { colorBySign: true, tickprefix: '$', tickformat: ',.0f' });
  renderBarChart('chart-weekday', data.by_weekday.days.map(d => d.slice(0, 3)), data.by_weekday.pnl,
    { colorBySign: true, tickprefix: '$', tickformat: ',.0f' });
  renderBarChart('chart-month', data.by_month.months, data.by_month.pnl,
    { colorBySign: true, tickprefix: '$', tickformat: ',.0f', xaxis: { tickangle: -45, tickfont: { size: 9 } } });
}

function renderDonut(elId, labels, values, height = 300) {
  if (!labels.length) {
    Plotly.purge(elId);
    document.getElementById(elId).innerHTML = '<div class="loading-spinner">No data</div>';
    return;
  }
  const traces = [{
    labels, values, type: 'pie', hole: 0.45,
    textinfo: 'label+percent', textposition: 'outside',
    textfont: { size: 10, color: DARK.text },
    marker: { line: { color: DARK.card, width: 2 } },
  }];
  const layout = makeLayout({
    height,
    showlegend: false,
    margin: { t: 10, r: 10, b: 10, l: 10 },
  });
  Plotly.newPlot(elId, traces, layout, PLOTLY_CONFIG);
}

function renderMarketBreakdown(data) {
  renderDonut('chart-country', data.by_country.labels, data.by_country.counts);
  renderDonut('chart-currency', data.by_currency.labels, data.by_currency.counts);
  renderBarChart('chart-sec-type', data.by_sec_type.labels, data.by_sec_type.counts,
    { color: DARK.blue, height: 300 });
}

function renderCommission(data) {
  if (data.values.length) {
    const traces = [{
      x: data.values, type: 'histogram', marker: { color: DARK.blue }, nbinsx: 30,
    }];
    const layout = makeLayout({
      height: 280,
      xaxis: { gridcolor: DARK.grid, tickprefix: '$', title: { text: 'Commission', font: { size: 11 } } },
      yaxis: { gridcolor: DARK.grid, title: { text: 'Count', font: { size: 11 } } },
      margin: { t: 10, r: 10, b: 50, l: 50 },
    });
    Plotly.newPlot('chart-comm-dist', traces, layout, PLOTLY_CONFIG);
  }

  const sym = data.by_symbol;
  if (sym.symbols.length) {
    const traces = [{
      y: sym.symbols, x: sym.total_comm, type: 'bar', orientation: 'h',
      marker: { color: DARK.blue },
      text: sym.total_comm.map(v => fmt(v, '$')),
      textposition: 'outside', textfont: { size: 10, color: DARK.muted },
    }];
    const h = Math.max(280, sym.symbols.length * 22);
    document.getElementById('chart-comm-sym').style.height = h + 'px';
    const layout = makeLayout({
      height: h,
      xaxis: { gridcolor: DARK.grid, tickprefix: '$', tickformat: ',.0f' },
      yaxis: { gridcolor: DARK.grid, autorange: 'reversed', tickfont: { size: 11 } },
      margin: { t: 5, r: 55, b: 30, l: 80 },
    });
    Plotly.newPlot('chart-comm-sym', traces, layout, PLOTLY_CONFIG);
  }
}

// ─── Trade Table ──────────────────────────────────────────────────────────

const COL_LABELS = {
  trade_time: 'Time', symbol: 'Symbol', sec_type: 'Type', side: 'Side',
  quantity: 'Qty', price: 'Price', notional: 'Notional',
  commission: 'Comm', realized_pnl: 'P&L', exchange: 'Exchange',
  country: 'Country', currency: 'CCY',
};

function renderTable(data) {
  document.getElementById('table-row-count').textContent = `${data.total_rows.toLocaleString()} rows`;

  // Header
  const thead = document.getElementById('table-head');
  thead.innerHTML = '<tr>' + data.columns.map(c => {
    const active = state.tableSortBy === c;
    const arrow = active ? (state.tableSortDir === 'asc' ? ' &#9650;' : ' &#9660;') : '';
    return `<th onclick="sortTable('${c}')">${COL_LABELS[c] || c}${arrow}</th>`;
  }).join('') + '</tr>';

  // Body
  const tbody = document.getElementById('table-body');
  const pnlIdx = data.columns.indexOf('realized_pnl');
  const sideIdx = data.columns.indexOf('side');
  const numCols = new Set(['quantity', 'price', 'notional', 'commission', 'realized_pnl']);

  tbody.innerHTML = data.rows.map(row => {
    const cells = row.map((v, i) => {
      const col = data.columns[i];
      let cls = '';
      let display = v;
      if (col === 'realized_pnl' && v != null) {
        cls = Number(v) > 0 ? 'text-profit' : Number(v) < 0 ? 'text-loss' : '';
        display = fmt(v, '$');
      } else if (col === 'side') {
        cls = v === 'BUY' || v === 'BOT' ? 'text-profit' : 'text-loss';
      } else if (numCols.has(col) && v != null && v !== '') {
        display = fmt(v, col === 'commission' || col === 'notional' ? '$' : '', '', col === 'price' ? 4 : 2);
      }
      return `<td class="${cls}">${display}</td>`;
    });
    return '<tr>' + cells.join('') + '</tr>';
  }).join('');

  // Pagination
  const totalPages = Math.ceil(data.total_rows / data.page_size) || 1;
  const pag = document.getElementById('table-pagination');
  pag.innerHTML = `
    <span class="text-muted small">Page ${data.page} of ${totalPages}</span>
    <div class="btn-group btn-group-sm">
      <button class="btn btn-outline-secondary" ${data.page <= 1 ? 'disabled' : ''} onclick="goPage(${data.page - 1})">Prev</button>
      <button class="btn btn-outline-secondary" ${data.page >= totalPages ? 'disabled' : ''} onclick="goPage(${data.page + 1})">Next</button>
    </div>
  `;
}

window.sortTable = function(col) {
  if (state.tableSortBy === col) {
    state.tableSortDir = state.tableSortDir === 'asc' ? 'desc' : 'asc';
  } else {
    state.tableSortBy = col;
    state.tableSortDir = col === 'trade_time' ? 'desc' : 'asc';
  }
  state.tablePage = 1;
  fetchTable();
};

window.goPage = function(p) {
  state.tablePage = p;
  fetchTable();
};

async function fetchTable() {
  const params = buildParams()
    + `&page=${state.tablePage}&page_size=${state.tablePageSize}`
    + `&sort_by=${state.tableSortBy}&sort_dir=${state.tableSortDir}`;
  try {
    const data = await fetchJSON('/api/trades' + params);
    renderTable(data);
  } catch (e) {
    console.error('Table fetch failed:', e);
  }
}

// ─── Orchestration ────────────────────────────────────────────────────────

async function refreshAll() {
  const params = buildParams();
  try {
    const [summary, cumPnl, pnlDist, symbolData, timeData, commData, marketData] = await Promise.all([
      fetchJSON('/api/summary' + params),
      fetchJSON('/api/charts/cumulative-pnl' + params),
      fetchJSON('/api/charts/pnl-distribution' + params),
      fetchJSON('/api/charts/symbol-breakdown' + params + '&top_n=25'),
      fetchJSON('/api/charts/time-patterns' + params),
      fetchJSON('/api/charts/commission' + params),
      fetchJSON('/api/charts/market-breakdown' + params),
    ]);
    renderSummary(summary);
    renderCumPnl(cumPnl);
    renderPnlDist(pnlDist);
    renderSymbol(symbolData);
    renderTimePatterns(timeData);
    renderCommission(commData);
    renderMarketBreakdown(marketData);
    fetchTable();
  } catch (e) {
    console.error('Refresh failed:', e);
    showToast('Failed to load dashboard data: ' + e.message);
  }
}

async function init() {
  try {
    const status = await fetchJSON('/api/status');
    if (status.error) {
      showToast('Data load error: ' + status.error);
    }
    if (status.loaded) {
      const pill = document.getElementById('status-pill');
      const src = status.source.startsWith('csv:') ? 'CSV' : 'Live';
      pill.textContent = `${status.row_count.toLocaleString()} rows | ${src} | ${status.date_range[0]} to ${status.date_range[1]}`;
      populateFilters(status.filter_options);
      if (status.date_range) {
        document.getElementById('filter-start').value = status.date_range[0];
        document.getElementById('filter-end').value = status.date_range[1];
      }
      state.filters = {};
      await refreshAll();
    } else {
      document.getElementById('status-pill').textContent = 'No data loaded';
    }
  } catch (e) {
    console.error('Init failed:', e);
    showToast('Failed to connect to server: ' + e.message);
  }
}

// ─── Event Listeners ──────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btn-apply').addEventListener('click', () => {
    collectFilters();
    state.tablePage = 1;
    refreshAll();
  });
  document.getElementById('btn-reset').addEventListener('click', resetFilters);
  document.getElementById('btn-reload').addEventListener('click', reloadData);
  document.getElementById('btn-reload-nav').addEventListener('click', reloadData);

  init();
});
