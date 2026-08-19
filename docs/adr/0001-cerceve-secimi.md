# ADR-0001: Web çerçevesi olarak Django

**Durum:** Kabul edildi · **Tarih:** 18.08.2026

## Bağlam

Sistem şunlara ihtiyaç duyuyor: kimlik doğrulama, rol/izin sistemi, yönetim
paneli, ORM ve migration, oturum yönetimi, CSRF koruması, çok dillilik, şablon
motoru, dosya yükleme ve REST API.

## Karar

**Django 5.2** + Django REST Framework kullanılacak.

## Gerekçe

Yukarıdaki listenin **tamamı Django çekirdeğinde** vardır. Özellikle:

- `django.contrib.auth` — kullanıcı, grup, izin sistemi hazır. 19 rolü Django
  `Group` olarak tanımlamak, kendi izin sistemimizi yazmaktan hem daha az kod
  hem daha az güvenlik riski demek.
- Migration sistemi — 131 tablo ve ilişkileri için olgun bir şema evrimi aracı.
- `django.contrib.admin` — sistem yöneticisi için sıfır kodla veri düzenleme.
- i18n çerçevesi — TR/EN gereksinimi için hazır altyapı.

Django'nun zayıf yanı asenkron başarımdır. Ancak tek işletmelik bir restoranda
eşzamanlı kullanıcı sayısı **onlarla** ifade edilir; bu ölçekte senkron model
fazlasıyla yeterlidir. ASGI yapılandırması ileride WebSocket gerekirse diye
hazır bırakılmıştır.

## Reddedilen alternatifler

**FastAPI + SQLAlchemy + Alembic**
Daha hızlı asenkron I/O sunar, ancak auth, izin, admin, i18n ve şablon
katmanlarının her biri ayrıca seçilip entegre edilmelidir. Bu, daha fazla
bağımlılık, daha fazla özel kod ve daha geniş güvenlik yüzeyi anlamına gelir.
Kazanılan başarım bu ölçekte kullanılmayacaktır.

**Flask**
Çok fazla parça el ile birleştirilmeli. Django ile aynı sonuca ulaşmak için
harcanacak emek, iş mantığından çalınırdı.

## Sonuçlar

- Senkron istek modeli — uzun süren yapay zekâ çağrıları isteği bloklar.
  Bu nedenle zaman aşımı ve iptal mekanizması zorunlu hâle geldi.
- Django ORM'e bağımlılık — veri erişimi Django dışına taşınamaz.
- Django'nun sürüm yaşam döngüsü takip edilmeli (LTS güncellemeleri).
