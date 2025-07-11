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

    # Hepsiburada Ayarları
    HEPSIBURADA_BASE_URL: str = "https://www.hepsiburada.com"
    HEPSIBURADA_SEARCH_API_URL: str = "https://blackgate.hepsiburada.com/moriaapi/api/product"
    HEPSIBURADA_REVIEW_API_URL: str = "https://user-content-gw-hermes.hepsiburada.com/queryapi/v2/ApprovedUserContents"
    HEPSIBURADA_API_CLIENT_ID: str = "MoriaDesktop"
    HEPSIBURADA_SEARCH_PAGE_SIZE: int = 36
    HEPSIBURADA_REVIEW_PAGE_SIZE: int = 100
    HEPSIBURADA_API_MIN_WAIT_TIME: int = 1
    HEPSIBURADA_API_MAX_WAIT_TIME: int = 3
    HEPSIBURADA_REQUIRED_COOKIES: list = ['_abck', 'bm_sz', 'bm_sv', 'ak_bmsc', 'hbus_sessionId']

    # Playwright & Chrome Ayarları
    PLAYWRIGHT_CDP_URL: str = "http://localhost:9222"
    # Farklı OS'ler için Chrome yolları. _get_chrome_path helper fonksiyonu doğru olanı bulacaktır.
    CHROME_APP_PATHS: dict = {
        "Darwin": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "Windows": [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ],
        "Linux": [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/opt/google/chrome/google-chrome",
        ]
    }
    CHROME_USER_DATA_DIR: str = os.path.join(os.path.expanduser("~"), "chrome-debug-profile")
    HEPSIBURADA_COOKIE_WARMUP_URL: str = "https://www.hepsiburada.com/ara?q=telefon"
    
    # HTTP İstek Ayarları
    REQUEST_TIMEOUT: int = 30  # Saniye cinsinden
    USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"

settings = Settings()

# Gerekli dizinleri oluştur
os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
os.makedirs(settings.DOWNLOADS_DIR, exist_ok=True)
