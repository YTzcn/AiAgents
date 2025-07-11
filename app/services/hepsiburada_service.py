from ..parsers.hepsiburada_parser import fetch_products_from_search, fetch_product_reviews, fetch_product_features
from typing import Dict, Any, List, Optional
import asyncio
import csv
import os
import json
from datetime import datetime
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
import random
import logging
import math

from app.core.config import settings

logger = logging.getLogger(__name__)

async def get_hepsiburada_product_info_and_reviews(url: str, export_csv: bool = False) -> Dict[str, Any]:
    """
    Orchestrates fetching products and reviews. If export_csv is True, data is
    written to the file instantly after each product is processed. Otherwise,
    data is processed concurrently and returned as JSON.
    """
    try:
        all_products_from_search = []
        
        logger.info("Hepsiburada ürün listesi ve sayfa sayısı çekiliyor...")
        first_page_result = await fetch_products_from_search(url)

        if not first_page_result or 'products' not in first_page_result:
             logger.error("Başlangıç ürün sayfası çekilemedi, işlem durduruldu.")
             return {"success": False, "error": "Failed to fetch initial product page."}

        all_products_from_search.extend(first_page_result.get('products', []))
        last_page = first_page_result.get('lastPage', 1)
        
        logger.info(f"Toplam {last_page} sayfa bulundu.")

        if last_page > 1: # 1. SAYFA KISITLAMASI KALDIRILDI
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)

            for page_num in range(2, last_page + 1):
                logger.info(f"📄 Sayfa {page_num}/{last_page} çekiliyor...")
                query_params['sayfa'] = [str(page_num)]
                
                new_query_string = urlencode(query_params, doseq=True)
                next_page_url_parts = list(parsed_url)
                next_page_url_parts[4] = new_query_string
                next_page_url = urlunparse(next_page_url_parts)
                
                page_result = await fetch_products_from_search(next_page_url)
                if page_result and 'products' in page_result:
                    all_products_from_search.extend(page_result.get('products', []))
                else:
                    logger.warning(f"⚠️ Sayfa {page_num} için ürünler çekilemedi. Devam ediliyor...")
                
                # Sunucuyu yormamak için sayfalar arasında makul ve rastgele bir süre bekle
                wait_time = random.uniform(settings.HEPSIBURADA_API_MIN_WAIT_TIME, settings.HEPSIBURADA_API_MAX_WAIT_TIME)
                await asyncio.sleep(wait_time)
        
        product_count = len(all_products_from_search)
        logger.info(f"Toplam {product_count} ürün bulundu. Yorum ve detaylar çekilecek...")

        if not all_products_from_search:
            logger.info("Hiç ürün bulunamadı.")
            return {"success": True, "message": "No products found."}

        # --- CSV EXPORT LOGIC ---
        if export_csv:
            os.makedirs(settings.DOWNLOADS_DIR, exist_ok=True) # Dizin'in var olduğundan emin ol
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(settings.DOWNLOADS_DIR, f"hepsiburada_reviews_{timestamp}.csv")
            
            headers = [
                'product_name', 'sku', 'price', 'product_url', 'review_content', 'review_star', 
                'review_created_at', 'customer_name', 'customer_surname', 'customer_display_name',
                'media_urls', 'product_features'
            ]

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                
                for i, product in enumerate(all_products_from_search):
                    # logger.info(f"[{i+1}/{product_count}] Ürün işleniyor: {product.get('variantList', [{}])[0].get('sku')}")
                    sku = product.get('variantList', [{}])[0].get('sku')
                    if not sku:
                        continue
                    
                    processed_product = await process_single_product(product, sku)
                    if processed_product:
                        # Append to CSV instantly
                        if processed_product.get('reviews'):
                            features_json = json.dumps(processed_product.get('features', {}), ensure_ascii=False)
                            for review in processed_product['reviews']:
                                media_list = review.get('media', []) or []
                                
                                # Gelen URL'lerin sonundaki ":webp" uzantısını kaldır
                                cleaned_urls = [
                                    media.get('fullMediaUrl').removesuffix(':webp')
                                    for media in media_list
                                    if media.get('fullMediaUrl')
                                ]
                                media_urls = json.dumps(cleaned_urls, ensure_ascii=False)


                                # Yorum içeriğini güvenli bir string haline getir
                                review_content = review.get('review', {}).get('content') # Önce içeriği al
                                # Eğer içerik None değilse temizle, None ise boş string ata
                                safe_review_content = review_content.replace('\n', ' ').replace('\r', ' ') if review_content else ""


                                writer.writerow({
                                    'product_name': processed_product.get('product_name'),
                                    'sku': processed_product.get('sku'),
                                    'price': processed_product.get('price'),
                                    'product_url': processed_product.get('product_url', ''), 
                                    'review_content': safe_review_content,
                                    'review_star': review.get('star'),
                                    'review_created_at': review.get('createdAt'),
                                    'customer_name': review.get('customer', {}).get('name'),
                                    'customer_surname': review.get('customer', {}).get('surname'),
                                    'customer_display_name': review.get('customer', {}).get('displayName'),
                                    'media_urls': media_urls,
                                    'product_features': features_json
                                })
                        else: # Product has no reviews
                             writer.writerow({
                                'product_name': processed_product.get('product_name'),
                                'sku': processed_product.get('sku'),
                                'price': processed_product.get('price'),
                                'product_url': processed_product.get('product_url', ''),
                                'product_features': json.dumps(processed_product.get('features', {}), ensure_ascii=False)
                            })

            logger.info(f"Veriler başarıyla CSV dosyasına aktarıldı: {file_path}")
            return {"success": True, "message": f"Data successfully exported to {file_path}"}

        # --- JSON RESPONSE LOGIC ---
        else:
            tasks = []
            for product in all_products_from_search:
                sku = product.get('variantList', [{}])[0].get('sku')
                if sku:
                    tasks.append(process_single_product(product, sku))
            
            processed_products = await asyncio.gather(*tasks)
            all_product_data = [p for p in processed_products if p]
            return {"success": True, "data": all_product_data}

    except Exception as e:
        logger.error(f"Servis katmanında bir hata oluştu: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def process_single_product(product: Dict[str, Any], sku: str) -> Optional[Dict[str, Any]]:
    """
    Helper function to process a single product: get its info and reviews.
    """
    try:
        variant_info = product.get('variantList', [{}])[0]
        product_name = variant_info.get('name')
        price = variant_info.get('listing', {}).get('priceInfo', {}).get('price')
        product_url_path = variant_info.get('url') # Arama sonucundan gelen ürün URL path'i

        # Ürün özelliklerini, yorum olup olmamasından bağımsız olarak her zaman çek
        features = {}
        if product_url_path:
            # fetch_product_features fonksiyonu zaten başına domain ekliyor
            features = await fetch_product_features(product_url_path)
        else:
            logger.warning(f"  - SKU {sku} için ürün URL'si arama sonucunda bulunamadı, özellikler çekilemiyor.")


        all_reviews = []
        page_size = settings.HEPSIBURADA_REVIEW_PAGE_SIZE
        
        # 1. İlk sayfayı çek ve toplam yorum sayısını öğren
        first_page_response = await fetch_product_reviews(sku, page=0, size=page_size)
        
        total_reviews = 0
        
        if not first_page_response or not isinstance(first_page_response, dict):
            logger.warning(f"  - SKU {sku} için geçerli bir yorum verisi alınamadı.")
            # Yorum olmasa bile ürün temel bilgilerini ve özelliklerini döndür
            return {
                "product_name": product_name, 
                "sku": sku, 
                "price": price, 
                "reviews": [],
                "features": features,
                "product_url": f"{settings.HEPSIBURADA_BASE_URL}/{product_url_path}" if product_url_path else ""
            }

        # İlk sayfanın yorumlarını ve toplam yorum sayısını ayrıştır
        data_node = first_page_response.get('data', {})
        if isinstance(data_node, dict):
            if 'approvedUserContent' in data_node: # Yeni format
                content_node = data_node.get('approvedUserContent', {})
                all_reviews.extend(content_node.get('approvedUserContentList', []))
                total_reviews = first_page_response.get('totalItemCount', 0)
            elif 'approvedUserContents' in data_node: # Eski format
                content_node = data_node.get('approvedUserContents', {})
                all_reviews.extend(content_node.get('userContents', []))
                total_reviews = content_node.get('listCount', 0)

        # logger.info(f"  - Toplam {total_reviews} yorum bulundu. İlk sayfadan {len(all_reviews)} yorum alındı.")

        # 2. Gerekliyse diğer sayfaları da çek
        if total_reviews > len(all_reviews):
            total_pages = math.ceil(total_reviews / page_size)
            # logger.info(f"  - {sku} için {total_pages} sayfa yorum çekilecek.")
            
            for page_num in range(1, int(total_pages)):
                await asyncio.sleep(random.uniform(settings.HEPSIBURADA_API_MIN_WAIT_TIME, settings.HEPSIBURADA_API_MAX_WAIT_TIME)) # API'ye nefes aldır
                
                next_page_response = await fetch_product_reviews(sku, page=page_num, size=page_size)
                
                new_reviews = []
                if next_page_response and isinstance(next_page_response, dict):
                    data_node = next_page_response.get('data', {})
                    if isinstance(data_node, dict):
                        if 'approvedUserContent' in data_node:
                            new_reviews = data_node.get('approvedUserContent', {}).get('approvedUserContentList', [])
                        elif 'approvedUserContents' in data_node:
                            new_reviews = data_node.get('approvedUserContents', {}).get('userContents', [])
                
                if new_reviews:
                    all_reviews.extend(new_reviews)
                else:
                    logger.warning(f"    - Sayfa {page_num + 1} boş geldi, {sku} için yorum çekme işlemi durduruluyor.")
                    break

        logger.info(f"SKU {sku} için toplam {len(all_reviews)} yorum işlendi.")

        product_full_url = ""
        if all_reviews:
            # Yorum varsa, oradaki tam URL'i kullanmak daha garantidir
            product_full_url = all_reviews[0].get('product', {}).get('url')
        elif product_url_path:
            # Yorum yoksa, arama sonucundaki path'ten tam URL oluştur
            product_full_url = f"{settings.HEPSIBURADA_BASE_URL}/{product_url_path}"


        return {
            "product_name": product_name,
            "sku": sku,
            "price": price,
            "reviews": all_reviews,
            "features": features,
            "product_url": product_full_url
        }
    except Exception as e:
        logger.error(f"❌ '{sku}' SKU'lu ürün işlenirken hata oluştu: {e}", exc_info=True)
        return None