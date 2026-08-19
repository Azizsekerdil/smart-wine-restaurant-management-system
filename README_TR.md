# 🍷 Wine House

**Akıllı Şarap Restoranı Yönetim Sistemi** — *Smart Wine Restaurant Management System*

Şarap odaklı restoranlar için yerel çalışan, çevrimdışı dayanıklı, rol tabanlı
bir işletme yönetim sistemi. Salon operasyonundan dijital şarap kavına, stok ve
maliyetten yapay zekâ destekli sommelier asistanına kadar tek bir uygulamada.

| | |
|---|---|
| **Sürüm** | 0.1.0 |
| **Durum** | Geliştirme sürümü — üretim öncesi |
| **Platform** | Windows (yerel kurulum) |
| **Diller** | Türkçe · English |
| **Lisans** | Tescilli (Proprietary) — bkz. [`LICENSE`](LICENSE) |

📖 Bu belge Türkçe sürümdür · **[English documentation](README_EN.md)**

---

## Hızlı başlangıç (Windows)

```powershell
# 1. Kurulum (bir kez)
powershell -ExecutionPolicy Bypass -File INSTALL_WINE_HOUSE.ps1
```

```
2. START_WINE_HOUSE.bat dosyasına çift tıklayın
3. Tarayıcı açılır: http://127.0.0.1:8000/
```

Ayrıntılı yönerge: [`docs/INSTALLATION_WINDOWS.md`](docs/INSTALLATION_WINDOWS.md)

---

## Ne yapar?

### Salon operasyonu
Masa planı ve durumları · rezervasyon ve çakışma denetimi · bekleme listesi ·
adisyon · mutfak/bar/şarap ekranları (KDS) · hazırlık fişi (KOT) · hesap bölme
ve birleştirme · çoklu ödeme · gün sonu kapanışı ve kasa mutabakatı

### Dijital şarap kavı
Üretici, apelasyon, üzüm bileşimi ve rekolte künyesi · kav/dolap/raf yerleşimi ·
sıcaklık ve nem takibi · parti (lot) bazlı şişe stoğu · **kadeh satışının açılmış
şişeden doğru düşmesi** · gerçekleşen verim ve dökülme analizi · Coravin/koruma
sistemi ayrımı · mantar hatası ve oksidasyon kaydı · tadım notları · içim aralığı
uyarıları · yemek–şarap eşleştirmesi · kav değerlemesi · mükerrer kayıt tespiti

### Menü, stok ve maliyet
Reçete ve porsiyon maliyeti · alerjen ve beslenme etiketleri · dinamik
fiyatlandırma ve happy hour · menü mühendisliği (Yıldız/At/Bilmece/Köpek) ·
FIFO/FEFO stok · son kullanma uyarıları · fire ve zayi analizi · tedarikçi,
satın alma ve teklif karşılaştırma

### Yapay zekâ (sağlayıcıdan bağımsız)
LM Studio (yerel) · Anthropic Claude · NVIDIA · Mock (çevrimdışı test)
Sommelier asistanı · yemek–şarap eşleştirme · doğal dille rapor sorgulama ·
gün sonu yönetici özeti · maliyet ve belirteç takibi

> Yapay zekâ **kapalıyken de** tüm temel restoran işlevleri tam çalışır.

### Güvenlik ve uyum
19 rol · en az yetki ilkesi · kritik işlemlerde ikinci onay · değiştirilemez
denetim kaydı · hassas alanların şifrelenmesi · KVKK/GDPR rıza, veri
taşınabilirliği ve silme · buluta gönderimden önce kişisel veri maskeleme ·
şifreli yedek ve doğrulamalı geri yükleme

---

## Öne çıkan tasarım kararları

| Karar | Gerekçe |
|---|---|
| **Yerel öncelikli (local-first)** | İnternet kesildiğinde restoran çalışmaya devam eder. Uygulama ve veritabanı aynı makinededir. |
| **Yapay zekâ isteğe bağlı** | Sistem yapay zekâ olmadan tam işlevseldir; AI yalnızca öneri üretir, veritabanını değiştirmez. |
| **Yerel model önceliği** | Müşteri verisi varsayılan olarak işletme dışına çıkmaz. Buluta gitmesi gerekirse kişisel veriler maskelenir ve kullanıcıya *tam olarak ne gönderildiği* gösterilir. |
| **Mali kayıtlar dondurulur** | Adisyon satırının fiyatı kaydedildiği anda kopyalanır; menü fiyatı sonradan değişse bile geçmiş hesap değişmez. |
| **Silme yerine iz bırakma** | Sipariş, ödeme, stok hareketi ve denetim kaydı fiziksel olarak silinmez. Düzeltme, ters kayıtla yapılır. |
| **Ödeme sandbox** | Gerçek ödeme ve e-Fatura entegrasyonu yalnızca adaptör arayüzü olarak hazırdır; canlı mod açık kullanıcı onayı gerektirir. |

---

## Proje durumu

| Alan | Durum |
|---|---|
| Testler | 255 test geçiyor |
| Kapsam (temel iş kuralları) | %82 |
| Bilinen zafiyet | Yok (`pip-audit` temiz) |
| Statik güvenlik analizi | 0 yüksek, 1 orta (bilinçli), 28 düşük |
| Çalışma zamanı bağımlılıkları | 27 paket, tamamı izin verici lisanslı |

Hangi özelliğin hazır, deneysel veya planlandığını görmek için uygulamada
**Özellik Durumu** ekranını açın veya [`docs/STATUS.md`](docs/STATUS.md) dosyasını
okuyun.

---

## Belgeler

| Belge | İçerik |
|---|---|
| [`README_TR.md`](README_TR.md) | Türkçe genel bakış |
| [`README_EN.md`](README_EN.md) | English overview |
| [`KULLANIM_KILAVUZU_TR.md`](KULLANIM_KILAVUZU_TR.md) | Rol bazlı kullanım kılavuzu |
| [`USER_GUIDE_EN.md`](USER_GUIDE_EN.md) | Role-based user guide |
| [`docs/INSTALLATION_WINDOWS.md`](docs/INSTALLATION_WINDOWS.md) | Windows kurulumu ve sorun giderme |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Mimari, modüller, veri akışı |
| [`docs/API.md`](docs/API.md) | REST API başvurusu |
| [`docs/AI_CONFIGURATION.md`](docs/AI_CONFIGURATION.md) | Yapay zekâ sağlayıcı yapılandırması |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Güvenlik modeli ve tehdit değerlendirmesi |
| [`docs/PRIVACY.md`](docs/PRIVACY.md) | KVKK/GDPR uyumu ve veri işleme |
| [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md) | Yedekleme ve geri yükleme |
| [`docs/LICENSE_AUDIT.md`](docs/LICENSE_AUDIT.md) | Lisans denetimi ve kod kökeni |
| [`docs/NVIDIA_MODEL_EVALUATION.md`](docs/NVIDIA_MODEL_EVALUATION.md) | NVIDIA model değerlendirmesi |
| [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) | Test raporu ve bilinen sorunlar |
| [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) | Sürüm öncesi denetim listesi |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Mimari kararlar (ADR) |
| [`CHANGELOG.md`](CHANGELOG.md) | Sürüm geçmişi |

---

## Sorumlu kullanım

Bu sistem alkollü içecek satışı yapan işletmeler içindir.

- Alkollü içecekler **18 yaşından küçüklere satılamaz**.
- Yapay zekâ önerileri **tıbbi veya sağlık tavsiyesi değildir**; sistem hiçbir
  koşulda sağlık iddiası üretmez.
- Alerjen bilgisi işletme beyanına dayanır ve mutfak kontrolünün yerine geçmez.
- Aşırı alkol tüketimi zararlıdır. Araç kullanacak misafirlere alkol
  önerilmemelidir.

---

*Wine House · Aziz Şekerdil · 2026*
