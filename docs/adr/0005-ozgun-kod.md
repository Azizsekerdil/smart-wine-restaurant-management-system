# ADR-0005: Üçüncü taraf projelerden kod alınmaması

**Durum:** Kabul edildi · **Tarih:** 18.08.2026

## Bağlam

Yönerge, GitHub'daki lisansı uygun örneklerden yararlanmayı öneriyordu.
İncelenen 7 referans deponun tamamı MIT lisanslıydı; yani kod almak hukuken
mümkündü.

## Karar

**Hiçbir üçüncü taraf projeden kod alınmadı.** Tüm kaynak kod bu proje için
özgün olarak yazıldı.

## Gerekçe

1. **Mimari uyuşmazlık.** İncelenen projelerin hiçbiri rol tabanlı erişim,
   ikinci onay akışı, değiştirilemez denetim kaydı veya şifreli kişisel veri
   gibi bu projenin temel gereksinimlerini karşılamıyordu.
2. **Alan uyuşmazlığı.** Projenin ayırt edici çekirdeği — kadeh/şişe ikili
   stoğu, açılmış şişe hacim takibi, verim analizi, içim aralığı, kav sıcaklık
   takibi — hiçbir referansta yoktu.
3. **Bakım yükü.** Alınan kod, kökenine bağlı bir bakım ve atıf yükümlülüğü
   doğurur.
4. **Test edilebilirlik.** Kendi yazdığımız kod, kendi test paketimizle %82
   kapsama ulaştı.

Referans depolar yalnızca **ürün araştırması** düzeyinde kullanıldı: hangi
modüller bekleniyor, hangi ekranlar var, hangi alanlar tutuluyor.

## GPL/AGPL projeler

Wine Cellar, SaleFlex.PyPOS ve RestaurantManagementSystem gibi kopyaleft
lisanslı projelerin **yalnızca README'leri** okundu. Kaynak kodları açılmadı,
çevrilmedi, yeniden adlandırılmadı ve yapısal olarak taklit edilmedi.

## Sonuçlar

- Telif atfı yükümlülüğü yalnızca *bağımlılıklar* düzeyindedir.
- `THIRD_PARTY_NOTICES.md` yalnızca pip paketlerini ve iki ön uç kütüphanesini
  listeler.
- Ticari kapalı kaynak dağıtımın önünde hukuki engel yoktur.
- Geliştirme süresi arttı; buna karşılık kod tabanı tutarlı ve tam test edilmiş.
