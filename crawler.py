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
from urllib.parse import unquote

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

WIKI_URLS = {
    "RMUC": "https://bbs.robomaster.com/wiki/20204847/809871",
    "RMUL": "https://bbs.robomaster.com/wiki/20204847/809872",
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


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


def fetch_manifest() -> dict:
    """抓取官方 wiki，返回结构化版本清单 {RMUC: [doc...], RMUL: [doc...]}。

    供爬虫 CLI 和「检查更新」接口复用。
    """
    all_docs = {}
    for key, url in WIKI_URLS.items():
        html = render_page(url)
        docs = parse_versions(html)
        for d in docs:
            d["event"] = key  # RMUC / RMUL
        all_docs[key] = docs
    return all_docs


def main():
    save = "--save" in sys.argv
    all_docs = fetch_manifest()

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
