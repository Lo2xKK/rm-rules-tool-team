"""版本对比：条款级对齐 + 文本 diff，突出赛季改动。

对齐 key = clause_no（如 "5.4.2"），对每个条款判断：
  added   —— 新版本有、旧版本无
  removed —— 旧版本有、新版本无
  modified—— 两边都有但正文变化（输出字符级 <ins>/<del> diff）
"""
import difflib
import html
import re
import sqlite3

from parser import DB_PATH
from updater import parse_version
from clean import clean_text


def _norm(text):
    return re.sub(r"\s+", "", text or "")


def inline_diff(old: str, new: str) -> str:
    """字符级 diff，返回带 <ins>/<del> 标记的 HTML 片段。"""
    def esc(s):
        return html.escape(s).replace("\n", "<br>")

    sm = difflib.SequenceMatcher(None, old, new)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append(esc(old[i1:i2]))
        elif op == "delete":
            out.append("<del>" + esc(old[i1:i2]) + "</del>")
        elif op == "insert":
            out.append("<ins>" + esc(new[j1:j2]) + "</ins>")
        elif op == "replace":
            out.append("<del>" + esc(old[i1:i2]) + "</del>")
            out.append("<ins>" + esc(new[j1:j2]) + "</ins>")
    return "".join(out)


def _esc(s):
    return html.escape(s).replace("\n", "<br>")


def old_diff_html(old: str, new: str) -> str:
    """旧版视角：被删/被改的部分标红（供双栏视图左栏）。"""
    sm = difflib.SequenceMatcher(None, old, new)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append(_esc(old[i1:i2]))
        elif op in ("delete", "replace"):
            out.append("<del>" + _esc(old[i1:i2]) + "</del>")
    return "".join(out)


def new_diff_html(old: str, new: str) -> str:
    """新版视角：新增/被改的部分标绿（供双栏视图右栏）。"""
    sm = difflib.SequenceMatcher(None, old, new)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append(_esc(new[j1:j2]))
        elif op in ("insert", "replace"):
            out.append("<ins>" + _esc(new[j1:j2]) + "</ins>")
    return "".join(out)


def get_versions(event: str, doc_type: str, lang: str = "中文版", season: str = "2026") -> list[str]:
    """某文档类型已入库的所有版本号（按语义版本升序）。"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT version FROM documents WHERE season=? AND event=? AND doc_type=? AND lang=?",
        (season, event, doc_type, lang),
    ).fetchall()
    conn.close()
    versions = [r[0] for r in rows]
    versions.sort(key=parse_version)
    return versions


def get_latest_version(event: str, doc_type: str, lang: str = "中文版", season: str = "2026") -> str | None:
    """某文档类型在指定赛季的最新版本号（按语义版本取最大）。"""
    versions = get_versions(event, doc_type, lang, season)
    return versions[-1] if versions else None


def _load(conn, season, event, doc_type, version, lang):
    row = conn.execute(
        "SELECT id FROM documents WHERE season=? AND event=? AND doc_type=? AND version=? AND lang=?",
        (season, event, doc_type, version, lang),
    ).fetchone()
    if not row:
        return None, {}
    clauses = conn.execute(
        "SELECT clause_no, title, level, page, content FROM clauses WHERE doc_id=? ORDER BY id",
        (row[0],),
    ).fetchall()
    return row[0], {
        c[0]: {"title": c[1], "level": c[2], "page": c[3], "content": c[4]} for c in clauses
    }


def compare(event: str, doc_type: str, from_v: str, to_v: str, lang: str = "中文版", season: str = "2026", from_season: str = None, to_season: str = None) -> dict:
    """对比两个版本，返回 {from, to, from_season, to_season, summary, changes}。

    默认同赛季（season 生效）；传 from_season / to_season 可跨赛季对比。
    """
    from_season = from_season or season
    to_season = to_season or season
    conn = sqlite3.connect(DB_PATH)
    from_id, old = _load(conn, from_season, event, doc_type, from_v, lang)
    to_id, new = _load(conn, to_season, event, doc_type, to_v, lang)
    conn.close()
    if from_id is None:
        raise ValueError(f"版本不存在: {from_v}")
    if to_id is None:
        raise ValueError(f"版本不存在: {to_v}")

    all_nos = sorted(set(old) | set(new), key=parse_version)
    added = removed = modified = unchanged = 0
    changes = []
    for no in all_nos:
        o, n = old.get(no), new.get(no)
        if o is None:
            added += 1
            changes.append({"clause_no": no, "title": n["title"], "type": "added", "new": clean_text(n["content"]), "new_page": n["page"]})
        elif n is None:
            removed += 1
            changes.append({"clause_no": no, "title": o["title"], "type": "removed", "old": clean_text(o["content"]), "old_page": o["page"]})
        else:
            o_c = clean_text(o["content"])
            n_c = clean_text(n["content"])
            if _norm(o_c) == _norm(n_c):
                unchanged += 1
            else:
                modified += 1
                changes.append({
                    "clause_no": no,
                    "title": n["title"] or o["title"],
                    "type": "modified",
                    "old": o_c,
                    "new": n_c,
                    "diff_html": inline_diff(o_c, n_c),
                    "old_html": old_diff_html(o_c, n_c),
                    "new_html": new_diff_html(o_c, n_c),
                    "old_page": o["page"],
                    "new_page": n["page"],
                })

    return {
        "from": from_v,
        "to": to_v,
        "from_season": from_season,
        "to_season": to_season,
        "from_doc_id": from_id,
        "to_doc_id": to_id,
        "summary": {"added": added, "removed": removed, "modified": modified, "unchanged": unchanged},
        "changes": changes,
    }


if __name__ == "__main__":
    import sys
    event = sys.argv[1] if len(sys.argv) > 1 else "RMUC"
    doc_type = sys.argv[2] if len(sys.argv) > 2 else "比赛规则手册"
    from_v = sys.argv[3] if len(sys.argv) > 3 else "V2.1.0"
    to_v = sys.argv[4] if len(sys.argv) > 4 else "V2.2.0"
    r = compare(event, doc_type, from_v, to_v)
    print(f"对比 {from_v} -> {to_v}:")
    print(f"  新增 {r['summary']['added']} / 修改 {r['summary']['modified']} / "
          f"删除 {r['summary']['removed']} / 未变 {r['summary']['unchanged']}")
    for c in r["changes"][:10]:
        print(f"  [{c['type']}] {c['clause_no']} {c['title']}")
