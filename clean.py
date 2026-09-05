"""内容清洗：去除 PDF/OCR 提取产生的豆腐块字符、页脚版权、纯页码行，压缩短行碎片。

PDF 提取文本里的"方框字符"本质是私用区（Private Use Area, U+E000–U+F8FF）码位：
项目符号/图标在字体里没有对应字形，浏览器渲染成豆腐块（□）。删除这些码位即可。
"""
import re

# 私用区字符（PUA）：PDF 图标/项目符号提取失败产生的豆腐块元凶
_PUA = re.compile(r"[\ue000-\uf8ff]")

# 规则编号：行首的 R57 这类编号（前面非字母数字/连字符）。
# 排除：场地标识（梯形高地/环形高地/定位标签）、RGB 颜色值 R255（前面是字母+空格，如 "RGB R255"）
_RULE_NO = re.compile(
    r"(?<![-A-Za-z0-9])"
    r"(?<![A-Za-z]\s)"
    r"R\d+(?:\.\d+)?"
    r"(?![-\d])"
    r"(?!\s*[A-Za-z])"
    r"(?!\s*(?:梯形高地|环形高地|定位标签|场地定位标))"
)

# 图注行："图 1-1 人才培养理念" 之类
_FIGURE = re.compile(r"^图\s*\d+[-–—]\d+")

# 纯页码行
_PAGE = re.compile(r"^\d{1,4}$")


def clean_text(text: str) -> str:
    """清洗文本，保留段落换行结构。

    处理：删除私用区字符、删除规则编号（R57）、删除版权页脚行（含 © 与大疆）、
    删除纯页码行、删除空白行、规范化换行。适用于对比视图的条款全文展示。
    """
    if not text:
        return ""
    lines = []
    for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        ln = _PUA.sub("", ln)
        ln = _RULE_NO.sub("。", ln)  # 规则编号替换成句号，作为规则条目的分隔
        ln = ln.strip()
        if not ln:
            continue
        if "©" in ln and "大疆" in ln:
            continue  # 版权页脚行
        if _PAGE.fullmatch(ln):
            continue  # 纯页码
        if _FIGURE.match(ln):
            continue  # 图注行
        lines.append(ln)
    return "\n".join(lines)


def plain(text: str) -> str:
    """清洗并压缩为连贯单段文本（去除换行），用于搜索结果的摘要片段。"""
    t = clean_text(text)
    # 中文断行直接连接；英文/数字之间的断行保留空格（避免单词粘连）
    t = re.sub(r"(?<=[A-Za-z0-9])\n(?=[A-Za-z0-9])", " ", t)
    t = t.replace("\n", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"。\s*。", "。", t)  # 合并规则编号替换后产生的连续句号
    t = re.sub(r"。 +", "。", t)  # 句号后多余空格去掉
    return t.strip()


def was_cleaned(raw: str, cleaned: str) -> bool:
    """判断清洗前后是否有实质变化（内容不同）。"""
    return raw != cleaned


def focus_snippet(cleaned: str, keywords: list[str], before: int = 40, after: int = 70) -> str:
    """多关键词聚焦摘要：在已清洗文本上，每个关键词截取上下文片段，用 … 连接。

    相邻片段重叠时自动合并，避免重复。用于搜索结果 snippet，比整段窗口更聚焦。
    """
    if not cleaned:
        return ""
    if not keywords:
        return cleaned[:after]
    positions = []
    for k in keywords:
        idx = cleaned.find(k)
        if idx >= 0:
            positions.append((idx, len(k)))
    if not positions:
        return cleaned[: before + after]
    positions.sort()
    segs = []
    for idx, ln in positions:
        s = max(0, idx - before)
        e = min(len(cleaned), idx + ln + after)
        if segs and s <= segs[-1][1]:
            segs[-1] = (segs[-1][0], max(segs[-1][1], e))
        else:
            segs.append((s, e))
    parts = [cleaned[s:e].strip() for s, e in segs]
    return " … ".join(parts)
