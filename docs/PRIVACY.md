# Gizlilik ve Kişisel Verilerin Korunması

> KVKK (6698 sayılı Kanun) ve GDPR uyumu · Sürüm 0.1.0

> **Yasal uyarı:** Bu belge yazılımın *teknik yeteneklerini* açıklar. Hukuki
> danışmanlık değildir. İşletmenin veri sorumlusu olarak kendi aydınlatma
> metnini, saklama politikasını ve VERBİS kaydını oluşturması gerekir.

---

## 1. İşlenen kişisel veriler

| Veri sahibi | Veri | İşleme amacı | Hukuki dayanak | Şifreli |
|---|---|---|---|---|
| Müşteri | Ad, soyad | Rezervasyon ve servis | Sözleşmenin ifası | ❌ |
| Müşteri | Telefon, e-posta | Rezervasyon bildirimi | Sözleşmenin ifası | ✅ |
| Müşteri | Doğum günü/ayı | Özel gün kutlaması | Açık rıza | ✅ |
| Müşteri | Alerji notu | Gıda güvenliği | Hayati menfaat | ❌ |
| Müşteri | Tercih ve ziyaret geçmişi | Hizmet kişiselleştirme | Açık rıza | ❌ |
| Personel | Kimlik no, IBAN, adres | İş sözleşmesi, bordro | Kanuni yükümlülük | ✅ |
| Personel | Telefon, e-posta, acil durum | İletişim | Sözleşmenin ifası | ✅ |
| Tedarikçi yetkilisi | Telefon, e-posta, vergi no | Ticari ilişki | Sözleşmenin ifası | ✅ |
| Kullanıcı | Giriş kayıtları, IP | Güvenlik | Meşru menfaat | ❌ |

**Veri minimizasyonu örneği:** Müşterinin doğum *yılı* saklanmaz — yalnızca
gün ve ay tutulur, çünkü amaç yalnızca doğum günü kutlamasıdır.

---

## 2. Rıza yönetimi

Her amaç için **ayrı** rıza alınır (`crm.ConsentRecord`):

| Amaç | Kod |
|---|---|
| Hizmet sunumu (rezervasyon, sipariş) | `service` |
| E-posta ile pazarlama | `marketing_email` |
| SMS ile pazarlama | `marketing_sms` |
| Tercih analizi / kişiselleştirme | `profiling` |
| Yapay zekâ ile analiz | `ai_processing` |
| Fotoğraf / görüntü kullanımı | `photo` |

**Rıza geri çekilmesi:** Kayıt **silinmez**; `withdrawn_at` doldurulur. Bu,
"rıza vardı" iddiasının ispatı için gereklidir. Geri çekildikten sonra
`has_consent()` `False` döner ve kampanya hedeflemesi o müşteriyi dışlar.

**Kampanya denetimi:** `Campaign.eligible_customers()` yalnızca ilgili amaç
için geçerli rızası olan müşterileri döndürür. Rızasız müşteriye pazarlama
mesajı hedeflenemez.

---

## 3. Veri sahibi hakları

### 3.1 Erişim ve taşınabilirlik (KVKK m.11 / GDPR m.20)

```
Müşteri → Müşteri kartı → "Veriyi dışa aktar"
```

veya API:

```
GET /api/v1/crm/customers/{id}/export_data/
```

Çıktı; kimlik bilgileri, rıza geçmişi, ziyaretler, tercihler, notlar ve
sadakat hareketlerini yapılandırılmış JSON olarak içerir. İşlem
`AuditAction.EXPORT` olarak denetime yazılır.

**Yetki:** `crm.can_export_customer_data`

### 3.2 Silme hakkı (KVKK m.7 / GDPR m.17)

Silme talebi `DataErasureRequest` olarak kaydedilir ve **ikinci onay**
gerektirir. Onaylandığında `anonymize_customer()` çalışır:

| İşlem | Sonuç |
|---|---|
| Ad, soyad, firma | "Anonimleştirilmiş" ile değiştirilir |
| Telefon, e-posta, doğum tarihi | Boşaltılır |
| Beslenme/alerji/genel notlar | Boşaltılır |
| Favoriler, ziyaret notları | Silinir |
| Müşteri kodu | `ANON-{id}` olur |
| Rızalar | Geri çekilmiş işaretlenir |
| **Adisyon ve rezervasyonlar** | **Korunur, kişi bağlantısı koparılır** |

**Neden mali kayıt korunur?** Vergi Usul Kanunu ve TTK gereği mali kayıtların
saklanması zorunludur. KVKK m.7/3 bu durumu açıkça istisna tutar. Anonimleştirme
sonrası adisyon tutarı durur ancak hangi kişiye ait olduğu bilinemez.

Uygulanan işlem `AuditAction.DATA_ERASURE` olarak **kritik** önem düzeyinde
kaydedilir ve korunan kayıtların dökümü `retained_records_note` alanına yazılır.

---

## 4. Yapay zekâ ve kişisel veri

Bu, sistemin en dikkat gerektiren gizlilik alanıdır.

### 4.1 Varsayılan davranış

```
Varsayılan sağlayıcı : LM Studio (aynı makinede çalışır)
Gizlilik modu        : AÇIK
Yerel model önceliği : AÇIK
```

Bu yapılandırmada **hiçbir müşteri verisi işletme dışına çıkmaz.**

### 4.2 Buluta gönderim olduğunda

Bulut sağlayıcı (Anthropic, NVIDIA) kullanıldığında `mask_pii()` çalışır:

| Veri türü | Maskelenmiş hâli |
|---|---|
| E-posta | `[E-POSTA]` |
| Telefon (TR ve uluslararası) | `[TELEFON]` |
| TC kimlik numarası | `[TCKN]` |
| IBAN | `[IBAN]` |
| Kredi kartı (Luhn doğrulamalı) | `[KART_NO]` |
| Kişi adı (belirtilirse) | `[KİŞİ]` |
| API anahtarları | `***GİZLİ***` |

**Şeffaflık:** Kullanıcı arayüzde "Sağlayıcıya fiilen gönderilen metni göster"
bağlantısıyla ne gönderildiğini görebilir. Ayrıca hangi türden kaç veri
maskelendiği özetlenir.

**Tam kapatma:** `WINEHOUSE_AI_LOCAL_ONLY=True` yapıldığında bulut sağlayıcılar
yedekleme zincirine hiç girmez.

### 4.3 Sağlayıcı veri işleme şartları

Bulut sağlayıcı kullanılacaksa, işletmenin ilgili sağlayıcının veri işleme
şartlarını incelemesi ve gerekirse veri işleyen sözleşmesi yapması gerekir.
Wine House bu sorumluluğu üstlenmez; yalnızca gönderilen veriyi en aza indirir.

---

## 5. Saklama süreleri

`WINEHOUSE_RETENTION_*` ortam değişkenleriyle yapılandırılır:

| Veri | Varsayılan | Ayar |
|---|---|---|
| Denetim kaydı | 730 gün (2 yıl) | `WINEHOUSE_RETENTION_AUDIT_DAYS` |
| Yapay zekâ çağrı kaydı | 180 gün | `WINEHOUSE_RETENTION_AI_LOG_DAYS` |
| Pasif müşteri verisi | 1095 gün (3 yıl) | `WINEHOUSE_RETENTION_CUSTOMER_DAYS` |
| Yedekler | 30 gün (en az 3 yedek daima korunur) | `WINEHOUSE_BACKUP_RETENTION_DAYS` |

Denetim kaydı temizliği:

```bash
.venv\Scripts\python.exe manage.py purge_audit_log --dry-run
.venv\Scripts\python.exe manage.py purge_audit_log
```

Kayıtlar **önce** `var/audit-archive/*.jsonl` dosyasına yazılır, **sonra**
veritabanından kaldırılır. Arşiv dosyası oluşturulamazsa hiçbir kayıt silinmez.

---

## 6. Teknik ve idari tedbirler

| Tedbir | Uygulama |
|---|---|
| Şifreleme (durağan veri) | Hassas alanlar Fernet ile şifreli |
| Şifreleme (yedek) | Yedek arşivleri Fernet ile şifreli |
| Erişim denetimi | 19 rol, en az yetki, salt okunur denetçi |
| İzlenebilirlik | Değiştirilemez denetim kaydı |
| Veri minimizasyonu | Doğum yılı saklanmaz; AI'ya giden veri maskelenir |
| Amaç sınırlaması | Her amaç için ayrı rıza |
| Erişim kaydı | Müşteri verisi dışa aktarımı denetime yazılır |
| Yetkisiz erişim tespiti | Yetki reddi kaydı + CAIO uyarısı |

---

## 7. Veri ihlali durumunda

1. **Tespit:** `Denetim kaydı` ekranından yetki reddi ve olağandışı erişimleri
   inceleyin (`?failed=1` filtresi).
2. **Kapsam:** `AuditAction.EXPORT` ve `VIEW` kayıtlarından hangi verinin
   görüntülendiğini/aktarıldığını çıkarın.
3. **Sınırlama:** İlgili kullanıcının hesabını pasifleştirin
   (`is_active=False`), parolasını sıfırlayın.
4. **Bildirim:** KVKK m.12/5 gereği ihlali öğrendiğinizden itibaren **72 saat
   içinde** Kurul'a ve ilgili kişilere bildirin.
5. **Kanıt:** Denetim kaydını arşivleyin (`purge_audit_log` çalıştırmadan önce).

---

## 8. Aydınlatma metni için asgari içerik

İşletmenin hazırlaması gereken aydınlatma metninde en az şunlar bulunmalıdır:

- Veri sorumlusunun kimliği
- İşlenen veri kategorileri (bu belgenin §1 tablosu)
- İşleme amaçları ve hukuki dayanakları
- Yurt dışına aktarım olup olmadığı (**bulut yapay zekâ kullanılıyorsa evet**)
- Saklama süreleri (§5)
- Veri sahibi hakları ve başvuru yolu
