from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from .routers import trendyol, hepsiburada
import warnings
import urllib3
import asyncio
import os
import subprocess
from fastapi.staticfiles import StaticFiles
from .core.config import settings
from typing import Dict, Any

# SSL uyarılarını bastır
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

app = FastAPI(
    title="Trendyol API",
    description="Trendyol ürün yorumları ve arama sonuçları için API",
    version="1.0.0"
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tüm originlere izin ver (production'da sınırlandırılmalı)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik dosyaları sunmak için
downloads_dir = settings.DOWNLOADS_DIR
os.makedirs(downloads_dir, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=downloads_dir), name="downloads")

# Playwright tarayıcılarını başlatma işlemi
@app.on_event("startup")
async def install_playwright_browsers():
    try:
        print("Playwright tarayıcıları kontrol ediliyor...")
        # Playwright tarayıcılarını kur (eğer yoksa)
        result = subprocess.run(
            ["playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            print("Playwright tarayıcıları başarıyla kuruldu veya zaten kurulu.")
        else:
            print(f"Playwright tarayıcıları kurulurken hata: {result.stderr}")
            # Hata durumunda pip ile playwright'ı kurmayı dene
            subprocess.run(["pip", "install", "playwright"], check=False)
            subprocess.run(["playwright", "install", "chromium"], check=False)
    except Exception as e:
        print(f"Playwright tarayıcıları kurulurken beklenmeyen hata: {e}")
        print("Uygulama tarayıcısız yedek modda çalışacak.")

# Routerları ekle
app.include_router(trendyol.router)
app.include_router(hepsiburada.router)

@app.get("/")
def read_root():
    return {"message": "FastAPI projesi çalışıyor!"}

# Hata ayıklama için basit bir endpoint
@app.get("/debug")
async def debug_info():
    """HTTP bağlantılarını test etmek için basit bir endpoint"""
    import socket
    import httpx
    import os
    
    results: Dict[str, Any] = {
        "hostname": socket.gethostname(),
        "ip_address": socket.gethostbyname(socket.gethostname()),
        "current_directory": os.getcwd(),
        "environment": os.environ.get("ENV", "development")
    }
    
    # Basit bir HTTP isteği yapalım
    try:
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            response = await client.get("https://www.google.com")
            results["google_status"] = response.status_code
    except Exception as e:
        results["google_error"] = str(e)
    
    # Trendyol'a bağlantıyı test edelim
    try:
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            response = await client.get("https://www.trendyol.com")
            results["trendyol_status"] = response.status_code
    except Exception as e:
        results["trendyol_error"] = str(e)
    
    # Playwright'ı test et
    try:
        from playwright.async_api import async_playwright
        results["playwright_installed"] = True
    except ImportError:
        results["playwright_installed"] = False
    
    return results

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
