# Yedekleme ve Geri Yükleme

> Sürüm 0.1.0

---

## 1. Neden önemli

Restoranın tüm mali geçmişi, müşteri verisi ve kav envanteri tek bir SQLite
dosyasındadır. Disk arızası veya fidye yazılımı, işletmenin tüm kaydını yok
edebilir. Bu modül bunu önlemek içindir.

**Altın kural:** Yedek, *geri yüklendiği doğrulanana kadar* yedek değildir.
Bu yüzden her yedek alındıktan sonra otomatik doğrulanır ve geri yükleme
tatbikatı ayrı bir test veritabanına yapılabilir.

---

## 2. Yedek nasıl alınır

### 2.1 Çift tıkla

```
BACKUP_WINE_HOUSE.bat
```

### 2.2 Arayüzden

```
Yedekleme → "Şimdi yedek al"
```

### 2.3 Komut satırından

```bash
.venv\Scripts\python.exe manage.py backup_now --apply-retention
```

Seçenekler: `--destination <klasör>` · `--no-encrypt` · `--no-verify`

### 2.4 Zamanlanmış (Windows Görev Zamanlayıcı)

```
Program  : powershell.exe
Argüman  : -NoProfile -ExecutionPolicy Bypass -File "D:\Wine_House\scripts\backup.ps1"
Başlangıç: D:\Wine_House
```

Önerilen sıklık: **günlük, servis kapanışından sonra** (ör. 03:00).

---

## 3. Yedeğin içeriği

Yedek bir ZIP arşividir (`.zip` veya şifreliyse `.zip.enc`):

| Dosya | İçerik |
|---|---|
| `manifest.json` | Sürüm, tarih, veritabanı motoru, tablo kayıt sayıları, alan kişi |
| `data.json` | Tüm uygulama verisi (`dumpdata`, doğal anahtarlı) |
| `database.sqlite3` | SQLite kullanılıyorsa ham veritabanı kopyası |

**Tutarlılık:** SQLite kopyası alınmadan önce `PRAGMA wal_checkpoint(TRUNCATE)`
çalıştırılır; WAL dosyasındaki bekleyen yazımlar ana dosyaya işlenir.

**Dışarıda bırakılanlar:** `contenttypes`, `auth.permission` ve `sessions`
tabloları — bunlar migration ile yeniden üretilir.

---

## 4. Şifreleme

Varsayılan olarak **açıktır** (`WINEHOUSE_BACKUP_ENCRYPTION=True`).

- Yöntem: Fernet (AES-128-CBC + HMAC-SHA256)
- Anahtar: `WINEHOUSE_FIELD_ENCRYPTION_KEY`

> ⚠️ **Kritik:** Yedek, alındığı anahtarla açılır. Anahtarı kaybederseniz
> yedekler kullanılamaz hâle gelir. `WINEHOUSE_FIELD_ENCRYPTION_KEY` değerini
> **yedeklerden ayrı, güvenli bir yerde** saklayın (parola yöneticisi, kasa).

Anahtar tanımlı değilken şifreli yedek istenirse işlem **açık hatayla** durur;
sessizce şifresiz yedek alınmaz.

---

## 5. Doğrulama

Her yedek alındıktan sonra otomatik doğrulanır. El ile:

```
Yedekleme → ilgili satır → "Doğrula"
```

Denetimler:

1. Dosya mevcut mu?
2. SHA-256 özeti kayıtla eşleşiyor mu?
3. Arşiv açılabiliyor mu?
4. `manifest.json` ve `data.json` var mı ve geçerli JSON mu?

Herhangi biri başarısızsa yedek **CORRUPT** işaretlenir ve geri yükleme
reddedilir.

---

## 6. Geri yükleme

Geri yükleme **kritik işlemdir** ve şu koruma katmanlarına sahiptir:

```
1. İkinci onay zorunlu (ApprovalRequest)
2. Yedek önce doğrulanır — bozuksa işlem yapılmaz
3. Canlı veritabanına yüklemeden önce OTOMATİK güvenlik yedeği alınır
4. Varsayılan hedef TEST veritabanıdır
```

### 6.1 Adımlar

```
Yedekleme → "Geri yükle"
  → Yedek seç
  → Hedef seç (Test veritabanı / Canlı veritabanı)
  → Gerekçe yaz
  → "Onay talebi oluştur"

Başka bir yetkili → Onay kuyruğu → Onayla
```

Onaydan sonra işlem uygulanır.

### 6.2 Hedefler

| Hedef | Davranış |
|---|---|
| **Test veritabanı** (varsayılan) | Veri ayrı bir dosyaya çıkarılır; canlı veritabanı **değişmez**. Tatbikat için. |
| **Canlı veritabanı** | Güvenlik yedeği alınır, sonra veri yüklenir. |

### 6.3 Geri yükleme tatbikatı

Yedeklerinizin gerçekten çalıştığını **düzenli olarak** sınayın:

1. Yedekleme → Geri yükle → Test veritabanını seç
2. Onaylat ve çalıştır
3. `verification_report` içindeki `expected_counts` ile üretimdeki kayıt
   sayılarını karşılaştır

Otomatik test karşılığı:
`tests/test_reports_backup_i18n.py::test_onayli_geri_yukleme_test_veritabanina_yapilir`

---

## 7. Saklama politikası

```
WINEHOUSE_BACKUP_RETENTION_DAYS=30
```

Süresi dolan yedek dosyaları silinir, **ancak en az 3 yedek her zaman
korunur**. Bu alt sınır, yanlış yapılandırılmış bir politikanın tüm yedekleri
silmesini önler.

Kayıt (metadata) silinmez; yalnızca dosya kaldırılır ve nota düşülür.

---

## 8. Nereye yedeklemeli

| Hedef | Değerlendirme |
|---|---|
| Aynı disk (varsayılan `backups/`) | ❌ Disk arızasında birlikte kaybolur |
| Farklı fiziksel disk | ✅ İyi |
| Ağ paylaşımı / NAS | ✅ İyi |
| USB bellek (dönüşümlü) | ✅ İyi — fidye yazılımına karşı çevrimdışı kopya |
| Bulut depolama | ⚠️ Şifreli yedek zorunlu; KVKK yurt dışı aktarım kuralı |

**Önerilen: 3-2-1 kuralı** — 3 kopya, 2 farklı ortam, 1 tanesi işletme dışında.

```powershell
# Ağ paylaşımına yedek
.\scripts\backup.ps1 -Destination "\\NAS\yedekler\winehouse"
```

---

## 9. Felaket kurtarma senaryosu

Makine tamamen kaybedildi:

1. Yeni makineye Python 3.12 kurun
2. Depoyu kopyalayın, `INSTALL_WINE_HOUSE.ps1` çalıştırın (örnek veri **yüklemeyin**)
3. `.env` içine **eski** `WINEHOUSE_FIELD_ENCRYPTION_KEY` değerini yazın
4. Yedek dosyasını `backups/` klasörüne koyun
5. Uygulamayı başlatın → Yedekleme ekranı → yedeği doğrulayın
6. Geri yükle → Canlı veritabanı → onaylatın

> 3. adım atlanırsa şifreli alanlar (telefon, IBAN) çözülemez.

---

## 10. Sorun giderme

| Belirti | Neden | Çözüm |
|---|---|---|
| "Yedek çözülemedi" | Şifreleme anahtarı farklı | Yedeğin alındığı anahtarı `.env` içine koyun |
| "Bütünlük hatası" | Dosya bozulmuş | Başka bir yedeği deneyin; disk sağlığını kontrol edin |
| "ENCRYPTION_KEY tanımlı değil" | Anahtar yok | Anahtar üretin veya `--no-encrypt` kullanın |
| "ikinci onay gerektirir" | Onay yok | Onay kuyruğundan başka bir yetkiliye onaylatın |
| Yedek çok büyük | Medya dosyaları | `media/` klasörünü ayrı yedekleyin |
