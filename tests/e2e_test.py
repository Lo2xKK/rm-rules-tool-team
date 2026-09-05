"""端到端自测：搜索 / 对比 / PDF 查看 / 检查更新 四条核心链路"""
import asyncio
from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8000/"
results = []


def log(name, ok, detail=""):
    mark = "✅" if ok else "❌"
    results.append((name, ok, detail))
    print(f"{mark} {name}  {detail}")


async def wait_pdf_loaded(page, max_ms=10000):
    """等 PDF modal 任一侧加载到非加载中文本（双 PDF 查看器用 pdfPageInfoL/R）"""
    waited = 0
    step = 300
    text = ""
    while waited < max_ms:
        for sel in ("#pdfPageInfoL", "#pdfPageInfoR"):
            try:
                t = await page.eval_on_selector(sel, "el => el.textContent")
                if "/" in t and "加载" not in t:
                    return t
            except Exception:
                pass
        await page.wait_for_timeout(step)
        waited += step
    return text


async def close_pdf_modal(page):
    try:
        await page.click(".pdf-close", timeout=2000)
        await page.wait_for_timeout(300)
    except Exception:
        pass


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # === 链路 1：搜索 → 结果 → 点卡片 → PDF ===
        await page.goto(URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1200)

        await page.fill("#q", "飞镖")
        await page.press("#q", "Enter")
        await page.wait_for_timeout(2000)

        stats = await page.eval_on_selector("#stats", "el => el.textContent")
        log("搜索 '飞镖'", "条" in stats, f"stats={stats!r}")

        result_count = await page.eval_on_selector_all("#results [data-doc]", "els => els.length")
        log("搜索结果渲染", result_count > 0, f"卡片数={result_count}")

        await page.click("#results [data-doc]")
        page_info = await wait_pdf_loaded(page)
        log("搜索→PDF 查看", "/" in page_info and "加载" not in page_info, f"pageInfo={page_info!r}")
        await close_pdf_modal(page)

        # === 链路 2：切到对比 → 选版本 → 对比 → 点卡片 → PDF ===
        await page.click("#tabCompare")
        await page.wait_for_timeout(800)

        cmp_doc_options = await page.eval_on_selector_all("#cmpDoc option", "els => els.length")
        log("对比 tab 文档下拉", cmp_doc_options > 0, f"选项数={cmp_doc_options}")

        await page.select_option("#cmpDoc", index=0)
        await page.wait_for_timeout(500)

        from_options = await page.eval_on_selector_all("#cmpFrom option", "els => els.map(o => o.value)")
        to_options = await page.eval_on_selector_all("#cmpTo option", "els => els.map(o => o.value)")
        if len(from_options) >= 2 and len(to_options) >= 1:
            # 版本按升序：最旧在前，最新在后；选最旧→最新做对比
            await page.select_option("#cmpFrom", from_options[0])
            await page.select_option("#cmpTo", from_options[-1])
            await page.click(".cmp-bar button:has-text('对比')")
            await page.wait_for_timeout(3000)

            cmp_results = await page.eval_on_selector_all(
                "#cmpResults [data-to-doc], #cmpResults [data-from-doc]", "els => els.length"
            )
            log("对比渲染结果卡片", cmp_results > 0, f"可点卡片数={cmp_results}")

            card = await page.query_selector("#cmpResults [data-to-doc], #cmpResults [data-from-doc]")
            if card:
                await card.click()
                page_info2 = await wait_pdf_loaded(page)
                log("对比→PDF 查看", "/" in page_info2 and "加载" not in page_info2, f"pageInfo={page_info2!r}")
                await close_pdf_modal(page)
            else:
                log("对比→PDF 查看", False, "无可点击的对比卡片")
        else:
            log("对比渲染结果卡片", False, f"from/options={from_options}/{to_options}")

        # === 链路 3：检查更新按钮 ===
        await page.click("#tabSearch")
        await page.wait_for_timeout(500)
        btn_exists = await page.query_selector("#checkBtn") is not None
        log("检查更新按钮存在", btn_exists)
        # 触发一次检查更新（即使 autoCheck 已触发过，再次点也能验证流程）
        await page.click("#checkBtn")
        await page.wait_for_timeout(3000)
        update_panel_hidden = await page.eval_on_selector("#updatePanel", "el => el.classList.contains('hidden')")
        update_text = await page.eval_on_selector("#updatePanel", "el => el.innerText")
        log("检查更新结果展示", not update_panel_hidden and len(update_text) > 0,
            f"hidden={update_panel_hidden}, text={update_text[:60]!r}")

        # === 总结 ===
        print("\n===== 总结 =====")
        ok_count = sum(1 for _, ok, _ in results if ok)
        print(f"通过 {ok_count}/{len(results)}")
        if errors:
            print(f"⚠️ 出现 {len(errors)} 个 pageerror:")
            for e in errors:
                print(f"  - {e}")
        else:
            print("无 pageerror")

        await browser.close()
        return 0 if ok_count == len(results) and not errors else 1


import sys
sys.exit(asyncio.run(main()))
