import asyncio
import httpx
import logging
from urllib.parse import urlparse, parse_qs, urlencode
from typing import Dict, Any, Optional
import json
import pyjson5 # pyjson5'i kendi adıyla import et
from bs4 import BeautifulSoup
import html
from playwright.async_api import async_playwright

from app.core.config import settings
from app.utils.hepsiburada_cookie_fetcher import fetch_hepsiburada_cookies_async

# Logger'ı yapılandır
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def _make_api_request(url: str, headers: dict, params: Optional[Dict[str, Any]] = None, retries: int = 2) -> Dict[str, Any]:
    """
    Hepsiburada API'sine httpx ile istek atar ve 403 hatası durumunda yeniden dener.
    """
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 403:
                    logger.warning(f"403 Forbidden hatası alındı (URL: {url}). Cookie'ler geçersiz olabilir. Yeniden denenecek...")
                    if attempt < retries:
                        raise httpx.HTTPStatusError("403 Forbidden", request=response.request, response=response)
                    else:
                        logger.error("Maksimum deneme sayısına ulaşıldı, 403 hatası devam ediyor.")
                        response.raise_for_status()

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403 and attempt < retries:
                await asyncio.sleep(settings.HEPSIBURADA_API_MIN_WAIT_TIME)
                continue
            else:
                logger.error(f"API isteği başarısız oldu: URL={url}, Hata={e}")
                return {}
        except httpx.RequestError as e:
            logger.error(f"İstek sırasında kritik bir hata oluştu: URL={url}, Hata={e}")
            return {}
    return {}


def _get_default_headers(cookie_string: str, user_agent: str, referer: str = settings.HEPSIBURADA_BASE_URL + "/") -> dict:
    """Creates a default dictionary of headers for Hepsiburada API requests."""
    return {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'tr,en;q=0.9',
        'origin': settings.HEPSIBURADA_BASE_URL,
        'referer': referer,
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': user_agent,
        'x-client-id': settings.HEPSIBURADA_API_CLIENT_ID,
        'cookie': cookie_string
    }


async def fetch_products_from_search(url: str) -> Dict[str, Any]:
    """
    Verilen Hepsiburada arama URL'sinden ürünleri çeker.
    Her çağrıda yeni cookie'ler alarak Akamai korumasını aşmayı hedefler.
    """
    logger.info(f"Hepsiburada arama sonuçları çekiliyor: {url}")
    max_retries = 2
    for attempt in range(max_retries + 1): # +1 ile toplam deneme sayısı doğru olur
        try:
            cookie_dict, user_agent = await fetch_hepsiburada_cookies_async()
            if not cookie_dict:
                logger.error("Cookie'ler alınamadı, ürün arama işlemi iptal edildi.")
                return {}

            cookie_string = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
            headers = _get_default_headers(cookie_string, user_agent)

            parsed_frontend_url = urlparse(url)
            query_params = parse_qs(parsed_frontend_url.query)

            api_params = {
                'pageType': 'Search',
                'size': settings.HEPSIBURADA_SEARCH_PAGE_SIZE,
                'page': query_params.get('sayfa', [1])[0]
            }
            
            search_query = query_params.get('q')
            if not search_query:
                raise ValueError("Arama sorgusu 'q' URL'de bulunamadı.")
            api_params['q'] = search_query[0]

            api_base_url = settings.HEPSIBURADA_SEARCH_API_URL
            
            # Doğrudan _make_api_request'i çağır ve sonucu dön
            return await _make_api_request(api_base_url, headers=headers, params=api_params, retries=1)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403 and attempt < max_retries:
                # 403 hatası zaten _make_api_request içinde loglandı, burada tekrar loglamaya gerek yok.
                await asyncio.sleep(settings.HEPSIBURADA_API_MAX_WAIT_TIME)
                continue # Döngünün başına dönerek yeni cookie almayı tetikle
            else:
                logger.error(f"Ürün arama işlemi {e.response.status_code} hatasıyla son denemede de başarısız oldu.")
                return {}
    logger.error("Ürün arama işlemi maksimum deneme sayısına ulaştıktan sonra başarısız oldu.")
    return {}


async def fetch_product_reviews(sku: str, page: int = 0, size: int = 100) -> Dict[str, Any]:
    """
    Belirli bir ürün (SKU) için yorumları çeker.
    Yeni 'user-content-gw-hermes' endpoint'ini kullanır.
    """
    # Bu log çok sık çağrıldığı için DEBUG seviyesine düşürülebilir veya kaldırılabilir. Şimdilik kaldırıyorum.
    # logger.info(f"'{sku}' için {page}. sayfa yorumları çekiliyor...") 
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            cookie_dict, user_agent = await fetch_hepsiburada_cookies_async()
            if not cookie_dict:
                logger.error(f"Cookie'ler alınamadı, {sku} için yorum çekme işlemi iptal edildi.")
                return {}

            cookie_string = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
            referer_url = f"{settings.HEPSIBURADA_BASE_URL}/product-p-{sku}-yorumlari"
            headers = _get_default_headers(cookie_string, user_agent, referer=referer_url)
            # Add specific headers for this request if any
            headers['cache-control'] = 'no-cache'
            headers['pragma'] = 'no-cache'
            headers['priority'] = 'u=1, i'


            api_url = settings.HEPSIBURADA_REVIEW_API_URL
            params = {
                "sku": sku,
                "from": page * size,
                "size": size,
                "includeSiblingVariantContents": "true",
                "includeSummary": "true",
            }
            
            # Bu API çağrısı için deneme hakkını _make_api_request'e devrediyoruz.
            return await _make_api_request(api_url, headers=headers, params=params, retries=1)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403 and attempt < max_retries:
                # 403 hatası zaten _make_api_request içinde loglandı.
                await asyncio.sleep(settings.HEPSIBURADA_API_MAX_WAIT_TIME)
                continue
            else:
                logger.error(f"Yorum çekme işlemi ({sku}) {e.response.status_code} hatasıyla son denemede de başarısız oldu.")
                return {}
    logger.error(f"Yorum çekme işlemi ({sku}) maksimum deneme sayısına ulaştıktan sonra başarısız oldu.")
    return {} 


async def fetch_product_features(product_url: str) -> Dict[str, Any]:
    """
    Verilen Hepsiburada ürün sayfasının HTML'ini Playwright kullanarak indirir.
    Bu yöntem, sayfanın JavaScript ile oluşturulan içeriğini almayı garanti eder.
    Önce 'reduxStore' script'ini, bulunamazsa 'product-detail-app-initial-state' script'ini dener.
    """
    # Bu log da çok sık çağrılıyor, şimdilik kaldırıyorum.
    # logger.info(f"Ürün özellikleri çekiliyor: {product_url}")

    if not product_url.startswith(settings.HEPSIBURADA_BASE_URL):
        product_url = f"{settings.HEPSIBURADA_BASE_URL}{product_url}"

    page = None
    try:
        # Bu fonksiyon, 9222 portunda bir tarayıcının çalışır durumda olmasını sağlar.
        # Biz bu tarayıcıya yeniden bağlanarak işlemi gerçekleştireceğiz.
        cookies, user_agent = await fetch_hepsiburada_cookies_async()
        if not cookies:
            logger.error("Tarayıcı başlatılamadığı veya cookie alınamadığı için özellikler çekilemiyor.")
            return {}

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(settings.PLAYWRIGHT_CDP_URL)
            context = browser.contexts[0]
            page = await context.new_page()
            
            await page.goto(product_url, wait_until="domcontentloaded", timeout=60000)

            await page.evaluate("window.scrollBy(0, 1000)")
            
            # Verinin script etiketine yüklendiğinden emin olmak için akıllı bekleme.
            # 'reduxStore' etiketinin hem var olmasını hem de içinin dolu olmasını bekler.
            js_condition = """
            () => {
                const element = document.getElementById('reduxStore');
                return element && element.textContent.length > 5000;
            }
            """
            try:
                await page.wait_for_function(js_condition, timeout=20000)
            except Exception:
                logger.warning(f"Sayfa içeriği beklenenden yavaş yüklendi veya 'reduxStore' bulunamadı ({product_url}). Devam ediliyor...")

            html_content = await page.content()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            script_tag = soup.find('script', id='reduxStore')
            source_log = "reduxStore"
            if not script_tag:
                logger.warning("'reduxStore' script'i bulunamadı, 'product-detail-app-initial-state' deneniyor.")
                script_tag = soup.find('script', id='product-detail-app-initial-state')
                source_log = "product-detail-app-initial-state"

            if script_tag:
                script_content = script_tag.getText()
                if script_content:
                    unescaped_content = html.unescape(script_content)
                    
                    # --- Bracket Sayma ile Sadece 'expends' listesini çıkarma ---
                    start_key = '"expends":'
                    start_index = unescaped_content.find(start_key)
                    if start_index == -1:
                        logger.error(f"'{start_key}' anahtarı script içinde bulunamadı.")
                        return {}
                    
                    open_bracket_index = unescaped_content.find('[', start_index)
                    if open_bracket_index == -1:
                        logger.error(f"'{start_key}' anahtarından sonra açılış bracket'ı '[' bulunamadı.")
                        return {}

                    bracket_level = 1
                    current_pos = open_bracket_index + 1
                    content_len = len(unescaped_content)
                    while bracket_level > 0 and current_pos < content_len:
                        char = unescaped_content[current_pos]
                        if char == '[':
                            bracket_level += 1
                        elif char == ']':
                            bracket_level -= 1
                        current_pos += 1
                    
                    if bracket_level != 0:
                        logger.error("Eşleşen kapanış bracket'ı ']' bulunamadı. 'expends' listesi eksik olabilir.")
                        return {}
                        
                    expends_list_str = unescaped_content[open_bracket_index:current_pos]
                    
                    try:
                        expends_list = pyjson5.loads(expends_list_str)
                    except Exception as e:
                        logger.error(f"Ayıklanan 'expends' listesi JSON'a çevrilirken hata oluştu: {e}")
                        return {}

                    features_dict = {}
                    for group in expends_list:
                        properties = group.get('properties', [])
                        for prop in properties:
                            if 'name' in prop and 'property' in prop:
                                features_dict[prop['name']] = prop['property']
                    
                    logger.info(f"{len(features_dict)} adet ürün özelliği '{source_log}' kaynağından bulundu.")
                    return features_dict

            logger.warning("Özellikleri içeren script etiketi bulunamadı.")
            return {}

    except Exception as e:
        logger.error(f"Ürün özellikleri Playwright ile çekilirken hata oluştu: {e}", exc_info=True)
        return {}
    finally:
        if page:
            await page.close() 