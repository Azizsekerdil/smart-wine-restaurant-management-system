# Güvenlik

> Sürüm 0.1.0 · Son güncelleme: 18.08.2026

---

## 1. Tehdit modeli

Wine House bir restoranın **kasa, stok ve müşteri verisini** tutar. Gerçekçi
tehditler şunlardır:

| Tehdit | Kim | Karşı önlem |
|---|---|---|
| Kasa açığını gizlemek için adisyon silme | İç personel | Silme yok; iptal onaya bağlı ve denetim kaydına yazılır |
| Yetkisiz indirim / ikram | İç personel | Rol bazlı indirim limiti + limit aşımında ikinci onay |
| Stok açığını gizlemek için sayım düzeltmesi | İç personel | Sayım farkı `StockMovement` üretir; hareketler silinemez |
| Müşteri iletişim listesinin dışarı çıkarılması | İç personel | Şifreli alanlar + `view_customer_contact` izni + dışa aktarım denetim kaydı |
| Kişisel verinin buluta sızması | Sistem tasarımı | Gönderim öncesi maskeleme + kullanıcıya gösterme + yalnızca-yerel modu |
| API anahtarının günlüğe/ekrana düşmesi | Sistem tasarımı | Her handler'da maskeleme filtresi + `redact_key` |
| Yapay zekânın veriyi bozması | Sistem tasarımı | AI veritabanına yazmaz; her öneri insan onayı bekler |
| Geliştirici stüdyosunun kötüye kullanımı | İç/dış saldırgan | Politika motoru + çalışma alanı sınırı + üretimde varsayılan kapalı |
| Parola deneme saldırısı | Dış saldırgan | 5 denemede 15 dakika kilit + `LoginAttempt` kaydı |

**Kapsam dışı:** İşletim sistemi düzeyinde ele geçirilmiş bir makine. Yerel
yönetici hakkına sahip bir saldırgan veritabanı dosyasına doğrudan erişebilir.
Bu nedenle hassas alanlar şifrelenir ve yedekler ayrıca şifrelenir.

---

## 2. Kimlik doğrulama

| Yöntem | Kullanım | Not |
|---|---|---|
| Kullanıcı adı + parola | Tüm ekranlar | En az 10 karakter; Django parola doğrulayıcıları etkin |
| Personel kodu + PIN | POS terminali | 4–8 rakam, karma olarak saklanır, düz metin tutulmaz |
| API belirteci (token) | REST API | `/api/v1/auth/token/` |

**Hesap kilitleme:** 5 başarısız denemeden sonra 15 dakika. Başarılı girişte
sayaç sıfırlanır. Tüm denemeler `LoginAttempt` tablosuna yazılır.

---

## 3. Yetkilendirme

### 3.1 Roller

19 rol tanımlıdır (`src/apps/accounts/roles.py`). Her rol bir Django `Group`
olarak veritabanına yansıtılır ve izinleri desenlerle tanımlanır.

**En az yetki ilkesi örnekleri:**

| Rol | İzin sayısı | Yapamadıkları |
|---|---|---|
| Garson | 18 | Kav yönetimi, kullanıcı ekleme, gün sonu kapatma |
| Sommelier | 41 | Gün sonu, ödeme alma, personel yönetimi |
| Kasiyer | 12 | Menü değiştirme, stok düzeltme |
| Denetçi | 101 | **Hiçbir yazma işlemi** |
| Sistem yöneticisi | 519 | — |

### 3.2 Salt okunur koruma

Denetçi rolündeki kullanıcı, izin listesi ne olursa olsun **HTTP yazma
yöntemleri** (POST/PUT/PATCH/DELETE) kullanamaz. Bu, görünüm karışımında
yöntem düzeyinde uygulanır.

### 3.3 İkinci onay (görevler ayrılığı)

Kritik işlemler `ApprovalRequest` üretir:

- Adisyon iptali · ödeme iadesi · limit üstü indirim · ikram
- Fiyat değiştirme · stok düzeltmesi · yüksek değerli fire
- Gün sonu kapanışı · yedekten geri yükleme
- Müşteri verisi silme · yapay zekâ önerisi uygulama
- Geliştirici stüdyosu birleştirmesi

**Kural:** Kullanıcı kendi talebini onaylayamaz (`_guard_review`). Onay
alınmadan işlem uygulanmaz — talep oluşturulur ve fonksiyon
`ApprovalRequiredError` fırlatır.

---

## 4. Veri koruma

### 4.1 Şifrelenen alanlar

| Model | Alan |
|---|---|
| `crm.Customer` | telefon, e-posta, doğum tarihi |
| `hr.Employee` | kimlik no, telefon, e-posta, adres, IBAN, acil durum |
| `inventory.Supplier` | telefon, e-posta, vergi numarası |
| `accounts.User` | telefon |
| `core.AppSetting` | gizli değerler |

**Yöntem:** Fernet (AES-128-CBC + HMAC-SHA256), `enc$v1$` önekli. Anahtar
`WINEHOUSE_FIELD_ENCRYPTION_KEY` ortam değişkeninden okunur.

**Doğrulama:** `tests/test_security.py::test_sifreli_alan_veritabaninda_duz_metin_degil`
testi, veritabanına ham SQL ile bakarak telefon numarasının düz metin
olmadığını kanıtlar.

### 4.2 Şifreli alanda arama

Şifreli alanda `WHERE phone = ?` çalışmaz. Bunun için `blind_index()` HMAC-SHA256
özeti ayrı bir sütunda tutulur. Aynı düz metin daima aynı özeti verir; özetten
düz metne dönülemez.

### 4.3 Gizli değer maskeleme

`mask_secrets()` şu biçimleri tanır ve maskeler: Anthropic (`sk-ant-`), OpenAI
(`sk-`), NVIDIA (`nvapi-`), GitHub (`ghp_`/`gho_`/…), AWS (`AKIA`/`ASIA`),
`Bearer` belirteçleri, `*_API_KEY=`/`*_SECRET=`/`*_TOKEN=`/`*PASSWORD=`
atamaları ve PEM özel anahtar blokları.

Uygulandığı yerler:
- Tüm günlük handler'ları (`SecretMaskingFilter`)
- Denetim kaydı mesajları ve değişiklik sözlüğü
- Stüdyo terminal çıktısı (`masked_output()`)
- Sağlayıcı hata gövdeleri

---

## 5. Denetim kaydı

`core.AuditLog` **yalnızca eklenir**:

- `save()` var olan bir kaydı güncellemeye çalışırsa `ValueError` fırlatır
- `delete()` her zaman `ValueError` fırlatır
- Saklama süresi dolan kayıtlar `purge_audit_log` komutuyla **önce JSONL
  arşivine yazılır**, sonra veritabanından kaldırılır

Aynı değiştirilemezlik `inventory.StockMovement` ve `crm.LoyaltyTransaction`
için de geçerlidir.

**Kaydedilen olaylar:** giriş/çıkış/başarısız giriş, yetki reddi, oluşturma/
güncelleme/silme, ödeme/iade/iptal/indirim, stok düzeltme/fire, dışa aktarım,
yedekleme/geri yükleme, yapay zekâ isteği ve öneri uygulama, ayar değişikliği,
rıza ve veri silme.

---

## 6. AI Development Studio

Bu modül yapay zekânın kod önermesine izin verir; bu nedenle en sıkı korumaya
sahiptir.

### 6.1 Erişim

- Yalnızca `sysadmin` ve `owner` rolleri (veya süper kullanıcı)
- `WINEHOUSE_DEVSTUDIO_ENABLED` **üretimde varsayılan `False`**
- `WINEHOUSE_DEVSTUDIO_ALLOW_COMMANDS` varsayılan `False` — kapalıyken yalnızca
  öneri üretilir, hiçbir komut çalışmaz

### 6.2 Politika motoru

Yapay zekâ **komut çalıştırmaz**; yapılandırılmış eylem önerir. Her öneri:

1. **Kabuk metakarakteri** (`|`, `&`, `;`, `>`, `<`, `` ` ``, `$(`) → RED
2. **Yasak desen** → RED
   - `git push --force`, `git reset --hard`, `filter-branch`, `git clean -fdx`
   - `rm -rf`, `del /s`, `Remove-Item -Recurse`
   - credential/vault/keychain okuma
   - `curl`/`wget`/`Invoke-WebRequest` (ağ dışa aktarımı)
   - `printenv`, `Get-ChildItem env:` (ortam sızdırma)
   - `runas`, `sudo`, `-Verb RunAs` (yetki yükseltme)
3. **Yasak çalıştırılabilir** → RED
   `powershell`, `cmd`, `bash`, `curl`, `reg`, `netsh`, `sc`, `schtasks`,
   `format`, `diskpart`, `vssadmin`, `wmic`, `icacls`, `mshta`, … (37 komut)
4. **İzin listesi** → salt okunur komutlar (`git status/diff/log`, `pytest`,
   `ruff`) İZİN; yazma komutları (`git add/commit`, `pip install`) ONAY
5. Listede yoksa → RED

### 6.3 Dosya koruması

| Denetim | Sonuç |
|---|---|
| Çalışma alanı dışı (`../`, mutlak yol, sembolik bağlantı) | RED |
| `.env`, `*.key`, `*.pem`, `id_rsa*`, `secrets*`, `*.sqlite3` | RED |
| `.git/` iç dizini | RED |
| `.venv/`, `node_modules/` | RED |
| `settings/`, `security.py`, `policy.py`, `roles.py`, `.github/workflows/` | EK ONAY |
| Diğer kaynak dosyalar | ONAY |

### 6.4 Birleştirme koşulları

`DevSession.can_merge` yalnızca şu üçü birlikte sağlandığında `True` döner:
kullanıcı onayı **ve** testler çalıştırılmış **ve** testler geçmiş.
Ayrıca çalışma dalı oluşturulmuş olmalıdır.

---

## 7. Yapay zekâ gizliliği

| Katman | Davranış |
|---|---|
| Varsayılan sağlayıcı | LM Studio (yerel) — veri işletme dışına çıkmaz |
| `WINEHOUSE_AI_LOCAL_ONLY=True` | Bulut sağlayıcılar zincire hiç girmez |
| `WINEHOUSE_AI_PRIVACY_MODE=True` | Buluta gönderim öncesi PII maskelenir |
| Şeffaflık | Kullanıcı, sağlayıcıya *fiilen gönderilen metni* arayüzde görebilir |
| Maliyet sınırı | Aylık bütçe aşılınca bulut çağrıları engellenir (`BLOCKED` kaydı) |
| Öneri uygulama | AI veritabanına yazmaz; `AISuggestion` insan onayı bekler |

Maskelenen veri türleri: e-posta, telefon (TR ve uluslararası), TCKN, IBAN,
Luhn-geçerli kart numarası, API anahtarları ve kullanıcı tarafından belirtilen
serbest terimler (ör. müşteri adı).

---

## 8. Güvenlik denetimi sonuçları

| Araç | Sonuç |
|---|---|
| `pip-audit` | **No known vulnerabilities found** |
| `bandit` (orta+) | 0 yüksek · 1 orta · 28 düşük |
| `detect-secrets` | Temiz — depoda gizli değer yok |
| `manage.py check` | Sorun yok |
| Test paketi | 255/255 geçti |

**Tek orta seviye bulgu:** `dev.py` içinde `ALLOWED_HOSTS` listesinde `0.0.0.0`.
Bu, geliştirme sırasında başka bir cihazdan erişim için bilinçli bir seçimdir ve
`# noqa: S104` ile işaretlenmiştir. `prod.py` bu değeri kullanmaz.

---

## 9. Üretim öncesi kontrol listesi

- [ ] `DJANGO_DEBUG=False`
- [ ] `DJANGO_SECRET_KEY` üretim için yeniden üretildi
- [ ] `WINEHOUSE_FIELD_ENCRYPTION_KEY` tanımlı ve yedeklendi
- [ ] `DJANGO_ALLOWED_HOSTS` yalnızca gerçek adresleri içeriyor
- [ ] `WINEHOUSE_DEVSTUDIO_ENABLED=False`
- [ ] `WINEHOUSE_PAYMENT_MODE=sandbox` (canlı ödeme onaylanmadıysa)
- [ ] İlk yönetici parolası değiştirildi
- [ ] Zamanlanmış yedekleme kuruldu ve bir kez doğrulandı
- [ ] `CHECK_WINE_HOUSE.bat` hatasız çalışıyor

Tam liste: [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md)

---

## 10. Güvenlik açığı bildirimi

Bu depo private'tır. Güvenlik açığı tespit ederseniz depo sahibine doğrudan
bildirin; genel bir issue açmayın.
