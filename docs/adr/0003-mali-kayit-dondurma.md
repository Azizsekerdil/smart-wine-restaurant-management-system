# ADR-0003: Mali kayıtların dondurulması ve silinmemesi

**Durum:** Kabul edildi · **Tarih:** 18.08.2026

## Bağlam

Restoran sistemleri mali kayıt tutar. İki risk vardır:

1. Menü fiyatı değişince geçmiş adisyonların tutarı da değişirse muhasebe bozulur.
2. Personel, kasa açığını gizlemek için kayıt silebilir.

## Karar

1. **Fiyat dondurma:** `OrderLine`, oluşturulurken `unit_price`, `tax_rate`,
   `unit_cost` ve `item_name` değerlerini menüden **kopyalar**.
2. **Silme yok:** `Order`, `OrderLine`, `Payment`, `StockMovement`,
   `LoyaltyTransaction` ve `AuditLog` fiziksel olarak silinmez.
3. **Ters kayıt:** Düzeltme, ters yönlü yeni bir kayıtla yapılır.
4. **Gün sonu dondurma:** `close_business_day`, tüm toplamları
   `DailySalesSnapshot` içine yazar; raporlar bu tablodan okur.

## Gerekçe

- Bir yıl sonra çalıştırılan rapor aynı sonucu vermelidir.
- `StockMovement.save()` var olan kaydı güncellemeye çalışırsa `ValueError`
  fırlatır; `delete()` her zaman reddeder. Bu, uygulama katmanında bir
  değişmezdir ve testle doğrulanır.
- Stok bakiyesi her zaman hareketlerin toplamıyla denetlenebilir.

## Reddedilen alternatifler

**Menü fiyatına referansla hesaplama.** Tek doğruluk kaynağı olurdu ama geçmiş
hesapları değiştirirdi — muhasebe açısından kabul edilemez.

**Yumuşak silme (soft delete) yeterli sayılması.** `is_deleted` bayrağı listeden
gizler ama toplamları değiştirir. Mali kayıtta iptal, ayrı bir durum
(`VOID`) ve gerekçe gerektirir.

## Sonuçlar

- Veritabanı zamanla büyür; arşivleme stratejisi gerekir.
- Hatalı kayıt düzeltmesi iki kayıt üretir — kullanıcıya bu açıklanmalıdır.
- Denetim izi güçlüdür: kim, ne zaman, neyi, neden değiştirdi bilinir.
