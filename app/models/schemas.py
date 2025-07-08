from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any

class ProductProperty(BaseModel):
    name: str
    value: str

class ProductInfo(BaseModel):
    boutiqueId: Optional[str] = None
    merchantId: str
    contentId: str
    url: str
    name: str
    properties: Optional[List[ProductProperty]] = []

class Review(BaseModel):
    userFullName: Optional[str] = "Anonim"
    lastModifiedDate: Optional[int] = None
    rate: float
    comment: str
    likeCount: Optional[int] = 0

class ProductReview(BaseModel):
    productInfo: ProductInfo
    reviews: List[Review] = []
    totalReviews: int = 0
    error: Optional[str] = None

class SearchResult(BaseModel):
    products: List[Dict[str, Any]] = []
    totalCount: int = 0
    page: int = 1
    error: Optional[str] = None

class ProductReviewsResponse(BaseModel):
    success: bool
    totalProducts: int
    totalPages: int
    products: List[Dict[str, Any]] = []
    csv_file: Optional[str] = None
    error: Optional[str] = None
