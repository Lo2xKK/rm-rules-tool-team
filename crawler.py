"""RoboMaster 官方规则爬虫（阶段 0）。

功能：
  1. 用 Playwright 渲染官方 wiki 页面（正文是 JS 异步加载，需真实浏览器）。
  2. 解析出结构化版本清单：文档类型 / 语言 / 版本号 / 发布日期 / PDF 直链。

用法：
    .venv/Scripts/python.exe crawler.py            # 抓取并打印版本清单
    .venv/Scripts/python.exe crawler.py --save     # 额外保存到 data/versions.json
"""
import json
import os
import re
import sys
import time
from urllib.parse import unquote

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

WIKI_URLS = {
    "RMUC": "https://bbs.robomaster.com/wiki/20204847/809871",
    "RMUL": "https://bbs.robomaster.com/wiki/20204847/809872",
}

# 历史赛季数据源（robomaster.com 资料站 announcement 页，每赛季一个页面 ID）
# 总入口：https://www.robomaster.com/zh-CN/resource/announcement/competition
ANNOUNCEMENT_URLS = {
    "2025": "https://www.robomaster.com/zh-CN/resource/pages/announcement/1768",
    "2024": "https://www.robomaster.com/zh-CN/resource/pages/announcement/1653",
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _load_config():
    """从 config.json 覆盖数据源配置（新赛季只需改配置、不改代码）。

    覆盖项：wiki_urls（当前赛季 wiki）、announcement_urls（历史赛季资料站）、
    user_agent。config.json 缺失或损坏时静默回退到上方硬编码默认值。
    """
    global UA
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return
    if cfg.get("wiki_urls"):
        WIKI_URLS.update(cfg["wiki_urls"])
    if cfg.get("announcement_urls"):
        ANNOUNCEMENT_URLS.update(cfg["announcement_urls"])
    if cfg.get("user_agent"):
        UA = cfg["user_agent"]


_load_config()


def extract_season(text: str) -> str | None:
    """从文件名/标题提取赛季年份。

    官方命名统一为「RoboMaster 2026」「机甲大师 2026」等，年份紧跟赛事名。
    注意：不能用发布日期（2026 赛季的 V1.0.0 发布于 2025-10-21，跨年）。
    """
    m = re.search(r"(?:RoboMaster|机甲大师|RM)\s*[（(]?\s*(\d{4})", text or "")
    if m:
        return m.group(1)
    return None


def render_page(url: str) -> str:
    """渲染页面并返回完整 HTML。"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="zh-CN")
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)  # 等待正文异步加载
        html = page.content()
        browser.close()
        return html


def parse_versions(html: str) -> list[dict]:
    """从渲染后 HTML 解析结构化版本清单。

    DOM 结构：h1=文档类型，h2=语言，table=版本列表（版本|发布日期|文档）。
    """
    soup = BeautifulSoup(html, "lxml")
    docs = []
    doc_type, doc_lang = None, None

    for el in soup.find_all(["h1", "h2", "table"]):
        if el.name == "h1":
            doc_type = el.get_text(strip=True)
        elif el.name == "h2":
            doc_lang = el.get_text(strip=True)
        elif el.name == "table":
            for tr in el.find_all("tr"):
                cells = tr.find_all(["td", "th"])
                if len(cells) < 3:
                    continue
                version = cells[0].get_text(strip=True)
                date = cells[1].get_text(strip=True)
                link = cells[2].find("a", href=True)
                if not link or ".pdf" not in link["href"].lower():
                    continue
                url = link["href"]
                docs.append({
                    "doc_type": doc_type,
                    "lang": doc_lang,
                    "version": version,
                    "date": date,
                    "url": url,
                    "filename": unquote(url.split("/")[-1]),
                })
    return docs


def parse_announcement(html: str, season: str = "2025") -> list[dict]:
    """解析 robomaster.com 资料站 announcement 页面的规则文件表格。

    表格列：适用赛事 | 类别 | 版本 | 手册下载 | 状态 | 发布日期，前两列用 rowspan 合并，
    需向下填充。只取三类核心文档（规则手册/制作规范/参赛手册），跳过增补说明、串口协议等。
    """
    soup = BeautifulSoup(html, "lxml")
    docs = []
    cur_event = None
    cur_category = None

    EVENT_MAP = {"超级对抗赛": "RMUC", "高校联盟赛": "RMUL"}
    CATEGORY_MAP = {
        "规则手册": "比赛规则手册",
        "机器人制作规范手册": "机器人制作规范手册",
        "参赛手册": "参赛手册",
    }

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
        if "手册下载" not in header:
            continue

        for tr in rows[1:]:
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue
            n = len(cells)
            if n >= 6:
                cur_event = cells[0].get_text(strip=True)
                cur_category = cells[1].get_text(strip=True)
                version = cells[2].get_text(strip=True)
                download_cell = cells[3]
                date = cells[5].get_text(strip=True)
            elif n == 5:
                cur_category = cells[0].get_text(strip=True)
                version = cells[1].get_text(strip=True)
                download_cell = cells[2]
                date = cells[4].get_text(strip=True)
            elif n == 4:
                version = cells[0].get_text(strip=True)
                download_cell = cells[1]
                date = cells[3].get_text(strip=True)
            else:
                continue

            if cur_category not in CATEGORY_MAP:
                continue
            if not re.match(r"^\d+(\.\d+){1,2}$", version):
                continue
            link = download_cell.find("a", href=True)
            if not link or ".pdf" not in link["href"].lower():
                continue

            url = link["href"]
            filename = unquote(url.split("/")[-1])
            version_v = "V" + version
            doc_type = CATEGORY_MAP[cur_category]

            # 高校系列赛通用（制作规范手册）同时适用于 RMUC 和 RMUL
            events = ["RMUC", "RMUL"] if cur_event == "高校系列赛通用" else [EVENT_MAP.get(cur_event, cur_event)]
            for ev in events:
                dt = doc_type
                # RMUL 制作规范 doc_type 对齐 2026 数据（无「手册」二字）
                if ev == "RMUL" and doc_type == "机器人制作规范手册":
                    dt = "机器人制作规范"
                docs.append({
                    "event": ev,
                    "doc_type": dt,
                    "lang": "中文版",
                    "version": version_v,
                    "date": date,
                    "url": url,
                    "filename": filename,
                    "season": season,
                })
    return docs


def fetch_announcement(season: str = "2025") -> list[dict]:
    """抓取指定赛季的资料站 announcement 页面，返回结构化版本清单（list）。"""
    url = ANNOUNCEMENT_URLS.get(season)
    if not url:
        raise ValueError(f"未配置赛季 {season} 的数据源 URL（见 ANNOUNCEMENT_URLS）")
    html = render_page(url)
    return parse_announcement(html, season)


MANIFEST_TTL = 600  # 官方清单缓存有效期（秒）

_MANIFEST_CACHE = {"data": None, "ts": 0.0}


def fetch_manifest(force: bool = False) -> dict:
    """抓取官方 wiki，返回结构化版本清单 {RMUC: [doc...], RMUL: [doc...]}。

    带 TTL 内存缓存（默认 10 分钟）：缓存命中时直接返回，避免每次「检查更新」
    都真实渲染官方页面（每次十几秒）。force=True 强制重新渲染。

    供爬虫 CLI 和「检查更新」接口复用。
    """
    if not force and _MANIFEST_CACHE["data"] is not None and (time.time() - _MANIFEST_CACHE["ts"]) < MANIFEST_TTL:
        return _MANIFEST_CACHE["data"]
    all_docs = {}
    for key, url in WIKI_URLS.items():
        html = render_page(url)
        docs = parse_versions(html)
        for d in docs:
            d["event"] = key  # RMUC / RMUL
            d["season"] = extract_season(d["filename"]) or "2026"  # 当前页面即 2026 赛季
        all_docs[key] = docs
    _MANIFEST_CACHE["data"] = all_docs
    _MANIFEST_CACHE["ts"] = time.time()
    return all_docs


def invalidate_manifest_cache():
    """清除清单缓存（下载入库后调用，确保下次「检查更新」重新渲染拿到最新）。"""
    _MANIFEST_CACHE["data"] = None
    _MANIFEST_CACHE["ts"] = 0.0


def main():
    save = "--save" in sys.argv
    all_docs = fetch_manifest(force=True)  # CLI 手动抓取，总是拿最新

    # 打印摘要
    for key, docs in all_docs.items():
        print(f"\n===== {key}（共 {len(docs)} 个 PDF）=====")
        for d in docs:
            print(f"  [{d['doc_type']} | {d['lang']}] {d['version']}  {d['date']}")

    if save:
        os.makedirs("data", exist_ok=True)
        with open("data/versions.json", "w", encoding="utf-8") as f:
            json.dump(all_docs, f, ensure_ascii=False, indent=2)
        print("\n已保存到 data/versions.json")


if __name__ == "__main__":
    main()
