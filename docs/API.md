# REST API

> Sürüm 0.1.0 · Taban adres: `http://127.0.0.1:8000/api/v1/`

---

## 1. Genel

| Konu | Değer |
|---|---|
| Biçim | JSON |
| Kimlik doğrulama | Oturum çerezi veya `Token` başlığı |
| Yetkilendirme | Django izinleri — arayüzle aynı kurallar |
| Sayfalama | `?page=N` · varsayılan 50 kayıt |
| Arama | `?search=...` |
| Sıralama | `?ordering=alan` / `?ordering=-alan` |
| Hız sınırı | Kullanıcı 2000/saat · anonim 60/saat · AI 120/saat |

### Kimlik doğrulama

```bash
# Belirteç al
curl -X POST http://127.0.0.1:8000/api/v1/auth/token/ \
     -d "username=yonetici&password=..."
# → {"token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"}

# Kullan
curl -H "Authorization: Token 9944b0..." http://127.0.0.1:8000/api/v1/cellar/wines/
```

> **Güvenlik:** API, arayüzle **aynı** izin sistemini kullanır. Garson
> yetkisiyle alınan bir belirteç, kav yönetimi uç noktalarına erişemez.
> Yetkisiz her istek denetim kaydına yazılır.

---

## 2. Servis keşfi

| Uç nokta | Yöntem | Açıklama |
|---|---|---|
| `/api/v1/` | GET | Modül listesi ve bağlantıları |
| `/api/v1/health/` | GET | Sağlık kontrolü — **kimlik gerektirmez** |
| `/api/v1/auth/token/` | POST | Belirteç alma |

### Sağlık kontrolü

```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": { "engine": "sqlite3", "reachable": true },
  "ai": { "default_provider": "lmstudio", "local_only": false, "privacy_mode": true },
  "payment_mode": "sandbox",
  "offline_capable": true
}
```

Bu uç nokta hiçbir gizli bilgi döndürmez ve `CHECK_WINE_HOUSE.bat` tarafından
kullanılır.

---

## 3. Şarap kavı — `/api/v1/cellar/`

| Uç nokta | Yöntem | Açıklama |
|---|---|---|
| `wines/` | GET, POST | Şarap listesi / oluşturma |
| `wines/{id}/` | GET, PUT, PATCH, DELETE | Tek şarap |
| `wines/{id}/open_bottle/` | POST | **Şişe açar ve stoktan düşer** |
| `wines/{id}/pour/` | POST | **Kadeh servis eder** |
| `wines/valuation/` | GET | Kav değerlemesi |
| `wines/drink_window_alerts/` | GET | İçim aralığı uyarıları |
| `wines/detect_duplicates/` | POST | Mükerrer kayıt taraması |
| `lots/` | GET, POST | Parti (lot) yönetimi |
| `openings/` | GET | Açılmış şişeler (salt okunur) |
| `openings/{id}/finish/` | POST | Açık şişeyi kapatır |
| `tasting-notes/` | GET, POST | Tadım notları |
| `pairings/` | GET, POST | Yemek–şarap eşleştirmeleri |
| `locations/` | GET, POST | Kav konumları |
| `readings/` | GET, POST | Sıcaklık/nem ölçümleri |
| `faults/` | GET, POST | Şarap kusurları |
| `regions/`, `grapes/`, `producers/` | GET, POST | Referans veriler |

### Filtreler

```
GET /api/v1/cellar/wines/?type=red&by_glass=1&search=öküzgözü
```

### Kadeh servisi

```bash
curl -X POST http://127.0.0.1:8000/api/v1/cellar/wines/1/pour/ \
     -H "Authorization: Token ..." -H "Content-Type: application/json" \
     -d '{"volume_ml": 150, "pour_type": "glass_sale"}'
```

```json
{
  "pour": { "id": 42, "volume_ml": 150, "pour_type": "glass_sale" },
  "opening": { "id": 7, "remaining_ml": 600, "glasses_remaining": 4,
               "yield_percent": "20.00" },
  "opened_new_bottle": true,
  "remaining_glasses": 4
}
```

`opened_new_bottle: true` ise kapalı şişe stoğundan **1 şişe düşmüştür**.

**Yetki:** `cellar.can_pour_glass` · **Hata:** yeterli stok yoksa `400`.

---

## 4. Operasyon — `/api/v1/operations/`

| Uç nokta | Yöntem | Açıklama |
|---|---|---|
| `orders/` | GET, POST | Adisyonlar (`?open=1` açık olanlar) |
| `orders/{id}/add_line/` | POST | Satır ekler (**fiyat dondurulur**) |
| `orders/{id}/send/` | POST | İstasyonlara gönderir (KOT üretir) |
| `orders/{id}/split/` | POST | Koltuk bazlı hesap bölme |
| `orders/{id}/pay/` | POST | Tahsilat (sandbox) |
| `orders/{id}/void/` | POST | İptal (onay gerekebilir) |
| `tickets/` | GET | Hazırlık fişleri (`?station=kitchen&active=1`) |
| `tickets/{id}/bump/` | POST | Fişi bir sonraki duruma ilerletir |
| `reservations/` | GET, POST | Rezervasyonlar |
| `reservations/{id}/assign_tables/` | POST | Masa atar (**çakışma denetimi**) |
| `waitlist/` | GET, POST | Bekleme listesi |
| `tables/`, `sections/` | GET, POST | Masa ve salon bölümleri |
| `payment-methods/` | GET, POST | Ödeme yöntemleri |
| `business-days/` | GET | İş günleri |
| `business-days/{id}/close/` | POST | Gün sonu kapanışı |

### Onay gerektiren işlemler

Yetkiniz yoksa `202 Accepted` döner ve onay talebi oluşturulur:

```json
{
  "detail": "Adisyon iptali yönetici onayı gerektirir. Onay talebi oluşturuldu.",
  "approval_id": 17
}
```

**İşlem uygulanmamıştır.** Başka bir yetkilinin onaylaması gerekir.

### Masa çakışması

```json
HTTP 409 Conflict
{ "detail": "Masa çakışması: RZV-0002 (18.08 19:00)" }
```

---

## 5. Menü — `/api/v1/catalog/`

| Uç nokta | Yöntem | Açıklama |
|---|---|---|
| `items/` | GET, POST | Menü ürünleri |
| `items/{id}/recalculate_cost/` | POST | Reçeteden maliyeti yeniden hesaplar |
| `categories/` | GET, POST | Kategoriler |
| `recipes/` | GET, POST | Reçeteler |
| `allergens/` | GET, POST | Alerjenler |
| `price-rules/` | GET, POST | Fiyat kuralları / kampanyalar |

Filtreler: `?item_type=wine&category=3&available=1`

---

## 6. Stok — `/api/v1/inventory/`

| Uç nokta | Yöntem | Açıklama |
|---|---|---|
| `items/` | GET, POST | Stok kalemleri (`?low_stock=1`) |
| `items/reorder_suggestions/` | GET | Sipariş önerileri (**yalnızca öneri**) |
| `items/expiring/` | GET | SKT yaklaşan partiler (`?days=7`) |
| `lots/` | GET, POST | Partiler |
| `movements/` | GET | Stok hareketleri (**salt okunur**) |
| `wastage/` | GET, POST | Fire kayıtları |
| `suppliers/` | GET, POST | Tedarikçiler |
| `orders/` | GET, POST | Satın alma siparişleri |
| `orders/{id}/quotation_comparison/` | GET | Teklif karşılaştırması |
| `receipts/` | GET, POST | Mal kabul |
| `receipts/{id}/post_to_stock/` | POST | Stoğa işler (parti oluşturur) |
| `counts/` | GET, POST | Stok sayımları |
| `counts/{id}/post_variances/` | POST | Sayım farklarını işler |

> `movements/` yalnızca okunabilir. Stok hareketleri değiştirilemez denetim
> izidir; düzeltme ters kayıtla yapılır.

---

## 7. Müşteri — `/api/v1/crm/`

| Uç nokta | Yöntem | Açıklama |
|---|---|---|
| `customers/` | GET, POST | Müşteriler |
| `customers/{id}/export_data/` | GET | **KVKK veri taşınabilirliği** |
| `customers/{id}/request_erasure/` | POST | **KVKK silme talebi** |
| `consents/` | GET, POST | Rıza kayıtları |
| `loyalty-accounts/` | GET, POST | Sadakat hesapları |
| `loyalty-transactions/` | GET, POST | Puan hareketleri |
| `campaigns/` | GET, POST | Kampanyalar |
| `visit-notes/` | GET, POST | Ziyaret notları |

### Gizlilik

Telefon ve e-posta yalnızca `crm.view_customer_contact` iznine sahip
kullanıcılara döner; diğerleri maskelenmiş değer görür:

```json
{ "phone": "+9…33", "email": "de…st" }
```

Telefonla arama (şifreli alanda HMAC özeti üzerinden):

```
GET /api/v1/crm/customers/?phone=%2B90+555+111+22+33
```

---

## 8. Personel — `/api/v1/hr/`

| Uç nokta | Yöntem | Açıklama |
|---|---|---|
| `employees/` | GET, POST | Personel (`?department=service&active=1`) |
| `shifts/` | GET, POST | Vardiyalar |
| `assignments/` | GET, POST | Vardiya atamaları |
| `leaves/` | GET, POST | İzin talepleri |
| `performance/` | GET | Performans göstergeleri (salt okunur) |

Kimlik numarası, IBAN ve adres yalnızca `hr.view_employee_sensitive` izniyle
`sensitive` nesnesi içinde döner; aksi hâlde `null`.

---

## 9. Raporlar — `/api/v1/reporting/`

| Uç nokta | Yöntem | Açıklama |
|---|---|---|
| `reports/catalog/` | GET | Erişebildiğiniz raporların listesi |
| `reports/run/{code}/` | GET | Raporu JSON olarak çalıştırır |
| `daily-sales/` | GET | Günlük satış özetleri |
| `forecasts/` | GET | Satış tahminleri |
| `runs/` | GET | Rapor koşum geçmişi |

```
GET /api/v1/reporting/reports/run/sarap-karlilik/?start=2026-08-01&end=2026-08-18
```

```json
{
  "title": "Şarap Kârlılığı",
  "subtitle": "Dönem: 01.08.2026 – 18.08.2026",
  "columns": ["Üretici", "Şarap", "Rekolte", "Şişe", "Kadeh", "Ciro", "Maliyet", "Kâr", "Marj %"],
  "rows": [["Anadolu Terroir", "Öküzgözü Rezerv", "2020", "12", "0", "14400.00", "3600.00", "10800.00", "75.00"]],
  "totals": ["TOPLAM", "", "", "12", "0", "14400.00", "3600.00", "10800.00", ""],
  "row_count": 1
}
```

PDF/Excel/CSV indirmek için arayüz uç noktası kullanılır:

```
/rapor/{kod}/disa-aktar/{pdf|xlsx|csv}/?start=...&end=...
```

---

## 10. Yapay zekâ — `/api/v1/ai/`

| Uç nokta | Yöntem | Açıklama |
|---|---|---|
| `providers/` | GET | Sağlayıcı yapılandırması (**anahtar döndürmez**) |
| `providers/health/` | GET | Canlı sağlık kontrolü |
| `providers/{code}/models/` | GET | Sağlayıcının **canlı** model listesi |
| `ask/` | POST | Soru sorar (maskeleme + yedekleme zinciri) |
| `pairing/` | POST | Yemek–şarap eşleştirme önerisi |
| `conversations/` | GET, POST | Sohbet oturumları |
| `calls/` | GET | Çağrı kayıtları (salt okunur) |
| `suggestions/` | GET | Öneri kuyruğu |
| `suggestions/{id}/approve/` | POST | Öneriyi onaylar |
| `suggestions/{id}/reject/` | POST | Öneriyi reddeder |
| `pricing/` | GET, POST | Model fiyatlandırması |
| `budgets/` | GET | Aylık bütçe durumu |
| `feedback/` | GET, POST | Yanıt kalitesi geri bildirimi |

### Soru sorma

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ai/ask/ \
     -H "Authorization: Token ..." -H "Content-Type: application/json" \
     -d '{"prompt": "Kuzu tandır için şarap öner", "feature": "pairing"}'
```

```json
{
  "text": "…",
  "provider": "lmstudio",
  "model": "google/gemma-4-12b-qat",
  "is_mock": false,
  "used_fallback": false,
  "attempted_providers": ["lmstudio"],
  "privacy_notice": "Yerel sağlayıcı kullanıldı; veri işletme dışına çıkmadı.",
  "sent_to_provider": null,
  "usage": { "prompt_tokens": 149, "completion_tokens": 88, "total_tokens": 237 },
  "latency_ms": 4821,
  "call_log_id": 512
}
```

Bulut sağlayıcı kullanıldığında `sent_to_provider`, **maskelenmiş** metni
içerir — kullanıcı ne gönderildiğini görebilir.

**Yetkiler:** bulut için `aiservices.can_use_cloud_ai` · öneri uygulamak için
`aiservices.can_apply_ai_suggestion`

### Hatalar

| Kod | Anlam |
|---|---|
| `403` | Bulut yapay zekâ yetkisi yok |
| `409` | Kavda stokta şarap yok (eşleştirme) |
| `503` | Hiçbir sağlayıcı yanıt vermedi |

---

## 11. Hata biçimi

```json
{ "detail": "Ödeme tutarı (1500.00) kalan borçtan (1100.00) büyük olamaz." }
```

| Kod | Anlam |
|---|---|
| `400` | İş kuralı ihlali (mesaj Türkçe ve açıklayıcıdır) |
| `401` | Kimlik doğrulanmadı |
| `403` | Yetki yok — **denetim kaydına yazılır** |
| `404` | Kayıt yok |
| `409` | Çakışma (masa, tekillik) |
| `202` | Onay talebi oluşturuldu, işlem uygulanmadı |
| `503` | Dış servis erişilemez |

---

## 12. Tam uç nokta listesi

Çalışan sistemde:

```
GET /api/v1/
```

veya:

```bash
.venv\Scripts\python.exe manage.py show_urls 2>NUL || \
.venv\Scripts\python.exe -c "import os,sys;sys.path.insert(0,'src');os.environ.setdefault('DJANGO_SETTINGS_MODULE','winehouse.settings.dev');import django;django.setup();from django.urls import get_resolver;print(len(get_resolver().reverse_dict))"
```
