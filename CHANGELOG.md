# Değişiklik Günlüğü

Bu projenin tüm önemli değişiklikleri bu dosyada belgelenir.

Biçim [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) temellidir ve
proje [Semantic Versioning](https://semver.org/lang/tr/) kullanır.

---

## [Yayımlanmamış] — herkese açık aday (public candidate), 2026-08-19

Bu bölüm, deponun herkese açık hâle getirilmek üzere hazırlanan sürümünde
yapılan değişiklikleri kaydeder. Sürüm numarası hâlâ 0.1.0'dır; ürün
davranışındaki değişiklikler aşağıda ayrıca belirtilmiştir.

### Güvenlik — düzeltildi

- **Zorunlu parola değişimi artık gerçekten zorlanıyor.**
  `must_change_password` bayrağı yalnızca bir uyarı mesajı üretiyordu;
  işaretlenen kullanıcı tüm ekranlara erişebiliyordu. Yeni
  `PasswordChangeRequiredMiddleware`, parola değiştirilene kadar korunan her
  ekranı, REST kaynağını ve Django yönetim panelini kapatır.
- **PIN oturumu artık yönetim yüzeyine erişemiyor.** `pin_login` belgelerinde
  "yönetim ekranlarına erişim sağlamaz" yazıyordu ama açılan oturum tam
  yetkiliydi. Yeni `PinSessionScopeMiddleware` PIN oturumunu salon/mutfak/bar
  ekranlarıyla sınırlar; yönetim için parolayla giriş gerekir.
- **Parola karması Argon2id'ye yükseltildi** (PBKDF2 yalnızca eski karmaları
  doğrulamak için listede kalır; Django ilk girişte otomatik yükseltir).
- **Dil değiştirme görünümündeki açık yönlendirme kapatıldı.** `Referer`
  başlığı doğrulanmadan yönlendirme hedefi yapılıyordu.
- **`create_user_with_role` artık parola politikasını uyguluyor**; zayıf parola
  sessizce kabul edilmiyor.
- **API anahtarı önizlemesi yalnızca son 4 karakteri gösteriyor**; sağlayıcı ön
  eki (`sk-ant-`, `nvapi-`) artık arayüzde görünmüyor.
- Geliştirme profilinden yanıltıcı `0.0.0.0` `ALLOWED_HOSTS` girdisi çıkarıldı.
- `except` bloğunda silinen `exc` değişkenini kapatan kırılgan lambda deseni
  iki uç noktada düzeltildi.
- Şablonda gereksiz `|safe` filtresi kaldırıldı.

### Güvenlik — bağımlılıklar

- `pypdf` 6.1.1 → 6.16.1 (71 hizmet kesintisi danışması).
- `lxml` 6.1.2'ye sabitlendi (GHSA-vfmq-68hx-4jfw, HIGH, XXE). Bunu mümkün
  kılmak için `cyclonedx-bom` geliştirme bağımlılıklarından çıkarıldı — bu
  paket `lxml < 6`'ya bağlanıyordu. SBOM üretimi artık Syft ile yapılır.
- `idna` 3.19'a sabitlendi.
- PyInstaller ve pywebview `requirements-packaging.txt` dosyasına ayrıldı:
  bu araçlar geniş ve eski bir geçişli bağımlılık ağacı getiriyor ve ürünün
  çalışma zamanında yer almıyor.

### Gizlilik

- **Müşteri listesinde telefon numarası artık maskeleniyor**; tam değer
  yalnızca yetkili rolün açtığı detay ekranında görünür.
- Örnek veri telefon numaraları **aranamaz** hâle getirildi
  (`+90 5XX XXX XX 07`). Ekran görüntüsü veya sunum paylaşıldığında gerçek bir
  aboneye ulaşmak mümkün değildir.

### Değiştirildi

- **AI ajanı yetki zarfı (`apps.hsp.authority`) kaldırıldı.** Delegasyon ve
  parasal yetki modeli kodda vardı ama hiçbir ürün akışı onu çağırmıyordu;
  Wine House'ta komut çalıştıran bir ajan yok. Karşılığı olmayan bir yetenek
  ima eden yönetim ekranı yayımlamak yerine bileşen ve testleri kaldırıldı
  (`hsp` migration 0003). Komut çalıştıran ajanlar eklenirse, zorlama
  noktasıyla *birlikte* geri getirilmelidir.
- **PDF ve sunum yazı tipi artık depoda paketli DejaVu Sans.** Önceden işletim
  sistemindeki bir yazı tipi (çoğunlukla tescilli Arial) aranıp gömülüyordu.
- Sunum çıktıları `docs/presentation/` altına `_PUBLIC` sonekiyle üretiliyor.
- `requirements*.txt` dosyaları saf ASCII yapıldı: UTF-8 Türkçe yorumlar,
  UTF-8 olmayan Windows yerel ayarlarında eski `pip` sürümlerinde
  `UnicodeDecodeError` ile kuruluma engel oluyordu.
- Test ayarlarındaki Fernet biçimli anahtar dizgesi kaldırıldı; anahtar artık
  sabit bir tohumdan türetilir (davranış aynı, depoda anahtar yok).
- Sunumdaki tüm sayılar depodan mekanik olarak ölçüldü; doğrulanamayan
  "%82 iş kuralı kapsamı" ve "31 kapatılan zafiyet" iddiaları kaldırıldı.
- Tüm kod tabanı `ruff` ve `black` denetiminden temiz geçiyor.

### Kaldırıldı (yalnızca herkese açık aday kapsamı)

- Tescilli `LICENSE` dosyası — lisans seçimi bekliyor
  (`LICENSE_DECISION_PENDING.md`).
- İç Ar-Ge çalışma belgeleri, ana yönerge (prompt) dosyaları ve iç faz /
  boşluk raporları — depo kapsamı ve kurumsal hijyen gereği. Bu belgeler
  ürünün çalışmasıyla ilgili değildir.

### Eklendi

- `SECURITY.md`, `PRIVACY.md`, `AI_TRANSPARENCY.md`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `docs/known-limitations.md`
- `sbom.spdx.json`, `sbom.cdx.json`, `PUBLIC_RELEASE_MANIFEST.json`
- `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.gitleaks.toml`
- `tests/test_bootstrap_and_session_scope.py` — 49 yeni gerileme testi
  (varsayılan kimlik bilgisi yok, zorunlu parola değişimi, PIN kapsamı,
  Argon2id, maskeleme, açık yönlendirme).

---

## [0.1.0] — 2026-08-18

İlk geliştirme sürümü. Çalışan, test edilmiş ve belgelenmiş temel sistem.

### Eklendi

**Altyapı**
- Django 5.2 tabanlı, src-layout proje düzeni; dev/prod/test ayar profilleri
- Yerel öncelikli mimari: SQLite (WAL), çevrimdışı çalışma, CDN bağımlılığı yok
- Değiştirilemez denetim kaydı (`AuditLog`) ve istek bağlamı ara katmanı
- Fernet ile hassas alan şifrelemesi ve HMAC tabanlı aranabilir özet
- Gizli değer ve kişisel veri maskeleme altyapısı
- Güvenlik odaklı Django sistem kontrolleri

**Yetkilendirme**
- 19 restoran rolü ve en az yetki ilkesine göre izin haritası
- Kritik işlemler için ikinci onay akışı (görevler ayrılığı zorunlu)
- POS için PIN girişi, hesap kilitleme, giriş denemesi kaydı

**Restoran operasyonu**
- Salon bölümü, masa planı ve masa durumları
- Rezervasyon, zaman çakışması denetimi, bekleme listesi
- Adisyon; fiyat, KDV ve maliyetin satır oluşturulurken dondurulması
- İstasyon başına hazırlık fişi (KOT) ve mutfak/bar/şarap ekranları (KDS)
- Hesap bölme (koltuk bazlı) ve adisyon birleştirme
- Çoklu ödeme yöntemi, komisyon hesabı, sandbox ödeme modu
- Gün sonu kapanışı, kasa mutabakatı ve dondurulmuş günlük özet

**Şarap kavı**
- Üretici, bölge/apelasyon, üzüm bileşimi ve rekolte künyesi
- Kav/dolap/raf/bölme yerleşimi, sıcaklık ve nem ölçümü, aralık dışı uyarısı
- Parti (lot) bazlı şişe stoğu ve FEFO çıkışı
- Şişe açma ve kadeh servisinin stoktan doğru düşmesi
- Açılmış şişe hacim takibi, gerçekleşen verim, tazelik süresi
- Coravin/koruma sistemi ayrımı
- Şarap kusuru kaydı (mantar hatası, oksidasyon, dökülme, kırılma)
- Tadım notları, uzman/müşteri puanları, içim aralığı durumu
- Yemek ve peynir eşleştirmesi, şarap uçuşu, tadım etkinliği
- Şarap kulübü ve özel kav müşterisi modelleri
- Kav değerlemesi ve mükerrer/şüpheli kayıt tespiti

**Menü ve stok**
- Menü kategorisi, ürün, reçete ve porsiyon maliyeti
- Alerjen ve beslenme etiketleri, çok dilli ad/açıklama
- Dinamik fiyatlandırma, happy hour, kampanya kuralları
- QR menü (misafir görünümü, maliyet/stok sızdırmaz)
- FIFO/FEFO stok, parti takibi, son kullanma uyarıları
- Mal kabul, stok sayımı, transfer, fire kaydı
- Tedarikçi yönetimi, satın alma talebi, teklif karşılaştırma
- Minimum seviye tabanlı sipariş önerisi

**Müşteri ve personel**
- KVKK uyumlu müşteri kaydı; amaç bazlı rıza yönetimi
- Veri taşınabilirliği (dışa aktarım) ve onaya bağlı anonimleştirme
- Sadakat programı, puan kazanımı ve kullanımı
- Kampanya tanımı ve rıza denetimli hedef kitle hesabı
- Personel kartı, vardiya, izin, performans göstergeleri
- Rol bazlı eğitim merkezi

**Raporlama**
- 13 rapor: günlük satış, ürün satışı, ödeme dağılımı, şarap kârlılığı,
  kadeh/şişe karşılaştırması, kav değerlemesi, fire analizi, stok değerlemesi,
  masa devir hızı, personel performansı, menü mühendisliği, yapay zekâ maliyeti,
  satış tahmini
- PDF / Excel / CSV dışa aktarım
- Türkçe karakter garantisi: UTF-8 BOM'lu CSV, PDF'e gömülü TrueType yazı tipi
- TR/EN sayı, para ve tarih biçimlendirmesi

**Yapay zekâ**
- Sağlayıcıdan bağımsız `AIProvider` soyutlaması
- LM Studio, Anthropic Claude, NVIDIA ve Mock adaptörleri
- Model adları koda gömülmez; her zaman sağlayıcıdan okunur
- Görev bazlı yerel model önerisi (uzmanlık uyumsuzluğunu eleyen puanlama)
- Yedekleme zinciri: yerel öncelik, bütçe engeli, sonda daima mock
- Buluta gönderim öncesi kişisel veri maskeleme ve kullanıcıya gösterme
- Zaman aşımı, yeniden deneme, üstel geri çekilme, istek iptali
- Belirteç ve maliyet takibi, aylık bütçe sınırı
- Sommelier asistanı ve yemek–şarap eşleştirmesi
- Yapay zekâ önerilerinin insan onayı olmadan uygulanmaması

**Geliştirici araçları**
- Güvenli AI Development Studio ve politika motoru
- CAIO kalite gözlem ajanı ve bulgu üretimi
- Şifreli yedekleme, SHA-256 doğrulama, onaya bağlı geri yükleme
- Saklama politikası (en az 3 yedek daima korunur)

**Arayüz**
- 72 şablon, şarap temalı tasarım sistemi
- Rol duyarlı gezinme; ortam rozetleri (geliştirme/sandbox/gizlilik)
- Açık ve koyu tema, yazdırma stilleri
- Erişilebilirlik: 44 px dokunma hedefi, odak halkası, renk+metin çift kodlama
- Bootstrap 5.3.3 ve htmx 2.0.4 yerel olarak paketlendi

**Windows**
- `INSTALL_WINE_HOUSE.ps1` kurulum sihirbazı
- `START` / `STOP` / `CHECK` / `BACKUP_WINE_HOUSE.bat` (çift tıklanır)
- 26 denetimli sistem sağlık kontrolü
- Masaüstü kısayolu oluşturma

**Kalite**
- 255 test; temel iş kurallarında %82 kapsam
- CI iş akışı (GitHub Actions)
- SBOM (CycloneDX 1.6) ve lisans denetimi

### Güvenlik

Geliştirme sırasında `pip-audit` ile tespit edilen bilinen zafiyetler kapatıldı:

- Django 5.2.6 → **5.2.16** (PYSEC-2026-2091, -2092, -2448, -2449)
- Pillow 11.3.0 → **12.3.0** (PYSEC-2026-165 ve 19 ek kayıt)
- cryptography 45.0.7 → **50.0.0** (PYSEC-2026-35, -36, -2141, -3552…3554,
  GHSA-537c-gmf6-5ccf)
- python-dotenv 1.1.1 → **1.2.2** (PYSEC-2026-2270)
- pytest 8.4.2 → **9.0.3**, black 25.1.0 → **26.5.1** (geliştirme araçları)

Yükseltme sonrası tüm testler geçmiştir.

### Bilinen sınırlamalar

Aşağıdakiler bilinçli olarak tamamlanmamıştır ve arayüzde **Planlandı** veya
**Deneysel** olarak işaretlenir:

- Canlı ödeme ve e-Fatura entegrasyonu (yalnızca adaptör arayüzü)
- Termal yazıcı sürücüsü
- Toplu e-posta/SMS gönderimi
- Kav sensör entegrasyonu
- Etiket görsel analizi uçtan uca akışı
- Çok terminalli çevrimdışı senkronizasyon
- Windows `.exe` paketi (yapılandırma hazır, üretilmedi)

Ayrıntı: [`docs/STATUS.md`](docs/STATUS.md)
