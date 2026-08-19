# ADR-0002: Python 3.11 hedefi

**Durum:** Kabul edildi · **Tarih:** 18.08.2026

## Bağlam

Proje yönergesinde **Python 3.12** istenmişti. Geliştirme makinesinde kurulu
sürümler: **3.11.9** ve **3.14.0**. Python 3.12 kurulu değildi.

## Karar

Hedef aralık **Python 3.11 – 3.13**; geliştirme 3.11.9 ile yapıldı.

## Gerekçe

- **3.14 kullanılamaz:** Django 5.2 Python 3.10–3.13 aralığını destekler.
  3.14 henüz desteklenmiyor; kullanılsaydı desteklenmeyen bir kombinasyon
  üzerine inşa edilmiş olurdu.
- **3.12 kurmak yerine 3.11 kullanmak:** Kullanıcının makinesine izinsiz
  yazılım kurmak yerine mevcut uyumlu sürümle çalışmak tercih edildi. 3.11 ile
  3.12 arasında bu proje için davranış farkı yoktur.
- Kod, 3.12 ve 3.13 ile de çalışır. Kurulum betiği **önce 3.12**, sonra 3.13,
  sonra 3.11 arar; kullanıcının makinesinde 3.12 varsa onu kullanır.

## Sonuçlar

- `requires-python = ">=3.11,<3.14"`
- 3.12+ özellikleri (ör. PEP 695 tip parametreleri) kullanılmadı.
- CI iş akışı 3.11, 3.12 ve 3.13 üzerinde koşar.
