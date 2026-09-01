"""本地 Web 应用：RM 规则检索（搜索一次性铺开所有命中 + 版本对比 + 检查更新）。"""
import os
import sqlite3

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import uvicorn

from search import search, highlight
from updater import check_update, download_and_ingest
from compare import compare, get_versions
from parser import DB_PATH
from release_notes import extract_release_notes

app = FastAPI(title="RM 规则检索")

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RM 规则检索</title>
<style>
  :root {
    --bg: #f6f6f4; --card: #ffffff; --text: #1f1f1e;
    --muted: #6b6b68; --border: #e2e2de; --accent: #185fa5;
    --accent-bg: #e6f1fb; --mark: #fcd47f;
    --ok: #1a7f4b; --warn: #c9820a; --add: #1a7f4b; --del: #b3261e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
         background: var(--bg); color: var(--text); padding: 32px 20px; }
  .wrap { max-width: 820px; margin: 0 auto; }
  .topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
  h1 { font-size: 22px; font-weight: 600; }
  .sub { color: var(--muted); font-size: 13px; margin-top: 4px; }
  .check-btn { font-size: 14px; padding: 9px 18px; border: 1px solid var(--border);
    border-radius: 10px; background: var(--card); color: var(--text); cursor: pointer;
    white-space: nowrap; transition: background .15s; }
  .check-btn:hover { background: var(--accent-bg); border-color: var(--accent); color: var(--accent); }
  .check-btn:disabled { opacity: .55; cursor: not-allowed; }
  .check-btn-red { background: #c62828 !important; border-color: #c62828 !important; color: #fff !important; }
  .check-btn-red:hover { background: #b02424 !important; color: #fff !important; }
  .check-btn-green { background: #2e7d32 !important; border-color: #2e7d32 !important; color: #fff !important; }
  .check-btn-green:hover { background: #276a2b !important; color: #fff !important; }
  .check-btn-checking { opacity: .6; cursor: wait; }
  .hidden { display: none; }
  .update-panel { background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px 20px; margin: 16px 0 4px; }
  .upd-loading { color: var(--muted); font-size: 14px; }
  .upd-ok { color: var(--ok); font-size: 14px; font-weight: 600; }
  .upd-error { color: #b3261e; font-size: 14px; }
  .upd-head { font-size: 14px; font-weight: 600; margin-bottom: 10px; }
  .upd-list { max-height: 300px; overflow-y: auto; }
  .upd-item { font-size: 13px; padding: 7px 0; border-bottom: 1px solid var(--border);
    line-height: 1.5; color: #3a3a37; }
  .upd-item:last-child { border-bottom: none; }
  .badge { display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 5px;
    margin-right: 6px; vertical-align: 1px; }
  .badge-upd { background: #fdf0d7; color: var(--warn); }
  .badge-new { background: var(--accent-bg); color: var(--accent); }
  .upd-btn { margin-top: 12px; font-size: 14px; padding: 9px 22px; border: none;
    border-radius: 10px; background: var(--accent); color: #fff; cursor: pointer; }
  .upd-btn:hover { opacity: .92; }
  .upd-hint { margin-top: 10px; font-size: 12px; color: var(--muted); }

  .tabs { display: flex; gap: 8px; margin: 20px 0 16px; border-bottom: 1px solid var(--border); }
  .tab { font-size: 15px; padding: 9px 18px; border: none; background: none; color: var(--muted);
    cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; }
  .tab.active { color: var(--accent); font-weight: 600; border-bottom-color: var(--accent); }

  .search-box { display: flex; gap: 10px; margin: 4px 0 12px; }
  .search-box input { flex: 1; font-size: 15px; padding: 12px 16px;
    border: 1px solid var(--border); border-radius: 10px; background: var(--card); }
  .search-box select { font-size: 14px; padding: 12px 14px; border: 1px solid var(--border);
    border-radius: 10px; background: var(--card); color: var(--text); max-width: 240px; }
  .search-box input:focus { outline: none; border-color: var(--accent); }
  .search-box button { font-size: 15px; padding: 12px 22px; border: none;
    border-radius: 10px; background: var(--accent); color: #fff; cursor: pointer; }
  .stats { color: var(--muted); font-size: 13px; margin: 8px 0 16px; }
  .card { background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px 20px; margin-bottom: 12px; }
  .card-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
  .no { font-family: ui-monospace, Consolas, monospace; font-size: 14px;
    color: var(--accent); font-weight: 600; }
  .title { font-size: 15px; font-weight: 600; }
  .meta { margin-left: auto; font-size: 12px; color: var(--muted); white-space: nowrap; }
  .snippet { font-size: 14px; line-height: 1.7; color: #3a3a37; }
  mark { background: var(--mark); border-radius: 3px; padding: 0 2px; color: inherit; }
  .empty { color: var(--muted); text-align: center; padding: 60px 0; font-size: 14px; }

  .cmp-bar { display: flex; align-items: center; gap: 10px; margin: 4px 0 16px; flex-wrap: wrap; }
  .cmp-bar label { font-size: 14px; color: var(--muted); }
  .cmp-bar select { font-size: 14px; padding: 8px 12px; border: 1px solid var(--border);
    border-radius: 8px; background: var(--card); color: var(--text); }
  .cmp-bar button { font-size: 14px; padding: 9px 22px; border: none; border-radius: 8px;
    background: var(--accent); color: #fff; cursor: pointer; }
  .cmp-summary { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
  .cmp-stat { flex: 1; min-width: 90px; text-align: center; padding: 12px 8px;
    background: var(--card); border: 1px solid var(--border); border-radius: 10px; }
  .cmp-stat .num { font-size: 22px; font-weight: 700; }
  .cmp-stat .lbl { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .stat-add .num { color: var(--add); } .stat-del .num { color: var(--del); }
  .stat-mod .num { color: var(--warn); }
  .cmp-item { background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px 20px; margin-bottom: 12px; }
  .cmp-item-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; }
  .badge-add { background: #e3f3e8; color: var(--add); }
  .badge-del { background: #fbe4e2; color: var(--del); }
  .badge-mod { background: #fdf0d7; color: var(--warn); }
  .cmp-content { font-size: 14px; line-height: 1.8; color: #3a3a37; }
  ins { background: #d8f0dd; text-decoration: none; padding: 0 2px; border-radius: 3px; }
  del { background: #fbdcd9; text-decoration: line-through; padding: 0 2px; border-radius: 3px; }
  .rn-title { font-size: 14px; font-weight: 600; margin: 4px 0 10px; color: var(--text); }
  .rn-item { background: var(--card); border: 1px solid var(--border);
    border-left: 3px solid var(--accent); border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; }
  .rn-head { font-size: 14px; font-weight: 600; color: var(--accent); margin-bottom: 6px; }
  .rn-date { font-size: 12px; color: var(--muted); font-weight: 400; margin-left: 6px; }
  .rn-item ul { margin: 0; padding-left: 18px; }
  .rn-item li { font-size: 13px; line-height: 1.7; color: #3a3a37; margin: 2px 0; }
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div>
      <h1>RM 规则检索</h1>
      <div class="sub">搜索规则内容 · 版本对比 · 检查更新 · 数据源：官方规则手册</div>
    </div>
    <button id="checkBtn" class="check-btn" onclick="doCheckUpdate()">检查更新</button>
  </div>
  <div id="updatePanel" class="update-panel hidden"></div>

  <div class="tabs">
    <button id="tabSearch" class="tab active" onclick="switchTab('search')">搜索</button>
    <button id="tabCompare" class="tab" onclick="switchTab('compare')">版本对比</button>
  </div>

  <div id="searchView">
    <div class="search-box">
      <select id="searchDoc" class="doc-select" onchange="doSearch()"></select>
      <input id="q" placeholder="输入关键词，如：飞镖 发射 限制（空格分隔多词）" autofocus>
      <button onclick="doSearch()">搜索</button>
    </div>
    <div class="stats" id="stats"></div>
    <div id="results"><div class="empty">输入关键词开始搜索</div></div>
  </div>

  <div id="compareView" class="hidden">
    <div class="cmp-bar">
      <label>文档</label>
      <select id="cmpDoc" onchange="loadVersions()"></select>
      <label>从</label>
      <select id="cmpFrom"></select>
      <label>到</label>
      <select id="cmpTo"></select>
      <button onclick="doCompare()">对比</button>
    </div>
    <div id="cmpSummary"></div>
    <div id="rnBox"></div>
    <div id="cmpResults"><div class="empty">选择两个版本，点击对比查看改动</div></div>
  </div>
</div>
<script>
async function loadDoctypes() {
  const resp = await fetch('/api/doctypes');
  const data = await resp.json();
  const evName = { RMUC: '超级对抗赛', RMUL: '高校联盟赛' };
  const opts = data.doctypes.map(d =>
    '<option value="' + d.event + '|' + d.doc_type + '">' + (evName[d.event] || d.event) + ' · ' + d.doc_type + '</option>'
  ).join('');
  document.getElementById('searchDoc').innerHTML = '<option value="">全部文档</option>' + opts;
  document.getElementById('cmpDoc').innerHTML = opts;
  const rulesOpt = Array.from(document.getElementById('cmpDoc').options).find(o => o.textContent.includes('比赛规则手册'));
  if (rulesOpt) document.getElementById('cmpDoc').value = rulesOpt.value;
  loadVersions();
}

function switchTab(tab) {
  document.getElementById('searchView').classList.toggle('hidden', tab !== 'search');
  document.getElementById('compareView').classList.toggle('hidden', tab !== 'compare');
  document.getElementById('tabSearch').classList.toggle('active', tab === 'search');
  document.getElementById('tabCompare').classList.toggle('active', tab === 'compare');
  if (tab === 'compare') loadVersions();
}

async function doSearch() {
  const q = document.getElementById('q').value.trim();
  const stats = document.getElementById('stats');
  const box = document.getElementById('results');
  if (!q) { box.innerHTML = '<div class="empty">输入关键词开始搜索</div>'; stats.textContent=''; return; }
  const doc = document.getElementById('searchDoc').value;
  let url = '/api/search?q=' + encodeURIComponent(q);
  if (doc) {
    const p = doc.split('|');
    url += '&event=' + encodeURIComponent(p[0]) + '&doc_type=' + encodeURIComponent(p[1]);
  }
  const resp = await fetch(url);
  const data = await resp.json();
  stats.textContent = '命中 ' + data.count + ' 条';
  if (!data.results.length) {
    box.innerHTML = '<div class="empty">没有匹配的条款，换个关键词试试</div>';
    return;
  }
  box.innerHTML = data.results.map(r =>
    '<div class="card">' +
      '<div class="card-head">' +
        '<span class="no">' + r.clause_no + '</span>' +
        '<span class="title">' + r.title + '</span>' +
        '<span class="meta">' + r.version + ' · 第 ' + r.page + ' 页</span>' +
      '</div>' +
      '<p class="snippet">' + r.snippet + '</p>' +
    '</div>'
  ).join('');
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
    panel.innerHTML = '<div class="upd-error">检查失败：' + e + '</div>';
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
    panel.innerHTML = '<div class="upd-error">更新失败：' + e + '</div>';
  }
}

async function loadVersions() {
  const doc = document.getElementById('cmpDoc').value;
  if (!doc) return;
  const p = doc.split('|');
  const resp = await fetch('/api/versions?event=' + encodeURIComponent(p[0]) + '&doc_type=' + encodeURIComponent(p[1]));
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
  const box = document.getElementById('cmpResults');
  const sum = document.getElementById('cmpSummary');
  if (!from || !to) return;
  box.innerHTML = '<div class="empty">正在对比 ' + from + ' → ' + to + ' …</div>';
  document.getElementById('rnBox').innerHTML = '';
  const doc = document.getElementById('cmpDoc').value;
  const p = doc.split('|');
  const ev = encodeURIComponent(p[0]);
  const dt = encodeURIComponent(p[1]);
  const [cmpResp, rnResp] = await Promise.all([
    fetch('/api/compare?event=' + ev + '&doc_type=' + dt + '&from=' + encodeURIComponent(from) + '&to=' + encodeURIComponent(to)),
    fetch('/api/release-notes?event=' + ev + '&doc_type=' + dt)
  ]);
  const data = await cmpResp.json();
  const rnData = await rnResp.json();
  renderCompare(data, sum, box);
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

function renderCompare(data, sum, box) {
  const s = data.summary;
  sum.innerHTML =
    '<div class="cmp-stat stat-add"><div class="num">' + s.added + '</div><div class="lbl">新增条款</div></div>' +
    '<div class="cmp-stat stat-mod"><div class="num">' + s.modified + '</div><div class="lbl">修改条款</div></div>' +
    '<div class="cmp-stat stat-del"><div class="num">' + s.removed + '</div><div class="lbl">删除条款</div></div>' +
    '<div class="cmp-stat"><div class="num">' + s.unchanged + '</div><div class="lbl">未变条款</div></div>';
  if (!data.changes.length) {
    box.innerHTML = '<div class="empty">两个版本完全一致，无任何改动</div>';
    return;
  }
  box.innerHTML = data.changes.map(c => {
    const badge = { added: 'badge-add', removed: 'badge-del', modified: 'badge-mod' }[c.type];
    const label = { added: '新增', removed: '删除', modified: '修改' }[c.type];
    let body = '';
    if (c.type === 'modified') body = c.diff_html;
    else if (c.type === 'added') body = escHtml(c.new);
    else body = escHtml(c.old);
    return '<div class="cmp-item">' +
      '<div class="cmp-item-head">' +
        '<span class="no">' + c.clause_no + '</span>' +
        '<span class="title">' + escHtml(c.title) + '</span>' +
        '<span class="badge ' + badge + '">' + label + '</span>' +
      '</div>' +
      '<div class="cmp-content">' + body + '</div>' +
    '</div>';
  }).join('');
}

function escHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\\n/g, '<br>');
}

document.getElementById('q').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});
loadDoctypes();
autoCheck();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML


@app.get("/api/search")
def api_search(q: str = "", event: str = None, doc_type: str = None, lang: str = "中文版"):
    results = search(q, event=event, doc_type=doc_type, lang=lang)
    kws = [k for k in q.split() if k.strip()]
    out = []
    for r in results:
        content = r["content"].replace("\n", " ")
        idx = min([content.find(k) for k in kws if content.find(k) >= 0], default=0)
        start = max(0, idx - 50)
        end = min(len(content), idx + 110)
        snippet = content[start:end].strip()
        snippet = highlight(snippet, kws)
        out.append({
            "clause_no": r["clause_no"],
            "title": r["title"],
            "page": r["page"],
            "version": r["version"],
            "doc_type": r["doc_type"],
            "event": r["event"],
            "snippet": snippet,
        })
    return {"query": q, "count": len(out), "results": out}


@app.get("/api/doctypes")
def api_doctypes(lang: str = "中文版"):
    """返回已入库的文档类型组合，供前端下拉选择。"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT event, doc_type FROM documents WHERE lang=? ORDER BY event, doc_type",
        (lang,),
    ).fetchall()
    conn.close()
    return {"doctypes": [{"event": r[0], "doc_type": r[1]} for r in rows]}


@app.get("/api/check-update")
def api_check_update():
    report, _ = check_update()
    return {
        "current": len(report["current"]),
        "update": report["update"],
        "new": report["new"],
        "has_update": bool(report["update"] or report["new"]),
    }


@app.post("/api/update")
def api_update():
    report, _ = check_update()
    docs = report["update"] + report["new"]
    if not docs:
        return {"ok": True, "downloaded": 0, "items": [], "message": "已是最新，无需更新"}
    results = download_and_ingest(docs)
    return {"ok": True, "downloaded": len(results), "items": results}


@app.get("/api/versions")
def api_versions(event: str = "RMUC", doc_type: str = "比赛规则手册", lang: str = "中文版"):
    return {"versions": get_versions(event, doc_type, lang)}


@app.get("/api/compare")
def api_compare(
    from_v: str = Query(..., alias="from"),
    to: str = Query(...),
    event: str = "RMUC",
    doc_type: str = "比赛规则手册",
    lang: str = "中文版",
):
    return compare(event, doc_type, from_v, to, lang)


@app.get("/api/release-notes")
def api_release_notes(event: str = "RMUC", doc_type: str = "比赛规则手册", lang: str = "中文版"):
    """返回该文档类型全部版本的官方修改日志（从最新版 PDF 开头提取）。"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT version, pdf_path FROM documents WHERE event=? AND doc_type=? AND lang=? "
        "ORDER BY version DESC LIMIT 1",
        (event, doc_type, lang),
    ).fetchone()
    conn.close()
    if not row or not row[1] or not os.path.exists(row[1]):
        return {"notes": []}
    return {"notes": extract_release_notes(row[1]), "source_version": row[0]}


if __name__ == "__main__":
    import threading
    import webbrowser

    def _open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8000/")

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)
