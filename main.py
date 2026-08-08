import os
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests

# ===== 從 Railway 環境變數讀取 =====
TARGET_URL = os.getenv("TARGET_URL", "https://tixcraft.com/ticket/area/26_aespa/22415")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "45"))  # 秒，建議 40~60
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
EXCLUDE_KEYWORDS = ["身障", "輪椅", "disabled", "wheelchair", "身障席", "身障區"]

def send_discord(message: str):
    """發送 Discord 通知"""
    if not DISCORD_WEBHOOK_URL:
        print("未設定 DISCORD_WEBHOOK_URL，只印出訊息：")
        print(message)
        return

    payload = {
        "content": message,
        "username": "TixCraft 監票機器人"
    }
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code not in (200, 204):
            print(f"Discord 發送失敗：{resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Discord 錯誤：{e}")

def has_available_tickets(page):
    """檢查是否有非身障區的票，回傳 (有票?, 區域列表)"""
    available = []

    # 常見區域 selector（依實際頁面可能需微調）
    selectors = [
        "div.zone.area-list ul li a",
        ".zone a",
        "ul.area-list li a",
        ".area-list a"
    ]

    areas = []
    for sel in selectors:
        found = page.query_selector_all(sel)
        if found:
            areas = found
            break

    for area in areas:
        text = (area.inner_text() or "").strip()
        href = area.get_attribute("href") or ""

        if not text:
            continue
        # 排除售完
        if any(x in text for x in ["售完", "Sold Out", "sold out", "完售"]):
            continue
        if not href or "javascript" in href.lower():
            continue
        # 排除身障相關
        if any(kw.lower() in text.lower() for kw in EXCLUDE_KEYWORDS):
            continue

        available.append(text)

    # 額外檢查剩餘席次文字
    for font in page.query_selector_all("font"):
        txt = (font.inner_text() or "").strip()
        if re.search(r"剩餘|remaining|席次|席", txt, re.I):
            if not any(kw in txt for kw in EXCLUDE_KEYWORDS):
                available.append(f"[剩餘] {txt}")

    # 去重
    available = list(dict.fromkeys(available))
    return len(available) > 0, available

def main():
    print(f"[{datetime.now()}] 開始監控：{TARGET_URL}")
    print(f"檢查間隔：{CHECK_INTERVAL} 秒")

    if not DISCORD_WEBHOOK_URL:
        print("警告：未設定 DISCORD_WEBHOOK_URL，只會印 log，不會推播")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-TW"
        )
        page = context.new_page()

        while True:
            try:
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3)  # 等待動態內容載入

                has_ticket, areas = has_available_tickets(page)

                if has_ticket:
                    msg = (
                        f"**🎟️ 發現可用票！**\n"
                        f"時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"連結：{TARGET_URL}\n\n"
                        f"**可用區域：**\n" + "\n".join(f"• {a}" for a in areas)
                    )
                    print(msg)
                    send_discord(msg)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 目前無符合條件的票")

            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 監控錯誤：{e}")

            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
