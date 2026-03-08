#!/usr/bin/env python3
"""
GitHub 이슈 페이지를 Playwright로 스크린샷 캡처한다.
"""
import asyncio
import os
from playwright.async_api import async_playwright

REPO = "sigongjoa/-remote-print-agent"
ISSUES = [
    (1, "01_architecture"),
    (2, "02_notion_db_schema"),
    (3, "03_local_dispatcher"),
    (4, "04_academy_executor"),
    (5, "05_kakao_notification"),
    (6, "06_setup"),
]
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")


async def capture():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})

        for issue_num, slug in ISSUES:
            url = f"https://github.com/{REPO}/issues/{issue_num}"
            print(f"캡처 중: #{issue_num} → {slug}.png")
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(1500)

            out_path = os.path.join(OUTPUT_DIR, f"{slug}.png")
            await page.screenshot(path=out_path, full_page=True)
            print(f"  저장: {out_path}")

        await browser.close()
    print("\n모든 스크린샷 캡처 완료.")


if __name__ == "__main__":
    asyncio.run(capture())
