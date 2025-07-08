import asyncio
import httpx
from urllib.parse import urlparse, parse_qs, urlencode, urljoin
from datetime import datetime
import os
import re
from typing import Dict, List, Optional, Any, Tuple
import socket
import json
from playwright.async_api import async_playwright

from ..parsers.trendyol_parser import fetch_review_page, fetch_product_details, append_reviews_to_csv
from ..core.config import settings

# Bağlantı hatalarını işlemek için bir retry decorator oluştur
async def with_retry(func, *args, max_retries=3, **kwargs):
    """Fonksiyon çağrısını belirtilen sayıda yeniden dener"""
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout, socket.gaierror) as e:
            last_exception = e
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"Bağlantı hatası, {wait_time} saniye sonra yeniden deneniyor... (Deneme {attempt+1}/{max_retries})")
            await asyncio.sleep(wait_time)
    
    print(f"Maksimum deneme sayısına ulaşıldı. Son hata: {last_exception}")
    return None

async def fetch_search_results(url: str, page: int = 1) -> Dict:
    """
    Trendyol arama sonuçlarını headless tarayıcı ile çeker
    """
    # URL'den temel parametreleri çıkar
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    
    # Arama API endpoint'i - yeni curl'den alınan
    api_url = "https://apigw.trendyol.com/discovery-web-searchgw-service/v2/api/infinite-scroll/sr"
    
    # Parametreleri hazırla
    params = {}
    
    # Mevcut parametreleri kopyala
    for key, value in query_params.items():
        params[key] = value[0]
    
    # Sayfa numarasını ekle
    params["pi"] = page
    
    # Curl'den alınan diğer parametreleri ekle
    if "q" in params:
        params["qt"] = params["q"]
        params["st"] = params["q"]
    
    # Standart parametreler
    default_params = {
        "os": "1",
        "culture": "tr-TR",
        "userGenderId": "1",
        "pId": "0",
        "isLegalRequirementConfirmed": "false",
        "searchStrategyType": "DEFAULT",
        "productStampType": "TypeA",
        "scoringAlgorithmId": "2",
        "fixSlotProductAdsIncluded": "true",
        "searchAbDecider": "AdvertSlotPeriod_1,AD_B,QR_B,qrw_b,SimD_B,BSA_D,SuggestionLC_B,res_B,BMSA_B,RRIn_B,SCB_B,SuggestionHighlight_B,BP_B,CatTR_B,SuggestionTermActive_A,AZSmartlisting_62,BH2_B,MB_B,MRF_1,ARR_B,MA_B,SP_B,PastSearches_B,SuggestionJFYProducts_B,SuggestionQF_B,BadgeBoost_A,FilterRelevancy_1,SuggestionBadges_B,ProductGroupTopPerformer_B,OpenFilterToggle_2,RR_2,BS_2,SuggestionPopularCTR_B",
        "channelId": "1"
    }
    
    # Default parametreleri ekle (eğer yoksa)
    for key, value in default_params.items():
        if key not in params:
            params[key] = value
    
    # Query string'i oluştur
    query_string = urlencode(params)
    full_url = f"{api_url}?{query_string}"
    
    try:
        # Playwright ile headless tarayıcı başlat
        async with async_playwright() as p:
            # Tarayıcıyı başlat
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=settings.USER_AGENT,
                viewport={'width': 1920, 'height': 1080}
            )
            
            # Context'e gerekli çerezleri ekle
            await context.add_cookies([
                {"name": "platform", "value": "web", "domain": ".trendyol.com", "path": "/"},
                {"name": "countryCode", "value": "TR", "domain": ".trendyol.com", "path": "/"},
                {"name": "language", "value": "tr", "domain": ".trendyol.com", "path": "/"}
            ])
            
            # Yeni sayfa oluştur
            page_browser = await context.new_page()
            
            # Bütün header'ları ekle
            await page_browser.set_extra_http_headers({
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'tr,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
                'baggage': 'ty.kbt.name=ViewSearchResult,ty.platform=Web,ty.business_unit=Core Commerce,ty.channel=TR,com.trendyol.observability.business_transaction.name=ViewSearchResult,ty.source.service.name=WEB Storefront TR,ty.source.deployment.environment=production,ty.source.service.version=b1729d82,ty.source.client.path=/sr,ty.source.service.type=client',
                'cache-control': 'no-cache',
                'origin': 'https://www.trendyol.com',
                'pragma': 'no-cache',
                'priority': 'u=1, i',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
            })
            
            # İsteği hazırla ve response'u dinle
            
            # İsteği yap ve yanıtı yakalamak için ağ isteğini izle
            response_data = None
            
            async def handle_response(response):
                nonlocal response_data
                if response.url.startswith(api_url):
                    try:
                        response_data = await response.json()
                    except:
                        try:
                            response_data = await response.text()
                        except:
                            pass
            
            # Response event listener'ı ekle
            page_browser.on("response", handle_response)
            
            # Sayfaya git
            await page_browser.goto(full_url, wait_until="networkidle")
            
            # Tarayıcıyı kapat
            await browser.close()
            
            # Response verisini kontrol et
            if response_data:
            
                if isinstance(response_data, dict):
                    data = response_data
                    # Yanıt 'result' anahtarı altında geliyor
                    result_data = data.get("result", {})
                    if not result_data:
                        print("API yanıtında 'result' anahtarı bulunamadı veya boş.")
                        # Alternatif yöntemi dene
                        return await fetch_search_results_fallback(url, page)
                        
                    products = result_data.get("products", [])
                    total_count = result_data.get("totalCount", 0)
                    
                    return {
                        "products": products,
                        "totalCount": total_count,
                        "page": page
                    }
                elif isinstance(response_data, str):
                    try:
                        data = json.loads(response_data)
                        result_data = data.get("result", {})
                        if not result_data:
                            print("API yanıtında 'result' anahtarı bulunamadı veya boş.")
                            # Alternatif yöntemi dene
                            return await fetch_search_results_fallback(url, page)
                        
                        products = result_data.get("products", [])
                        total_count = result_data.get("totalCount", 0)
                        
                        return {
                            "products": products,
                            "totalCount": total_count,
                            "page": page
                        }
                    except json.JSONDecodeError:
                        print("JSON parse hatası")
                        # Alternatif yöntemi dene
                        return await fetch_search_results_fallback(url, page)
            
            # Headless browser'dan yanıt alınamadıysa fallback'e geç
            print("Headless browser ile yanıt alınamadı, httpx ile deneniyor...")
            return await fetch_search_results_fallback(url, page)
                
    except Exception as e:
        print(f"Headless browser hatası: {e}")
        # Hata durumunda alternatif yönteme geri dön
        return await fetch_search_results_fallback(url, page)

async def fetch_search_results_fallback(url: str, page: int = 1) -> Dict:
    """
    Trendyol arama sonuçlarını httpx ile çeker (yedek yöntem)
    """
    # URL'den temel parametreleri çıkar
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    
    # Arama API endpoint'i - yeni curl'den alınan
    api_url = "https://apigw.trendyol.com/discovery-web-searchgw-service/v2/api/infinite-scroll/sr"
    
    # Parametreleri hazırla
    params = {}
    
    # Mevcut parametreleri kopyala
    for key, value in query_params.items():
        params[key] = value[0]
    
    # Sayfa numarasını ekle
    params["pi"] = page
    
    # Curl'den alınan diğer parametreleri ekle
    if "q" in params:
        params["qt"] = params["q"]
        params["st"] = params["q"]
    
    # Standart parametreler
    default_params = {
        "os": "1",
        "culture": "tr-TR",
        "userGenderId": "1",
        "pId": "0",
        "isLegalRequirementConfirmed": "false",
        "searchStrategyType": "DEFAULT",
        "productStampType": "TypeA",
        "scoringAlgorithmId": "2",
        "fixSlotProductAdsIncluded": "true",
        "searchAbDecider": "AdvertSlotPeriod_1,AD_B,QR_B,qrw_b,SimD_B,BSA_D,SuggestionLC_B,res_B,BMSA_B,RRIn_B,SCB_B,SuggestionHighlight_B,BP_B,CatTR_B,SuggestionTermActive_A,AZSmartlisting_62,BH2_B,MB_B,MRF_1,ARR_B,MA_B,SP_B,PastSearches_B,SuggestionJFYProducts_B,SuggestionQF_B,BadgeBoost_A,FilterRelevancy_1,SuggestionBadges_B,ProductGroupTopPerformer_B,OpenFilterToggle_2,RR_2,BS_2,SuggestionPopularCTR_B",
        "channelId": "1"
    }
    
    # Default parametreleri ekle (eğer yoksa)
    for key, value in default_params.items():
        if key not in params:
            params[key] = value
    
    # Curl'den alınan headers
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'tr,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
        'baggage': 'ty.kbt.name=ViewSearchResult,ty.platform=Web,ty.business_unit=Core Commerce,ty.channel=TR,com.trendyol.observability.business_transaction.name=ViewSearchResult,ty.source.service.name=WEB Storefront TR,ty.source.deployment.environment=production,ty.source.service.version=b1729d82,ty.source.client.path=/sr,ty.source.service.type=client',
        'cache-control': 'no-cache',
        'origin': 'https://www.trendyol.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': settings.USER_AGENT
    }
    
    # Basit cookie bilgisi
    cookies = {
        'platform': 'web',
        'countryCode': 'TR',
        'language': 'tr',
    }
    
    response = None
    try:
        # Özel timeouts ve SSL doğrulama ayarları ile client oluştur
        async with httpx.AsyncClient(timeout=30.0, verify=False, cookies=cookies, http2=True) as client:

            # Yeniden deneme mekanizması
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await client.get(api_url, params=params, headers=headers)
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout, socket.gaierror) as conn_err:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"Bağlantı hatası, {wait_time} saniye sonra yeniden deneniyor... (Deneme {attempt+1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"Maksimum deneme sayısına ulaşıldı: {conn_err}")
                        return {"products": [], "totalCount": 0, "page": page, "error": f"Bağlantı hatası: {conn_err}"}
            
            if response:
                
                if response.status_code == 200:
                    data = response.json()
                    # Yanıt 'result' anahtarı altında geliyor
                    result_data = data.get("result", {})
                    if not result_data:
                        print("API yanıtında 'result' anahtarı bulunamadı veya boş.")
                        return {"products": [], "totalCount": 0, "page": page, "error": "Geçersiz yanıt yapısı"}
                        
                    products = result_data.get("products", [])
                    total_count = result_data.get("totalCount", 0)
                    
                    return {
                        "products": products,
                        "totalCount": total_count,
                        "page": page
                    }
                else:
                    print(f"Error fetching search results: {response.status_code}")
                    
                    # Alternatif yöntem: doğrudan web sayfasını çek
                    print("API yanıt vermedi, alternatif bir kaynak deneniyor...")
                    search_url = f"https://www.trendyol.com/sr?pi={page}"
                    if 'q' in params:
                        search_url += f"&q={params['q']}"
                        
                    print(f"Alternatif URL: {search_url}")
                    web_response = await client.get(search_url, headers={
                        'User-Agent': settings.USER_AGENT,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                    })
                    
                    if web_response.status_code == 200:
                        html_content = web_response.text
                        # Sayfadan ürün verilerini çıkar
                        window_data_match = re.search(r'window\.__SEARCH_APP_INITIAL_STATE__\s*=\s*({.*?});', html_content, re.DOTALL)
                        if window_data_match:
                            try:
                                search_data = json.loads(window_data_match.group(1))
                                products = search_data.get("products", {}).get("products", [])
                                return {
                                    "products": products,
                                    "totalCount": search_data.get("products", {}).get("totalCount", 0),
                                    "page": page
                                }
                            except json.JSONDecodeError:
                                pass
                    
                    # Alternatif de çalışmazsa boş sonuç döndür
                    return {"products": [], "totalCount": 0, "page": page, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        print(f"Exception while fetching search results: {e}")
        return {"products": [], "totalCount": 0, "page": page, "error": str(e)}
    
    if response:
        # ... (response işleme)
        return {"products": [], "totalCount": 0, "page": page, "error": "Beklenmedik durum"}
    else:
        # Döngü hiç çalışmazsa veya response alamazsa
        return {"products": [], "totalCount": 0, "page": page, "error": "İstek yapılamadı"}

async def get_product_reviews(url: str, export_csv: bool = False) -> Dict:
    """
    Trendyol ürün yorumlarını çeker
    """
    try:
        # CSV dosyası için zaman damgası oluştur
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        csv_filename = f"trendyol_yorumlar_{timestamp}.csv"
        is_first_write = True  # İlk yazma işlemi için bayrak
        
        # Tüm ürünleri toplamak için dizi
        all_products = []
        
        # URL'den temel parametreleri çıkar
        parsed_url = urlparse(url)
        
        # Sayfa sayısını belirle
        current_page = 1
        total_pages = 1
        total_count = 0
        has_next_page = True
        
        print(f"\n===== TÜM SAYFALARI TARAMA İŞLEMİ BAŞLADI =====\n")
        
        # İlk sayfayı çek ve toplam sayfa sayısını öğren
        while has_next_page:
            # Trendyol search API'sini kullanarak ürünleri çekme
            print(f"\n🔍 Sayfa {current_page} ürünleri çekiliyor")
            
            search_data = await fetch_search_results(url, current_page)
            
            # İlk sayfada toplam sayfa sayısını hesapla
            if current_page == 1:
                total_count = search_data.get("totalCount", 0)
                # String olabilecek değeri sayıya çevir
                try:
                    total_count = int(total_count)
                except (ValueError, TypeError):
                    total_count = 0
                    
                products_per_page = 24  # Trendyol'da sayfa başına 24 ürün gösteriliyor
                # Bölme işlemini güvenli bir şekilde yap
                if total_count > 0 and products_per_page > 0:
                    total_pages = (total_count + products_per_page - 1) // products_per_page  # Yukarı yuvarlama
                else:
                    total_pages = 1  # Eğer total_count 0 ise en az 1 sayfa var
                    
                print(f"\n===== TOPLAM {total_count} ÜRÜN BULUNDU ({total_pages} SAYFA) =====\n")
            
            products = search_data.get("products", [])
            
            if not products:
                print(f"⚠️ Sayfa {current_page}'de ürün bulunamadı")
                break  # Ürün yoksa döngüden çık
            
            print(f"✅ Sayfa {current_page}/{total_pages}: {len(products)} ürün bulundu")
            
            # Ürünleri topla
            all_products.extend(products)

            
            # Her ürün için yorumları toplama
            for product in products:
                # Ürün bilgilerini çıkar
                content_id_match = re.search(r'-p-(\d+)', product.get("url", ""))
                content_id = content_id_match.group(1) if content_id_match else None
                boutique_id = product.get("variants", [{}])[0].get("campaignId") if product.get("variants") else None
                merchant_id = product.get("merchantId")
                
                if not content_id:
                    print(f"⚠️ ContentId bulunamadı: {product.get('url')}")
                    continue  # ContentId yoksa bu ürünü atla
                
                print(f"\n--------------------------------------------")
                print(f"ÜRÜN: {product.get('name')}")
                print(f"ContentID: {content_id}, MerchantID: {merchant_id}, BoutiqueID: {boutique_id or 'Yok'}")
                product_url = f"https://www.trendyol.com{product.get('url')}"
                print(f"URL: {product_url}")
                
                # Ürün detay sayfasını çek
                print(f"Ürün detayları çekiliyor: {product_url}")
                
                product_properties = []
                try:
                    # Ürün detaylarını çek
                    product_details = await fetch_product_details(product_url)
                    if product_details and product_details.get("additionalProperty"):
                        product_properties = product_details["additionalProperty"]
                        print(f"✅ Ürün özellikleri başarıyla çekildi: {len(product_properties)} özellik")
                    elif product_details and isinstance(product_details, dict) and product_details.get("@type") == "Product":
                        # Yeni JSON-LD yapısı için
                        product_properties = product_details.get("additionalProperty", [])
                        print(f"✅ Ürün özellikleri başarıyla çekildi: {len(product_properties)} özellik")
                    else:
                        print(f"⚠️ Ürün özellikleri bulunamadı")
                        product_properties = []
                except Exception as detail_error:
                    print(f"⚠️ Ürün detayları çekme hatası: {detail_error}")
                
                # Ürün yorumlarını toplama
                product_reviews = {
                    "productInfo": {
                        "boutiqueId": boutique_id,
                        "merchantId": merchant_id,
                        "contentId": content_id,
                        "url": f"https://www.trendyol.com{product.get('url')}",
                        "name": product.get("name"),
                        "properties": product_properties  # Ürün özelliklerini ekle
                    },
                    "reviews": []
                }
                
                # İlk sayfayı çek ve toplam sayfa sayısını öğren (Sayfa 0'dan başla)
                first_page_params = {
                    "page": 0,
                    "order": "DESC",
                    "orderBy": "Score",
                    "channelId": "1",
                    "sellerId": merchant_id,
                    "contentId": content_id
                }
                
                print(f"\nFetching first page with params: {urlencode(first_page_params)}")
                
                # fetchReviewPage fonksiyonunu kullanarak ilk sayfayı çek
                first_page_data = await fetch_review_page(first_page_params)
                
                if not first_page_data:
                    # İlk yöntem başarısız oldu, ikinci yöntemi dene
                    print(f"\nFirst method failed, trying second method with boutiqueId")
                    if boutique_id:
                        second_page_params = {
                            "page": 0,
                            "order": "DESC",
                            "orderBy": "Score",
                            "channelId": "1",
                            "merchantId": merchant_id,
                            "boutiqueId": boutique_id
                        }
                        
                        print(f"Fetching with second method params: {urlencode(second_page_params)}")
                        
                        # İkinci yöntemle tekrar dene
                        second_page_data = await fetch_review_page(second_page_params)
                        
                        if not second_page_data:
                            # Yorum yoksa sonraki ürüne geç
                            print(f"❌ Yorum bulunamadı!")
                            product_reviews["error"] = "Yorum bulunamadı"
                            continue
                        
                        # Güvenli veri çekme
                        review_result = second_page_data.get("result", {})
                        product_reviews_data = review_result.get("productReviews", {})
                        first_page_reviews = product_reviews_data.get("content", [])
                        product_reviews["reviews"].extend(first_page_reviews)
                        
                        # Toplam sayfa sayısını al
                        review_total_pages = product_reviews_data.get("totalPages", 1)
                        # String olabilecek değeri sayıya çevir
                        try:
                            review_total_pages = int(review_total_pages)
                        except (ValueError, TypeError):
                            review_total_pages = 1
                            
                        # 0 veya negatif gelirse 1 olarak düzelt
                        if review_total_pages < 1:
                            review_total_pages = 1
                        
                        # İlk sayfa yorumlarını konsola yazdır
                        print(f"\n✅ Sayfa 1/{review_total_pages}: {len(first_page_reviews)} yorum bulundu")
                        
                        
                        # Yorumları CSV dosyasına anlık olarak ekle
                        if export_csv:
                            await append_reviews_to_csv(first_page_reviews, product_reviews["productInfo"], csv_filename, is_first_write)
                            is_first_write = False  # İlk yazma işlemi tamamlandı
                            print(f"✅ Sayfa 1 yorumları CSV dosyasına eklendi")
                        
                        print(f"Total pages: {review_total_pages}")
                        
                        # Diğer sayfaları çek (1. sayfadan başla çünkü 0. sayfayı zaten aldık)
                        for page_num in range(1, min(review_total_pages, 100) + 1):
                            page_params = {
                                "page": page_num,
                                "order": "DESC",
                                "orderBy": "Score",
                                "channelId": "1",
                                "merchantId": merchant_id,
                                "boutiqueId": boutique_id
                            }
                            # fetchReviewPage fonksiyonunu kullanarak sayfayı çek
                            page_data = await fetch_review_page(page_params)
                            
                            if page_data:
                                review_result = page_data.get("result", {})
                                product_reviews_data = review_result.get("productReviews", {})
                                page_reviews = product_reviews_data.get("content", [])
                                
                                if page_reviews:
                                    product_reviews["reviews"].extend(page_reviews)
                                    
                                    # Bu sayfadaki yorumları konsola yazdır
                                    print(f"\n✅ Sayfa {page_num}/{review_total_pages}: {len(page_reviews)} yorum bulundu")
                                   
                                    
                                    # Yorumları CSV dosyasına anlık olarak ekle
                                    if export_csv:
                                        await append_reviews_to_csv(page_reviews, product_reviews["productInfo"], csv_filename, is_first_write)
                                        is_first_write = False  # İlk yazma işlemi tamamlandı
                                        print(f"✅ Sayfa {page_num} yorumları CSV dosyasına eklendi")
                                else:
                                    print(f"Page data: {page_data}")
                                    print(f"❌ Sayfa {page_num}: Yorum içeriği bulunamadı")
                            else:
                                print(f"❌ Sayfa {page_num}: Yorum bulunamadı")
                                
                                # Eğer art arda 5 sayfa boş gelirse, muhtemelen daha fazla sayfa yoktur
                                if page_num > 5:
                                    empty_page_count = 1
                                    for i in range(1, 5):
                                        if page_num - i >= 1:
                                            prev_page_params = {
                                                "page": page_num - i,
                                                "order": "DESC",
                                                "orderBy": "Score",
                                                "channelId": "1",
                                                "merchantId": merchant_id,
                                                "boutiqueId": boutique_id
                                            }
                                            
                                            prev_page_data = await fetch_review_page(prev_page_params)
                                            if not prev_page_data or not prev_page_data.get("result", {}).get("productReviews", {}).get("content"):
                                                empty_page_count += 1
                                    
                                    if empty_page_count >= 5:
                                        print(f"\n⚠️ Art arda 5 boş sayfa. Muhtemelen daha fazla yorum yok. Sayfa çekme işlemi durduruldu.")
                                        break
                            
                            # Her 10 sayfada bir 3 saniye bekle (rate limiting'i önlemek için)
                            if page_num % 10 == 0:
                                print(f"Waiting 3 seconds to avoid rate limiting...")
                                await asyncio.sleep(3)
                    else:
                        # Alternatif parametre de yoksa bu ürünü atla
                        print(f"❌ Yorumlar alınamadı!")
                        product_reviews["error"] = "Yorumlar alınamadı"
                        continue
                else:
                    # İlk yöntem başarılı
                    # İlk sayfadaki yorumları ekle
                    review_result = first_page_data.get("result", {})
                    product_reviews_data = review_result.get("productReviews", {})
                    first_page_reviews = product_reviews_data.get("content", [])
                    product_reviews["reviews"].extend(first_page_reviews)
                    
                    # Toplam sayfa sayısını al
                    review_total_pages = product_reviews_data.get("totalPages", 1)
                    # String olabilecek değeri sayıya çevir
                    try:
                        review_total_pages = int(review_total_pages)
                    except (ValueError, TypeError):
                        review_total_pages = 1
                        
                    # 0 veya negatif gelirse 1 olarak düzelt
                    if review_total_pages < 1:
                        review_total_pages = 1
                    
                    # İlk sayfa yorumlarını konsola yazdır
                    print(f"\n✅ Sayfa 1/{review_total_pages}: {len(first_page_reviews)} yorum bulundu")
                   
                    
                    # Yorumları CSV dosyasına anlık olarak ekle
                    if export_csv:
                        await append_reviews_to_csv(first_page_reviews, product_reviews["productInfo"], csv_filename, is_first_write)
                        is_first_write = False  # İlk yazma işlemi tamamlandı
                        print(f"✅ Sayfa 1 yorumları CSV dosyasına eklendi")
                    
                    # Toplam sayfa sayısını al
                    print(f"Total pages: {review_total_pages}")
                    
                    # Diğer sayfaları çek (1. sayfadan başla çünkü 0. sayfayı zaten aldık)
                    for page_num in range(1, min(review_total_pages, 100) + 1):
                        page_params = {
                            "page": page_num,
                            "order": "DESC",
                            "orderBy": "Score",
                            "channelId": "1",
                            "sellerId": merchant_id,
                            "contentId": content_id
                        }
                        # fetchReviewPage fonksiyonunu kullanarak sayfayı çek
                        page_data = await fetch_review_page(page_params)
                        
                        if page_data:
                            review_result = page_data.get("result", {})
                            product_reviews_data = review_result.get("productReviews", {})
                            page_reviews = product_reviews_data.get("content", [])
                            
                            if page_reviews:
                                product_reviews["reviews"].extend(page_reviews)
                                
                                # Bu sayfadaki yorumları konsola yazdır
                                print(f"\n✅ Sayfa {page_num}/{review_total_pages}: {len(page_reviews)} yorum bulundu")
                                
                                
                                # Yorumları CSV dosyasına anlık olarak ekle
                                if export_csv:
                                    await append_reviews_to_csv(page_reviews, product_reviews["productInfo"], csv_filename, is_first_write)
                                    is_first_write = False  # İlk yazma işlemi tamamlandı
                                    print(f"✅ Sayfa {page_num} yorumları CSV dosyasına eklendi")
                            else:
                                print(f"Page data: {page_data}")
                                print(f"❌ Sayfa {page_num}: Yorum içeriği bulunamadı")
                        else:
                            print(f"❌ Sayfa {page_num}: Yorum bulunamadı")
                            
                            # Eğer art arda 5 sayfa boş gelirse, muhtemelen daha fazla sayfa yoktur
                            if page_num > 5:
                                empty_page_count = 1
                                for i in range(1, 5):
                                    if page_num - i >= 1:
                                        prev_page_params = {
                                            "page": page_num - i,
                                            "order": "DESC",
                                            "orderBy": "Score",
                                            "channelId": "1",
                                            "sellerId": merchant_id,
                                            "contentId": content_id
                                        }
                                        
                                        prev_page_data = await fetch_review_page(prev_page_params)
                                        if not prev_page_data or not prev_page_data.get("result", {}).get("productReviews", {}).get("content"):
                                            empty_page_count += 1
                                    
                                    if empty_page_count >= 5:
                                        print(f"\n⚠️ Art arda 5 boş sayfa. Muhtemelen daha fazla yorum yok. Sayfa çekme işlemi durduruldu.")
                                        break
                        
                        # Her 10 sayfada bir 3 saniye bekle (rate limiting'i önlemek için)
                        if page_num % 10 == 0:
                            print(f"Waiting 3 seconds to avoid rate limiting...")
                            await asyncio.sleep(3)
                        # Her sayfa isteği arasında 1 saniye bekle
                        await asyncio.sleep(1)
                        # Her 10 sayfada bir 5 saniye bekle
                        if page_num % 10 == 0:
                            await asyncio.sleep(5)
                
                # Bu ürünün tüm yorumlarını listeye ekle
                product_reviews["totalReviews"] = len(product_reviews["reviews"])
                print(f"\n✅ TOPLAM: {product_reviews['totalReviews']} yorum toplandı")
            
            # Sonraki sayfaya geç
            current_page += 1
            
            # Tüm sayfalar tamamlandıysa döngüden çık
            if current_page > total_pages:
                has_next_page = False
            
            # Her sayfadan sonra 2 saniye bekle (rate limiting'i önlemek için)
            print(f"Waiting 2 seconds before next page...")
            await asyncio.sleep(2)
        
        print(f"\n===== İŞLEM TAMAMLANDI: TOPLAM {len(all_products)} ÜRÜN TARANDI =====\n")
        
        # CSV dosyası yolu
        csv_path = None
        if export_csv:
            csv_path = os.path.join(os.getcwd(), csv_filename)
            print(f"\n✅ CSV dosyası oluşturuldu: {csv_path}")
        
        return {
            "success": True,
            "totalProducts": len(all_products),
            "totalPages": total_pages,
            "products": all_products,
            "csv_file": csv_path
        }
        
    except Exception as error:
        print(f'Trendyol ürün yorumları çekme hatası: {error}')
        return {"success": False, "error": str(error)}

async def search_products(url: str, page: int = 1) -> Dict:
    """
    Trendyol arama sonuçlarını çeker
    """
    return await fetch_search_results(url, page)
