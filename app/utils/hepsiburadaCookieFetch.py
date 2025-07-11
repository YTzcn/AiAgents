from playwright.sync_api import sync_playwright

def fetch_hepsiburada_cookie(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)…",
            locale="tr-TR"
        )
        page = context.new_page()
        page.goto(url)
        # Çerezleri al
        cookies = context.cookies()
        # İstek yapacağınız HTTP client'a çerezleri ekleyin
        cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        browser.close()
        # Şimdi cookie_header ile requests veya aiohttp isteği yapabilirsiniz
        return cookie_header

cookie_str = fetch_hepsiburada_cookie("https://www.hepsiburada.com/")
