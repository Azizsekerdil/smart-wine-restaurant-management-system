# Kullanım Kılavuzu

> Wine House 0.1.0 · Rol bazlı kullanım

Bu kılavuz göreve göre bölümlenmiştir; kendi rolünüzün bölümünü okumanız
yeterlidir. Uygulama içindeki **Eğitim Merkezi** (📘 simgesi) aynı içeriği
ekran ekran sunar.

---

## Giriş

| Yol | Adres |
|---|---|
| Parola ile giriş | `http://127.0.0.1:8000/hesap/giris/` |
| POS hızlı giriş (personel kodu + PIN) | `http://127.0.0.1:8000/hesap/pin/` |

PIN 4–8 rakamdır ve yöneticiniz tarafından tanımlanır. Beş hatalı denemeden
sonra hesap **15 dakika kilitlenir**.

**Dil değiştirme:** Sağ üstteki **TR / EN** düğmeleri. Tercihiniz hesabınıza
kaydedilir.

### Ekranın üstündeki rozetler

| Rozet | Anlamı |
|---|---|
| GELİŞTİRME MODU | Sistem test yapılandırmasında çalışıyor |
| Ödeme: Sandbox | **Gerçek para hareketi yok** |
| Gizlilik modu açık | Yapay zekâya giden veriler maskeleniyor |

---

## 🍽️ Garson

### Masa açma
**Salon → Masa planı** · Boş masaya tıklayın, misafir sayısını girin.

Masa renkleri: yeşil boş · mavi oturdu · sarı sipariş alındı · gri servis
edildi · kırmızı hesap istendi

### Sipariş girme
Adisyon ekranından ürün seçin; adet, koltuk numarası ve özel istek girin.

> **Koltuk numarasını girin.** Hesabı sonradan bölmek isterseniz bu zorunludur.

### Mutfağa gönderme
**"Mutfağa gönder"** düğmesi. Sistem yemekleri mutfağa, içecekleri bara,
şarapları sommelier ekranına otomatik yönlendirir. Gönderilmiş satır tekrar
gönderilmez.

### İndirim
İndirim yetkiniz sınırlıdır (varsayılan %5). Sınırı aşarsanız işlem
**uygulanmaz**; yöneticiye onay talebi gider. İkram (bedelsiz ürün) **her zaman**
onay gerektirir.

### Hesap bölme
Adisyon → **"Hesabı böl"** · Her koltuk için ayrı adisyon oluşur.
Kısmi ödeme alınmış adisyon bölünemez.

### Sık karşılaşılan uyarılar

| Uyarı | Anlamı |
|---|---|
| "Masada zaten açık adisyon var" | Mevcut adisyona satır ekleyin |
| "… şu anda serviste değil" | Ürün tükendi olarak işaretlenmiş |
| "İndirim yetki sınırınızı aşıyor" | Onay talebi oluşturuldu, indirim uygulanmadı |

---

## 🍷 Sommelier

### Şarap arama
**Kav → Şaraplar** · Ad, üretici, SKU veya barkodla arayın.
Filtreler: tür · kadeh satışı · kritik stok

### Şarap kartı
Künye, tadım profili (gövde/asidite/tanen/tatlılık), üzüm bileşimi, servis
sıcaklığı, dekantasyon süresi, içim aralığı, partiler, açık şişeler ve yemek
eşleştirmeleri tek ekranda.

### Şişe açma
Şarap kartı → servis yöntemi seçin → **"Şişe aç"**

| Yöntem | Tazelik süresi |
|---|---|
| Standart | 48 saat |
| Koruma sistemi (argon/vakum) | 1 hafta |
| İğne sistemi (Coravin benzeri) | 30 gün |
| Tadım | 24 saat |

Sistem **FEFO** kuralıyla en erken tüketilmesi gereken partiden düşer.

### Kadeh servisi
Şarap kartı → hacim ve tür seçin → **"Kadeh servis et"**

- Açık şişe varsa ondan düşülür
- Yoksa **otomatik yeni şişe açılır** ve stoktan 1 şişe düşer
- **Dökülme ve ikramı da kaydedin** — verim analizi buna dayanır

### Açık şişeler
**Kav → Açık şişeler** · Tazelik süresini aşan şişeler sarı işaretlenir.

**Verim** sütunu şişeden gerçekte ne kadar servis edildiğini gösterir. Teorik
5 kadeh yerine 4 çıkıyorsa dökülme veya ölçüsüz servis vardır.

### Şarap kusuru
Mantar hatası, oksidasyon, dökülme veya kırılma tespit ettiğinizde kaydedin.
Sistem stoktan düşer ve maliyeti hesaplar.

### Yapay zekâ eşleştirmesi
**Yapay Zekâ → Sommelier** · Yemeği tarif edin, öneri alın.

> Öneri yalnızca **kavda stokta olan** şaraplardan seçilir ve sizin onayınız
> olmadan eşleştirme kaydına işlenmez.

---

## 👨‍🍳 Mutfak ve Bar

**Hazırlık → Mutfak / Bar / Şarap ekranı** · Ekran 30 saniyede bir yenilenir.

| Kenarlık | Anlamı |
|---|---|
| Gri | Süre içinde |
| Sarı | Hedef sürenin %70'i geçti |
| Kırmızı | **Gecikti** |
| Yeşil | Hazır |

**Fiş ilerletme:** **"İlerlet →"** · Sırada → Hazırlanıyor → Hazır → Servis edildi

⚠️ **Alerjen uyarısı** fişte kırmızı satır olarak görünür. Bu bilgi müşteri
beyanına dayanır; şüphede kalırsanız sorumluya danışın.

---

## 💳 Kasiyer

**Ödeme alma:** Adisyon → **"Ödeme al"** → yöntem ve tutar

- Kısmi ödeme alınabilir; kalan borç görünür
- Kart ödemesinde referans zorunludur
- Tamamen ödenen adisyon otomatik kapanır, masa "temizleniyor" olur

> **Sandbox uyarısı:** Bu sürümde gerçek ödeme ağ geçidi bağlı değildir. Kayıt
> tutulur, gerçek para hareketi olmaz.

**İptal ve iade:** Yetkiniz yoksa onay talebi oluşturulur; işlem **uygulanmaz**.

---

## 📋 Rezervasyon görevlisi

**Salon → Rezervasyonlar** · Filtreler: bugün · yaklaşan · tümü

Masa atarken sistem **çakışma denetimi** yapar: aynı masa, zaman aralıkları
kesişecek biçimde iki rezervasyona verilemez. Kapasite de denetlenir.

Rezervasyondaki alerji notu mutfak fişinde görünür.

**Bekleme listesi:** Tahmini süreyi aşan kayıtlar sarı işaretlenir.

---

## 📦 Depo ve satın alma

| İş | Ekran | Not |
|---|---|---|
| Stok | Stok → Stok kalemleri | "Minimum altı" filtresi kritik kalemleri gösterir |
| Partiler / SKT | Stok → Partiler | Kırmızı: süresi geçmiş · Sarı: yaklaşıyor |
| Mal kabul | Sipariş → mal kabul → "Stoğa işle" | Reddedilen miktarı ayrı girin |
| Sayım | Sayım → "Farkları işle" | Fark stok hareketi olur ve **silinemez** |
| Fire | Stok → Fire | Maliyet otomatik hesaplanır |
| Sipariş önerileri | Stok → Sipariş önerileri | **Yalnızca öneri** — sistem sipariş oluşturmaz |

Stok çıkışı **FEFO** ile en erken tükenecek partiden yapılır.

---

## 📊 Yönetici

### Gün sonu
**Salon → Gün sonu**

> Açık adisyon varken gün kapatılamaz. Önce hepsini kapatın.

Sayılan nakdi girin; sistem beklenen nakitle karşılaştırır ve farkı gösterir.
Kapanış sonrası veriler **dondurulur** ve raporlar bu veriden okunur.

### Raporlar
**Raporlar** · 13 rapor · dönem seçin · PDF / Excel / CSV indirin.
Türkçe karakterler üç biçimde de doğru görünür.

### Onay kuyruğu
**Profil menüsü → Onay kuyruğu** · Kendi talebinizi onaylayamazsınız
(görevler ayrılığı).

### Denetim kaydı
**Profil menüsü → Denetim kaydı** · "Yalnızca başarısız" filtresi yetkisiz
erişim denemelerini gösterir.

### Kullanıcı ve rol
**Profil menüsü → Kullanıcılar / Roller** · Her rolün hangi izinlere sahip
olduğunu **Roller** ekranından görebilirsiniz.

---

## 🔐 Sistem yöneticisi

| İş | Nasıl |
|---|---|
| Sağlık kontrolü | `CHECK_WINE_HOUSE.bat` — 26 denetim, gizli değer yazdırmaz |
| Yedekleme | **Yedekleme** ekranı veya `BACKUP_WINE_HOUSE.bat` |
| Geri yükleme | Onay gerektirir; varsayılan hedef **test veritabanı** |
| Yapay zekâ ayarları | Yapay Zekâ → Sağlayıcı ayarları → "Bağlantıları sına" |
| Özellik durumu | Profil menüsü → Özellik durumu |

> ⚠️ `WINEHOUSE_FIELD_ENCRYPTION_KEY` değerini **yedeklerden ayrı** güvenli bir
> yerde saklayın. Kaybederseniz yedekler açılamaz.

> API anahtarları arayüzden **girilmez**; yalnızca `.env` dosyasında veya
> işletim sistemi ortam değişkeninde tutulur.

---

## Sorumlu servis

- Alkollü içecekler **18 yaşından küçüklere satılamaz**
- Yapay zekâ önerileri **tıbbi tavsiye değildir**
- Alerjen bilgisi işletme beyanıdır; mutfak kontrolünün yerine geçmez
- Araç kullanacak misafirlere alkol önerilmemelidir
