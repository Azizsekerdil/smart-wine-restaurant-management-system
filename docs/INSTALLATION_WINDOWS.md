# Windows Kurulumu

> Sürüm 0.1.0 · Windows 10/11

---

## 1. Gereksinimler

| Gereksinim | Ayrıntı |
|---|---|
| İşletim sistemi | Windows 10 (1809+) veya Windows 11 |
| Python | **3.12** önerilir (3.11 ve 3.13 de çalışır) |
| Disk | ~500 MB (bağımlılıklar dâhil) |
| Bellek | 2 GB (yerel yapay zekâ kullanılacaksa 8 GB+) |
| İnternet | **Yalnızca kurulum sırasında.** Sonrasında gerekmez. |

### Python kurulumu

Python kurulu değilse: https://www.python.org/downloads/

> ⚠️ Kurulum sırasında **"Add python.exe to PATH"** kutusunu işaretleyin.

Doğrulama:

```powershell
py -0
```

---

## 2. Kurulum

1. Proje klasörünü `D:\Wine_House` konumuna yerleştirin.
2. `INSTALL_WINE_HOUSE.ps1` dosyasına **sağ tıklayın** →
   **"PowerShell ile çalıştır"**.

Alternatif olarak PowerShell'de:

```powershell
cd D:\Wine_House
powershell -ExecutionPolicy Bypass -File INSTALL_WINE_HOUSE.ps1
```

### Kurulum adımları

| # | Adım | Açıklama |
|---|---|---|
| 1 | Python denetimi | 3.12 → 3.13 → 3.11 sırasıyla aranır |
| 2 | Sanal ortam | `.venv` klasörü oluşturulur |
| 3 | Bağımlılıklar | 27 çalışma zamanı paketi (+isteğe bağlı geliştirme araçları) |
| 4 | `.env` üretimi | Django gizli anahtarı ve şifreleme anahtarı **otomatik üretilir** |
| 5 | Veritabanı | 131 tablo oluşturulur |
| 6 | Roller | 19 rol ve izinleri tanımlanır |
| 7 | İlk yönetici | Kullanıcı adı ve parola sorulur (parola ekranda görünmez) |
| 8 | Örnek veri | İsteğe bağlı sentetik veri |

Kurulum **API anahtarı istemez**. Sistem yapay zekâ olmadan tam çalışır.

### Kurulum seçenekleri

```powershell
# Örnek veri yüklemeden
.\INSTALL_WINE_HOUSE.ps1 -SkipDemoData

# Yönetici oluşturmayı atlayarak
.\INSTALL_WINE_HOUSE.ps1 -SkipAdmin

# Belirli bir Python ile
.\INSTALL_WINE_HOUSE.ps1 -PythonPath "C:\Python312\python.exe"
```

---

## 3. Çalıştırma

| Dosya | İşlev |
|---|---|
| **START_WINE_HOUSE.bat** | Sunucuyu başlatır, tarayıcıyı açar |
| **STOP_WINE_HOUSE.bat** | Sunucuyu durdurur |
| **CHECK_WINE_HOUSE.bat** | Sistem sağlık kontrolü (26 denetim) |
| **BACKUP_WINE_HOUSE.bat** | Yedek alır ve doğrular |

> Bu `.bat` dosyaları **çift tıklanarak** çalıştırılmak üzere hazırlanmıştır.
> PowerShell penceresine yapıştırılmaları gerekmez. PowerShell mantığı ayrı
> `.ps1` dosyalarındadır (`scripts/` klasörü).

### Adresler

| Ekran | Adres |
|---|---|
| Ana panel | http://127.0.0.1:8000/ |
| Giriş | http://127.0.0.1:8000/hesap/giris/ |
| POS PIN girişi | http://127.0.0.1:8000/hesap/pin/ |
| QR menü (misafir) | http://127.0.0.1:8000/menu/qr/ |
| REST API | http://127.0.0.1:8000/api/v1/ |
| Django yönetimi | http://127.0.0.1:8000/django-admin/ |

### Başlatma seçenekleri

```powershell
# Farklı port
.\scripts\start.ps1 -Port 8080

# İşletme ağındaki diğer cihazlardan erişim
.\scripts\start.ps1 -BindHost 0.0.0.0

# Üretim ayarlarıyla (DEBUG kapalı)
.\scripts\start.ps1 -Production

# Tarayıcı açmadan
.\scripts\start.ps1 -NoBrowser
```

> `-BindHost 0.0.0.0` kullanırsanız `.env` içindeki `DJANGO_ALLOWED_HOSTS`
> değerine makinenin IP adresini eklemeyi unutmayın.

---

## 4. İlk yönetici

Kurulum sırasında oluşturulmadıysa:

```powershell
.venv\Scripts\python.exe manage.py create_admin
```

Etkileşimsiz (otomatik kurulum için):

```powershell
$env:WINEHOUSE_ADMIN_PASSWORD = "GucluBirParola.2026!"
.venv\Scripts\python.exe manage.py create_admin --username yonetici --non-interactive
```

> Parola **komut satırı argümanı olarak alınmaz** — komut geçmişine ve işlem
> listesine düşmesini önlemek için ortam değişkeninden okunur.

Rol seçenekleri: `--role sysadmin` (varsayılan), `owner`, `general_manager` …

---

## 5. Masaüstü kısayolu

Kurulum sırasında sorulur. Sonradan:

```powershell
.\scripts\create_shortcut.ps1
```

---

## 6. Zamanlanmış yedekleme

Windows Görev Zamanlayıcı → **Temel Görev Oluştur**

```
Ad        : Wine House Günlük Yedek
Tetikleyici: Günlük · 03:00
Eylem     : Program başlat
Program   : powershell.exe
Bağımsız  : -NoProfile -ExecutionPolicy Bypass -File "D:\Wine_House\scripts\backup.ps1"
Başlangıç : D:\Wine_House
```

Ayrıntı: [`BACKUP_RESTORE.md`](BACKUP_RESTORE.md)

---

## 7. Yapay zekâ (isteğe bağlı)

Sistem yapay zekâ olmadan tam çalışır. Etkinleştirmek isterseniz:

### LM Studio (önerilen — yerel, ücretsiz, gizli)

1. https://lmstudio.ai → indir ve kur
2. Bir *instruct* modeli indirin (Gemma veya Llama sınıfı)
3. **Developer** → **Start Server**
4. `CHECK_WINE_HOUSE.bat` ile doğrulayın

### Bulut sağlayıcı

`.env` dosyasına anahtarı ekleyin:

```
ANTHROPIC_API_KEY=...
NVIDIA_API_KEY=...
```

veya kalıcı ortam değişkeni olarak:

```powershell
[Environment]::SetEnvironmentVariable("NVIDIA_API_KEY", "<anahtar>", "User")
```

Ayrıntı: [`AI_CONFIGURATION.md`](AI_CONFIGURATION.md)

---

## 8. Sorun giderme

| Belirti | Neden | Çözüm |
|---|---|---|
| "Uyumlu Python bulunamadı" | Python yok veya sürüm uyumsuz | Python 3.12 kurun, PATH'e ekleyin |
| "bu sistemde betik çalıştırma devre dışı" | PowerShell yürütme politikası | `powershell -ExecutionPolicy Bypass -File ...` kullanın |
| "8000 portu zaten kullanımda" | Sunucu zaten çalışıyor veya başka uygulama | `STOP_WINE_HOUSE.bat` veya `-Port 8080` |
| Bağımlılık kurulumu başarısız | İnternet veya güvenlik duvarı | Bağlantıyı kontrol edin, kurulumu tekrar çalıştırın |
| "Sanal ortam bulunamadı" | Kurulum tamamlanmadı | `INSTALL_WINE_HOUSE.ps1` çalıştırın |
| PDF'te Türkçe karakter bozuk | TrueType yazı tipi bulunamadı | Arial/Tahoma/DejaVu Sans kurulu olmalı |
| Türkçe karakterler konsolda bozuk | Kod sayfası | `.bat` dosyaları `chcp 65001` yapar; PowerShell 7 önerilir |
| Giriş yapılamıyor | Hesap kilitli | 15 dakika bekleyin veya `manage.py create_admin` ile yeni hesap |

### Tanılama

```powershell
CHECK_WINE_HOUSE.bat
```

Bu betik 26 denetim yapar ve hiçbir gizli değer yazdırmaz.

---

## 9. Güncelleme

```powershell
# 1. Önce yedek alın
BACKUP_WINE_HOUSE.bat

# 2. Yeni sürümü alın
git pull

# 3. Bağımlılıkları güncelleyin
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 4. Veritabanı şemasını güncelleyin
.venv\Scripts\python.exe manage.py migrate

# 5. Rolleri eşitleyin (yeni izinler için)
.venv\Scripts\python.exe manage.py sync_roles

# 6. Doğrulayın
CHECK_WINE_HOUSE.bat
```

---

## 10. Kaldırma

1. `STOP_WINE_HOUSE.bat` ile sunucuyu durdurun
2. **Yedek alın** — veritabanı silinecektir
3. `D:\Wine_House` klasörünü silin
4. Masaüstü kısayolunu silin

> `backups/` klasörünü ayrı bir yere kopyalamadan silmeyin.
