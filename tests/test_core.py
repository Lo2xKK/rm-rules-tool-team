# -*- coding: utf-8 -*-
"""核心模块单测：clean（清洗正则）/ compare（diff）/ updater（版本解析）/ parser（切分）。

保护对象：clean.py 里手调的正则（规则编号 vs 场地标识 vs RGB 颜色值）、
compare.py 的字符级 diff、updater.py 的版本号兼容解析。
运行：python tests/test_core.py
"""
import glob
import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from clean import clean_text, plain, was_cleaned, focus_snippet
from compare import inline_diff, old_diff_html, new_diff_html
from updater import parse_version, normalize_doc_type


class CleanTest(unittest.TestCase):
    """clean.py 清洗规则（手调正则，最需要回归保护）。"""

    def test_pua_removed(self):
        # 私用区字符（豆腐块元凶）删除
        self.assertEqual(clean_text("正文\uf06c内容"), "正文内容")

    def test_rule_no_replaced(self):
        # 规则编号 R57 替换成句号作分隔
        self.assertEqual(clean_text("R57 机器人不得主动接触对方"), "。 机器人不得主动接触对方")

    def test_field_marker_kept(self):
        # 场地标识「R3 梯形高地」不能当成规则编号删掉
        self.assertEqual(clean_text("R3 梯形高地内禁止"), "R3 梯形高地内禁止")

    def test_rgb_kept(self):
        # RGB 颜色值「R255」不能当成规则编号删掉
        self.assertEqual(clean_text("RGB R255 表示红色"), "RGB R255 表示红色")

    def test_copyright_removed(self):
        self.assertEqual(clean_text("© 2026 大疆 版权所有"), "")

    def test_pure_page_removed(self):
        self.assertEqual(clean_text("42"), "")

    def test_figure_removed(self):
        self.assertEqual(clean_text("图 1-1 人才培养理念"), "")

    def test_plain_joins_cjk(self):
        # 中文断行直接连接
        self.assertEqual(plain("规则\n内容"), "规则内容")

    def test_plain_keeps_latin_space(self):
        # 英文/数字之间断行保留空格，避免单词粘连
        self.assertEqual(plain("Robo\nMaster 系统"), "Robo Master 系统")

    def test_plain_merges_double_period(self):
        # 规则编号替换后产生的连续句号合并
        self.assertEqual(plain("R57 内容。R58 内容"), "。内容。内容")

    def test_was_cleaned(self):
        self.assertTrue(was_cleaned("正文\uf06c内容", "正文内容"))
        self.assertFalse(was_cleaned("相同", "相同"))

    def test_focus_snippet_merges_overlap(self):
        # 相邻关键词片段重叠时合并，不产生中间省略号
        cleaned = "前文一二三四五六七八九十飞镖发射限制后文"
        s = focus_snippet(cleaned, ["飞镖", "发射"])
        self.assertNotIn(" … ", s)

    def test_focus_snippet_no_keyword(self):
        cleaned = "一段没有关键词的文本"
        self.assertEqual(focus_snippet(cleaned, []), cleaned[:70])


class CompareTest(unittest.TestCase):
    """compare.py 字符级 diff 纯函数。"""

    def test_inline_diff_replace(self):
        d = inline_diff("旧规则", "新规则")
        self.assertIn("<del>旧</del>", d)
        self.assertIn("<ins>新</ins>", d)

    def test_inline_diff_insert(self):
        d = inline_diff("规则", "规则内容")
        self.assertIn("<ins>内容</ins>", d)
        self.assertNotIn("<del>", d)

    def test_inline_diff_delete(self):
        d = inline_diff("规则内容", "规则")
        self.assertIn("<del>内容</del>", d)
        self.assertNotIn("<ins>", d)

    def test_inline_diff_equal(self):
        self.assertEqual(inline_diff("相同", "相同"), "相同")

    def test_old_diff_html(self):
        # 旧版视角只标删除/替换的旧文本，不含新文本
        d = old_diff_html("旧规则", "新规则")
        self.assertIn("<del>旧</del>", d)
        self.assertNotIn("新规则", d)

    def test_new_diff_html(self):
        # 新版视角只标新增/替换的新文本
        d = new_diff_html("旧规则", "新规则")
        self.assertIn("<ins>新</ins>", d)


class VersionTest(unittest.TestCase):
    """updater.py 版本号解析（历年格式兼容）。"""

    def test_parse_version_three_part(self):
        self.assertEqual(parse_version("V2.2.0"), (2, 2, 0))

    def test_parse_version_two_part(self):
        # 2024 赛季两位版本号
        self.assertEqual(parse_version("V1.0"), (1, 0, 0))

    def test_parse_version_invalid(self):
        self.assertEqual(parse_version("无版本"), (0, 0, 0))

    def test_parse_version_orderable(self):
        # 两位与三位版本号可比：2.1.0 > 2.0
        self.assertGreater(parse_version("V2.1.0"), parse_version("V2.0"))

    def test_normalize_doc_type(self):
        # 中英混排取中文部分
        self.assertEqual(normalize_doc_type("比赛规则手册 Rule Manual"), "比赛规则手册")


class ParserTest(unittest.TestCase):
    """parser.py TOC 切分（集成，依赖真实 PDF 数据）。"""

    @unittest.skipUnless(
        os.path.isdir(os.path.join(BASE, "data", "pdfs")),
        "无 data/pdfs 目录，跳过",
    )
    def test_extract_clauses(self):
        from parser import extract_clauses
        pdfs = sorted(glob.glob(os.path.join(BASE, "data", "pdfs", "*.pdf")))
        self.assertTrue(pdfs, "data/pdfs 下无 PDF")
        clauses = extract_clauses(pdfs[0])
        self.assertGreater(len(clauses), 0, "TOC 切分应产出条款")
        self.assertTrue(all(c["no"] for c in clauses), "每条应有条款号")


class CacheTest(unittest.TestCase):
    """crawler.fetch_manifest 的 TTL 缓存行为（mock 渲染，不真抓官方）。"""

    def test_manifest_cache_avoids_rerender(self):
        from unittest import mock
        import crawler
        crawler.invalidate_manifest_cache()

        with mock.patch.object(crawler, "render_page", return_value="<html></html>"), \
             mock.patch.object(crawler, "parse_versions", return_value=[]):
            crawler.fetch_manifest()
        # 缓存命中：不再渲染
        with mock.patch.object(crawler, "render_page", return_value="<html></html>") as rp, \
             mock.patch.object(crawler, "parse_versions", return_value=[]):
            crawler.fetch_manifest()
            self.assertEqual(rp.call_count, 0)
        # force=True：强制重新渲染两次（RMUC + RMUL）
        with mock.patch.object(crawler, "render_page", return_value="<html></html>") as rp2, \
             mock.patch.object(crawler, "parse_versions", return_value=[]):
            crawler.fetch_manifest(force=True)
            self.assertEqual(rp2.call_count, 2)

    def test_manifest_cache_invalidate(self):
        from unittest import mock
        import crawler
        crawler.invalidate_manifest_cache()
        with mock.patch.object(crawler, "render_page", return_value="<html></html>"), \
             mock.patch.object(crawler, "parse_versions", return_value=[]):
            crawler.fetch_manifest()
        crawler.invalidate_manifest_cache()
        with mock.patch.object(crawler, "render_page", return_value="<html></html>") as rp, \
             mock.patch.object(crawler, "parse_versions", return_value=[]):
            crawler.fetch_manifest()
            self.assertEqual(rp.call_count, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
