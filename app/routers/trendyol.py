from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from ..services.trendyol_service import get_product_reviews, search_products

router = APIRouter(
    prefix="/trendyol",
    tags=["trendyol"],
    responses={404: {"description": "Not found"}},
)

@router.get("/urun-yorumlari")
async def get_product_reviews_endpoint(
    url: str = Query(..., description="Trendyol ürün arama URL'si. Örnek: https://www.trendyol.com/sr?q=telefon"),
    export_csv: bool = Query(False, description="Yorumları CSV dosyasına aktarmak için 'true' olarak ayarlayın")
):
    """
    Trendyol ürün yorumlarını çeker ve döndürür.
    
    - **url**: Trendyol arama sayfası URL'si
    - **export_csv**: Yorumları CSV dosyasına aktarmak için true/false
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL parametresi gerekli. Örnek: ?url=https://www.trendyol.com/sr?q=telefon")
    
    if not url.startswith("https://www.trendyol.com"):
        raise HTTPException(status_code=400, detail="Geçerli bir Trendyol URL'si değil. URL 'https://www.trendyol.com' ile başlamalıdır.")
    
    result = await get_product_reviews(url, export_csv)
    
    if not result.get("success", False):
        raise HTTPException(status_code=500, detail=result.get("error", "Bilinmeyen bir hata oluştu"))
    
    return result

@router.get("/search")
async def search_products_endpoint(
    url: str = Query(..., description="Trendyol arama URL'si. Örnek: https://www.trendyol.com/sr?q=telefon"),
    pi: int = Query(1, description="Sayfa numarası", ge=1)
):
    """
    Trendyol arama sonuçlarını çeker ve döndürür.
    
    - **url**: Trendyol arama sayfası URL'si
    - **pi**: Sayfa numarası (1'den başlar)
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL parametresi gerekli. Örnek: ?url=https://www.trendyol.com/sr?q=telefon")
    
    if not url.startswith("https://www.trendyol.com"):
        raise HTTPException(status_code=400, detail="Geçerli bir Trendyol URL'si değil. URL 'https://www.trendyol.com' ile başlamalıdır.")
    
    result = await search_products(url, pi)
    
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result.get("error", "Bilinmeyen bir hata oluştu"))
    
    return result
