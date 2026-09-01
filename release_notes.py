"""提取官方规则手册开头的「修改日志」（Release Notes）。

官方 PDF 开头有一张「日期 | 版本 | 修改记录」表格，逐条列出每版改动，
且常带条款号引用（如「详见 5.4.2 性能体系」）。提取它作为版本对比的官方佐证。
"""
import re

import pymupdf

# PDF 里的 bullet 符号（含私用区字符 U+F06C / U+E628）
_BULLETS = "•·\u2022\uf06c\ue628-–—"


def _clean_item(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[\s" + re.escape(_BULLETS) + r"]+", "", line)
    return line.strip()


def extract_release_notes(pdf_path: str) -> list[dict]:
    """从 PDF 提取修改日志，返回 [{date, version, items: [...]}]（版本从新到旧）。"""
    doc = pymupdf.open(pdf_path)
    pages = min(doc.page_count, 15)  # 修改日志 + 目录都在最前面
    full = "".join(doc[i].get_text() for i in range(pages))
    doc.close()

    idx_log = full.find("修改日志")
    if idx_log == -1:
        return []
    idx_end = full.find("目录", idx_log)
    if idx_end == -1:
        idx_end = idx_log + 3000
    seg = full[idx_log:idx_end]

    pattern = re.compile(r"(\d{4}\.\d{2}\.\d{2})\s*\n\s*(V\d+\.\d+\.\d+)")
    matches = list(pattern.finditer(seg))

    notes = []
    for i, m in enumerate(matches):
        date, version = m.group(1), m.group(2)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(seg)
        content = seg[start:end]
        items = []
        for line in content.split("\n"):
            item = _clean_item(line)
            if not item:
                continue
            if re.match(r"^(日期|版本|修改记录)$", item):
                continue
            if "©" in item and "大疆" in item:  # 页脚
                continue
            items.append(item)
        notes.append({"date": date, "version": version, "items": items})
    return notes


if __name__ == "__main__":
    import glob
    pdf = glob.glob("data/pdfs/*规则手册V2.2.0*.pdf")[0]
    notes = extract_release_notes(pdf)
    print(f"共 {len(notes)} 个版本的修改日志\n")
    for n in notes[:5]:
        print(f"[{n['version']}] {n['date']}（{len(n['items'])} 条）")
        for it in n["items"]:
            print(f"  - {it}")
        print()
