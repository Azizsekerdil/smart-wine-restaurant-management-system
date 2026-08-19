# Mimari

> Sürüm 0.1.0 · Son güncelleme: 18.08.2026

---

## 1. Tasarım ilkeleri

| İlke | Ne anlama geliyor | Nasıl uygulandı |
|---|---|---|
| **Yerel öncelikli** | İnternet kesildiğinde restoran çalışmaya devam eder | Uygulama + veritabanı aynı makinede; hiçbir temel işlev ağ çağrısına bağlı değil |
| **Güvenli varsayılan** | Tehlikeli özellikler kapalı doğar | AI Development Studio kapalı, ödeme sandbox, gizlilik modu açık |
| **İzlenebilirlik** | Kim ne zaman ne yaptı, geriye dönük olarak bilinir | Değiştirilemez `AuditLog`; mali kayıtlar silinmez, ters kayıtla düzeltilir |
| **Mali dondurma** | Geçmiş hesap sonradan değişmez | Adisyon satırında fiyat, KDV ve ürün adı kaydedildiği anda kopyalanır |
| **Yapay zekâ yardımcıdır, yetkili değildir** | AI veri değiştirmez | Her öneri `AISuggestion` olarak kaydedilir ve insan onayı bekler |
| **En az yetki** | Kullanıcı yalnızca görevini görür | 19 rol, izin desenleriyle tanımlı; denetçi rolünde hiç yazma izni yok |

---

## 2. Teknoloji seçimi

### 2.1 Neden Django (FastAPI değil)?

Bu karar [ADR-0001](adr/0001-cerceve-secimi.md) içinde ayrıntılıdır. Özet:

Gereksinim listesi **kimlik doğrulama, rol/izin sistemi, yönetim paneli, ORM +
migration, oturum yönetimi, CSRF koruması, çok dillilik ve şablon motoru**
içeriyor. Django bunların tamamını çekirdekte sunar. FastAPI ile aynı sonuca
ulaşmak için bu katmanların her biri ayrıca seçilip entegre edilmeliydi — daha
fazla bağımlılık, daha fazla özel kod, daha fazla güvenlik yüzeyi.

Django'nun eksiği asenkron başarımdır; ancak tek işletmelik bir restoran
sisteminde eşzamanlı kullanıcı sayısı onlarla ifade edilir. Bu ölçekte Django'nun
senkron modeli fazlasıyla yeterlidir. REST API ihtiyacı Django REST Framework
ile karşılanır.

### 2.2 Yığın

| Katman | Seçim | Lisans |
|---|---|---|
| Çatı | Django 5.2 | BSD-3-Clause |
| REST API | Django REST Framework 3.16 | BSD |
| Veritabanı (varsayılan) | SQLite (WAL modu) | Kamu malı |
| Veritabanı (çok kullanıcılı) | PostgreSQL (isteğe bağlı) | PostgreSQL lisansı |
| Arayüz | Django şablonları + Bootstrap 5.3 + HTMX 2.0 | MIT / BSD-2 |
| HTTP istemcisi | httpx | BSD-3-Clause |
| Şifreleme | cryptography (Fernet) | Apache-2.0 / BSD-3 |
| PDF | ReportLab | BSD |
| Excel | openpyxl | MIT |
| Test | pytest + pytest-django | MIT |

### 2.3 Python sürümü

Hedef: **Python 3.11 – 3.13**. Django 5.2 bu aralığı destekler.

> **Not:** Yönergede Python 3.12 istenmişti. Geliştirme makinesinde 3.12 kurulu
> değildi (3.11.9 ve 3.14.0 mevcuttu). Django 5.2 henüz 3.14'ü desteklemediği
> için **3.11.9** kullanıldı. Kod 3.12 ile de çalışır; kurulum betiği önce 3.12,
> sonra 3.13, sonra 3.11 arar. Ayrıntı: [ADR-0002](adr/0002-python-surumu.md).

---

## 3. Kod düzeni

```
D:\Wine_House\
├── manage.py                  Django yönetim aracı
├── INSTALL_WINE_HOUSE.ps1     Kurulum
├── START/STOP/CHECK/BACKUP_WINE_HOUSE.bat
├── scripts/                   PowerShell mantığı + healthcheck.py
├── src/
│   ├── winehouse/             Proje yapılandırması
│   │   ├── settings/          base · dev · prod · test
│   │   ├── urls.py            Arayüz yönlendirmeleri
│   │   └── api_urls.py        REST API kökü
│   ├── apps/                  İş alanları (bounded context)
│   ├── templates/             72 HTML şablonu
│   ├── static/                CSS + yerel Bootstrap/HTMX
│   └── locale/                Çeviri dosyaları
├── tests/                     255 test
├── docs/                      Belgeler + SBOM
└── var/                       Veritabanı (sürüm denetimi dışında)
```

### 3.1 Uygulamalar

| Uygulama | Sorumluluk | Ana modeller |
|---|---|---|
| `core` | Taban modeller, denetim kaydı, güvenlik, ayarlar | `AuditLog`, `AppSetting`, `FeatureFlag` |
| `accounts` | Kullanıcı, rol, yetki, ikinci onay | `User`, `RoleProfile`, `ApprovalRequest` |
| `catalog` | Menü, kategori, reçete, alerjen, fiyat kuralı | `MenuItem`, `Recipe`, `PriceRule` |
| `cellar` | Şarap kavı, kadeh servisi, tadım, eşleştirme | `Wine`, `BottleLot`, `BottleOpening`, `PouringRecord` |
| `inventory` | Tedarikçi, stok, parti, satın alma, fire | `StockItem`, `StockLot`, `StockMovement` |
| `operations` | Masa, rezervasyon, adisyon, KDS, ödeme, gün sonu | `Order`, `OrderLine`, `PrepTicket`, `Payment` |
| `crm` | Müşteri, rıza, sadakat, kampanya | `Customer`, `ConsentRecord`, `LoyaltyAccount` |
| `hr` | Personel, vardiya, izin, performans | `Employee`, `Shift`, `PerformanceMetric` |
| `reporting` | Rapor üreteçleri, dışa aktarım, günlük özet | `DailySalesSnapshot`, `ReportRun` |
| `aiservices` | Sağlayıcı katmanı, sohbet, maliyet, öneri | `AICallLog`, `AISuggestion`, `AIBudget` |
| `devstudio` | Güvenli geliştirici stüdyosu ve politika motoru | `DevSession`, `DevAction` |
| `caio` | Kalite gözlemi ve geliştirme önerisi | `ObservationRun`, `Finding` |
| `backups` | Yedekleme, doğrulama, geri yükleme | `BackupRecord`, `RestoreRecord` |
| `training` | Rol bazlı eğitim merkezi | `TrainingModule`, `TrainingLesson` |

### 3.2 Katman kuralı

```
Görünüm (views/api)  →  Servis (services.py)  →  Model (models.py)
```

- **Görünümler** yalnızca istek/yanıt çevirisi yapar; iş kuralı içermez.
- **Servisler** iş kurallarını taşır, atomik işlem yürütür, denetim kaydı yazar.
  Bir işlem birden çok tabloyu etkiliyorsa mutlaka servistedir.
- **Modeller** veri şeklini ve *tek kayıt üzerindeki* değişmezleri korur
  (ör. denetim kaydının güncellenemezliği).

Bu ayrım sayesinde iş kuralları arayüzden bağımsız test edilebilir; testlerin
çoğu servis katmanını doğrudan çağırır.

---

## 4. Kritik veri akışları

### 4.1 Sipariş yaşam döngüsü

```
Rezervasyon ──▶ Masa açılışı ──▶ Adisyon (Order)
                                     │
                                     ├── OrderLine (fiyat DONDURULUR)
                                     │
                                     ▼
                            send_to_stations()
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              PrepTicket        PrepTicket       PrepTicket
              (mutfak)            (bar)         (şarap/somm.)
                    │                │                │
                    └────────────────┼────────────────┘
                                     ▼
                              bump_ticket() ──▶ SERVED
                                     │
                                     ▼
                            take_payment() (sandbox)
                                     │
                                     ▼
                          close_business_day()
                                     │
                                     ▼
                         DailySalesSnapshot (DONDURULUR)
```

**Neden fiyat dondurulur?** Menü fiyatı yarın değişirse dünkü adisyonun tutarı
değişmemelidir. `OrderLine`, `unit_price`, `tax_rate`, `unit_cost` ve
`item_name` alanlarını satır oluşturulurken kopyalar.

**Neden gün sonu dondurulur?** Rapor bir yıl sonra çalıştırıldığında aynı sonucu
vermelidir. `close_business_day` tüm toplamları `DailySalesSnapshot` içine yazar;
raporlar bu tablodan okur.

### 4.2 Kadeh satışının stoktan düşmesi

Bu, sistemin en ince iş kuralıdır. Şarap iki farklı birimde satılır (şişe ve
kadeh) ama stok tek birimde (şişe) tutulur.

```
pour_glass(wine, 150 ml)
   │
   ├─▶ Yeterli hacimli AÇIK şişe var mı?
   │      │
   │      ├── Evet ──▶ o şişeyi kullan
   │      │
   │      └── Hayır ─▶ open_bottle()
   │                      │
   │                      ├─▶ FEFO ile parti seç (en erken best_before)
   │                      ├─▶ BottleLot.bottles_remaining -= 1   ← STOK DÜŞER
   │                      └─▶ BottleOpening (remaining_ml = 750)
   │
   ├─▶ BottleOpening.remaining_ml -= 150
   ├─▶ PouringRecord yaz (satış / tadım / ikram / dökülme)
   └─▶ Kalan < yarım kadeh ise şişeyi FINISHED işaretle
```

**Verim takibi:** `BottleOpening.yield_percent`, servis edilen hacmin şişe
hacmine oranıdır. Teorik 5 kadeh yerine 4 kadeh çıkıyorsa fark dökülme veya
ölçüsüz servistir; `kadeh-sise-karsilastirma` raporu bunu gösterir.

**Yarış koşulu koruması:** Hem `open_bottle` hem `pour_glass`
`select_for_update()` ile satır kilidi alır. İki garson aynı anda son şişeyi
açamaz.

### 4.3 Stok çıkışı (FIFO / FEFO)

`StockItem.tracking_mode` seçime göre sıralama değişir:

- **FEFO** — `expires_on` artan (son kullanma tarihi yakın olan önce çıkar)
- **FIFO** — `received_on` artan (önce giren önce çıkar)

Her çıkış, tüketilen **her parti için ayrı** bir `StockMovement` yazar. Bakiye
her zaman hareketlerin toplamıyla doğrulanabilir. `StockMovement` güncellenemez
ve silinemez; düzeltme ters yönlü yeni hareketle yapılır.

### 4.4 Yapay zekâ isteği

```
ask(user, feature, prompt)
   │
   ├─▶ Yedekleme zinciri kur (yerel öncelik / yalnızca-yerel filtresi)
   │
   └─▶ Her sağlayıcı için sırayla:
          │
          ├─▶ Bulut mu? ──▶ Aylık bütçe aşıldı mı? ──▶ Evet: ATLA + BLOCKED kaydı
          │
          ├─▶ Gizlilik: mask_pii() ──▶ e-posta, telefon, TCKN, IBAN, kart no,
          │                            API anahtarı → maskelenir
          │
          ├─▶ provider.chat(...)
          │      ├── Başarılı ─▶ maliyet hesapla, bütçeye ekle, AICallLog yaz
          │      └── Hata ─────▶ FALLBACK kaydı, sıradaki sağlayıcı
          │
          └─▶ Zincirin sonunda daima `mock` bulunur → akış hiç çökmez
```

Kullanıcı arayüzde **sağlayıcıya fiilen gönderilen metni** görebilir.

---

## 5. Güvenlik mimarisi

### 5.1 Yetkilendirme katmanları

1. **Rol → izin** eşlemesi (`accounts/roles.py`) — Django `Group` + `Permission`
2. **Görünüm karışımı** (`AuditedPermissionMixin`) — izin/rol denetimi + reddi
   denetim kaydına yazar
3. **Salt okunur koruma** — denetçi rolü yazma HTTP yöntemi kullanamaz
4. **İkinci onay** — kritik işlemler `ApprovalRequest` üretir; talep sahibi
   kendi talebini onaylayamaz

### 5.2 Veri koruma

| Katman | Uygulama |
|---|---|
| Hassas alanlar | `EncryptedCharField` / `EncryptedTextField` — Fernet, `enc$v1$` önekli |
| Aranabilirlik | `blind_index()` — HMAC-SHA256; özetten düz metne dönülemez |
| Günlükler | `SecretMaskingFilter` — her handler'da; API anahtarları maskelenir |
| Buluta gönderim | `mask_pii()` — e-posta, telefon, TCKN, IBAN, Luhn-geçerli kart no |
| Yedekler | Fernet şifreleme + SHA-256 bütünlük özeti |

### 5.3 AI Development Studio politika motoru

Yapay zekâ **komut çalıştırmaz**; yapılandırılmış eylem önerir. Her öneri şu
sırayla denetlenir:

1. Kabuk metakarakteri (`|`, `&&`, `;`, `>`, `` ` ``) → **RED**
2. Yasak desen (force push, `rm -rf`, credential okuma, ağ dışa aktarımı) → **RED**
3. Yasak çalıştırılabilir (`powershell`, `curl`, `reg`, `format`, …) → **RED**
4. İzin listesi → salt okunur komutlar **İZİN**, yazma komutları **ONAY**
5. Listede yoksa → **RED**

Dosya yazımında ayrıca: çalışma alanı sınırı (sembolik bağlantı ve `..` kaçışı
dâhil), korumalı dosya deseni (`.env`, `*.key`, `*.sqlite3`), hassas kaynak
dosya (ek onay).

Ayrıntı: [`SECURITY.md`](SECURITY.md)

---

## 6. Çevrimdışı çalışma

| Bileşen | Çevrimdışı davranış |
|---|---|
| Uygulama sunucusu | Yerelde çalışır — etkilenmez |
| Veritabanı | Yerel SQLite — etkilenmez |
| Arayüz varlıkları | Bootstrap/HTMX depoda paketli, CDN yok — etkilenmez |
| PDF yazı tipi | İşletim sistemindeki TrueType — etkilenmez |
| Yapay zekâ (yerel) | LM Studio aynı makinede — etkilenmez |
| Yapay zekâ (bulut) | Erişilemez → zincir `mock`'a düşer, akış çökmez |
| Çok terminalli senkronizasyon | `OfflineOperation` kuyruğu — **Deneysel** |

---

## 7. Ölçeklenme yolu

Bu sürüm **tek işletme, tek makine** için tasarlanmıştır.

| Büyüme | Yapılacak |
|---|---|
| Birden çok POS terminali | `WINEHOUSE_DB_ENGINE=postgres` + sunucuyu `0.0.0.0` üzerinde çalıştır |
| Yüksek eşzamanlılık | PostgreSQL + WSGI sunucusu (waitress/gunicorn) |
| Çok şubeli işletme | Şube boyutu eklenmeli — bu sürümün kapsamı dışında |
| Gerçek zamanlı KDS | Şu an 30 sn'de bir yenileme; WebSocket'e geçilebilir (ASGI hazır) |

---

## 8. Bilinçli olarak yapılmayanlar

Bu sürümde **kasıtlı olarak** bulunmayan ve arayüzde "Planlandı" işaretli olanlar:

- **Canlı ödeme entegrasyonu** — yalnızca adaptör arayüzü. Gerçek ödeme
  altyapısı bağlamak PCI-DSS kapsamına girer ve açık kullanıcı onayı gerektirir.
- **e-Fatura / e-Arşiv** — kamu entegrasyonu. Aynı gerekçe.
- **Termal yazıcı sürücüsü** — adaptör arayüzü hazır, donanım sürücüsü yok.
- **Toplu e-posta/SMS gönderimi** — kampanya tanımı ve rıza denetimi çalışıyor;
  gönderim yok.
- **Kav sensör entegrasyonu** — ölçüm modeli hazır, el ile giriş çalışıyor;
  donanım bağlantısı yok.
- **Etiket görsel analizi** — görsel destekli model tespiti çalışıyor; uçtan uca
  etiket okuma akışı yok.

Bunların "yapılmış gibi" gösterilmemesi bilinçli bir tasarım kararıdır; her biri
`FeatureFlag` ile işaretlenir ve arayüzde rozetle görünür.
