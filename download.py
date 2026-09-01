"""首次全量建库：下载官方全部文档并入库（命令行用，避免页面一次下载几十个阻塞）。

用法：
    .venv/Scripts/python.exe download.py              # 下载 RMUC + RMUL 全部文档
    .venv/Scripts/python.exe download.py --only-rmuc  # 只下载超级对抗赛
    .venv/Scripts/python.exe download.py --rules-cn   # 只下载 RMUC 规则手册中文版（对比功能核心数据）
    .venv/Scripts/python.exe download.py --zh-only    # 只下载所有中文版文档（规则/制作规范/参赛手册）
"""
import sys

from crawler import fetch_manifest
from updater import download_and_ingest


def main():
    only_rmuc = "--only-rmuc" in sys.argv
    rules_cn = "--rules-cn" in sys.argv
    zh_only = "--zh-only" in sys.argv
    manifest = fetch_manifest()

    all_docs = []
    for event, docs in manifest.items():
        if only_rmuc and event != "RMUC":
            continue
        for d in docs:
            if rules_cn:
                if d.get("event") == "RMUC" and "规则手册" in d["doc_type"] and d["lang"] == "中文版":
                    all_docs.append(d)
            elif zh_only:
                if d["lang"] == "中文版":
                    all_docs.append(d)
            else:
                all_docs.append(d)

    print(f"共 {len(all_docs)} 个文档，开始下载入库（已入库的会自动跳过）...\n")
    results = download_and_ingest(all_docs)

    ok = [r for r in results if r["status"] == "ok"]
    skipped = [r for r in results if r["status"] == "skipped"]
    failed = [r for r in results if r["status"] == "error"]

    print(f"\n===== 完成 =====")
    print(f"新入库: {len(ok)} 个")
    print(f"跳过(已存在): {len(skipped)} 个")
    print(f"失败: {len(failed)} 个")
    for r in ok:
        print(f"  [入库] {r['doc_type']} {r['version']} | 条款 {r['clauses']} 条")
    for r in failed:
        print(f"  [失败] {r['filename']}: {r.get('error')}")


if __name__ == "__main__":
    main()
