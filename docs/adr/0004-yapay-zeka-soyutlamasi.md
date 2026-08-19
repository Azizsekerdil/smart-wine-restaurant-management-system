# ADR-0004: Sağlayıcıdan bağımsız yapay zekâ katmanı

**Durum:** Kabul edildi · **Tarih:** 18.08.2026

## Bağlam

Sistem dört farklı yapay zekâ sağlayıcısını desteklemeli: yerel LM Studio,
Anthropic Claude, NVIDIA ve test için sahte bir sağlayıcı. Sağlayıcılar farklı
API sözleşmeleri kullanır ve model katalogları sık değişir.

Ek olarak: müşteri verisi buluta gitmemeli, maliyet kontrol edilmeli, sağlayıcı
çökünce sistem çalışmaya devam etmeli.

## Karar

1. **Soyut `AIProvider` sınıfı.** Uygulama kodu hiçbir zaman doğrudan bir
   sağlayıcıyı içe aktarmaz; `registry.get_provider()` üzerinden çalışır.
2. **Model adları koda gömülmez.** Her sağlayıcı `list_models()` uygular ve
   modeller çalışma zamanında okunur.
3. **Yedekleme zinciri.** Sağlayıcılar sırayla denenir; zincirin sonunda daima
   `mock` bulunur, böylece akış hiç çökmez.
4. **Tek kapı.** Tüm çağrılar `aiservices.services.ask()` üzerinden geçer;
   maskeleme, bütçe ve kayıt burada uygulanır.
5. **AI yazma yetkisi yok.** Öneriler `AISuggestion` olarak kaydedilir ve insan
   onayı bekler.

## Gerekçe

- **Model adı gömmek kırılgandır.** Sağlayıcılar modelleri emekliye ayırır;
  gömülü ad bir gün 404 döner. Ayrıca yönerge bunu açıkça yasakladı.
- **Tek kapı, tutarlı politika demektir.** Gizlilik maskelemesi, bütçe kontrolü
  ve maliyet kaydı tek yerde uygulanır; yeni bir özellik eklendiğinde bunları
  unutmak mümkün değildir.
- **Mock'un zincir sonunda olması**, yapay zekânın hiçbir koşulda uygulamayı
  çökertmemesini garanti eder.

## Reddedilen alternatifler

**LangChain veya benzeri bir çerçeve.** Büyük bağımlılık ağacı, hızlı değişen
API'ler ve bu proje için gereksiz soyutlama katmanları. Dört sağlayıcı için
~600 satır kendi kodumuz daha denetlenebilir.

**Tek sağlayıcıya bağlanmak.** Yönerge bunu yasakladı; ayrıca yerel model
gizlilik açısından gereklidir.

## Sonuçlar

- Yeni sağlayıcı eklemek `AIProvider` alt sınıfı + kayıt defteri girdisi demek.
- Sağlayıcıya özgü yetenekler (ör. Anthropic'in `count_tokens` ucu) soyut
  arayüzde değil, alt sınıfta bulunur.
- Testler sahte HTTP taşıyıcısıyla çalışır; hiçbir test ağ çağrısı yapmaz.
