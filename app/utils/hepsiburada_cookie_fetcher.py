
import asyncio
from playwright.async_api import async_playwright
import logging
import random
import os
import socket
import subprocess
from pathlib import Path
import platform
from typing import Optional

from app.core.config import settings # Ayarları import et

# Logger'ı yapılandır
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _get_chrome_path() -> Optional[str]:
    """
    Mevcut işletim sistemi için ayar dosyasından geçerli bir Chrome yolu bulur.
    """
    system = platform.system()
    paths = settings.CHROME_APP_PATHS.get(system)
    if not paths:
        return None
    
    if isinstance(paths, str) and os.path.exists(paths):
        return paths
    elif isinstance(paths, list):
        for path in paths:
            if os.path.exists(path):
                return path
    return None

async def fetch_hepsiburada_cookies_async():
    """
    9222 portunu kontrol eder; boşsa Chrome'u debug modunda kendi başlatır,
    doluysa mevcut Chrome'a bağlanır. Manuel komut ihtiyacını ortadan kaldırır.
    """
    # port = 9222 # Ayarlardan alınacak
    
    # 1. Portun kullanımda olup olmadığını kontrol et
    parsed_cdp_url = settings.PLAYWRIGHT_CDP_URL
    port = int(parsed_cdp_url.split(':')[-1])

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        is_port_in_use = s.connect_ex(('localhost', port)) == 0

    if not is_port_in_use:
        user_data_dir = settings.CHROME_USER_DATA_DIR
        chrome_app_path = _get_chrome_path()

        if not chrome_app_path:
            logger.error("Chrome uygulaması sisteminizde bulunamadı. Lütfen config.py dosyasındaki yolları kontrol edin.")
            return None, settings.USER_AGENT
        
        command = []
        current_system = platform.system()
        
        # macOS: Odağı çalmaması için -g bayrağı ile başlat
        if current_system == "Darwin" and "/Contents/MacOS/" in chrome_app_path:
            app_bundle_path = chrome_app_path.split("/Contents/MacOS/")[0]
            if app_bundle_path.endswith(".app"):
                logger.info("macOS algılandı. Chrome'un odağı çalmaması için arka planda başlatılacak.")
                command = ['open', '-g', '-a', app_bundle_path, '--args']
        
        # Windows: Minimize edilmiş (simge durumunda) başlat
        elif current_system == "Windows":
            logger.info("Windows algılandı. Chrome minimize edilmiş olarak başlatılacak.")
            # Bu liste Popen'a doğrudan verilecek
            command = [chrome_app_path]

        # Linux ve diğerleri: Standart başlatma
        else:
            logger.info(f"{current_system} algılandı. Chrome standart şekilde başlatılacak.")
            command = [chrome_app_path]

        # Ortak argümanları ekle
        command.extend([
            f'--remote-debugging-port={port}',
            f'--user-data-dir={user_data_dir}'
        ])

        try:
            startupinfo = None
            # Windows'a özel başlatma ayarları
            if current_system == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 6  # 6 = SW_MINIMIZE

            # stdout ve stderr'i DEVNULL'a yönlendirerek tarayıcı loglarını gizle
            subprocess.Popen(
                command, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo # Windows dışı sistemlerde None olacak
            )
            logger.info("Yeni Chrome tarayıcısı başlatıldı, bağlanmak için 5 saniye bekleniyor...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Chrome başlatılırken hata oluştu: {e}", exc_info=True)
            return None, settings.USER_AGENT
    # else:
    #     logger.info(f"{port} portu zaten kullanımda. Mevcut Chrome işlemine bağlanılacak.")


    page = None
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.connect_over_cdp(settings.PLAYWRIGHT_CDP_URL)
                context = browser.contexts[0]
            except Exception as e:
                logger.error(f"Çalışan Chrome'a bağlanılamadı. Hata: {e}", exc_info=True)
                logger.error("Eğer Chrome manuel olarak başlatıldıysa, doğru port ve ayarlarla çalıştığından emin olun.")
                return None, settings.USER_AGENT

            # Her seferinde yeni sayfa oluşturmak yerine mevcut olanı yeniden kullan.
            # Bu, macOS'te pencerenin öne fırlamasını engeller.
            if context.pages:
                page = context.pages[0]
            else:
                page = await context.new_page()

            await page.goto(settings.HEPSIBURADA_COOKIE_WARMUP_URL, wait_until="load", timeout=60000)

            try:
                accept_button = page.locator('button[id="onetrust-accept-btn-handler"]')
                await accept_button.wait_for(state="visible", timeout=10000)
                await accept_button.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                # Cookie banner her zaman çıkmayabilir, bu bir hata değil.
                pass

            # Sayfayı yavaşça aşağı kaydırarak insan davranışını taklit et
            await page.evaluate("window.scrollBy(0, 4900)")
            await asyncio.sleep(random.uniform(1, 3))

            # Fareyi rastgele hareket ettir
            for _ in range(random.randint(1, 2)):
                scroll_amount = random.randint(-500, 500)
                await page.mouse.wheel(0, scroll_amount)
                await asyncio.sleep(random.uniform(0.5, 1.5))

            # Sayfanın oturması için kısa bir bekleme
            await page.wait_for_timeout(random.randint(2000, 4000))
            
            # Gerçek User-Agent'ı sayfadan al
            actual_user_agent = await page.evaluate("() => navigator.userAgent")

            all_cookies = await context.cookies()

            cookie_dict = {
                cookie['name']: cookie.get('value', '') 
                for cookie in all_cookies 
                if 'name' in cookie and cookie.get('name') in settings.HEPSIBURADA_REQUIRED_COOKIES
            }

            # Sayfayı kapatmıyoruz, çünkü bir sonraki işlemde yeniden kullanılacak.
            # await page.close()

            # En kritik ilk iki cookie'nin alınıp alınmadığını kontrol et
            if not all(key in cookie_dict for key in settings.HEPSIBURADA_REQUIRED_COOKIES[:2]):
                logger.warning(f"Gerekli tüm Akamai cookie'leri alınamadı. Alınanlar: {list(cookie_dict.keys())}")
                return None, actual_user_agent

            return cookie_dict, actual_user_agent
            
    except Exception as e:
        logger.error(f"Playwright ile cookie alınırken bir hata oluştu: {e}", exc_info=True)
        # Hata durumunda sayfayı kapatmayı denemiyoruz çünkü var olmayabilir
        # veya yeniden kullanılacağı için açık kalması daha iyi olabilir.
        return None, settings.USER_AGENT

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