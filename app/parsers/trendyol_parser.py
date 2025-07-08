import httpx
import re
import csv
import os
from urllib.parse import urlparse, parse_qs, urlencode
import json
from datetime import datetime
import asyncio
import socket
from ..core.config import settings
from playwright.async_api import async_playwright
import random

async def fetch_review_page(params):
    """
    Trendyol ürün yorumları sayfasını headless tarayıcı ile çeker
    """
    # Yeni API URL config'den alınıyor
    url = settings.TRENDYOL_REVIEW_API_URL
    
    # Query string'i oluştur
    query_string = urlencode(params)
    full_url = f"{url}?{query_string}"
    
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
            page = await context.new_page()
            
            # Bütün header'ları ekle
            await page.set_extra_http_headers({
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'tr,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
                'baggage': 'ty.kbt.name=ViewReviewRatings,ty.platform=Web,ty.business_unit=Core Commerce,ty.channel=TR,com.trendyol.observability.business_transaction.name=ViewReviewRatings,ty.source.service.name=WEB Storefront TR,ty.source.deployment.environment=production,ty.source.service.version=b1729d82,ty.source.client.path=unknown,ty.source.service.type=client',
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
                if response.url.startswith(url):
                    try:
                        response_data = await response.json()
                    except:
                        try:
                            response_data = await response.text()
                        except:
                            pass
            
            # Response event listener'ı ekle
            page.on("response", handle_response)
            
            # Sayfaya git
            await page.goto(full_url, wait_until="networkidle")
            
            # Tarayıcıyı kapat
            await browser.close()
            
            # Response verisini kontrol et
            if response_data:
                if isinstance(response_data, dict):
                    return response_data
                elif isinstance(response_data, str):
                    try:
                        return json.loads(response_data)
                    except:
                        print("JSON parse hatası")
                        return None
            
            # Eğer response alınamadıysa alternatif yöntemle dene
            print("Headless browser ile yanıt alınamadı, httpx ile deneniyor...")
            return await fetch_review_page_fallback(params)
                
    except Exception as e:
        print(f"Headless browser hatası: {e}")
        # Hata durumunda alternatif yönteme geri dön
        return await fetch_review_page_fallback(params)

async def fetch_review_page_fallback(params):
    """
    Trendyol ürün yorumları sayfasını httpx ile çeker (yedek yöntem)
    """
    # Yeni API URL config'den alınıyor
    url = settings.TRENDYOL_REVIEW_API_URL
    
    # Curl'den alınan headers
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'tr,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
        'baggage': 'ty.kbt.name=ViewReviewRatings,ty.platform=Web,ty.business_unit=Core Commerce,ty.channel=TR,com.trendyol.observability.business_transaction.name=ViewReviewRatings,ty.source.service.name=WEB Storefront TR,ty.source.deployment.environment=production,ty.source.service.version=b1729d82,ty.source.client.path=unknown,ty.source.service.type=client',
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
    
    try:
        # SSL doğrulamayı devre dışı bırak ve daha uzun timeout süresi belirle
        async with httpx.AsyncClient(timeout=30.0, verify=False, cookies=cookies) as client:
            
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching review page: {response.status_code}")
                return None
    except (httpx.ConnectError, httpx.ConnectTimeout, socket.gaierror) as conn_error:
        print(f"Bağlantı hatası (yorumlar): {conn_error}")
        # DNS problemi olabilir, alternatif bir yöntem dene
        try:
            # Alternatif URL
            alternative_url = settings.TRENDYOL_ALT_REVIEW_API_URL
            async with httpx.AsyncClient(timeout=30.0, verify=False, cookies=cookies) as client:

                response = await client.get(alternative_url, params=params, headers=headers)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Alternatif de başarısız: {response.status_code}")
                    return None
        except Exception as alt_error:
            print(f"Alternatif de başarısız (hata): {alt_error}")
            return None
    except Exception as e:
        print(f"Exception while fetching review page: {e}")
        return None

async def fetch_product_details(url):
    """
    Ürün detay sayfasını headless tarayıcı ile çeker
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with async_playwright() as p:
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
                page = await context.new_page()

                # Curl'den alınan header ve cookie'leri ekle
                await page.set_extra_http_headers({
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'accept-language': 'tr,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
                    'cache-control': 'no-cache',
                    'pragma': 'no-cache',
                    'priority': 'u=0, i',
                    'referer': 'https://www.trendyol.com/sr?q=AWOX&qt=AWOX&st=AWOX&os=1&pi=2',
                    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"macOS"',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'same-origin',
                    'sec-fetch-user': '?1',
                    'upgrade-insecure-requests': '1',
                    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0'
                })
                # Curl'den alınan cookie'leri ekle
                await context.add_cookies([
                    {"name": "hvtb", "value": "1", "domain": ".trendyol.com", "path": "/"},
                    {"name": "platform", "value": "web", "domain": ".trendyol.com", "path": "/"},
                    {"name": "OptanonAlertBoxClosed", "value": "2025-06-05T21:22:46.040Z", "domain": ".trendyol.com", "path": "/"},
                    {"name": "pid", "value": "edd0d63e-f8e2-497c-8edd-484ba0be366a", "domain": ".trendyol.com", "path": "/"},
                    {"name": "WebAbTesting", "value": "A_13-B_69-C_81-D_73-E_44-F_19-G_55-H_81-I_20-J_21-K_99-L_99-M_13-N_51-O_86-P_22-Q_97-R_77-S_26-T_49-U_18-V_37-W_23-X_47-Y_62-Z_90", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_gcl_au", "value": "1.1.808692516.1749158566", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_ym_uid", "value": "1749158569298936504", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_ym_d", "value": "1749158569", "domain": ".trendyol.com", "path": "/"},
                    {"name": "utmCampaignLT30d", "value": "not set", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_hjSessionUser_3408726", "value": "eyJpZCI6ImYwN2VkZjg1LWQyMDUtNTI0OC04MDczLThlMTEyY2FkMDZiZCIsImNyZWF0ZWQiOjE3NDkxNTg1Njc2NzMsImV4aXN0aW5nIjp0cnVlfQ==", "domain": ".trendyol.com", "path": "/"},
                    {"name": "storefrontId", "value": "1", "domain": ".trendyol.com", "path": "/"},
                    {"name": "language", "value": "tr", "domain": ".trendyol.com", "path": "/"},
                    {"name": "countryCode", "value": "TR", "domain": ".trendyol.com", "path": "/"},
                    {"name": "anonUserId", "value": "6387a2d0-4cf4-11f0-8532-bdcbb98642ec", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_hjSessionUser_2713408", "value": "eyJpZCI6IjYyYzExNTU0LTQ2ZTMtNTA0Yi1hYjRkLTJjYTcxY2M0MDk1OSIsImNyZWF0ZWQiOjE3NTEyODY5MjQyNDIsImV4aXN0aW5nIjp0cnVlfQ==", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_ga_1VG7004E6C", "value": "GS2.1.s1751315306$o1$g0$t1751315306$j60$l0$h0", "domain": ".trendyol.com", "path": "/"},
                    {"name": "COOKIE_TY.Anonym", "value": "tx=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cm46dHJlbmR5b2w6YW5vbmlkIjoiM2FjOGI0ZTg1NWYxMTFmMDk4ODVkYTY0Mjc5ZmNjOWQiLCJyb2xlIjoiYW5vbiIsImF0d3J0bWsiOiIzYWM4YjRlNC01NWYxLTExZjAtOTg4NS1kYTY0Mjc5ZmNjOWQiLCJhcHBOYW1lIjoidHkiLCJhdWQiOiJzYkF5ell0WCtqaGVMNGlmVld5NXR5TU9MUEpXQnJrYSIsImV4cCI6MTkwOTEwMzUwMSwiaXNzIjoiYXV0aC50cmVuZHlvbC5jb20iLCJuYmYiOjE3NTEzMTU1MDF9.e7oLvkRCXfIjmLw4XfaiNuvxvvUE4TG8Gw4J7PA3fSQ", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_hjDonePolls", "value": "993510", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_ga_FZ7435S7BY", "value": "GS2.1.s1751454130$o4$g1$t1751454131$j59$l0$h0", "domain": ".trendyol.com", "path": "/"},
                    {"name": "utmSourceLT30d", "value": "direct", "domain": ".trendyol.com", "path": "/"},
                    {"name": "utmMediumLT30d", "value": "not set", "domain": ".trendyol.com", "path": "/"},
                    {"name": "COOKIE_TY.IsUserAgentMobileOrTablet", "value": "false", "domain": ".trendyol.com", "path": "/"},
                    {"name": "ForceUpdateSearchAbDecider", "value": "forced", "domain": ".trendyol.com", "path": "/"},
                    {"name": "FirstSession", "value": "0", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_cfuvid", "value": "DpdL72_TjE3sFKnSmpCWZVfPAJOL9BbwYUlfO3wC2Qg-1751878462920-0.0.1.1-604800000", "domain": ".trendyol.com", "path": "/"},
                    {"name": "userid", "value": "undefined", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_ym_isad", "value": "1", "domain": ".trendyol.com", "path": "/"},
                    {"name": "sid", "value": "8ie8741dPX", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_ga_1", "value": "GS2.1.s1751887493$o28$g0$t1751887496$j57$l0$h1294065729", "domain": ".trendyol.com", "path": "/"},
                    {"name": "forceUpdateAbDecider", "value": "forced", "domain": ".trendyol.com", "path": "/"},
                    {"name": "WebRecoAbDecider", "value": "ABallInOneRecoVersion_1-ABbasketRecoVersion_1-ABcollectionRecoVersion_1-ABshopTheLookVersion_1-ABcrossRecoAdsVersion_1-ABsimilarRecoVersion_1-ABsimilarRecoAdsVersion_1-ABcompleteTheLookVersion_1-ABattributeRecoVersion_1-ABcrossRecoVersion_1-ABsimilarSameBrandVersion_1-ABcrossSameBrandVersion_1-ABpdpGatewayVersion_1", "domain": ".trendyol.com", "path": "/"},
                    {"name": "__cf_bm", "value": "Gu5T9gxBpeoG7ACMlqnH.1hPAsTSeRCs0uc3Q8k6Nhg-1751889250-1.0.1.1-bbHywcxlSL9of6dGLtiy2XZJyQvHtdP2isgqgzpgILBTEiCGoSJRwbAiM.oE.lqgwXr.xw8x70S.15a5IpMF1nek_8ksC35CUgm9NUPNCqM", "domain": ".trendyol.com", "path": "/"},
                    {"name": "UserInfo", "value": "%7B%22Gender%22%3Anull%2C%22UserTypeStatus%22%3Anull%2C%22ForceSet%22%3Afalse%7D", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_hjSession_3408726", "value": "eyJpZCI6IjBkOTVhODE0LWRmMGQtNDI3MS04MzhjLTIyNzg2MTZiNzY4ZCIsImMiOjE3NTE4ODkyNTE2MTQsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MH0=", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_ga", "value": "GA1.2.1853960060.1749158567", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_gid", "value": "GA1.2.130582697.1751889252", "domain": ".trendyol.com", "path": "/"},
                    {"name": "WebAbDecider", "value": "ABres_B-ABBMSA_B-ABRRIn_B-ABSCB_B-ABSuggestionHighlight_B-ABBP_B-ABCatTR_B-ABSuggestionTermActive_A-ABAZSmartlisting_62-ABBH2_B-ABMB_B-ABMRF_1-ABARR_B-ABMA_B-ABSP_B-ABPastSearches_B-ABSuggestionJFYProducts_B-ABSuggestionQF_B-ABBadgeBoost_A-ABFilterRelevancy_1-ABSuggestionBadges_B-ABProductGroupTopPerformer_B-ABOpenFilterToggle_2-ABRR_2-ABBS_2-ABSuggestionPopularCTR_B", "domain": ".trendyol.com", "path": "/"},
                    {"name": "AbTesting", "value": "SFWBFP_B-SFWDBSR_A-SFWDQL_B-SFWDRS_A-SFWDSAOFv2_B-SFWDSFAG_B-SFWDTKV2_A-SFWPSCB_B-SSTPRFL_B-STSBuynow_B-STSCouponV2_A-STSImageSocialProof_A-STSRecoRR_B-STSRecoSocialProof_A-WCOnePageCheckoutv3_A-WebAATestPidStRndGulf_A%7C1751891181%7Cedd0d63e-f8e2-497c-8edd-484ba0be366a", "domain": ".trendyol.com", "path": "/"},
                    {"name": "msearchAb", "value": "ABAdvertSlotPeriod_1-ABAD_B-ABQR_B-ABqrw_b-ABSimD_B-ABBSA_D-ABSuggestionLC_B", "domain": ".trendyol.com", "path": "/"},
                    {"name": "recoAb", "value": "collectionReco%3AshopTheLook_V1_1", "domain": ".trendyol.com", "path": "/"},
                    {"name": "homepageAb", "value": "homepage%3AadWidgetSorting_V1_1-componentSMHPLiveWidgetFix_V3_1-firstComponent_V3_2-sorter_V4_b-performanceSorting_V1_3-topWidgets_V1_1%2CnavigationSection%3Asection_V1_1%2CnavigationSideMenu%3AsideMenu_V1_1", "domain": ".trendyol.com", "path": "/"},
                    {"name": "__cflb", "value": "04dToXpE75gnanWf1Jct5BHNFbbVQqWRGUwYiMkUDs", "domain": ".trendyol.com", "path": "/"},
                    {"name": "OptanonConsent", "value": "isGpcEnabled=0&datestamp=Mon+Jul+07+2025+14%3A56%3A21+GMT%2B0300+(GMT%2B03%3A00)&version=202402.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&genVendors=V77%3A0%2CV67%3A0%2CV79%3A0%2CV71%3A0%2CV69%3A0%2CV7%3A0%2CV5%3A0%2CV9%3A0%2CV1%3A0%2CV70%3A0%2CV3%3A0%2CV68%3A0%2CV78%3A0%2CV17%3A0%2CV76%3A0%2CV80%3A0%2CV16%3A0%2CV72%3A0%2CV10%3A0%2CV40%3A0%2C&consentId=91e9afc4-3fb1-4656-8171-48e782033248&interactionCount=2&isAnonUser=1&landingPath=NotLandingPage&groups=C0002%3A1%2CC0004%3A1%2CC0003%3A1%2CC0001%3A1%2CC0007%3A1%2CC0009%3A1%2CC0005%3A0&geolocation=TR%3B06&AwaitingReconsent=false", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_gat_UA-13174585-60", "value": "1", "domain": ".trendyol.com", "path": "/"},
                    {"name": "VisitCount", "value": "37", "domain": ".trendyol.com", "path": "/"},
                    {"name": "SearchMode", "value": "1", "domain": ".trendyol.com", "path": "/"},
                    {"name": "_ga_NMNGDGYKS4", "value": "GS2.2.s1751889252$o19$g1$t1751889382$j60$l0$h0", "domain": ".trendyol.com", "path": "/"}
                ])
                
                print(f"Product detail URL (Headless): {url}")
                
                # Sayfaya git
                await page.goto(url, wait_until="networkidle")
                # Cloudflare'ı aşmak için insana yakın davranışlar ekle
                wait_time = random.randint(2000, 5000)
                await page.wait_for_timeout(wait_time)  # 2-5 saniye rastgele bekle
                await page.mouse.move(random.randint(50, 400), random.randint(100, 500))
                await page.keyboard.press("PageDown")
                await page.wait_for_timeout(random.randint(1000, 2000))
                
                # Sayfanın HTML içeriğini al
                html_content = await page.content()
                
                # Tarayıcıyı kapat
                await browser.close()

                # Cloudflare engeli var mı kontrol et
                if any(x in html_content for x in ["Cloudflare", "Checking your browser", "Attention Required!"]):
                    print(f"Cloudflare engeli tespit edildi, tekrar denenecek (deneme {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(random.randint(2, 5))
                        continue
                
                # Tüm JSON-LD scriptlerini bul
                json_ld_matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
                product_json_ld = None
                for json_ld_text in json_ld_matches:
                    try:
                        data = json.loads(json_ld_text.strip())
                        if isinstance(data, dict) and data.get("@type") == "Product":
                            product_json_ld = data
                            break
                    except Exception:
                        continue
                if product_json_ld:
                    return product_json_ld
                if json_ld_matches:
                    try:
                        json_ld_data = json.loads(json_ld_matches[0].strip())
                        return json_ld_data
                    except json.JSONDecodeError as e:
                        print(f"JSON parse error: {e}")
                        product_detail_match = re.search(r'window\.__PRODUCT_DETAIL_APP_INITIAL_STATE__\s*=\s*({.*?});', html_content, re.DOTALL)
                        if product_detail_match:
                            try:
                                product_data = json.loads(product_detail_match.group(1))
                                return {"productData": product_data.get("product", {})}
                            except json.JSONDecodeError:
                                pass
                        return None
                else:
                    print("JSON-LD data not found in HTML")
                    product_detail_match = re.search(r'window\.__PRODUCT_DETAIL_APP_INITIAL_STATE__\s*=\s*({.*?});', html_content, re.DOTALL)
                    if product_detail_match:
                        try:
                            product_data = json.loads(product_detail_match.group(1))
                            return {"productData": product_data.get("product", {})}
                        except json.JSONDecodeError:
                            pass
                    return None
        except Exception as e:
            print(f"Headless browser hatası (ürün detayları): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(random.randint(2, 5))
                continue
            # Hata durumunda alternatif yönteme geri dön
            return await fetch_product_details_fallback(url)

async def fetch_product_details_fallback(url):
    """
    Ürün detay sayfasını httpx ile çeker (yedek yöntem)
    """
    # Curl'den alınan headers
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'tr,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': settings.USER_AGENT
    }
    
    # Basit cookie bilgisi
    cookies = {
        'platform': 'web',
        'countryCode': 'TR',
        'language': 'tr',
    }
    
    try:
        # SSL doğrulamayı devre dışı bırak ve daha uzun timeout süresi belirle
        async with httpx.AsyncClient(timeout=30.0, verify=False, cookies=cookies) as client:
            print(f"Product detail URL (fallback): {url}")
            
            # Yeniden deneme mekanizması
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await client.get(url, headers=headers)
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout, socket.gaierror) as conn_err:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"Bağlantı hatası, {wait_time} saniye sonra yeniden deneniyor... (Deneme {attempt+1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"Maksimum deneme sayısına ulaşıldı: {conn_err}")
                        return None
            
            if response.status_code == 200:
                html_content = response.text
                
                # JSON-LD verilerini bul
                json_ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html_content, re.DOTALL)
                if json_ld_match:
                    json_ld_text = json_ld_match.group(1).strip()
                    try:
                        json_ld_data = json.loads(json_ld_text)
                        return json_ld_data
                    except json.JSONDecodeError as e:
                        print(f"JSON parse error: {e}")
                        # Script taglerindeki ürün verilerini bulmaya çalış
                        product_detail_match = re.search(r'window\.__PRODUCT_DETAIL_APP_INITIAL_STATE__\s*=\s*({.*?});', html_content, re.DOTALL)
                        if product_detail_match:
                            try:
                                product_data = json.loads(product_detail_match.group(1))
                                return {"productData": product_data.get("product", {})}
                            except json.JSONDecodeError:
                                pass
                        return None
                else:
                    print("JSON-LD data not found in HTML")
                    # Script taglerindeki ürün verilerini bulmaya çalış
                    product_detail_match = re.search(r'window\.__PRODUCT_DETAIL_APP_INITIAL_STATE__\s*=\s*({.*?});', html_content, re.DOTALL)
                    if product_detail_match:
                        try:
                            product_data = json.loads(product_detail_match.group(1))
                            return {"productData": product_data.get("product", {})}
                        except json.JSONDecodeError:
                            pass
                    return None
            else:
                print(f"Error fetching product details: {response.status_code}")
                return None
    except Exception as e:
        print(f"Exception while fetching product details: {e}")
        return None

async def append_reviews_to_csv(reviews, product_info, filename, is_first_write=False):
    """
    Yorumları CSV dosyasına ekler
    """
    # downloads dizinini kullan
    file_path = os.path.join(settings.DOWNLOADS_DIR, filename)
    
    # CSV başlıkları
    headers = [
        'Ürün Adı', 'Ürün URL', 'Content ID', 'Merchant ID', 'Boutique ID',
        'Kullanıcı Adı', 'Yorum Tarihi', 'Puan', 'Yorum', 'Beğeni Sayısı',
        'Ürün Özellikleri'
    ]
    
    # Ürün özelliklerini string olarak birleştir
    product_properties = ""
    if product_info.get('properties'):
        # Özellikleri parse etmeden, JSON string olarak kaydet
        try:
            product_properties = json.dumps(product_info['properties'], ensure_ascii=False)
        except:
            # Hata durumunda boş string döndür
            product_properties = ""
    
    # Dizin yoksa oluştur
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    mode = 'w' if is_first_write else 'a'
    with open(file_path, mode, newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # İlk yazma işlemiyse başlıkları yaz
        if is_first_write:
            writer.writerow(headers)
        
        # Her yorum için bir satır oluştur
        for review in reviews:
            # Yorumu temizle (newline karakterlerini kaldır)
            comment = review.get('comment', '').replace('\n', ' ').replace('\r', '')
            
            # Tarihi düzenle
            review_date = review.get('lastModifiedDate', '')
            
            # Tarih zaten string formatında geliyor, doğrudan kullan
            # Örnek: "14 Temmuz 2023"
            
            row = [
                product_info['name'],
                product_info['url'],
                product_info['contentId'],
                product_info['merchantId'],
                product_info.get('boutiqueId', ''),
                review.get('userFullName', 'Anonim'),
                review_date,  # String formatında tarih direkt kullanılıyor
                review.get('rate', 0),
                comment,
                review.get('reviewLikeCount', 0),  # likeCount değil reviewLikeCount kullanılıyor
                product_properties
            ]
            
            writer.writerow(row)
    
    return file_path
