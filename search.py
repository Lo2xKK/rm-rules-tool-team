"""搜索核心：关键词检索条款，支持多关键词 AND，返回带出处的命中列表。"""
import sqlite3

DB_PATH = "data/rules.db"


def search(query: str, limit: int = 100, event: str = None, doc_type: str = None, lang: str = "中文版", versions: list = None, season: str = None) -> list[dict]:
    """关键词检索条款（多关键词 AND），按相关性排序返回。

    相关性打分规则（针对中文规则文本；不引入 FTS5，因 FTS5 默认分词器
    会把连续汉字合并成单个 token、trigram 又要求查询 >=3 字，对 2 字词
    如「飞镖/惩罚」均无法召回）：
    - 关键词在正文出现次数（频率）
    - 关键词首次出现位置越靠前越相关
    - 标题命中重加权（+200）、条款号命中加权（+100）
    - 超长条款轻微惩罚（避免靠绝对出现次数霸榜）
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    keywords = [k.strip() for k in query.split() if k.strip()]
    if not keywords:
        return []
    conds = ["content LIKE ?"] * len(keywords)
    params = ["%" + k + "%" for k in keywords]
    if season:
        conds.append("d.season = ?"); params.append(season)
    if event:
        conds.append("d.event = ?"); params.append(event)
    if doc_type:
        conds.append("d.doc_type = ?"); params.append(doc_type)
    if lang:
        conds.append("d.lang = ?"); params.append(lang)
    if versions:
        placeholders = ",".join("?" * len(versions))
        conds.append(f"d.version IN ({placeholders})")
        params.extend(versions)
    where = " AND ".join(conds)
    sql = (
        "SELECT c.id, c.clause_no, c.title, c.page, c.content, "
        "d.doc_type, d.version, d.lang, d.event, d.season, d.id AS doc_id "
        "FROM clauses c JOIN documents d ON c.doc_id = d.id "
        f"WHERE {where}"
    )
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    # 相关性打分 + 排序
    scored = []
    for r in rows:
        content = (r["content"] or "").lower()
        title = (r["title"] or "").lower()
        clause_no = (r["clause_no"] or "").lower()
        s = 0.0
        for kw in keywords:
            k = kw.lower()
            cnt = content.count(k)
            s += cnt * 10.0                                # 出现频率
            first = content.find(k)
            if first >= 0:
                s += max(0.0, 100.0 - first) * 0.5         # 首次位置靠前加分
            if k in title:
                s += 200.0                                  # 标题命中重加权
            if clause_no and k in clause_no:
                s += 100.0                                  # 条款号命中加权
        s -= len(content) / 800.0                           # 超长条款轻微惩罚
        scored.append((s, r))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    return [dict(r) for _, r in scored[:limit]]


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
