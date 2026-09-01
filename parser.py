"""阶段 1：把规则手册 PDF 解析成结构化条款，存入 SQLite。

切分策略：用 PDF 自带目录（TOC）拿到条款号 + 标题 + 页码，
再在正文文本流里按标题精确定位，切出每个条款的正文。
"""
import glob
import re
import sqlite3
import os

import pymupdf

DB_PATH = "data/rules.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT,
        doc_type TEXT,
        version TEXT,
        lang TEXT,
        filename TEXT,
        pdf_path TEXT
    )""")
    # 迁移：旧表无 event 列则添加，并回填（历史数据均为 RMUC）
    cols = [r[1] for r in c.execute("PRAGMA table_info(documents)")]
    if "event" not in cols:
        c.execute("ALTER TABLE documents ADD COLUMN event TEXT")
        c.execute("UPDATE documents SET event='RMUC' WHERE event IS NULL")
    c.execute("""CREATE TABLE IF NOT EXISTS clauses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER,
        clause_no TEXT,
        title TEXT,
        level INTEGER,
        page INTEGER,
        content TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_clauses_doc ON clauses(doc_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_clauses_no ON clauses(clause_no)")
    conn.commit()
    return conn


def extract_clauses(pdf_path: str) -> list[dict]:
    """解析 PDF，返回条款列表 [{no, title, level, page, content}]。"""
    doc = pymupdf.open(pdf_path)
    toc = doc.get_toc()
    pages = [doc[i].get_text() for i in range(doc.page_count)]

    # 全文流 + 每页偏移
    full_text = ""
    page_bounds = []  # (start, end, page_no)
    for i, t in enumerate(pages):
        start = len(full_text)
        full_text += t + "\n"
        page_bounds.append((start, len(full_text), i + 1))

    # 带条款号的 TOC 条目
    items = []
    for level, title, page in toc:
        m = re.match(r"^(\d+(?:\.\d+)*)\s*(.*)$", title.strip())
        if m:
            items.append({
                "no": m.group(1),
                "title": m.group(2).strip(),
                "level": level,
                "page": page,
            })

    def locate(title_no, title, page):
        """在起始页附近定位标题，返回全文偏移。"""
        if page - 1 >= len(page_bounds):
            return None
        start = page_bounds[page - 1][0]
        seg = full_text[start:]
        pat = re.escape(title_no) + r"\s*" + re.escape(title)
        m = re.search(pat, seg)
        return start + m.start() if m else None

    clauses = []
    for i, item in enumerate(items):
        pos = locate(item["no"], item["title"], item["page"])
        if pos is None:
            pos = page_bounds[item["page"] - 1][0] if item["page"] - 1 < len(page_bounds) else 0
        # 下一条款的起点
        if i + 1 < len(items):
            nxt = items[i + 1]
            end = locate(nxt["no"], nxt["title"], nxt["page"])
            if end is None:
                end = page_bounds[nxt["page"] - 1][0]
        else:
            end = len(full_text)
        content = full_text[pos:end].strip()
        clauses.append({**item, "content": content})

    return clauses


def ingest_pdf(pdf_path: str, doc_type: str, version: str, lang: str, conn=None, event: str = "RMUC"):
    """解析一个 PDF 并入库，返回文档 id 与条款数。"""
    conn = conn or sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 去重：同 (event, doc_type, version, lang) 已入库则跳过
    existed = cur.execute(
        "SELECT id FROM documents WHERE event=? AND doc_type=? AND version=? AND lang=?",
        (event, doc_type, version, lang),
    ).fetchone()
    if existed:
        return existed[0], 0
    clauses = extract_clauses(pdf_path)
    filename = os.path.basename(pdf_path)
    cur.execute(
        "INSERT INTO documents(event, doc_type, version, lang, filename, pdf_path) VALUES(?,?,?,?,?,?)",
        (event, doc_type, version, lang, filename, pdf_path),
    )
    doc_id = cur.lastrowid
    for cl in clauses:
        cur.execute(
            "INSERT INTO clauses(doc_id, clause_no, title, level, page, content) VALUES(?,?,?,?,?,?)",
            (doc_id, cl["no"], cl["title"], cl["level"], cl["page"], cl["content"]),
        )
    conn.commit()
    return doc_id, len(clauses)


if __name__ == "__main__":
    pdf = glob.glob("data/pdfs/*.pdf")[0]
    conn = init_db()
    doc_id, n = ingest_pdf(pdf, "比赛规则手册", "V2.2.0", "中文版", conn)
    print(f"入库完成: doc_id={doc_id}, 条款数={n}")
    # 抽样看 2 条正文切分效果
    cur = conn.cursor()
    for row in cur.execute(
        "SELECT clause_no, title, page, substr(content,1,120) FROM clauses WHERE doc_id=? LIMIT 3",
        (doc_id,),
    ):
        print(f"\n[{row[0]} {row[1]} p{row[2]}]")
        print(row[3].replace("\n", " "))
