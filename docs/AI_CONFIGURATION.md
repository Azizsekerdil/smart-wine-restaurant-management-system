# Yapay Zekâ Yapılandırması

> Sürüm 0.1.0

---

## 1. Temel ilke

Wine House **yapay zekâ olmadan da tam çalışır.** Yapay zekâ yalnızca öneri
üretir; hiçbir koşulda veritabanında kritik değişiklik yapmaz.

```
Varsayılan sağlayıcı : LM Studio (yerel)
Gizlilik modu        : AÇIK
Yerel model önceliği : AÇIK
Aylık maliyet sınırı : 10 USD
```

---

## 2. Desteklenen sağlayıcılar

| Kod | Sağlayıcı | Tür | API anahtarı |
|---|---|---|---|
| `lmstudio` | LM Studio | Yerel | Gerekmez |
| `anthropic` | Anthropic Claude | Bulut | `ANTHROPIC_API_KEY` |
| `nvidia` | NVIDIA | Bulut | `NVIDIA_API_KEY` |
| `mock` | Sahte sağlayıcı | Yerel | Gerekmez |

**Model adları koda gömülmez.** Her sağlayıcının model listesi çalışma
zamanında `/models` uç noktasından okunur.

---

## 3. LM Studio (önerilen)

### 3.1 Kurulum

1. https://lmstudio.ai adresinden LM Studio'yu indirin
2. Bir model indirin (öneri: Gemma veya Llama sınıfı bir *instruct* modeli)
3. **Developer** sekmesi → **Start Server**
4. Sunucu `http://localhost:1234` adresinde açılır

### 3.2 Yapılandırma

```
WINEHOUSE_LMSTUDIO_BASE_URL=http://localhost:1234/v1
WINEHOUSE_LMSTUDIO_MODEL=
WINEHOUSE_LMSTUDIO_TIMEOUT=60
```

`WINEHOUSE_LMSTUDIO_MODEL` boş bırakılırsa uygulama **göreve uygun modeli
otomatik seçer**.

### 3.3 Görev bazlı model seçimi

Uygulama, yüklü modeller arasından göreve uygun olanı seçer ve **uygun
olmayanları eler**:

| Görev | Tercih edilen | Elenen |
|---|---|---|
| Genel sohbet / sommelier | instruct, chat, gemma, llama, mistral | math, embed, coder, vision |
| Kodlama | coder, code, deepseek, starcoder | math, embed, vision |
| Görsel analiz | vision, vl, llava, moondream | math, embed, coder |
| Analitik | math, reason, qwq, r1 | embed, vision |
| Gömme | embed, bge, e5, nomic | chat, instruct, coder |

Ayrıca alan dışı modeller (tıbbi vb.) genel görevlerde önerilmez.

> **Neden bu eleme var?** Canlı testte, yalnızca olumlu ipuçlarına bakan bir
> seçim algoritması genel sommelier sorusu için bir *matematik modeli* seçti ve
> model soruyu matematik problemi sandı. Eleme mantığı bu kusurdan doğdu.

### 3.4 Sorun giderme

| Belirti | Çözüm |
|---|---|
| "LM Studio sunucusuna ulaşılamadı" | LM Studio açık mı? Developer → Start Server yapıldı mı? |
| "Yüklü model yok" | LM Studio'da bir model yükleyin |
| Yanıt boş geliyor | Akıl yürütme modeli olabilir; uygulama `reasoning_content` alanını okur |
| Çok yavaş | Daha küçük model seçin veya `max_tokens` düşürün |

---

## 4. Anthropic Claude

### 4.1 API anahtarı

Anahtar **uygulama arayüzünden girilmez**. Yalnızca ortamdan okunur:

```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "<anahtarınız>", "User")
```

veya `.env` dosyasına `ANTHROPIC_API_KEY=...`

### 4.2 Yapılandırma

```
WINEHOUSE_ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
WINEHOUSE_ANTHROPIC_MODEL=
WINEHOUSE_ANTHROPIC_TIMEOUT=60
```

Model boş bırakılırsa hesabın erişebildiği **en yeni** model kullanılır
(Anthropic listeyi en yeni başta döndürür).

### 4.3 Teknik notlar

Anthropic Messages API'si OpenAI sözleşmesinden farklıdır; adaptör bunu ele alır:

- Kimlik `x-api-key` başlığıyla (`Authorization: Bearer` değil)
- `anthropic-version` başlığı zorunlu
- Sistem istemi mesaj listesinde değil, ayrı `system` alanında
- `max_tokens` zorunlu
- Yanıt `content` bir *blok dizisidir*
- Kullanım: `usage.input_tokens` / `usage.output_tokens`

---

## 5. NVIDIA

Ayrıntılı model değerlendirmesi: [`NVIDIA_MODEL_EVALUATION.md`](NVIDIA_MODEL_EVALUATION.md)

```
NVIDIA_API_KEY=<anahtarınız>
WINEHOUSE_NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
WINEHOUSE_NVIDIA_MODEL=nvidia/ising-calibration-1.5-31b
```

> ⚠️ **Model adını mutlaka belirtin.** `/v1/models` uç noktası hesabın
> kullanamayacağı modelleri de listeler; otomatik seçim erişilemeyen bir
> modele düşebilir.

---

## 6. Gizlilik ayarları

```
WINEHOUSE_AI_PRIVACY_MODE=True     # Buluta gönderim öncesi PII maskele
WINEHOUSE_AI_LOCAL_ONLY=False      # True: bulut sağlayıcılar zincire girmez
WINEHOUSE_AI_PREFER_LOCAL=True     # Yerel sağlayıcıları başa al
```

### Maskelenen veri türleri

E-posta · telefon (TR ve uluslararası) · TC kimlik numarası · IBAN ·
Luhn-geçerli kart numarası · API anahtarları · belirtilen kişi adları

**Şeffaflık:** Kullanıcı arayüzde *sağlayıcıya fiilen gönderilen metni*
görebilir ve hangi türden kaç veri maskelendiğini okuyabilir.

---

## 7. Yedekleme zinciri

```
WINEHOUSE_AI_FALLBACK_ORDER=lmstudio,anthropic,nvidia,mock
```

Zincir şu kurallara göre düzenlenir:

1. `LOCAL_ONLY=True` ise bulut sağlayıcılar **çıkarılır**
2. `PREFER_LOCAL=True` ise yerel sağlayıcılar **başa alınır**
3. `mock` her zaman **sonda** bulunur

Bir sağlayıcı başarısız olursa sıradaki denenir. Zincirin sonunda mock
bulunduğu için yapay zekâ akışı **hiç çökmez** — en kötü durumda "gerçek model
yanıtı değildir" etiketli bir yanıt döner.

---

## 8. Maliyet kontrolü

```
WINEHOUSE_AI_MONTHLY_COST_LIMIT_USD=10
```

- Maliyet yalnızca **fiyatı elle tanımlanmış** modeller için hesaplanır.
  Uygulama hiçbir sağlayıcının fiyatını varsaymaz.
- Fiyat tanımlamak için: `Yapay Zekâ → Maliyet` ekranı veya
  `/api/v1/ai/pricing/` uç noktası
- Aylık sınır aşıldığında **bulut** çağrıları engellenir (`BLOCKED` kaydı);
  yerel sağlayıcılar çalışmaya devam eder
- Yerel sağlayıcılar maliyet üretmez

---

## 9. Yapay zekâ özellikleri

| Özellik | Durum | Ekran |
|---|---|---|
| Sommelier asistanı | ✅ Hazır | Yapay Zekâ → Sommelier |
| Yemek–şarap eşleştirme | ✅ Hazır | Yapay Zekâ → Sommelier |
| Genel konsol | ✅ Hazır | Yapay Zekâ → Konsol |
| Öneri kuyruğu | ✅ Hazır | Yapay Zekâ → Öneriler |
| Maliyet takibi | ✅ Hazır | Yapay Zekâ → Maliyet |
| Gün sonu yönetici özeti | ✅ Hazır | `summarize_business_day()` |
| Doğal dille rapor sorgulama | ⚠️ Deneysel | API üzerinden |
| Satış tahmini yorumu | ⚠️ Deneysel | Raporlar → Tahmin |
| Etiket görsel analizi | 📋 Planlandı | — |

---

## 10. Güvenlik kuralları

1. **API anahtarları asla koda yazılmaz** — yalnızca ortamdan okunur
2. **Anahtarlar günlüğe düşmez** — her handler'da maskeleme filtresi
3. **Anahtarlar arayüzde tam gösterilmez** — yalnızca `nvap…gUqA` biçiminde
4. **Anahtarlar depoya girmez** — `.env` `.gitignore` içinde
5. **Yapay zekâ veritabanına yazmaz** — her öneri insan onayı bekler
6. **Bulut kullanımı yetki gerektirir** — `aiservices.can_use_cloud_ai`
