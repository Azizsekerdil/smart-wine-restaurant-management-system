# Bağımlılık Lisansları

> Üretim tarihi: 18.08.2026 · Otomatik üretilmiştir

Bu belge, [`LICENSE_AUDIT.md`](LICENSE_AUDIT.md) denetiminin bağımlılık
bölümünün özetidir. Tam döküm `sbom/` klasöründedir.

---

## 1. Çalışma zamanı kapanışı (ürünle dağıtılır)

**27 paket · güçlü kopyaleft yok · ticari kapalı kaynak dağıtıma uygun**

| Paket | Sürüm | Lisans |
|---|---|---|
| anyio | 4.14.2 | MIT |
| asgiref | 3.12.1 | BSD-3-Clause |
| certifi | 2026.7.22 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.1 | MIT |
| colorama | 0.4.6 | BSD |
| cryptography | 50.0.0 | Apache-2.0 OR BSD-3-Clause |
| django | 5.2.16 | BSD-3-Clause |
| django-htmx | 1.23.2 | MIT |
| djangorestframework | 3.16.1 | BSD |
| et-xmlfile | 2.0.0 | MIT |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.18 | BSD-3-Clause |
| openpyxl | 3.1.5 | MIT |
| pillow | 12.3.0 | MIT-CMU |
| pycparser | 3.0 | BSD-3-Clause |
| python-dateutil | 2.9.0.post0 | Apache-2.0 / BSD-3 (çift) |
| python-dotenv | 1.2.2 | BSD-3-Clause |
| qrcode | 8.2 | BSD |
| reportlab | 4.4.3 | BSD |
| six | 1.17.0 | MIT |
| sqlparse | 0.6.0 | BSD |
| typing-extensions | 4.16.0 | PSF-2.0 |
| tzdata | 2025.2 | Apache-2.0 |
| whitenoise | 6.9.0 | MIT |

### Kopyaleft taraması

```
GÜÇLÜ KOPYALEFT (GPL / AGPL / SSPL / EUPL / CDDL) : YOK
ZAYIF  KOPYALEFT (MPL / LGPL)                     : certifi (MPL-2.0)
```

`certifi` değiştirilmeden kullanıldığı için kaynak kod açma yükümlülüğü
doğurmaz.

---

## 2. Güvenlik durumu

`pip-audit` ile taranmıştır:

```
No known vulnerabilities found
```

### Uygulanan güvenlik yükseltmeleri (18.08.2026)

| Paket | Önce | Sonra | Kapatılan zafiyet |
|---|---|---|---|
| Django | 5.2.6 | **5.2.16** | PYSEC-2026-2091, -2092, -2448, -2449 |
| Pillow | 11.3.0 | **12.3.0** | PYSEC-2026-165 ve 19 ek kayıt |
| cryptography | 45.0.7 | **50.0.0** | PYSEC-2026-35, -36, -2141, -3552…3554, GHSA-537c-gmf6-5ccf |
| python-dotenv | 1.1.1 | **1.2.2** | PYSEC-2026-2270 |
| pytest (dev) | 8.4.2 | **9.0.3** | PYSEC-2026-1845 |
| black (dev) | 25.1.0 | **26.5.1** | PYSEC-2026-2120, -2121 |

Yükseltme sonrası 255 testin tamamı geçmiştir.

---

## 3. Geliştirme araçları

Bu araçlar ürünle dağıtılmaz; lisansları ürün lisansını etkilemez.

| Araç | Lisans | Not |
|---|---|---|
| pytest, ruff, black, mypy, pre-commit, pip-licenses, pywebview | MIT / BSD | Sorunsuz |
| bandit, pip-audit, detect-secrets | Apache-2.0 | Sorunsuz |
| pyinstaller | GPL-2.0 + bootloader istisnası | Üretilen `.exe` tescilli kalabilir |
| rfc3987 | GPL-3.0+ | Yalnızca dev; jsonschema biçim denetleyicisi |
| chardet | LGPL-2.1+ | Yalnızca dev araç zinciri |

---

## 4. İsteğe bağlı: PostgreSQL

`psycopg` (LGPL-3.0) yalnızca `WINEHOUSE_DB_ENGINE=postgres` seçildiğinde
kurulur. Ayrık kütüphane olarak dinamik kullanıldığı için LGPL kapalı kaynak
uygulamaya izin verir.

---

## 5. Yeniden üretme

```bash
.venv\Scripts\python.exe -m pip_audit
.venv\Scripts\python.exe -m piplicenses --from=mixed --format=markdown --output-file=docs/sbom/dependency-licenses.md
syft dir:. -o spdx-json=sbom.spdx.json -o cyclonedx-json=sbom.cdx.json
```
