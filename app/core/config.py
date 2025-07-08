import os
from pydantic import BaseModel

class Settings(BaseModel):
    """
    Uygulama ayarları
    """
    # API Ayarları
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Trendyol API"
    
    # CORS Ayarları
    BACKEND_CORS_ORIGINS: list = ["*"]
    
    # Dosya Ayarları
    UPLOADS_DIR: str = os.path.join(os.getcwd(), "uploads")
    DOWNLOADS_DIR: str = os.path.join(os.getcwd(), "downloads")
    
    # Rate Limiting Ayarları
    RATE_LIMIT_SECONDS: int = 3  # API çağrıları arasında beklenecek süre (saniye)
    
    # Trendyol API Ayarları
    TRENDYOL_BASE_URL: str = "https://www.trendyol.com"
    TRENDYOL_API_URL: str = "https://apigw.trendyol.com/discovery-web-searchgw-service/v2/api/infinite-scroll/sr"
    TRENDYOL_REVIEW_API_URL: str = "https://apigw.trendyol.com/discovery-web-websfxsocialreviewrating-santral/product-reviews-detailed"
    
    # Alternatif API URL'leri (birincil URL çalışmazsa)
    TRENDYOL_ALT_API_URL: str = "https://public-mdc.trendyol.com/discovery-web-searchgw-service/v2/api/infinite-scroll/sr"
    TRENDYOL_ALT_REVIEW_API_URL: str = "https://apigw.trendyol.com/discovery-web-socialgw-service/api/review/products"
    
    # HTTP İstek Ayarları
    REQUEST_TIMEOUT: int = 30  # Saniye cinsinden
    USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"

settings = Settings()

# Gerekli dizinleri oluştur
os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
os.makedirs(settings.DOWNLOADS_DIR, exist_ok=True)
