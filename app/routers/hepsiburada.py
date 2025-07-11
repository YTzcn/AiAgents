from fastapi import APIRouter, Query, HTTPException
from ..services.hepsiburada_service import get_hepsiburada_product_info_and_reviews
from ..core.config import settings

router = APIRouter(
    prefix="/hepsiburada",
    tags=["hepsiburada"],
    responses={404: {"description": "Not found"}},
)

@router.get("/urun-bilgi-ve-yorumlar")
async def get_product_info_and_reviews_endpoint(
    url: str = Query(..., description="Hepsiburada ürün arama URL'si. Örnek: https://www.hepsiburada.com/ara?q=telefon"),
    export_csv: bool = Query(False, description="Sonuçları CSV dosyasına aktarmak için 'true' olarak ayarlayın")
):
    """
    Hepsiburada arama sonucundaki ürünlerin temel bilgilerini ve yorumlarını çeker.
    
    - **url**: Hepsiburada arama sayfası URL'si
    - **export_csv**: Sonuçları CSV dosyasına aktarmak için true/false
    """
    if not url or not url.startswith(settings.HEPSIBURADA_BASE_URL):
        raise HTTPException(
            status_code=400, 
            detail=f"Geçerli bir Hepsiburada URL'si gereklidir. Örn: {settings.HEPSIBURADA_BASE_URL}/ara?q=some-product"
        )
    
    try:
        result = await get_hepsiburada_product_info_and_reviews(url, export_csv)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Servis katmanında bilinmeyen bir hata oluştu."))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Endpoint hatası: {str(e)}")