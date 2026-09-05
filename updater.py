"""检查更新 + 下载入库：对比官方最新版本清单与本地已入库版本。

供 server.py 的「检查更新」按钮调用：
  - check_update()          -> 抓官方清单，对比本地，返回 current/update/new 分组
  - download_and_ingest()   -> 下载 PDF 并解析入库（增量）
"""
import os
import re
import sqlite3
import urllib.request

from crawler import fetch_manifest, invalidate_manifest_cache, UA
from parser import DB_PATH, ingest_pdf, init_db

PDF_DIR = "data/pdfs"


def normalize_doc_type(name: str) -> str:
    """取文档类型的中文部分作为稳定标识。

    '比赛规则手册 Rule Manual' -> '比赛规则手册'
    避免官方标题中英混排与本地入库名不一致导致无法对齐。
    """
    m = re.match(r"^[\u4e00-\u9fff]+", (name or "").strip())
    return m.group(0) if m else (name or "").strip()


def parse_version(v: str) -> tuple:
    """'V2.2.0' -> (2, 2, 0)；无法解析返回 (0, 0, 0)。"""
    m = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", v or "")
    if not m:
        return (0, 0, 0)
    return tuple(int(x or 0) for x in m.groups())


def local_versions(lang: str = "中文版", season: str = "2026") -> dict:
    """本地已入库版本：{(season, event, doc_type, lang): 最大版本号字符串}。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT DISTINCT season, event, doc_type, version, lang FROM documents WHERE lang=? AND season=?",
            (lang, season),
        ).fetchall()
    finally:
        conn.close()
    best = {}
    for season, event, doc_type, version, lang in rows:
        key = (season, event, normalize_doc_type(doc_type), lang)
        if key not in best or parse_version(version) > parse_version(best[key]):
            best[key] = version
    return best


def _official_best(manifest: dict, lang: str = "中文版", season: str = "2026") -> dict:
    """官方清单里每个 (season, event, doc_type, lang) 的最新版本文档。"""
    best = {}
    for docs in manifest.values():
        for d in docs:
            if d["lang"] != lang:
                continue
            if d.get("season", "2026") != season:
                continue
            dt = normalize_doc_type(d["doc_type"])
            key = (d.get("season", "2026"), d.get("event", "RMUC"), dt, d["lang"])
            if key not in best or parse_version(d["version"]) > parse_version(best[key]["version"]):
                best[key] = {**d, "doc_type": dt}
    return best


def check_update(lang: str = "中文版", season: str = "2026"):
    """抓官方清单并对比本地（默认只看中文版 + 指定赛季），返回 (report, manifest)。

    report = {
        "current": [{doc, local_version}],   # 已最新
        "update":  [{doc, local_version}],   # 官方有新版本
        "new":     [{doc}],                  # 本地从未下载
    }
    """
    manifest = fetch_manifest()
    official = _official_best(manifest, lang, season)
    local = local_versions(lang, season)
    report = {"current": [], "update": [], "new": []}
    for key, d in official.items():
        if key in local:
            if parse_version(d["version"]) > parse_version(local[key]):
                report["update"].append({**d, "local_version": local[key]})
            else:
                report["current"].append({**d, "local_version": local[key]})
        else:
            report["new"].append(d)
    return report, manifest


def download_pdf(d: dict, dest_dir: str = PDF_DIR) -> str:
    """下载单个 PDF 到本地，返回保存路径。"""
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, d["filename"])
    req = urllib.request.Request(d["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        content = resp.read()
    with open(path, "wb") as f:
        f.write(content)
    return path


def download_and_ingest(docs: list[dict]) -> list[dict]:
    """下载 docs 里的 PDF 并解析入库，返回 [{filename, doc_type, version, status}]。"""
    conn = init_db()
    results = []
    for d in docs:
        doc_type = normalize_doc_type(d["doc_type"])
        event = d.get("event", "RMUC")
        season = d.get("season", "2026")
        try:
            # 已入库则跳过下载，避免重复拉取 PDF
            existed = conn.execute(
                "SELECT id FROM documents WHERE season=? AND event=? AND doc_type=? AND version=? AND lang=?",
                (season, event, doc_type, d["version"], d["lang"]),
            ).fetchone()
            if existed:
                results.append({
                    "filename": d["filename"], "doc_type": doc_type, "version": d["version"],
                    "doc_id": existed[0], "clauses": 0, "status": "skipped",
                })
                continue
            path = download_pdf(d)
            doc_id, n = ingest_pdf(path, doc_type, d["version"], d["lang"], conn, event=event, season=season)
            results.append({
                "filename": d["filename"], "doc_type": doc_type, "version": d["version"],
                "doc_id": doc_id, "clauses": n, "status": "ok",
            })
        except Exception as e:  # 单个失败不影响整体
            results.append({
                "filename": d["filename"], "doc_type": doc_type, "version": d["version"],
                "status": "error", "error": str(e),
            })
    conn.close()
    invalidate_manifest_cache()  # 入库后清缓存，下次「检查更新」重新比对
    return results


if __name__ == "__main__":
    report, _ = check_update()
    print(f"已最新: {len(report['current'])} 个")
    print(f"有新版本: {len(report['update'])} 个")
    print(f"新文档: {len(report['new'])} 个")
    for d in report["update"]:
        print(f"  [更新] {d['doc_type']} | {d['lang']}: {d['local_version']} -> {d['version']} ({d['date']})")
    for d in report["new"][:10]:
        print(f"  [新增] {d['doc_type']} | {d['lang']}: {d['version']} ({d['date']})")
