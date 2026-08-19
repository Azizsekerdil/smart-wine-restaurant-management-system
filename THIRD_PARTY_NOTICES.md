# Üçüncü Taraf Bildirimleri

Wine House aşağıdaki açık kaynak bileşenleri kullanır. Her bileşen kendi
lisansına tabidir; bu bildirimler ilgili lisansların atıf gerekliliklerini
karşılamak üzere sunulmuştur.

> **Kod kökeni:** Wine House'un kaynak kodu bu proje için özgün olarak
> yazılmıştır. Hiçbir üçüncü taraf projeden kod kopyalanmamıştır.

Tam ve makine okunur döküm (bu sürüm için üretilmiştir):
- [`sbom.spdx.json`](sbom.spdx.json) — SPDX 2.3 SBOM
- [`sbom.cdx.json`](sbom.cdx.json) — CycloneDX SBOM
- [`docs/DEPENDENCY_LICENSES.md`](docs/DEPENDENCY_LICENSES.md) — okunabilir lisans dökümü

---

## Çalışma zamanı bileşenleri (ürünle dağıtılır)

### Django — BSD-3-Clause
Copyright (c) Django Software Foundation and individual contributors.
https://www.djangoproject.com/

### Django REST Framework — BSD-3-Clause
Copyright (c) 2011-present, Encode OSS Ltd.
https://www.django-rest-framework.org/

### httpx / httpcore — BSD-3-Clause
Copyright (c) 2019, Encode OSS Ltd.
https://www.python-httpx.org/

### cryptography — Apache-2.0 VEYA BSD-3-Clause
Copyright (c) Individual contributors.
https://cryptography.io/

### ReportLab — BSD-3-Clause
Copyright (c) 2000-2024, ReportLab Inc.
https://www.reportlab.com/

### openpyxl — MIT
Copyright (c) 2010 openpyxl contributors.
https://openpyxl.readthedocs.io/

### Pillow — MIT-CMU (HPND)
Copyright (c) 1997-2011 by Secret Labs AB,
Copyright (c) 1995-2011 by Fredrik Lundh and contributors.
https://python-pillow.org/

### argon2-cffi / argon2-cffi-bindings — MIT
Copyright (c) 2015 Hynek Schlawack and the argon2-cffi contributors.
https://argon2-cffi.readthedocs.io/
Parola karması için kullanılır (Argon2id).

### WhiteNoise — MIT
Copyright (c) 2013 David Evans.
https://whitenoise.readthedocs.io/

### django-htmx — MIT
Copyright (c) Adam Johnson.
https://django-htmx.readthedocs.io/

### python-dotenv — BSD-3-Clause
Copyright (c) 2014, Saurabh Kumar.

### python-dateutil — Apache-2.0 VEYA BSD-3-Clause
Copyright (c) 2003-2011 Gustavo Niemeyer, 2012-2014 Tomi Pieviläinen.

### qrcode — BSD-3-Clause
Copyright (c) 2011, Lincoln Loop.

### tzdata — Apache-2.0
Copyright (c) IANA / Python Software Foundation.

### certifi — MPL-2.0
Copyright (c) Kenneth Reitz.
https://github.com/certifi/python-certifi

> MPL-2.0 dosya düzeyinde kopyalefttir. Wine House `certifi`'yi değiştirmeden,
> ayrı bir kütüphane olarak kullanır; bu nedenle ürünün kendi kaynak kodunu
> açma yükümlülüğü doğmaz. Kaynak kod yukarıdaki adresten edinilebilir.

### Diğer geçişli bağımlılıklar
anyio (MIT) · asgiref (BSD-3) · cffi (MIT-0) · charset-normalizer (MIT) ·
colorama (BSD-3) · et-xmlfile (MIT) · h11 (MIT) · idna (BSD-3) ·
pycparser (BSD-3) · six (MIT) · sqlparse (BSD-3) · typing-extensions (PSF-2.0)

---

## Ön uç bileşenleri (depoya paketlenmiştir)

### Bootstrap 5.3.3 — MIT
Copyright (c) 2011-2024 The Bootstrap Authors.
https://getbootstrap.com/
Dosya: `src/static/vendor/bootstrap.min.css`, `bootstrap.bundle.min.js`
Telif bildirimi küçültülmüş dosyaların başlığında korunmuştur.

### htmx 2.0.4 — BSD-2-Clause (0BSD)
Copyright (c) 2020, Big Sky Software.
https://htmx.org/
Dosya: `src/static/vendor/htmx.min.js`

> Bu dosyalar CDN yerine depoya dâhil edilmiştir; uygulama internetsiz
> çalışmak zorundadır.

---

## Yazı tipleri

### DejaVu Sans — Bitstream Vera Fonts Licence + Arev Fonts Licence
Copyright (c) 2003 Bitstream, Inc. (Bitstream Vera Fonts)
Copyright (c) 2006 Tavmjong Bah (Arev Fonts)
DejaVu changes are in the public domain.
https://dejavu-fonts.github.io/

Dosyalar:
- `src/static/fonts/DejaVuSans.ttf`
- `src/static/fonts/DejaVuSans-Bold.ttf`
- Lisans metni: `src/static/fonts/LICENSE_DEJAVU.txt`

> **Neden depoda paketli?** Daha önce PDF üretimi işletim sistemindeki bir
> yazı tipini (çoğunlukla Arial — Monotype'a ait tescilli bir yazı tipi)
> arayıp belgeye gömüyordu. Bu, üretilen PDF'in dağıtımını kullanıcının kendi
> yazı tipi lisansına bağlı kılıyor ve çıktının makineden makineye değişmesine
> yol açıyordu. DejaVu Sans **izin verici lisanslıdır, gömülmesi ve yeniden
> dağıtılması serbesttir**; artık öncelikli olarak o kullanılır ve çıktı her
> kurulumda aynıdır. Sunum ve raporların tamamı bu yazı tipiyle üretilir.

PDF'lerde ayrıca ReportLab'ın standart Helvetica (PDF base-14) adı geçebilir;
base-14 yazı tipleri belgeye gömülmez ve lisans yükümlülüğü doğurmaz.

---

## Geliştirme araçları (ürünle dağıtılmaz)

pytest · pytest-django · pytest-cov (MIT) · ruff · black · mypy (MIT) ·
pre-commit (MIT) · bandit · pip-audit · detect-secrets (Apache-2.0) ·
pip-licenses (MIT) · python-pptx (MIT) · pypdf (BSD-3) · lxml (BSD-3)

> SBOM üretimi `cyclonedx-bom` yerine **Syft** (Apache-2.0) ile yapılır; Syft
> ayrı bir ikili olarak çalışır ve Python bağımlılık ağacına hiçbir şey
> eklemez. `cyclonedx-bom`, `cyclonedx-python-lib[validation]` üzerinden
> `lxml < 6`'ya bağlanıp GHSA-vfmq-68hx-4jfw (HIGH) taşıyan bir lxml sürümünü
> zorunlu kıldığı için geliştirme bağımlılıklarından çıkarılmıştır.

---

## Paketleme araçları (OPSİYONEL — `requirements-packaging.txt`)

Bu araçlar varsayılan geliştirme kurulumunun **dışındadır**; yalnızca `.exe`
veya masaüstü kabuğu üretmek isteyenler kurar.

### pywebview — BSD-3-Clause
Copyright (c) 2014-2024 Roman Sirokov.

### PyInstaller — GPL-2.0 + bootloader istisnası
Copyright (c) 2010-2024, PyInstaller Development Team.

> PyInstaller'ın bootloader istisnası, PyInstaller ile paketlenen uygulamaların
> istenen lisansla (tescilli dâhil) dağıtılmasına açıkça izin verir. Ancak
> PyInstaller'ın **kendi kaynağı GPL-2.0'dır**; değiştirilmiş bir PyInstaller
> dağıtılacaksa bu yükümlülük geçerlidir.

---

## Simgeler ve görseller

Uygulamadaki tüm simgeler **Unicode emoji karakterleridir** ve telif konusu
değildir. Favicon (`src/static/img/favicon.svg`) bu proje için çizilmiş özgün
bir SVG'dir. Hiçbir stok görsel, ticari ikon seti veya üçüncü taraf
illüstrasyon kullanılmamıştır.

## Örnek veriler

`python manage.py seed_demo` komutunun ürettiği tüm veriler **sentetiktir**.
Üretici, şarap, müşteri, personel ve tedarikçi adları uydurmadır. Hiçbir gerçek
kurum, kişi veya ticari veri seti kullanılmamıştır.
