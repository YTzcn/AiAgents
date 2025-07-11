
import asyncio
from playwright.async_api import async_playwright
import logging
import random
import os
import socket
import subprocess
from pathlib import Path

# Logger'ı yapılandır
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kendi tarayıcımızı kullanacağımız için bu artık birincil değil, fallback olarak düşünülebilir.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

async def fetch_hepsiburada_cookies_async():
    """
    9222 portunu kontrol eder; boşsa Chrome'u debug modunda kendi başlatır,
    doluysa mevcut Chrome'a bağlanır. Manuel komut ihtiyacını ortadan kaldırır.
    """
    port = 9222
    
    # 1. Portun kullanımda olup olmadığını kontrol et
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        is_port_in_use = s.connect_ex(('localhost', port)) == 0

    if not is_port_in_use:
        # logger.info(f"{port} portu boş. Yeni Chrome tarayıcısı arka planda başlatılıyor...")
        user_data_dir = os.path.join(Path.home(), "chrome-debug-profile")
        chrome_app_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

        if not os.path.exists(chrome_app_path):
            logger.error(f"Chrome uygulaması beklenen yolda bulunamadı: {chrome_app_path}")
            return None, USER_AGENT
        
        command = [chrome_app_path, f'--remote-debugging-port={port}', f'--user-data-dir={user_data_dir}']
        try:
            # stdout ve stderr'i DEVNULL'a yönlendirerek tarayıcı loglarını gizle
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("Chrome başlatıldı. Bağlanmak için 5 saniye bekleniyor...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Chrome başlatılırken hata oluştu: {e}", exc_info=True)
            return None, USER_AGENT
    # else:
    #     logger.info(f"{port} portu zaten kullanımda. Mevcut Chrome işlemine bağlanılacak.")


    page = None
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.connect_over_cdp(f"http://localhost:{port}")
                context = browser.contexts[0]
                # logger.info(f"Chrome'a (localhost:{port}) başarıyla bağlanıldı.")
            except Exception as e:
                logger.error(f"Çalışan Chrome'a bağlanılamadı. Hata: {e}", exc_info=True)
                logger.error("Eğer Chrome manuel olarak başlatıldıysa, doğru port ve ayarlarla çalıştığından emin olun.")
                return None, USER_AGENT

            page = await context.new_page()

            # logger.info("Hepsiburada arama sayfasına gidiliyor...")
            await page.goto("https://www.hepsiburada.com/ara?q=telefon", wait_until="load", timeout=60000)

            try:
                # logger.info("Cookie onayı butonu aranıyor...")
                accept_button = page.locator('button[id="onetrust-accept-btn-handler"]')
                await accept_button.wait_for(state="visible", timeout=10000)
                await accept_button.click()
                # logger.info("Cookie onayı butonu başarıyla tıklandı.")

                # Tıklama sonrası sayfanın kendini yenilemesi veya oturması için bekle
                # logger.info("Tıklama sonrası sayfanın oturması bekleniyor...")
                await page.wait_for_load_state("networkidle", timeout=15000)
                # logger.info("Sayfa başarıyla oturdu.")
            except Exception:
                # Cookie banner her zaman çıkmayabilir, bu bir hata değil.
                # Bu yüzden uyarı logunu kaldırıyoruz.
                pass

            # Sayfayı yavaşça aşağı kaydırarak insan davranışını taklit et
            # logger.info("Sayfa sonuna doğru kaydırılıyor...")
            await page.evaluate("window.scrollBy(0, 4900)")
            await asyncio.sleep(random.uniform(1, 3))

            # Fareyi rastgele hareket ettir
            # logger.info("Fare imleci hareket ettiriliyor...")
            # Sayfayı yavaşça yukarı ve aşağı kaydır
            for _ in range(random.randint(1, 2)):
                scroll_amount = random.randint(-500, 500)
                await page.mouse.wheel(0, scroll_amount)
                await asyncio.sleep(random.uniform(0.5, 1.5))

            # Sayfanın oturması için kısa bir bekleme
            await page.wait_for_timeout(random.randint(2000, 4000))
            
            # logger.info("Cookie'ler alınıyor.")

            # Gerçek User-Agent'ı sayfadan al
            actual_user_agent = await page.evaluate("() => navigator.userAgent")

            all_cookies = await context.cookies()
            # logger.info(f"Bulunan {len(all_cookies)} cookie'den Akamai olanlar filtreleniyor.")

            cookie_dict = {
                cookie['name']: cookie.get('value', '') 
                for cookie in all_cookies 
                if 'name' in cookie and cookie.get('name') in ['_abck', 'bm_sz', 'bm_sv', 'ak_bmsc', 'hbus_sessionId']
            }

            # Bu yöntemde tarayıcıyı script kapatmaz, kullanıcı kapatır.
            # Sayfayı kapatmak yeterlidir.
            await page.close()
            page = None

            if '_abck' not in cookie_dict or 'bm_sz' not in cookie_dict:
                logger.warning(f"Gerekli tüm Akamai cookie'leri alınamadı. Alınanlar: {list(cookie_dict.keys())}")
                return None, actual_user_agent

            logger.info("Akamai cookie'leri başarıyla alındı.")
            return cookie_dict, actual_user_agent
            
    except Exception as e:
        logger.error(f"Playwright ile cookie alınırken bir hata oluştu: {e}", exc_info=True)
        if page:
            await page.close()
        return None, USER_AGENT

if __name__ == '__main__':
    # Bu script'i doğrudan test etmek için
    async def main():
        cookies, ua = await fetch_hepsiburada_cookies_async()
        if cookies:
            print("Başarıyla alınan cookie'ler:")
            print(cookies)
            print("\nKullanılan User-Agent:")
            print(ua)
            print("\nHeader için Cookie string'i:")
            print("; ".join([f"{k}={v}" for k, v in cookies.items()]))
        else:
            print("Cookie'ler alınamadı.")

    asyncio.run(main()) 