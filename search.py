"""搜索核心：关键词检索条款，支持多关键词 AND，返回带出处的命中列表。"""
import sqlite3

DB_PATH = "data/rules.db"


def search(query: str, limit: int = 100, event: str = None, doc_type: str = None, lang: str = "中文版") -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    keywords = [k.strip() for k in query.split() if k.strip()]
    if not keywords:
        return []
    conds = ["content LIKE ?"] * len(keywords)
    params = ["%" + k + "%" for k in keywords]
    if event:
        conds.append("d.event = ?"); params.append(event)
    if doc_type:
        conds.append("d.doc_type = ?"); params.append(doc_type)
    if lang:
        conds.append("d.lang = ?"); params.append(lang)
    where = " AND ".join(conds)
    sql = (
        "SELECT c.id, c.clause_no, c.title, c.page, c.content, "
        "d.doc_type, d.version, d.lang, d.event "
        "FROM clauses c JOIN documents d ON c.doc_id = d.id "
        f"WHERE {where} ORDER BY c.id LIMIT ?"
    )
    rows = conn.execute(sql, params + [limit]).fetchall()
    return [dict(r) for r in rows]


def highlight(text: str, keywords: list[str]) -> str:
    """给关键词加 <mark> 标记（供前端直接渲染）。"""
    for k in keywords:
        text = text.replace(k, f"<mark>{k}</mark>")
    return text


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "飞镖 发射"
    results = search(q)
    kws = [k for k in q.split() if k.strip()]
    print(f"搜索 '{q}' 命中 {len(results)} 条\n")
    for r in results[:8]:
        content = r["content"].replace("\n", " ")
        idx = min([content.find(k) for k in kws if content.find(k) >= 0], default=0)
        print(f"[{r['clause_no']} {r['title']}] p{r['page']} ({r['version']})")
        print("   ...", content[max(0, idx - 25):idx + 70].strip(), "...\n")
