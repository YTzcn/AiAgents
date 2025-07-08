# Trendyol API

Bu proje, Trendyol'dan ürün yorumlarını ve arama sonuçlarını çekmek için FastAPI tabanlı bir API sağlar.

## Özellikler

- Trendyol ürün arama sonuçlarını çekme
- Ürün yorumlarını çekme ve analiz etme
- Yorumları CSV formatında dışa aktırma
- Asenkron HTTP istekleri ile hızlı veri çekme

## Kurulum

### Gereksinimler

- Python 3.8+
- FastAPI
- Uvicorn
- HTTPX
- Pydantic
- Aiofiles

### Adımlar

1. Projeyi klonlayın:
```bash
git clone <repo-url>
cd AiAgents
```

2. Sanal ortam oluşturun ve aktif edin:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate  # Windows
```

3. Bağımlılıkları yükleyin:
```bash
pip install -r requirements.txt
```

4. Uygulamayı çalıştırın:
```bash
uvicorn app.main:app --reload
```

Uygulama varsayılan olarak http://127.0.0.1:8000 adresinde çalışacaktır.

## API Kullanımı

### Ürün Yorumlarını Çekme

```
GET /trendyol/urun-yorumlari?url={trendyol_url}&export_csv=true
```

Parametreler:
- `url`: Trendyol arama sayfası URL'si (örn. https://www.trendyol.com/sr?q=telefon)
- `export_csv`: Yorumları CSV dosyasına aktarmak için `true` olarak ayarlayın (isteğe bağlı)

### Arama Sonuçlarını Çekme

```
GET /trendyol/search?url={trendyol_url}&pi={page_number}
```

Parametreler:
- `url`: Trendyol arama sayfası URL'si (örn. https://www.trendyol.com/sr?q=telefon)
- `pi`: Sayfa numarası (varsayılan: 1)

## Swagger Dokümantasyonu

API dokümantasyonuna erişmek için tarayıcınızda şu adresi açın:
```
http://127.0.0.1:8000/docs
```

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır.
