let searchView = localStorage.getItem('searchView') || 'card';
let compareView = localStorage.getItem('compareView') || 'columns';
let lastSearchData = null;
let lastCompareData = null;
let lastSeasonCompareData = null;
let currentSeason = null;

function updateSearchViewButtons() {
  document.querySelectorAll('#searchViewSwitch .view-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.view === searchView);
  });
}
function updateCompareViewButtons() {
  document.querySelectorAll('#compareViewSwitch .view-btn, #seasonCompareViewSwitch .view-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.view === compareView);
  });
}
function switchSearchView(view) {
  searchView = view;
  localStorage.setItem('searchView', view);
  updateSearchViewButtons();
  if (lastSearchData) renderSearchResults();
}
function switchCompareView(view) {
  compareView = view;
  localStorage.setItem('compareView', view);
  updateCompareViewButtons();
  if (lastCompareData) renderCompare(lastCompareData);
  if (lastSeasonCompareData) filterScResults();
}

function renderSearchResults() {
  const box = document.getElementById('results');
  const data = lastSearchData;
  if (!data || !data.results.length) {
    box.innerHTML = '<div class="empty">没有匹配的条款，换个关键词试试</div>';
    return;
  }
  if (searchView === 'group') box.innerHTML = renderGroupView(data);
  else if (searchView === 'table') box.innerHTML = renderTableView(data);
  else box.innerHTML = renderCardView(data);
}

function renderCardView(data) {
  return data.results.map(r => {
    const rawBlock = r.cleaned
      ? '<button class="raw-toggle" type="button" data-id="' + r.id + '">显示原文</button><div class="raw-box hidden"></div>'
      : '';
    const sectionHtml = r.section ? '<span class="section">' + escHtml(r.section) + '</span>' : '';
    return '<div class="card" data-doc="' + r.doc_id + '" data-page="' + r.page + '" data-title="' + escHtml(r.clause_no + ' ' + r.title) + '" style="cursor:pointer;" title="点击查看 PDF 原文">' +
      '<div class="card-head">' +
        '<span class="no">' + r.clause_no + '</span>' +
        '<span class="title">' + r.title + '</span>' +
        sectionHtml +
        '<span class="meta">' + (r.season ? r.season + ' · ' : '') + r.doc_type + ' · ' + r.version + ' · 第 ' + r.page + ' 页</span>' +
      '</div>' +
      '<p class="snippet">' + r.snippet + '</p>' +
      rawBlock +
    '</div>';
  }).join('');
}

function renderGroupView(data) {
  const sections = data.sections || {};
  const groups = {};
  for (const r of data.results) {
    const top = (r.clause_no || '').split('.')[0];
    (groups[top] = groups[top] || []).push(r);
  }
  const keys = Object.keys(groups).sort((a, b) => (parseInt(a) || 0) - (parseInt(b) || 0));
  let html = '';
  for (const k of keys) {
    const t = sections[k];
    const head = t ? (k + ' ' + t) : ('第 ' + k + ' 章');
    html += '<div class="group"><div class="group-head"><span>' + head + '</span><span class="cnt">' + groups[k].length + ' 条命中</span></div>';
    for (const r of groups[k]) {
      const rawBlock = r.cleaned
        ? '<button class="raw-toggle" type="button" data-id="' + r.id + '">显示原文</button><div class="raw-box hidden"></div>'
        : '';
      html += '<div class="group-item" data-doc="' + r.doc_id + '" data-page="' + r.page + '" data-title="' + escHtml(r.clause_no + ' ' + r.title) + '" style="cursor:pointer;" title="点击查看 PDF 原文"><span class="gno">' + r.clause_no + '</span> <span class="gtitle">' + r.title + '</span>' +
        '<span class="gmeta">' + (r.season ? r.season + ' · ' : '') + r.doc_type + ' · ' + r.version + '</span>' +
        '<div class="gsnippet">' + r.snippet + '</div>' + rawBlock + '</div>';
    }
    html += '</div>';
  }
  return html;
}

function renderTableView(data) {
  let html = '<table class="search-table"><thead><tr><th>条款</th><th>标题</th><th>内容</th><th>来源</th></tr></thead><tbody>';
  for (const r of data.results) {
    const rawBlock = r.cleaned
      ? '<button class="raw-toggle" type="button" data-id="' + r.id + '">显示原文</button><div class="raw-box hidden"></div>'
      : '';
    html += '<tr data-doc="' + r.doc_id + '" data-page="' + r.page + '" data-title="' + escHtml(r.clause_no + ' ' + r.title) + '" style="cursor:pointer;" title="点击查看 PDF 原文"><td class="tno">' + r.clause_no + '</td><td>' + r.title + '</td><td>' + r.snippet + rawBlock + '</td><td class="tmeta">' + (r.season ? r.season + ' · ' : '') + r.doc_type + ' · ' + r.version + '</td></tr>';
  }
  html += '</tbody></table>';
  return html;
}

let selectedVersions = null;

function updateVerBtn() {
  const btn = document.getElementById('verBtn');
  btn.textContent = (!selectedVersions || selectedVersions.size === 0) ? '版本' : ('版本 ' + selectedVersions.size + ' 个');
}

async function onDocChange() {
  selectedVersions = null;
  updateVerBtn();
  await loadVerOptions();
  doSearch();
}

async function loadVerOptions() {
  const doc = document.getElementById('searchDoc').value;
  const panel = document.getElementById('verPanel');
  if (!doc) {
    panel.innerHTML = '<div style="font-size:12px;color:var(--muted);padding:4px 0;">请先选文档类型</div>';
    window.verList = [];
    return;
  }
  const p = doc.split('|');
  const resp = await fetch('/api/versions?season=' + encodeURIComponent(currentSeason || '') + '&event=' + encodeURIComponent(p[0]) + '&doc_type=' + encodeURIComponent(p[1]));
  const data = await resp.json();
  window.verList = data.versions;
  renderVerPanel();
}

function renderVerPanel() {
  const panel = document.getElementById('verPanel');
  const sel = selectedVersions || new Set(window.verList);
  let html = window.verList.map(v =>
    '<label><input type="checkbox" value="' + v + '" ' + (sel.has(v) ? 'checked' : '') + ' onchange="onVerChange()"> ' + v + '</label>'
  ).join('');
  html += '<div class="ver-actions"><span onclick="verAll()">全选</span><span onclick="verNone()">清空</span></div>';
  panel.innerHTML = html;
}

function onVerChange() {
  const checked = Array.from(document.querySelectorAll('#verPanel input:checked')).map(b => b.value);
  selectedVersions = (checked.length === window.verList.length) ? null : new Set(checked);
  updateVerBtn();
}

function verAll() { selectedVersions = null; renderVerPanel(); updateVerBtn(); }
function verNone() { selectedVersions = new Set(); renderVerPanel(); updateVerBtn(); }
function toggleVerPanel() { document.getElementById('verPanel').classList.toggle('hidden'); }

document.addEventListener('click', function(e) {
  const wrap = document.querySelector('.ver-select');
  const panel = document.getElementById('verPanel');
  if (wrap && panel && !wrap.contains(e.target)) {
    panel.classList.add('hidden');
  }
});

async function loadSeasons() {
  const resp = await fetch('/api/seasons');
  const data = await resp.json();
  const seasons = data.seasons || [];
  if (!seasons.length) return;
  currentSeason = seasons[0];  // 最新赛季在前
  const opts = seasons.map(s => '<option value="' + s + '">' + s + ' 赛季</option>').join('');
  document.getElementById('seasonSelect').innerHTML = opts;
  document.getElementById('cmpSeason').innerHTML = opts;
  document.getElementById('tocSeason').innerHTML = opts;
  await loadDoctypes();
}

function onSeasonChange() {
  const sel = document.getElementById('seasonSelect').value;
  const cmp = document.getElementById('cmpSeason').value;
  const s = (sel !== currentSeason) ? sel : cmp;
  if (!s || s === currentSeason) return;
  currentSeason = s;
  document.getElementById('seasonSelect').value = s;
  document.getElementById('cmpSeason').value = s;
  selectedVersions = null;
  updateVerBtn();
  loadDoctypes();
  doSearch();
}

async function loadDoctypes() {
  const resp = await fetch('/api/doctypes?season=' + encodeURIComponent(currentSeason || ''));
  const data = await resp.json();
  const evName = { RMUC: '超级对抗赛', RMUL: '高校联盟赛' };
  const opts = data.doctypes.map(d =>
    '<option value="' + d.event + '|' + d.doc_type + '">' + (evName[d.event] || d.event) + ' · ' + d.doc_type + '</option>'
  ).join('');
  document.getElementById('searchDoc').innerHTML = '<option value="">全部文档</option>' + opts;
  document.getElementById('cmpDoc').innerHTML = opts;
  document.getElementById('tocDoc').innerHTML = opts;
  const rulesOpt = Array.from(document.getElementById('cmpDoc').options).find(o => o.textContent.includes('比赛规则手册'));
  if (rulesOpt) document.getElementById('cmpDoc').value = rulesOpt.value;
  const tocRulesOpt = Array.from(document.getElementById('tocDoc').options).find(o => o.textContent.includes('比赛规则手册'));
  if (tocRulesOpt) document.getElementById('tocDoc').value = tocRulesOpt.value;
  loadVersions();
}

function switchTab(tab) {
  document.getElementById('searchView').classList.toggle('hidden', tab !== 'search');
  document.getElementById('compareView').classList.toggle('hidden', tab !== 'compare');
  document.getElementById('seasonCompareView').classList.toggle('hidden', tab !== 'seasonCompare');
  document.getElementById('tocView').classList.toggle('hidden', tab !== 'toc');
  document.getElementById('tabSearch').classList.toggle('active', tab === 'search');
  document.getElementById('tabCompare').classList.toggle('active', tab === 'compare');
  document.getElementById('tabSeasonCompare').classList.toggle('active', tab === 'seasonCompare');
  document.getElementById('tabToc').classList.toggle('active', tab === 'toc');
  if (tab === 'compare') loadVersions();
  if (tab === 'seasonCompare') loadScDoc();
  if (tab === 'toc') loadToc();
  history.replaceState(null, '', '#' + tab);
}

// ===== 目录浏览 =====
let tocData = null;
let tocDetailData = null;

async function onTocSeasonChange() {
  const season = document.getElementById('tocSeason').value;
  const resp = await fetch('/api/doctypes?season=' + encodeURIComponent(season));
  const data = await resp.json();
  const evName = { RMUC: '超级对抗赛', RMUL: '高校联盟赛' };
  const opts = data.doctypes.map(d =>
    '<option value="' + d.event + '|' + d.doc_type + '">' + (evName[d.event] || d.event) + ' · ' + d.doc_type + '</option>'
  ).join('');
  const sel = document.getElementById('tocDoc');
  sel.innerHTML = opts;
  const rulesOpt = Array.from(sel.options).find(o => o.textContent.includes('比赛规则手册'));
  if (rulesOpt) sel.value = rulesOpt.value;
  loadToc();
}

async function loadToc() {
  const doc = document.getElementById('tocDoc').value;
  const tree = document.getElementById('tocTree');
  if (!doc) { tree.innerHTML = '<div class="empty">请先选择文档</div>'; return; }
  const p = doc.split('|');
  const season = document.getElementById('tocSeason').value || currentSeason || '';
  tree.innerHTML = '<div class="empty">加载目录中…</div>';
  const resp = await fetch('/api/toc?season=' + encodeURIComponent(season) + '&event=' + encodeURIComponent(p[0]) + '&doc_type=' + encodeURIComponent(p[1]));
  const data = await resp.json();
  tocData = data;
  renderTocTree();
}

function renderTocTree() {
  const tree = document.getElementById('tocTree');
  if (!tocData || !tocData.toc.length) { tree.innerHTML = '<div class="empty">该文档无目录数据</div>'; return; }
  tree.innerHTML = tocData.toc.map(renderTocNode).join('');
}

function renderTocNode(node) {
  const hasChildren = node.children && node.children.length > 0;
  const toggle = hasChildren ? '<span class="toc-toggle">▸</span>' : '<span class="toc-toggle toc-toggle-empty"></span>';
  const children = hasChildren ? '<div class="toc-children">' + node.children.map(renderTocNode).join('') + '</div>' : '';
  return '<div class="toc-node-wrap">' +
    '<div class="toc-node" data-id="' + node.id + '" data-no="' + escHtml(node.no) + '">' +
      toggle +
      '<span class="tno">' + escHtml(node.no) + '</span>' +
      '<span class="ttitle">' + escHtml(node.title) + '</span>' +
    '</div>' +
    children +
  '</div>';
}

document.getElementById('tocTree').addEventListener('click', function(e) {
  const toggle = e.target.closest('.toc-toggle');
  if (toggle) {
    const wrap = toggle.closest('.toc-node-wrap');
    const children = wrap ? wrap.querySelector(':scope > .toc-children') : null;
    if (children) {
      const show = children.classList.contains('hidden');
      children.classList.toggle('hidden', !show);
      toggle.textContent = show ? '▾' : '▸';
    }
    return;
  }
  const node = e.target.closest('.toc-node');
  if (node) onTocNodeClick(parseInt(node.dataset.id), node);
});

async function onTocNodeClick(id, nodeEl) {
  document.querySelectorAll('#tocTree .toc-node.active').forEach(n => n.classList.remove('active'));
  if (nodeEl) nodeEl.classList.add('active');
  const resp = await fetch('/api/clause/' + id + '/detail');
  if (!resp.ok) return;
  const d = await resp.json();
  renderTocDetail(d);
}

function renderTocDetail(d) {
  tocDetailData = d;
  const box = document.getElementById('tocDetail');
  box.innerHTML =
    '<div class="toc-detail-head">' +
      '<div><span class="tno">' + escHtml(d.clause_no) + '</span> <span class="ttitle">' + escHtml(d.title) + '</span></div>' +
      '<div class="tmeta">' + escHtml(d.season) + ' · ' + escHtml(d.event) + ' · ' + escHtml(d.doc_type) + ' · ' + escHtml(d.version) + ' · 第 ' + d.page + ' 页</div>' +
    '</div>' +
    '<div class="toc-content">' + escHtml(d.content) + '</div>' +
    '<button class="toc-pdf-btn" onclick="openTocPdf()">查看 PDF 原文</button>';
}

function openTocPdf() {
  if (!tocDetailData) return;
  openPdfPair(tocDetailData.doc_id, tocDetailData.page, null, null, tocDetailData.clause_no + ' ' + tocDetailData.title, null, null);
}

function onTocJump() {
  const no = document.getElementById('tocJump').value.trim();
  if (!no || !tocData) return;
  const el = document.querySelector('#tocTree .toc-node[data-no="' + no + '"]');
  if (!el) {
    document.getElementById('tocDetail').innerHTML = '<div class="empty">未找到条款 ' + escHtml(no) + '</div>';
    return;
  }
  // 展开所有祖先，滚动定位
  let parent = el.closest('.toc-children');
  while (parent) {
    parent.classList.remove('hidden');
    const wrap = parent.closest('.toc-node-wrap');
    if (wrap) {
      const t = wrap.querySelector(':scope > .toc-node .toc-toggle');
      if (t) t.textContent = '▾';
    }
    parent = parent.parentElement ? parent.parentElement.closest('.toc-children') : null;
  }
  el.scrollIntoView({ block: 'center' });
  onTocNodeClick(parseInt(el.dataset.id), el);
}

document.getElementById('tocJump').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') onTocJump();
});

function saveSearchHistory(q) {
  const key = 'rmSearchHistory';
  let list = JSON.parse(localStorage.getItem(key) || '[]');
  list = list.filter(item => item !== q);
  list.unshift(q);
  if (list.length > 10) list = list.slice(0, 10);
  localStorage.setItem(key, JSON.stringify(list));
}
function getSearchHistory() {
  return JSON.parse(localStorage.getItem('rmSearchHistory') || '[]');
}
function showSearchHistory() {
  const box = document.getElementById('searchHistory');
  const list = getSearchHistory();
  if (!list.length) { box.classList.add('hidden'); return; }
  box.innerHTML = list.map(q => '<div class="search-history-item" data-q="' + escHtml(q) + '">' + escHtml(q) + '<span>历史</span></div>').join('') +
    '<div class="search-history-clear">清空历史</div>';
  box.querySelectorAll('.search-history-item').forEach(function(el) {
    el.addEventListener('click', function() {
      document.getElementById('q').value = el.getAttribute('data-q');
      hideSearchHistory();
      doSearch();
    });
  });
  const clearBtn = box.querySelector('.search-history-clear');
  if (clearBtn) clearBtn.addEventListener('click', clearSearchHistory);
  box.classList.remove('hidden');
}
function hideSearchHistory() { document.getElementById('searchHistory').classList.add('hidden'); }
function clearSearchHistory() { localStorage.removeItem('rmSearchHistory'); hideSearchHistory(); }
function quickSearch(q) { document.getElementById('q').value = q; hideSearchHistory(); doSearch(); }
function onSearchInput() { showSearchHistory(); }

document.addEventListener('click', function(e) {
  const wrap = document.querySelector('.search-box');
  const hist = document.getElementById('searchHistory');
  if (wrap && hist && !wrap.contains(e.target)) { hist.classList.add('hidden'); }
});

async function doSearch() {
  const q = document.getElementById('q').value.trim();
  const stats = document.getElementById('stats');
  const statsRow = document.getElementById('statsRow');
  if (!q) { document.getElementById('results').innerHTML = '<div class="empty">输入关键词开始搜索，或点击下方常用标签</div>'; stats.textContent=''; statsRow.classList.add('hidden'); lastSearchData = null; return; }
  saveSearchHistory(q);
  const doc = document.getElementById('searchDoc').value;
  let url = '/api/search?q=' + encodeURIComponent(q) + '&season=' + encodeURIComponent(currentSeason || '');
  if (doc) {
    const p = doc.split('|');
    url += '&event=' + encodeURIComponent(p[0]) + '&doc_type=' + encodeURIComponent(p[1]);
  }
  if (selectedVersions && selectedVersions.size > 0) {
    url += '&versions=' + encodeURIComponent(Array.from(selectedVersions).join(','));
  }
  const resp = await fetch(url);
  const data = await resp.json();
  lastSearchData = data;
  stats.textContent = '命中 ' + data.count + ' 条';
  statsRow.classList.remove('hidden');
  renderSearchResults();
}

function setCheckBtn(state, count) {
  const btn = document.getElementById('checkBtn');
  btn.classList.remove('check-btn-red', 'check-btn-green', 'check-btn-checking');
  if (state === 'checking') {
    btn.classList.add('check-btn-checking');
    btn.textContent = '检查中…';
    btn.disabled = true;
  } else if (state === 'update') {
    btn.classList.add('check-btn-red');
    btn.textContent = '有更新（' + count + '）';
    btn.disabled = false;
  } else if (state === 'current') {
    btn.classList.add('check-btn-green');
    btn.textContent = '已是最新 ✓';
    btn.disabled = false;
  } else {
    btn.textContent = '检查更新';
    btn.disabled = false;
  }
}

async function autoCheck() {
  setCheckBtn('checking');
  try {
    const resp = await fetch('/api/check-update');
    const data = await resp.json();
    if (data.has_update) {
      setCheckBtn('update', data.update.length + data.new.length);
    } else {
      setCheckBtn('current');
    }
  } catch (e) {
    setCheckBtn('idle');
  }
}

async function doCheckUpdate() {
  const panel = document.getElementById('updatePanel');
  setCheckBtn('checking');
  panel.classList.remove('hidden');
  panel.innerHTML = '<div class="upd-loading">正在检查官方最新版本…（渲染官方页面约需几秒）</div>';
  try {
    const resp = await fetch('/api/check-update');
    const data = await resp.json();
    renderUpdateResult(data, panel);
    if (data.has_update) {
      setCheckBtn('update', data.update.length + data.new.length);
    } else {
      setCheckBtn('current');
    }
  } catch (e) {
    panel.innerHTML = '<div class="upd-error">检查更新失败：可能是网络问题或无法访问官方站点，请稍后重试，或改用命令行 <code>python download.py</code> 手动下载。</div>';
    setCheckBtn('idle');
  }
}

function renderUpdateResult(data, panel) {
  const total = data.update.length + data.new.length;
  window.pendingCount = total;
  if (!data.has_update) {
    panel.innerHTML = '<div class="upd-ok">✔ 本地已是最新版本（已同步 ' + data.current + ' 个文档）</div>';
    return;
  }
  let html = '<div class="upd-head">发现 ' + total + ' 个文档可更新</div>';
  html += '<div class="upd-list">';
  for (const d of data.update) {
    html += '<div class="upd-item"><span class="badge badge-upd">有新版本</span>' +
      d.doc_type + ' · ' + d.lang + '：本地 ' + d.local_version + ' → 官方 ' + d.version +
      '（' + d.date + '）</div>';
  }
  for (const d of data.new) {
    html += '<div class="upd-item"><span class="badge badge-new">新文档</span>' +
      d.doc_type + ' · ' + d.lang + '：' + d.version + '（' + d.date + '）</div>';
  }
  html += '</div>';
  html += '<button class="upd-btn" onclick="doDownloadUpdate()">下载并更新</button>';
  if (data.new.length > 10) {
    html += '<div class="upd-hint">新文档较多（首次建库），建议改用命令行全量下载：python download.py</div>';
  }
  panel.innerHTML = html;
}

async function doDownloadUpdate() {
  const panel = document.getElementById('updatePanel');
  const n = window.pendingCount || 0;
  if (n > 10 && !confirm('将下载 ' + n + ' 个文档，首次全量可能耗时较长（建议用命令行 python download.py）。是否继续？')) {
    return;
  }
  panel.innerHTML = '<div class="upd-loading">正在下载并解析入库…（增量通常几十秒，请勿关闭页面）</div>';
  try {
    const resp = await fetch('/api/update', { method: 'POST' });
    const data = await resp.json();
    if (data.ok) {
      const ok = data.items.filter(i => i.status === 'ok').length;
      const skip = data.items.filter(i => i.status === 'skipped').length;
      const err = data.items.filter(i => i.status === 'error').length;
      panel.innerHTML = '<div class="upd-ok">✔ 更新完成：新入库 ' + ok + ' 个，跳过 ' + skip + ' 个' +
        (err ? '，失败 ' + err + ' 个' : '') + '</div>' +
        '<button class="upd-btn" onclick="doCheckUpdate()">再次检查</button>';
    } else {
      panel.innerHTML = '<div class="upd-error">更新失败：' + (data.message || '未知错误') + '</div>';
    }
  } catch (e) {
    panel.innerHTML = '<div class="upd-error">下载更新失败：可能是网络问题，请稍后重试，或改用命令行 <code>python download.py</code> 手动下载。</div>';
  }
}

async function loadVersions() {
  const doc = document.getElementById('cmpDoc').value;
  if (!doc) return;
  const p = doc.split('|');
  const resp = await fetch('/api/versions?season=' + encodeURIComponent(currentSeason || '') + '&event=' + encodeURIComponent(p[0]) + '&doc_type=' + encodeURIComponent(p[1]));
  const data = await resp.json();
  const from = document.getElementById('cmpFrom');
  const to = document.getElementById('cmpTo');
  from.innerHTML = to.innerHTML = data.versions.map(v =>
    '<option value="' + v + '">' + v + '</option>'
  ).join('');
  if (data.versions.length >= 2) {
    from.value = data.versions[data.versions.length - 2];
    to.value = data.versions[data.versions.length - 1];
  } else if (data.versions.length === 1) {
    from.value = to.value = data.versions[0];
  }
}

async function doCompare() {
  const from = document.getElementById('cmpFrom').value;
  const to = document.getElementById('cmpTo').value;
  if (!from || !to) return;
  document.getElementById('cmpResults').innerHTML = '<div class="empty">正在对比 ' + from + ' → ' + to + ' …</div>';
  document.getElementById('rnBox').innerHTML = '';
  const doc = document.getElementById('cmpDoc').value;
  const p = doc.split('|');
  const ev = encodeURIComponent(p[0]);
  const dt = encodeURIComponent(p[1]);
  const [cmpResp, rnResp] = await Promise.all([
    fetch('/api/compare?season=' + encodeURIComponent(currentSeason || '') + '&event=' + ev + '&doc_type=' + dt + '&from=' + encodeURIComponent(from) + '&to=' + encodeURIComponent(to)),
    fetch('/api/release-notes?season=' + encodeURIComponent(currentSeason || '') + '&event=' + ev + '&doc_type=' + dt)
  ]);
  const data = await cmpResp.json();
  const rnData = await rnResp.json();
  lastCompareData = data;
  document.getElementById('cmpFilter').value = '';
  renderCompare(data);
  renderReleaseNotes(rnData.notes, from, to);
}

function renderReleaseNotes(notes, from, to) {
  const box = document.getElementById('rnBox');
  if (!notes || !notes.length) { box.innerHTML = ''; return; }
  const idxFrom = notes.findIndex(n => n.version === from);
  const idxTo = notes.findIndex(n => n.version === to);
  if (idxFrom === -1 || idxTo === -1) { box.innerHTML = ''; return; }
  const lo = Math.min(idxFrom, idxTo);
  const hi = Math.max(idxFrom, idxTo);
  const range = notes.slice(lo, hi + 1);  // notes 从新到旧，range 也从上到下最新→最旧
  let html = '<div class="rn-title">官方修改日志（' + from + ' → ' + to + '）</div>';
  for (const n of range) {
    html += '<div class="rn-item">' +
      '<div class="rn-head">' + n.version + '<span class="rn-date">' + n.date + '</span></div>' +
      '<ul>' + n.items.map(it => '<li>' + escHtml(it) + '</li>').join('') + '</ul>' +
      '</div>';
  }
  box.innerHTML = html;
}

async function loadScDoc() {
  const resp = await fetch('/api/doctypes');  // 不带 season，取跨赛季文档类型
  const data = await resp.json();
  const evName = { RMUC: '超级对抗赛', RMUL: '高校联盟赛' };
  const opts = data.doctypes.map(d =>
    '<option value="' + d.event + '|' + d.doc_type + '">' + (evName[d.event] || d.event) + ' · ' + d.doc_type + '</option>'
  ).join('');
  const sel = document.getElementById('scDoc');
  sel.innerHTML = opts;
  const rulesOpt = Array.from(sel.options).find(o => o.textContent.includes('比赛规则手册'));
  if (rulesOpt) sel.value = rulesOpt.value;
  loadScSeasons();
}

async function loadScSeasons() {
  const resp = await fetch('/api/seasons');
  const data = await resp.json();
  const seasons = data.seasons || [];
  const from = document.getElementById('scFromSeason');
  const to = document.getElementById('scToSeason');
  const opts = seasons.map(s => '<option value="' + s + '">' + s + ' 赛季</option>').join('');
  from.innerHTML = opts;
  to.innerHTML = opts;
  if (seasons.length >= 2) {
    from.value = seasons[seasons.length - 1];  // 最旧赛季
    to.value = seasons[0];  // 最新赛季
  }
}

async function doSeasonCompare() {
  const fromSeason = document.getElementById('scFromSeason').value;
  const toSeason = document.getElementById('scToSeason').value;
  const doc = document.getElementById('scDoc').value;
  if (!fromSeason || !toSeason || !doc) return;
  document.getElementById('scResults').innerHTML = '<div class="empty">正在对比 ' + fromSeason + ' → ' + toSeason + ' …</div>';
  document.getElementById('scSummary').innerHTML = '';
  const p = doc.split('|');
  const ev = encodeURIComponent(p[0]);
  const dt = encodeURIComponent(p[1]);
  const resp = await fetch('/api/compare-seasons?event=' + ev + '&doc_type=' + dt + '&from_season=' + encodeURIComponent(fromSeason) + '&to_season=' + encodeURIComponent(toSeason));
  const data = await resp.json();
  lastSeasonCompareData = data;
  document.getElementById('scFilter').value = '';
  renderSeasonCompare(data);
}

function renderSeasonCompare(data) {
  const d = Object.assign({}, data);
  d.from = (d.from_season || '') + ' ' + d.from;
  d.to = (d.to_season || '') + ' ' + d.to;
  renderCompareInto(d, 'scSummary', 'scResults');
}

function filterChanges(data, kw) {
  const kws = (kw || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!kws.length) return data;
  const changes = data.changes.filter(c => {
    const hay = (c.clause_no + ' ' + c.title + ' ' + (c.new || '') + ' ' + (c.old || '')).toLowerCase();
    return kws.every(k => hay.includes(k));
  });
  const s = { added: 0, removed: 0, modified: 0, unchanged: data.summary.unchanged };
  for (const c of changes) s[c.type] = (s[c.type] || 0) + 1;
  return Object.assign({}, data, { changes: changes, summary: s });
}

function filterCmpResults() {
  if (!lastCompareData) return;
  renderCompare(filterChanges(lastCompareData, document.getElementById('cmpFilter').value));
}

function filterScResults() {
  if (!lastSeasonCompareData) return;
  renderSeasonCompare(filterChanges(lastSeasonCompareData, document.getElementById('scFilter').value));
}

function renderCompare(data) {
  renderCompareInto(data, 'cmpSummary', 'cmpResults');
}

function renderMiniBar(s) {
  const total = s.added + s.modified + s.removed + s.unchanged;
  if (!total) return '';
  const pct = k => ((s[k] / total) * 100).toFixed(1);
  const segs = [];
  if (s.added) segs.push('<div class="bar-seg bar-add" style="width:' + pct('added') + '%" title="新增 ' + s.added + '"></div>');
  if (s.modified) segs.push('<div class="bar-seg bar-mod" style="width:' + pct('modified') + '%" title="修改 ' + s.modified + '"></div>');
  if (s.removed) segs.push('<div class="bar-seg bar-del" style="width:' + pct('removed') + '%" title="删除 ' + s.removed + '"></div>');
  if (s.unchanged) segs.push('<div class="bar-seg bar-unch" style="width:' + pct('unchanged') + '%" title="未变 ' + s.unchanged + '"></div>');
  return '<div class="mini-bar">' + segs.join('') + '</div>';
}

function renderCompareInto(data, sumId, boxId) {
  const sum = document.getElementById(sumId);
  const box = document.getElementById(boxId);
  const s = data.summary;
  sum.innerHTML =
    '<span class="cmp-inline">' +
      '<span class="c-add">新增 ' + s.added + '</span> · ' +
      '<span class="c-mod">修改 ' + s.modified + '</span> · ' +
      '<span class="c-del">删除 ' + s.removed + '</span> · ' +
      '<span class="c-unch">未变 ' + s.unchanged + '</span>' +
    '</span>' +
    renderMiniBar(s);
  if (!data.changes.length) {
    box.innerHTML = '<div class="empty">未检测到任何改动</div>';
    return;
  }
  if (compareView === 'columns') box.innerHTML = renderColumnsView(data);
  else box.innerHTML = renderCardCompare(data);
}

function renderCardCompare(data) {
  return data.changes.map(c => {
    const badge = { added: 'badge-add', removed: 'badge-del', modified: 'badge-mod' }[c.type];
    const label = { added: '新增', removed: '删除', modified: '修改' }[c.type];
    let body = '';
    if (c.type === 'modified') body = c.diff_html;
    else if (c.type === 'added') body = escHtml(c.new);
    else body = escHtml(c.old);
    let attrs = '';
    if (c.type === 'modified') {
      attrs = 'data-from-doc="' + data.from_doc_id + '" data-from-page="' + c.old_page + '" data-to-doc="' + data.to_doc_id + '" data-to-page="' + c.new_page + '"';
    } else if (c.type === 'added') {
      attrs = 'data-to-doc="' + data.to_doc_id + '" data-to-page="' + c.new_page + '"';
    } else {
      attrs = 'data-from-doc="' + data.from_doc_id + '" data-from-page="' + c.old_page + '"';
    }
    return '<div class="cmp-item" ' + attrs + ' data-title="' + escHtml(c.clause_no + ' ' + c.title) + '" style="cursor:pointer;" title="点击查看 PDF 对比">' +
      '<div class="cmp-item-head">' +
        '<span class="no">' + c.clause_no + '</span>' +
        '<span class="title">' + escHtml(c.title) + '</span>' +
        '<span class="badge ' + badge + '">' + label + '</span>' +
      '</div>' +
      '<div class="cmp-content">' + body + '</div>' +
    '</div>';
  }).join('');
}

function renderColumnsView(data) {
  const from = data.from, to = data.to;
  return data.changes.map(c => {
    const badge = { added: 'badge-add', removed: 'badge-del', modified: 'badge-mod' }[c.type];
    const label = { added: '新增', removed: '删除', modified: '修改' }[c.type];
    let left = '', right = '', leftAttr = '', rightAttr = '';
    const tt = escHtml(c.clause_no + ' ' + c.title);
    let cmpAttrs = '';
    if (c.type === 'modified') {
      left = c.old_html || ''; right = c.new_html || '';
      cmpAttrs = 'data-from-doc="' + data.from_doc_id + '" data-from-page="' + c.old_page + '" data-to-doc="' + data.to_doc_id + '" data-to-page="' + c.new_page + '"';
      leftAttr = 'data-from-doc="' + data.from_doc_id + '" data-from-page="' + c.old_page + '" data-title="' + tt + '" style="cursor:pointer;" title="查看旧版 PDF"';
      rightAttr = 'data-to-doc="' + data.to_doc_id + '" data-to-page="' + c.new_page + '" data-title="' + tt + '" style="cursor:pointer;" title="查看新版 PDF"';
    } else if (c.type === 'added') {
      right = escHtml(c.new);
      cmpAttrs = 'data-to-doc="' + data.to_doc_id + '" data-to-page="' + c.new_page + '"';
      rightAttr = 'data-to-doc="' + data.to_doc_id + '" data-to-page="' + c.new_page + '" data-title="' + tt + '" style="cursor:pointer;" title="查看新版 PDF"';
    } else {
      left = escHtml(c.old);
      cmpAttrs = 'data-from-doc="' + data.from_doc_id + '" data-from-page="' + c.old_page + '"';
      leftAttr = 'data-from-doc="' + data.from_doc_id + '" data-from-page="' + c.old_page + '" data-title="' + tt + '" style="cursor:pointer;" title="查看旧版 PDF"';
    }
    return '<div class="cmp-item" ' + cmpAttrs + ' data-title="' + tt + '" style="cursor:pointer;" title="点击查看 PDF 对比">' +
      '<div class="cmp-item-head">' +
        '<span class="no">' + c.clause_no + '</span>' +
        '<span class="title">' + escHtml(c.title) + '</span>' +
        '<span class="badge ' + badge + '">' + label + '</span>' +
      '</div>' +
      '<div class="cmp-cols">' +
        '<div><div class="col-label old">' + from + '</div><div class="col-box" ' + leftAttr + '>' + (left || '—') + '</div></div>' +
        '<div><div class="col-label new">' + to + '</div><div class="col-box" ' + rightAttr + '>' + (right || '—') + '</div></div>' +
      '</div>' +
    '</div>';
  }).join('');
}

function escHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/\n/g, '<br>');
}

async function fetchRaw(clauseId) {
  try {
    const resp = await fetch('/api/clause/' + clauseId + '/raw');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    return escHtml(data.raw);
  } catch (e) {
    return '<span style="color:#b3261e;">原文加载失败，请稍后重试</span>';
  }
}

let pdfState = { L: { doc: null, cur: 1, token: 0 }, R: { doc: null, cur: 1, token: 0 } };

function openPdfPair(fromDoc, fromPage, toDoc, toPage, title, fromLabel, toLabel) {
  document.getElementById('pdfTitle').textContent = title || 'PDF 原文';
  document.getElementById('pdfModal').classList.remove('hidden');
  pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/pdfjs/pdf.worker.min.js';
  pdfState.L.doc = null; pdfState.L.cur = 1;
  pdfState.R.doc = null; pdfState.R.cur = 1;
  document.getElementById('paneLabelL').textContent = fromLabel || '旧版';
  document.getElementById('paneLabelR').textContent = toLabel || '新版';
  document.getElementById('paneL').style.display = fromDoc ? '' : 'none';
  document.getElementById('paneR').style.display = toDoc ? '' : 'none';
  document.getElementById('paneCanvasL').innerHTML = '<canvas id="pdfCanvasL"></canvas>';
  document.getElementById('paneCanvasR').innerHTML = '<canvas id="pdfCanvasR"></canvas>';
  if (fromDoc) loadPdfSide('L', fromDoc, fromPage);
  else document.getElementById('pdfPageInfoL').textContent = '—';
  if (toDoc) loadPdfSide('R', toDoc, toPage);
  else document.getElementById('pdfPageInfoR').textContent = '—';
  document.getElementById('pdfAlignBtnL').style.display = (fromDoc && toDoc) ? '' : 'none';
  document.getElementById('pdfAlignBtnR').style.display = (fromDoc && toDoc) ? '' : 'none';
}

function loadPdfSide(side, docId, page) {
  const token = ++pdfState[side].token;
  document.getElementById('pdfPageInfo' + side).textContent = '加载中…';
  pdfjsLib.getDocument('/api/pdf/' + docId).promise.then(function(doc) {
    if (pdfState[side].token !== token) return;
    pdfState[side].doc = doc;
    pdfState[side].cur = Math.min(Math.max(page || 1, 1), doc.numPages);
    renderPdfPage(side);
  }).catch(function(e) {
    if (pdfState[side].token !== token) return;
    document.getElementById('paneCanvas' + side).innerHTML =
      '<div style="color:#fff;padding:24px;line-height:1.7;">该条款对应的 PDF 未能加载。<br>' +
      '常见原因：对应文档尚未下载。请点击右上角「检查更新」下载最新文档后重试。<br>' +
      '<span style="opacity:0.45;font-size:12px;">技术细节：' + e.message + '</span></div>';
  });
}

function renderPdfPage(side) {
  const st = pdfState[side];
  if (!st.doc) return;
  const doc = st.doc;
  const cur = st.cur;
  doc.getPage(cur).then(function(page) {
    if (pdfState[side].doc !== doc) return;
    const canvas = document.getElementById('pdfCanvas' + side);
    const viewport = page.getViewport({ scale: 1.3 });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext('2d');
    page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function() {
      if (pdfState[side].doc !== doc) return;
      document.getElementById('pdfPageInfo' + side).textContent = cur + ' / ' + doc.numPages;
    });
  });
}

function pdfPrev(side) { const st = pdfState[side]; if (st.doc && st.cur > 1) { st.cur--; renderPdfPage(side); } }
function pdfNext(side) { const st = pdfState[side]; if (st.doc && st.cur < st.doc.numPages) { st.cur++; renderPdfPage(side); } }
function alignPdfPages(target) {
  const L = pdfState.L, R = pdfState.R;
  if (!L.doc || !R.doc) return;
  if (target === 'R') {
    L.cur = Math.min(Math.max(R.cur, 1), L.doc.numPages);  // 旧版迁就新版
    renderPdfPage('L');
  } else {
    R.cur = Math.min(Math.max(L.cur, 1), R.doc.numPages);  // 新版迁就旧版
    renderPdfPage('R');
  }
}
function closePdf() {
  document.getElementById('pdfModal').classList.add('hidden');
  pdfState.L.doc = null; pdfState.R.doc = null;
}

document.getElementById('results').addEventListener('click', function(e) {
  const toggle = e.target.closest('.raw-toggle');
  if (toggle) {
    const box = toggle.nextElementSibling;
    if (box && box.classList.contains('raw-box')) {
      const show = box.classList.contains('hidden');
      box.classList.toggle('hidden', !show);
      toggle.textContent = show ? '收起原文' : '显示原文';
      if (show && !box.dataset.loaded) {
        box.dataset.loaded = '1';
        fetchRaw(toggle.dataset.id).then(function(html) { box.innerHTML = html; });
      }
    }
    return;
  }
  const el = e.target.closest('[data-doc]');
  if (el) openPdfPair(parseInt(el.dataset.doc), parseInt(el.dataset.page), null, null, el.dataset.title, null, null);
});

function handleCompareClick(e) {
  const el = e.target.closest('[data-to-doc],[data-from-doc]');
  if (!el) return;
  const item = el.closest('.cmp-item');
  const fromDoc = item ? item.getAttribute('data-from-doc') : null;
  const fromPage = item ? item.getAttribute('data-from-page') : null;
  const toDoc = item ? item.getAttribute('data-to-doc') : null;
  const toPage = item ? item.getAttribute('data-to-page') : null;
  const title = el.dataset.title || (item ? item.getAttribute('data-title') : '');
  openPdfPair(
    fromDoc ? parseInt(fromDoc) : null, fromPage ? parseInt(fromPage) : null,
    toDoc ? parseInt(toDoc) : null, toPage ? parseInt(toPage) : null,
    title, null, null
  );
}

document.getElementById('cmpResults').addEventListener('click', handleCompareClick);
document.getElementById('scResults').addEventListener('click', handleCompareClick);

document.getElementById('q').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});
document.getElementById('q').addEventListener('focus', showSearchHistory);
document.getElementById('q').addEventListener('input', onSearchInput);
updateSearchViewButtons();
updateCompareViewButtons();
loadSeasons();
autoCheck();

// 根据 URL hash 恢复当前 tab
(function initTabFromHash() {
  const hash = location.hash.replace('#', '');
  const valid = ['search', 'compare', 'seasonCompare'];
  if (valid.includes(hash)) switchTab(hash);
})();
window.addEventListener('hashchange', function() {
  const hash = location.hash.replace('#', '');
  const valid = ['search', 'compare', 'seasonCompare'];
  if (valid.includes(hash)) switchTab(hash);
});