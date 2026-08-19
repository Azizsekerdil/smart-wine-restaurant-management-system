# Sürüm Öncesi Denetim Listesi

> Her sürümden önce baştan sona uygulanır. Bir madde başarısızsa sürüm alınmaz.

---

## 1. Kod kalitesi

- [ ] `ruff check src tests` — hata yok
- [ ] `black --check src tests` — biçim uyumlu
- [ ] `mypy src` — kritik tip hatası yok
- [ ] `manage.py check` — sorun yok
- [ ] `manage.py makemigrations --check --dry-run` — bekleyen migration yok

## 2. Testler

- [ ] `pytest` — tüm testler geçiyor
- [ ] `pytest --cov` — temel iş kurallarında kapsam ≥ %80
- [ ] Uçtan uca kabul senaryosu (`-m e2e`) geçiyor
- [ ] Yeni özellikler için test yazıldı

## 3. Güvenlik

- [ ] `pip-audit` — bilinen zafiyet yok
- [ ] `bandit -r src --severity-level medium` — yüksek bulgu yok
- [ ] `detect-secrets scan` — gizli değer yok
- [ ] `git log --all -- .env` boş (anahtar hiç commit edilmemiş)
- [ ] `.gitignore` içinde `.env`, `*.sqlite3`, `backups/`, `logs/` var
- [ ] Yeni bağımlılıkların lisansı denetlendi

## 4. Yapılandırma

- [ ] `DJANGO_DEBUG=False` (üretim)
- [ ] `DJANGO_SECRET_KEY` üretim için ayrı üretildi
- [ ] `WINEHOUSE_FIELD_ENCRYPTION_KEY` tanımlı ve **ayrıca yedeklendi**
- [ ] `DJANGO_ALLOWED_HOSTS` yalnızca gerçek adresler
- [ ] `WINEHOUSE_DEVSTUDIO_ENABLED=False`
- [ ] `WINEHOUSE_DEVSTUDIO_ALLOW_COMMANDS=False`
- [ ] `WINEHOUSE_PAYMENT_MODE=sandbox` (canlı ödeme onaylanmadıysa)
- [ ] `WINEHOUSE_EINVOICE_MODE=sandbox`
- [ ] `WINEHOUSE_AI_PRIVACY_MODE=True`

## 5. Veri ve yedekleme

- [ ] Yedek alındı ve **doğrulandı**
- [ ] Geri yükleme tatbikatı test veritabanına yapıldı
- [ ] Zamanlanmış yedekleme görevi çalışıyor
- [ ] Şifreleme anahtarı yedeklerden ayrı bir yerde saklanıyor
- [ ] Örnek (demo) veri üretimden temizlendi

## 6. İşlevsel doğrulama

- [ ] `CHECK_WINE_HOUSE.bat` — hata yok
- [ ] Yönetici girişi çalışıyor
- [ ] Masa açma → sipariş → KDS → ödeme akışı çalışıyor
- [ ] Kadeh satışı açık şişeden doğru düşüyor
- [ ] Gün sonu kapanışı ve kasa mutabakatı çalışıyor
- [ ] Rapor PDF/Excel/CSV üretimi çalışıyor
- [ ] Türkçe karakterler üç biçimde de doğru
- [ ] TR/EN dil değişimi çalışıyor
- [ ] QR menü misafir görünümünde açılıyor
- [ ] İnternet kapalıyken temel işlevler çalışıyor

## 7. Yapay zekâ

- [ ] LM Studio bağlantısı sınandı (veya yokluğunda sistem çalışıyor)
- [ ] Bulut sağlayıcı yapılandırıldıysa maskeleme doğrulandı
- [ ] Aylık maliyet sınırı ayarlandı
- [ ] Mock sağlayıcı yedek olarak zincirin sonunda

## 8. Belgeler

- [ ] `CHANGELOG.md` güncellendi
- [ ] `docs/STATUS.md` gerçek durumu yansıtıyor
- [ ] `docs/TEST_REPORT.md` güncel
- [ ] Yeni "Deneysel"/"Planlandı" özellikler `FeatureFlag` ile işaretlendi
- [ ] `THIRD_PARTY_NOTICES.md` yeni bağımlılıkları içeriyor
- [ ] SBOM yeniden üretildi

## 9. Sürüm damgası

- [ ] `src/winehouse/__init__.py` içindeki `__version__` güncellendi
- [ ] `pyproject.toml` sürümü eşleşiyor
- [ ] Git etiketi oluşturuldu (`git tag -a v0.1.0 -m "..."`)

## 10. Kullanıcı onayı gerektirenler

Bu maddeler **açık kullanıcı onayı olmadan yapılmaz**:

- [ ] Deponun public yapılması
- [ ] GitHub Release yayımlanması
- [ ] Canlı ödeme veya e-Fatura modunun açılması
- [ ] Ücretli yapay zekâ hizmetine geçiş
- [ ] Üretim ortamına dağıtım
