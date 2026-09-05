"""本地 Web 应用：RM 规则检索（搜索一次性铺开所有命中 + 版本对比 + 检查更新）。"""
import hashlib
import json
import os
import socket
import sqlite3

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pymupdf
import uvicorn

from search import search, highlight
from updater import check_update, download_and_ingest
from compare import compare, get_versions, get_latest_version
from parser import DB_PATH, init_db
from release_notes import extract_release_notes
from clean import plain, clean_text, was_cleaned, focus_snippet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="RM 规则检索")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# 确保数据库文件与表结构存在（全新部署时 data/ 目录可能不存在，避免各接口报 no such table）
try:
    init_db().close()
except Exception:
    pass


# ---------- 访问控制（队内部署用，可关闭） ----------
def _load_access_password() -> str:
    """访问密码：优先环境变量 ACCESS_PASSWORD，其次 config.json 的 access_password。为空则不启用。"""
    pw = os.environ.get("ACCESS_PASSWORD", "").strip()
    if pw:
        return pw
    try:
        with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        return str(cfg.get("access_password", "") or "").strip()
    except Exception:
        return ""


ACCESS_PASSWORD = _load_access_password()
_AUTH_TOKEN = hashlib.sha256(ACCESS_PASSWORD.encode("utf-8")).hexdigest() if ACCESS_PASSWORD else ""


LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RM 规则检索 · 登录</title>
<style>
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;background:#f7f7f5;color:#1a1a1a}
  .card{width:320px;padding:36px 32px;background:#fff;border:1px solid #e5e4e0;border-radius:12px}
  h1{font-size:18px;font-weight:600;margin:0 0 6px}
  p{font-size:13px;color:#888;margin:0 0 24px}
  input{width:100%;box-sizing:border-box;padding:10px 12px;font-size:14px;border:1px solid #d4d2c9;border-radius:8px;outline:none}
  input:focus{border-color:#0f6e56}
  button{width:100%;margin-top:14px;padding:10px;font-size:14px;color:#fff;background:#0f6e56;border:none;border-radius:8px;cursor:pointer}
  button:hover{background:#085041}
  .err{color:#c0392b;font-size:12px;margin-top:10px;min-height:16px}
</style>
</head>
<body>
<div class="card">
  <h1>RM 规则检索</h1>
  <p>队内私有工具，请输入访问密码</p>
  <input id="pw" type="password" placeholder="访问密码" autofocus>
  <button id="btn">进入</button>
  <div class="err" id="err"></div>
</div>
<script>
async function login(){
  var pw = document.getElementById('pw').value;
  var r = await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
  if(r.ok){location.href='/';}else{document.getElementById('err').textContent='密码错误，请重试';}
}
document.getElementById('btn').addEventListener('click',login);
document.getElementById('pw').addEventListener('keydown',function(e){if(e.key==='Enter')login();});
</script>
</body>
</html>"""


@app.middleware("http")
async def auth_middleware(request, call_next):
    """除登录页与登录接口外，未登录一律拦截；未启用密码时完全放行。"""
    path = request.url.path
    if path in ("/login", "/api/login", "/favicon.ico"):
        return await call_next(request)
    if not _AUTH_TOKEN:
        return await call_next(request)
    if request.cookies.get("rm_auth") == _AUTH_TOKEN:
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "未授权，请先登录"}, status_code=401)
    return RedirectResponse("/login")


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse(LOGIN_HTML)


class LoginPayload(BaseModel):
    password: str


@app.post("/api/login")
async def api_login(payload: LoginPayload):
    if payload.password == ACCESS_PASSWORD:
        resp = JSONResponse({"ok": True})
        resp.set_cookie("rm_auth", _AUTH_TOKEN, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
        return resp
    return JSONResponse({"ok": False, "detail": "密码错误"}, status_code=401)


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))


def _get_sections(event: str, doc_type: str, lang: str, season: str = None) -> dict:
    """返回一级章节映射 {clause_no: title}，供搜索结果分组视图显示章节标题。"""
    conn = sqlite3.connect(DB_PATH)
    sql = "SELECT id FROM documents WHERE event=? AND doc_type=? AND lang=?"
    params = [event, doc_type, lang]
    if season:
        sql += " AND season=?"
        params.append(season)
    sql += " ORDER BY version DESC LIMIT 1"
    doc = conn.execute(sql, params).fetchone()
    if not doc:
        conn.close()
        return {}
    rows = conn.execute(
        "SELECT clause_no, title FROM clauses WHERE doc_id=? "
        "AND clause_no NOT LIKE '%.%' AND clause_no GLOB '[0-9]*'",
        (doc[0],),
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


@app.get("/api/search")
def api_search(q: str = "", event: str = None, doc_type: str = None, lang: str = "中文版", versions: str = None, season: str = None):
    ver_list = [v for v in (versions or "").split(",") if v.strip()]
    results = search(q, event=event, doc_type=doc_type, lang=lang, versions=ver_list or None, season=season)
    kws = [k for k in q.split() if k.strip()]
    # 章节映射（分组视图用；未选具体文档时回退到规则手册）
    sections = _get_sections(event or "RMUC", doc_type or "比赛规则手册", lang, season)
    out = []
    for r in results:
        raw = r["content"]
        cleaned = plain(raw)
        snippet_text = focus_snippet(cleaned, kws)
        snippet = highlight(snippet_text, kws)
        top = (r["clause_no"] or "").split(".")[0]
        out.append({
            "clause_no": r["clause_no"],
            "title": r["title"],
            "page": r["page"],
            "version": r["version"],
            "doc_type": r["doc_type"],
            "event": r["event"],
            "season": r["season"],
            "id": r["id"],
            "doc_id": r["doc_id"],
            "snippet": snippet,
            "cleaned": was_cleaned(raw, cleaned),
            "section": sections.get(top, ""),
        })
    return {"query": q, "count": len(out), "results": out, "sections": sections}


@app.get("/api/clause/{clause_id}/raw")
def api_clause_raw(clause_id: int):
    """按需返回单条条款的原始正文（搜索结果「显示原文」用，避免搜索响应携带全量原文）。"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT content FROM clauses WHERE id=?", (clause_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "条款不存在")
    return {"raw": row[0]}


@app.get("/api/toc")
def api_toc(event: str = "RMUC", doc_type: str = "比赛规则手册", lang: str = "中文版", season: str = "2026", version: str = None):
    """返回某文档的完整目录树（章节→条款），供「目录」tab 浏览。默认取最新版本。"""
    conn = sqlite3.connect(DB_PATH)
    params = [season, event, doc_type, lang]
    sql = "SELECT id, version FROM documents WHERE season=? AND event=? AND doc_type=? AND lang=?"
    if version:
        sql += " AND version=?"
        params.append(version)
    else:
        sql += " ORDER BY version DESC LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "该文档不存在")
    doc_id, doc_version = row
    rows = conn.execute(
        "SELECT id, clause_no, title, level, page FROM clauses WHERE doc_id=? ORDER BY id",
        (doc_id,),
    ).fetchall()
    conn.close()
    # 按 level 构建层级树
    toc = []
    stack = [{"children": toc}]
    for cid, clause_no, title, level, page in rows:
        while len(stack) > (level or 1):
            stack.pop()
        node = {"id": cid, "no": clause_no, "title": title, "level": level, "page": page, "children": []}
        stack[-1]["children"].append(node)
        stack.append(node)
    return {"doc_id": doc_id, "version": doc_version, "toc": toc}


@app.get("/api/clause/{clause_id}/detail")
def api_clause_detail(clause_id: int):
    """返回单条条款详情（清洗后正文 + 元信息），供目录浏览右侧展示。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT c.clause_no, c.title, c.page, c.content, d.id AS doc_id, d.version, d.season, d.event, d.doc_type "
        "FROM clauses c JOIN documents d ON c.doc_id = d.id WHERE c.id=?",
        (clause_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "条款不存在")
    return {
        "clause_no": row["clause_no"],
        "title": row["title"],
        "page": row["page"],
        "content": clean_text(row["content"]),
        "doc_id": row["doc_id"],
        "version": row["version"],
        "season": row["season"],
        "event": row["event"],
        "doc_type": row["doc_type"],
    }


@app.get("/api/seasons")
def api_seasons(lang: str = "中文版"):
    """返回已入库的赛季列表（最新在前）。"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT season FROM documents WHERE lang=? AND season IS NOT NULL ORDER BY season DESC",
        (lang,),
    ).fetchall()
    conn.close()
    return {"seasons": [r[0] for r in rows]}


@app.get("/api/status")
def api_status():
    """返回数据库状态（文档数），前端据此判断是否需要显示首次建库引导。"""
    try:
        conn = sqlite3.connect(DB_PATH)
    except sqlite3.Error:
        return {"documents": 0}  # data/ 目录或数据库文件不可用（全新部署）
    try:
        try:
            n = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        except sqlite3.OperationalError:
            n = 0  # 表未建
    finally:
        conn.close()
    return {"documents": n}


@app.get("/api/doctypes")
def api_doctypes(lang: str = "中文版", season: str = None):
    """返回已入库的文档类型组合，供前端下拉选择。"""
    conn = sqlite3.connect(DB_PATH)
    sql = "SELECT DISTINCT event, doc_type FROM documents WHERE lang=?"
    params = [lang]
    if season:
        sql += " AND season=?"
        params.append(season)
    sql += " ORDER BY event, doc_type"
    rows = conn.execute(sql, params).fetchall()
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
def api_versions(event: str = "RMUC", doc_type: str = "比赛规则手册", lang: str = "中文版", season: str = "2026"):
    return {"versions": get_versions(event, doc_type, lang, season)}


@app.get("/api/compare")
def api_compare(
    from_v: str = Query(..., alias="from"),
    to: str = Query(...),
    event: str = "RMUC",
    doc_type: str = "比赛规则手册",
    lang: str = "中文版",
    season: str = "2026",
):
    return compare(event, doc_type, from_v, to, lang, season)


@app.get("/api/compare-seasons")
def api_compare_seasons(
    event: str = "RMUC",
    doc_type: str = "比赛规则手册",
    from_season: str = "2025",
    to_season: str = "2026",
    lang: str = "中文版",
):
    """跨赛季对比：取两个赛季各自最新版本做条款级 diff。"""
    from_v = get_latest_version(event, doc_type, lang, from_season)
    to_v = get_latest_version(event, doc_type, lang, to_season)
    if not from_v:
        raise HTTPException(404, f"赛季 {from_season} 无该文档")
    if not to_v:
        raise HTTPException(404, f"赛季 {to_season} 无该文档")
    return compare(event, doc_type, from_v, to_v, lang, from_season=from_season, to_season=to_season)


@app.get("/api/release-notes")
def api_release_notes(event: str = "RMUC", doc_type: str = "比赛规则手册", lang: str = "中文版", season: str = "2026"):
    """返回该文档类型全部版本的官方修改日志（从最新版 PDF 开头提取）。"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT version, pdf_path FROM documents WHERE season=? AND event=? AND doc_type=? AND lang=? "
        "ORDER BY version DESC LIMIT 1",
        (season, event, doc_type, lang),
    ).fetchone()
    conn.close()
    if not row or not row[1] or not os.path.exists(row[1]):
        return {"notes": []}
    return {"notes": extract_release_notes(row[1]), "source_version": row[0]}


@app.get("/api/pdf/{doc_id}")
def api_pdf(doc_id: int):
    """返回文档对应的 PDF 文件，供前端 PDF.js 查看器加载。"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT pdf_path FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if not row or not row[0] or not os.path.exists(row[0]):
        return HTMLResponse("PDF 文件不存在", status_code=404)
    # 加缓存头：PDF 文件名含版本号，更新是新增文件而非覆盖，缓存 7 天安全，
    # 队友二次打开同一 PDF 直接命中浏览器缓存、秒开。
    return FileResponse(
        row[0],
        media_type="application/pdf",
        headers={"Cache-Control": "public, max-age=604800"},
    )


@app.get("/api/pdf/{doc_id}/meta")
def api_pdf_meta(doc_id: int):
    """返回 PDF 页数，供前端图片查看器翻页。"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT pdf_path FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if not row or not row[0] or not os.path.exists(row[0]):
        raise HTTPException(404, "PDF 文件不存在")
    try:
        doc = pymupdf.open(row[0])
        n = doc.page_count
        doc.close()
    except Exception:
        raise HTTPException(500, "PDF 解析失败")
    return {"num_pages": n}


@app.get("/api/pdf/{doc_id}/page/{page}")
def api_pdf_page(doc_id: int, page: int):
    """渲染 PDF 单页为 JPEG 返回（磁盘缓存），替代传输整份 PDF，3M 带宽下也能秒开。"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT pdf_path FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if not row or not row[0] or not os.path.exists(row[0]):
        raise HTTPException(404, "PDF 文件不存在")
    pdf_path = row[0]
    cache_dir = os.path.join(BASE_DIR, "data", "pages", str(doc_id))
    cache_file = os.path.join(cache_dir, f"{page}.jpg")
    if not os.path.exists(cache_file):
        try:
            doc = pymupdf.open(pdf_path)
            if page < 1 or page > doc.page_count:
                doc.close()
                raise HTTPException(404, "页码越界")
            pix = doc[page - 1].get_pixmap(dpi=150)
            data = pix.tobytes("jpeg", jpg_quality=82)
            doc.close()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(500, "渲染失败")
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "wb") as f:
            f.write(data)
    return FileResponse(cache_file, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800"})


def _get_lan_ip() -> str:
    """探测本机局域网 IP（用于启动时打印队友可访问的地址）。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    # 本地开发默认只监听本机；队内部署时设 HOST=0.0.0.0 让队友访问
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    lan_ip = _get_lan_ip()
    print("=" * 52)
    print("RM 规则检索已启动")
    print(f"  本机访问:   http://127.0.0.1:{port}")
    print(f"  局域网访问: http://{lan_ip}:{port}")
    print(f"  访问密码:   {'已启用' if ACCESS_PASSWORD else '未启用（本地开发）'}")
    print("=" * 52)

    if host in ("127.0.0.1", "localhost"):
        import threading
        import time
        import webbrowser

        def _open_browser():
            time.sleep(1.5)
            webbrowser.open(f"http://127.0.0.1:{port}")

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(app, host=host, port=port)
