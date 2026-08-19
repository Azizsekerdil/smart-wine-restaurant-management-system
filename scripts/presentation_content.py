"""Wine House tanıtım sunumu — içerik tanımı (TR / EN).

Sunum içeriği burada *veri* olarak tutulur; oluşturucular (PPTX, PDF, HTML)
bu veriyi okur. Böylece metin bir kez yazılır ve dört çıktıda da aynı kalır.

Slayt türleri
-------------
``title``    Kapak
``section``  Bölüm ayracı
``bullets``  Başlık + madde listesi
``stats``    Başlık + sayı kartları
``table``    Başlık + tablo
``flow``     Başlık + adım zinciri
``compare``  Başlık + iki sütunlu karşılaştırma
``screenshot`` Başlık + arayüz görseli (docs/screenshots/) + açıklama
``closing``  Kapanış
"""

from __future__ import annotations

from typing import Any

VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# TÜRKÇE
# ---------------------------------------------------------------------------
TR: dict[str, Any] = {
    "lang": "tr",
    "deck_title": "Wine House — Tanıtım",
    "product": "Wine House",
    "tagline": "Akıllı Şarap Restoranı Yönetim Sistemi",
    "footer": "Wine House · Aziz Şekerdil · 2026",
    "labels": {
        "slide": "Slayt",
        "of": "/",
        "swipe": "Kaydırarak ilerleyin · ← → tuşları",
        "close": "Kapat",
    },
    "slides": [
        # 1
        {
            "type": "title",
            "title": "Wine House",
            "subtitle": "Akıllı Şarap Restoranı Yönetim Sistemi",
            "meta": f"Sürüm {VERSION} · Tanıtım Sunumu · 2026",
            "note": "Yerel çalışan · çevrimdışı dayanıklı · rol tabanlı",
        },
        # 2
        {
            "type": "stats",
            "title": "Bir bakışta",
            "subtitle": "Ölçülmüş, test edilmiş, çalışan sistem",
            "items": [
                ("16", "Django uygulaması"),
                ("129", "veritabanı tablosu"),
                ("19", "kullanıcı rolü"),
                ("13", "hazır rapor"),
                ("380", "otomatik test · tamamı geçiyor"),
                ("%73", "satır kapsamı (tüm kod)"),
                ("0", "bilinen çalışma zamanı zafiyeti"),
                ("29", "çalışma zamanı bağımlılığı"),
            ],
        },
        # 3
        {
            "type": "bullets",
            "title": "Şarap restoranı neden farklı?",
            "subtitle": "Standart POS yazılımlarının çözemediği sorun",
            "items": [
                "Şarap **iki birimde** satılır — şişe ve kadeh — ama stok tek birimde tutulur.",
                "Açılan bir şişe **bozulmaya başlar**; ne zaman açıldığı ve nasıl korunduğu önemlidir.",
                "Bir şişeden çıkması gereken kadeh sayısı ile **gerçekte çıkan** arasındaki fark, doğrudan kâr kaybıdır.",
                "Şarabın bir **içim aralığı** vardır; zamanında satılmayan şişe değer kaybeder.",
                "Kav sıcaklığı birkaç derece saparsa **binlerce liralık envanter** zarar görür.",
                "Sommelier'nin önerisi, o an **stokta olan** şarapla sınırlı olmalıdır.",
            ],
        },
        # 4
        {
            "type": "bullets",
            "title": "Wine House ne yapar?",
            "subtitle": "Tek uygulamada, tek veritabanında",
            "items": [
                "**Salon operasyonu** — masa planı, rezervasyon, adisyon, mutfak ekranı, ödeme, gün sonu",
                "**Dijital şarap kavı** — künye, yerleşim, parti takibi, kadeh servisi, verim analizi",
                "**Menü ve maliyet** — reçete, porsiyon maliyeti, alerjen, dinamik fiyatlandırma",
                "**Stok ve satın alma** — FIFO/FEFO, son kullanma, fire, tedarikçi, teklif karşılaştırma",
                "**Müşteri ve personel** — KVKK uyumlu CRM, sadakat, vardiya, performans",
                "**Raporlama** — 13 rapor, PDF / Excel / CSV",
                "**Yapay zekâ** — sommelier asistanı, sağlayıcıdan bağımsız, gizlilik korumalı",
            ],
        },
        # 5
        {
            "type": "table",
            "title": "Tasarım ilkeleri",
            "subtitle": "Her karar bir gerekçeye dayanır",
            "columns": ["İlke", "Ne anlama geliyor"],
            "rows": [
                ["Yerel öncelikli", "İnternet kesildiğinde restoran çalışmaya devam eder"],
                ["Yapay zekâ isteğe bağlı", "AI kapalıyken tüm temel işlevler tam çalışır"],
                ["Mali kayıtlar dondurulur", "Menü fiyatı değişse bile geçmiş hesap değişmez"],
                ["Silme yerine iz bırakma", "Düzeltme ters kayıtla yapılır; denetim izi korunur"],
                ["Güvenli varsayılan", "Tehlikeli özellikler kapalı doğar"],
                ["En az yetki", "Kullanıcı yalnızca görevini görür"],
            ],
        },
        # 6
        {
            "type": "section",
            "title": "Salon Operasyonu",
            "subtitle": "Masadan kasaya kesintisiz akış",
        },
        # 7
        {
            "type": "bullets",
            "title": "Masa planı",
            "subtitle": "Salonun anlık durumu tek ekranda",
            "items": [
                "Bölüm bazlı yerleşim: ana salon, teras, bar, kav odası",
                "Sekiz masa durumu renkle **ve metinle** kodlanır — düşük ışıkta da okunur",
                "Masanın üzerinde açık adisyon numarası ve güncel tutar görünür",
                "Masaya tıklayınca doğrudan adisyona geçilir",
                "Dokunmatik POS için 44 piksellik hedef alanlar",
            ],
        },
        # 8
        {
            "type": "flow",
            "title": "Rezervasyon çakışma denetimi",
            "subtitle": "Aynı masa iki kez verilemez",
            "steps": [
                "Rezervasyon oluştur",
                "Masa ata",
                "Zaman aralığı kesişiyor mu?",
                "Kapasite yeterli mi?",
                "Onay veya ret",
            ],
            "note": "Çakışma varsa sistem masayı atamaz ve hangi rezervasyonla çakıştığını söyler.",
        },
        # 9
        {
            "type": "compare",
            "title": "Adisyon: fiyat neden dondurulur?",
            "subtitle": "Mali doğruluğun temeli",
            "left_title": "Dondurulmasaydı",
            "left": [
                "Menü fiyatı bugün değişir",
                "Dünkü adisyonun tutarı da değişir",
                "Muhasebe ile kasa tutmaz",
                "Geçmiş rapor her çalıştırmada farklı sonuç verir",
            ],
            "right_title": "Wine House'ta",
            "right": [
                "Satır oluşurken fiyat, KDV, maliyet ve ürün adı **kopyalanır**",
                "Menü sonradan değişse bile geçmiş hesap sabit kalır",
                "Bir yıl sonra çalıştırılan rapor aynı sonucu verir",
                "Gün sonu kapanışında toplamlar ayrıca dondurulur",
            ],
        },
        # 10
        {
            "type": "bullets",
            "title": "Hazırlık fişi ve mutfak ekranı",
            "subtitle": "KOT üretimi ve KDS akışı",
            "items": [
                "Sipariş gönderildiğinde **istasyon başına** ayrı fiş üretilir",
                "Yemek mutfağa, içecek bara, şarap sommelier ekranına düşer — otomatik",
                "Fiş rengi süreye göre değişir: gri → sarı → **kırmızı (gecikti)**",
                "Alerjen uyarısı fişte kırmızı satır olarak görünür",
                "Fiş ilerletme: Sırada → Hazırlanıyor → Hazır → Servis edildi",
                "Gönderilmiş satır asla iki kez gönderilmez",
            ],
        },
        # 11
        {
            "type": "bullets",
            "title": "Hesap bölme ve ödeme",
            "subtitle": "Koltuk bazlı bölme, çoklu ödeme",
            "items": [
                "Koltuk numarasına göre otomatik bölme — her koltuk ayrı adisyon olur",
                "Adisyon birleştirme: iki masa birleşirse hesaplar da birleşir",
                "Nakit, kart, yemek kartı, havale, hediye çeki, sadakat puanı",
                "Kısmi ödeme desteklenir; kalan borç her an görünür",
                "Kart komisyonu otomatik hesaplanır ve net tutar raporlanır",
                "**Sandbox modu:** bu sürümde gerçek para hareketi yoktur",
            ],
        },
        # 12
        {
            "type": "bullets",
            "title": "Gün sonu ve kasa mutabakatı",
            "subtitle": "Kapanış bir kez yapılır ve dondurulur",
            "items": [
                "Açık adisyon varken gün **kapatılamaz** — eksik hesap gün sonuna karışmaz",
                "Beklenen nakit ile sayılan nakit karşılaştırılır, fark gösterilir",
                "Ödeme yöntemi dağılımı, iptal ve iade tutarları hesaplanır",
                "Tüm toplamlar günlük özet tablosuna **dondurulur**",
                "Raporlar bu dondurulmuş özetten okur — geçmiş hiç değişmez",
            ],
        },
        # 13
        {
            "type": "section",
            "title": "Dijital Şarap Kavı",
            "subtitle": "Sistemin ayırt edici çekirdeği",
        },
        # 14
        {
            "type": "bullets",
            "title": "Şarap künyesi",
            "subtitle": "Bir sommelier'nin bilmek istediği her şey",
            "items": [
                "Üretici, bağ, ülke → bölge → apelasyon hiyerarşisi",
                "Üzüm bileşimi ve oranları — %60 Öküzgözü, %40 Boğazkere",
                "Rekolte, alkol oranı, şişe hacmi, sülfit ve vegan bilgisi",
                "Tadım profili: gövde · asidite · tanen · tatlılık (0–5 ölçek)",
                "Aroma notları, servis sıcaklığı, dekantasyon süresi, kadeh tipi",
                "İçim aralığı: başlangıç · zirve · bitiş yılı",
                "Barkod, iç QR kodu, etiket fotoğrafı",
            ],
        },
        # 15
        {
            "type": "bullets",
            "title": "Kav yerleşimi ve saklama koşulları",
            "subtitle": "Envanterin fiziksel gerçekliği",
            "items": [
                "Hiyerarşik yerleşim: kav → dolap → raf → bölme → vitrin",
                "Her konum için hedef sıcaklık, nem ve tolerans tanımlanır",
                "Sıcaklık/nem ölçümleri kaydedilir; aralık dışı sapma **uyarı üretir**",
                "Konum doluluk oranı ve depolanan şişe sayısı anlık görünür",
                "Özel kav müşterilerinin şişeleri ayrı tutulur ve **işletme değerlemesine dâhil edilmez**",
            ],
        },
        # 16
        {
            "type": "bullets",
            "title": "Parti (lot) takibi ve FEFO",
            "subtitle": "Hangi şişe önce çıkmalı?",
            "items": [
                "Her satın alma partisi ayrı izlenir: giriş tarihi, birim maliyet, tedarikçi, konum",
                "**FEFO** — en erken tüketilmesi gereken parti önce açılır",
                "Parti bazlı maliyet, doğru kârlılık hesabının temelidir",
                "Fatura referansı ve tedarikçi bağlantısı korunur",
                "Kalan şişe sayısı, giren şişe sayısını asla aşamaz (veritabanı kısıtı)",
            ],
        },
        # 17
        {
            "type": "flow",
            "title": "Kadeh satışı stoktan nasıl düşer?",
            "subtitle": "Sistemin en ince iş kuralı",
            "steps": [
                "Kadeh servis et (150 ml)",
                "Yeterli hacimli açık şişe var mı?",
                "Yoksa: FEFO ile parti seç → stoktan 1 şişe düş",
                "Açık şişenin kalan hacmini 150 ml azalt",
                "Servis kaydı yaz (satış / tadım / ikram / dökülme)",
            ],
            "note": "Yarım kadehten az kalırsa şişe otomatik olarak 'bitti' işaretlenir. "
            "İki garson aynı anda son şişeyi açamaz — satır kilidi vardır.",
        },
        # 18
        {
            "type": "stats",
            "title": "Verim analizi",
            "subtitle": "750 ml şişe · 150 ml kadeh · teorik 5 kadeh",
            "items": [
                ("5", "beklenen kadeh"),
                ("4", "gerçekleşen kadeh"),
                ("600 ml", "servis edilen"),
                ("%80", "gerçekleşen verim"),
                ("150 ml", "kayıp"),
                ("1 kadeh", "kaçan gelir · her şişede"),
            ],
            "note": "Teorik ile gerçekleşen arasındaki fark dökülme veya ölçüsüz servisi işaret eder. "
            "Kadeh/şişe karşılaştırma raporu bunu şişe şişe gösterir.",
        },
        # 19
        {
            "type": "bullets",
            "title": "Açılmış şişe ve kusur takibi",
            "subtitle": "Kayıp nerede oluşuyor?",
            "items": [
                "Servis yöntemine göre tazelik süresi: standart 48 saat · koruma sistemi 1 hafta · iğne sistemi 30 gün",
                "Süresini aşan şişeler ekranda işaretlenir",
                "Kusur kaydı: mantar hatası (TCA), oksidasyon, redüksiyon, ısı hasarı, dökülme, kırılma",
                "Her kusur stoktan düşer ve **tahmini kayıp** hesaplanır",
                "Çözüm izlenir: tedarikçiye iade · zayi · misafire yenisi",
            ],
        },
        # 20
        {
            "type": "bullets",
            "title": "İçim aralığı ve kav değerlemesi",
            "subtitle": "Envanter bir varlıktır, zamanla değişir",
            "items": [
                "Her şarap için durum hesaplanır: erken · içilebilir · **zirvede** · yakında tüketilmeli · zirveyi geçmiş",
                "Zirveyi geçmek üzere olan şişeler öncelik listesine düşer",
                "Kav değerlemesi: maliyet değeri, satış değeri, potansiyel kâr",
                "Açık şişelerin kalan hacmi de değerlemeye dâhil edilir",
                "Minimum şişe sayısının altına düşen şaraplar için kritik stok uyarısı",
            ],
        },
        # 21
        {
            "type": "bullets",
            "title": "Mükerrer ve şüpheli kayıt tespiti",
            "subtitle": "Veri kalitesi kendiliğinden bozulmaz",
            "items": [
                "Aynı barkodun iki farklı kayıtta kullanılması",
                "Aynı üretici + çok benzer ad + aynı rekolte (bulanık eşleştirme)",
                "Mantıksız rekolte — gelecek yıl veya 120 yıldan eski",
                "Fiyat anomalisi — satış fiyatı alış fiyatının altında",
                "**Sistem hiçbir kaydı kendiliğinden silmez veya birleştirmez** — yalnızca inceleme için uyarır",
            ],
        },
        # 22
        {
            "type": "section",
            "title": "Menü, Stok ve Maliyet",
            "subtitle": "Kârlılığın sayısal temeli",
        },
        # 23
        {
            "type": "bullets",
            "title": "Reçete ve porsiyon maliyeti",
            "subtitle": "Her tabağın gerçek maliyeti",
            "items": [
                "Reçete satırları stok kalemlerine bağlanır",
                "Porsiyon maliyeti, stokun **ağırlıklı ortalama** birim maliyetinden hesaplanır",
                "Fire payı yüzdesi maliyete eklenir",
                "Brüt kâr, marj yüzdesi ve **maliyet oranı** (food cost) otomatik",
                "Alerjen ve beslenme etiketleri (vejetaryen, vegan, glutensiz) ürüne bağlanır",
                "Dinamik fiyatlandırma: happy hour, kampanya, gece yarısını aşan zaman aralıkları",
            ],
        },
        # 24
        {
            "type": "table",
            "title": "Menü mühendisliği",
            "subtitle": "Hangi ürün kalmalı, hangisi değişmeli?",
            "columns": ["Kadran", "Popülerlik", "Kâr", "Ne yapmalı"],
            "rows": [
                ["Yıldız", "Yüksek", "Yüksek", "Koru, öne çıkar"],
                ["At", "Yüksek", "Düşük", "Maliyeti düşür veya fiyatı gözden geçir"],
                ["Bilmece", "Düşük", "Yüksek", "Tanıt, sommelier önerisine ekle"],
                ["Köpek", "Düşük", "Düşük", "Menüden çıkarmayı değerlendir"],
            ],
            "note": "Kasavana-Smith yöntemi · satış verisinden otomatik hesaplanır",
        },
        # 25
        {
            "type": "bullets",
            "title": "Stok, satın alma ve fire",
            "subtitle": "Girişten çıkışa tam izlenebilirlik",
            "items": [
                "FIFO veya FEFO — kalem bazında seçilir",
                "Son kullanma tarihi yaklaşan partiler için uyarı",
                "Mal kabul: kısmi ret, soğuk zincir kontrolü, otomatik parti oluşturma",
                "Stok sayımı: sistem miktarı ile sayılan karşılaştırılır, fark **hareket olarak** işlenir",
                "Fire kaydı 11 gerekçeyle: bozulma, SKT, kırılma, dökülme, personel yemeği…",
                "Minimum seviye tabanlı sipariş önerisi — **sistem sipariş oluşturmaz, önerir**",
                "Teklif karşılaştırma: en ucuz ve en hızlı ayrı ayrı işaretlenir",
            ],
        },
        # 26
        {
            "type": "bullets",
            "title": "Stok hareketleri değiştirilemez",
            "subtitle": "Bakiye her zaman doğrulanabilir",
            "items": [
                "Her giriş ve çıkış ayrı bir hareket kaydı üretir",
                "Kayıt oluştuktan sonra **güncellenemez ve silinemez** — kod düzeyinde engellenir",
                "Hata düzeltmesi ters yönlü yeni bir hareketle yapılır",
                "Stok bakiyesi her zaman hareketlerin toplamıyla denetlenebilir",
                "Aynı değişmezlik sadakat puanı ve denetim kaydı için de geçerlidir",
            ],
        },
        # 27
        {
            "type": "section",
            "title": "Müşteri, Personel ve Raporlar",
        },
        # 28
        {
            "type": "bullets",
            "title": "KVKK uyumlu müşteri yönetimi",
            "subtitle": "Veri koruma bir sonradan eklenti değil",
            "items": [
                "Telefon, e-posta ve kimlik bilgileri **şifreli** saklanır",
                "Şifreli alanda arama: geri döndürülemez HMAC özeti üzerinden",
                "Her amaç için **ayrı rıza**: hizmet, e-posta, SMS, profilleme, yapay zekâ analizi",
                "Rıza geri çekildiğinde kayıt silinmez — ispat için `geri çekilme zamanı` yazılır",
                "Veri taşınabilirliği: müşterinin tüm verisi tek tıkla dışa aktarılır",
                "Silme hakkı: kişisel veri anonimleştirilir, **mali kayıt yasal süre boyunca korunur**",
                "Doğum **yılı** saklanmaz — yalnızca gün ve ay (veri minimizasyonu)",
            ],
        },
        # 29
        {
            "type": "bullets",
            "title": "13 rapor · 3 biçim",
            "subtitle": "Türkçe karakter garantisiyle",
            "items": [
                "Satış: günlük özet · ürün ve kategori · ödeme dağılımı · satış tahmini",
                "Şarap: kârlılık · kadeh/şişe karşılaştırması · kav değerlemesi",
                "Stok: fire analizi · stok değerlemesi",
                "Operasyon: masa devir hızı · personel performansı · menü mühendisliği",
                "Yapay zekâ: maliyet ve belirteç kullanımı",
                "**PDF · Excel · CSV** — üçünde de ç ğ ı İ ö ş ü doğru görünür",
            ],
        },
        # 30
        {
            "type": "table",
            "title": "Türkçe karakter nasıl garanti ediliyor?",
            "subtitle": "Çoğu sistemin sessizce bozduğu yer",
            "columns": ["Biçim", "Sorun", "Wine House çözümü"],
            "rows": [
                ["CSV", "Excel dosyayı yanlış kodlamayla açar", "UTF-8 BOM ile yazılır; çift tıklamada bozulmaz"],
                ["Excel", "Sayılar metin olarak yazılır", "Sayılar sayı tipinde; TR sayı ve tarih biçimi"],
                ["PDF", "Gömülü yazı tipi Türkçe'yi kapsamaz", "Sistemdeki TrueType bulunur ve **gömülür**"],
                ["PDF (yazı tipi yok)", "Sessizce bozuk çıktı", "Açık hata verilir — bozuk PDF üretilmez"],
            ],
        },
        # 31
        {
            "type": "section",
            "title": "Yapay Zekâ",
            "subtitle": "Yardımcı, yetkili değil",
        },
        # 32
        {
            "type": "bullets",
            "title": "Sağlayıcıdan bağımsız mimari",
            "subtitle": "Tek bir şirkete bağlı kalmadan",
            "items": [
                "**LM Studio** (yerel) · **Anthropic Claude** · **NVIDIA** · **Mock** (çevrimdışı test)",
                "Model adları koda gömülmez — her zaman sağlayıcıdan **canlı okunur**",
                "Göreve göre model seçimi: sohbet, kodlama, görsel, analitik, gömme",
                "Zaman aşımı, yeniden deneme, üstel geri çekilme, istek iptali",
                "Yedekleme zinciri: bir sağlayıcı çökerse sıradaki denenir",
                "Zincirin sonunda **daima Mock** bulunur — yapay zekâ akışı hiç çökmez",
            ],
        },
        # 33
        {
            "type": "compare",
            "title": "Gizlilik: buluta ne gidiyor?",
            "subtitle": "Kullanıcı her zaman görür",
            "left_title": "Varsayılan davranış",
            "left": [
                "Varsayılan sağlayıcı **yerel** LM Studio",
                "Müşteri verisi işletme dışına çıkmaz",
                "`Yalnızca yerel` modu bulutu tamamen kapatır",
                "Aylık maliyet sınırı aşılırsa bulut engellenir",
            ],
            "right_title": "Buluta gitmesi gerekirse",
            "right": [
                "E-posta, telefon, TCKN, IBAN, kart no **maskelenir**",
                "API anahtarları hiçbir koşulda gönderilmez",
                "Kullanıcı **fiilen gönderilen metni** ekranda görür",
                "Hangi türden kaç veri maskelendiği raporlanır",
            ],
        },
        # 34
        {
            "type": "bullets",
            "title": "Yapay zekâ veritabanına yazamaz",
            "subtitle": "Kesin sınır",
            "items": [
                "Her öneri **kayıt olarak** saklanır ve insan onayı bekler",
                "Onaylanmadan hiçbir fiyat, stok, menü veya eşleştirme değişmez",
                "Sommelier önerisi yalnızca **kavda stokta olan** şaraplardan seçilir",
                "Sistem istemi sağlık iddiasını ve tıbbi tavsiyeyi açıkça yasaklar",
                "18 yaş sınırı ve sorumlu tüketim her öneri ekranında hatırlatılır",
                "Her çağrı kaydedilir: sağlayıcı, model, belirteç, maliyet, gecikme, sonuç",
            ],
        },
        # 35
        {
            "type": "section",
            "title": "Güvenlik ve Kalite",
        },
        # 36
        {
            "type": "table",
            "title": "19 rol · en az yetki",
            "subtitle": "Herkes yalnızca görevini görür",
            "columns": ["Rol", "İzin", "Yapamadıkları"],
            "rows": [
                ["Garson", "18", "Kav yönetimi · kullanıcı ekleme · gün sonu"],
                ["Sommelier", "41", "Gün sonu · ödeme alma · personel yönetimi"],
                ["Kasiyer", "12", "Menü değiştirme · stok düzeltme"],
                ["Denetçi", "101", "**Hiçbir yazma işlemi**"],
                ["Sistem yöneticisi", "519", "—"],
            ],
        },
        # 37
        {
            "type": "bullets",
            "title": "İkinci onay ve denetim kaydı",
            "subtitle": "Görevler ayrılığı",
            "items": [
                "Kritik işlemler onay gerektirir: iptal, iade, limit üstü indirim, ikram, stok düzeltme, geri yükleme",
                "**Kullanıcı kendi talebini onaylayamaz**",
                "Onay alınmadan işlem uygulanmaz — talep oluşturulur ve süreç durur",
                "Denetim kaydı **değiştirilemez ve silinemez** — kod düzeyinde engellenir",
                "Yetki reddi de kaydedilir; yetkisiz erişim denemeleri izlenebilir",
                "Saklama süresi dolan kayıtlar önce arşive yazılır, sonra kaldırılır",
            ],
        },
        # 38
        {
            "type": "bullets",
            "title": "Yedekleme ve geri yükleme",
            "subtitle": "Yedek, geri yüklendiği doğrulanana kadar yedek değildir",
            "items": [
                "Şifreli ZIP arşivi + SHA-256 bütünlük özeti",
                "Her yedek alındıktan sonra **otomatik doğrulanır**",
                "Geri yükleme ikinci onay gerektirir",
                "Canlı veritabanına yüklemeden önce **otomatik güvenlik yedeği** alınır",
                "Varsayılan hedef test veritabanı — tatbikat yapılabilir",
                "Saklama politikası **en az 3 yedeği daima korur**",
                "Windows Görev Zamanlayıcı ile günlük otomatik yedek",
            ],
        },
        # 39
        {
            "type": "stats",
            "title": "Kalite göstergeleri",
            "subtitle": "Ölçüldü, raporlandı",
            "items": [
                ("380", "test · tamamı geçiyor"),
                ("%73", "satır kapsamı (tüm kod)"),
                ("0", "çalışma zamanı bağımlılığında bilinen zafiyet"),
                ("0", "yüksek/orta seviye statik analiz bulgusu"),
                ("0", "gizli anahtar taraması bulgusu"),
                ("23", "veritabanı göçü (migration)"),
            ],
            "note": "Sayılar sürüm anında depodan ölçülmüştür: pytest, coverage, "
            "pip-audit/osv-scanner (çalışma zamanı bağımlılıkları), bandit ve "
            "semgrep (orta+ seviye), gitleaks. Ayrıntı: PUBLIC_RELEASE_MANIFEST.json",
        },
        # 40
        {
            "type": "table",
            "title": "Teknik künye",
            "columns": ["Katman", "Seçim"],
            "rows": [
                ["Dil / Çatı", "Python 3.11+ · Django 5.2 · Django REST Framework"],
                ["Veritabanı", "SQLite (WAL) · PostgreSQL seçeneği"],
                ["Arayüz", "Bootstrap 5.3 + HTMX — **yerel paketli, CDN yok**"],
                ["Şifreleme", "Fernet (AES-128-CBC + HMAC-SHA256)"],
                ["Raporlama", "ReportLab (PDF) · openpyxl (Excel)"],
                ["Yapay zekâ", "httpx tabanlı özel adaptör katmanı"],
                ["Kurulum", "Tek PowerShell betiği · çift tıklanan .bat dosyaları"],
            ],
        },
        # 41
        {
            "type": "compare",
            "title": "Dürüst durum bildirimi",
            "subtitle": "Tamamlanmamış hiçbir özellik tamamlanmış gibi gösterilmez",
            "left_title": "Hazır ve çalışıyor",
            "left": [
                "Salon operasyonu · KDS · ödeme · gün sonu",
                "Şarap kavı · kadeh servisi · verim analizi",
                "Stok · satın alma · fire · sayım",
                "CRM · KVKK · personel · 13 rapor",
                "Yapay zekâ katmanı · yedekleme · 19 rol",
            ],
            "right_title": "Deneysel veya planlandı",
            "right": [
                "Canlı ödeme ve e-Fatura (yalnızca adaptör)",
                "Termal yazıcı sürücüsü",
                "Toplu e-posta/SMS gönderimi",
                "Kav sensör entegrasyonu",
                "Etiket görsel analizi · çok terminalli senkronizasyon",
            ],
            "note": "Her özellik uygulamada rozetle işaretlenir: Hazır · Deneysel · Planlandı",
        },
        # 42
        {
            "type": "closing",
            "title": "Wine House",
            "subtitle": "Akıllı Şarap Restoranı Yönetim Sistemi",
            "items": [
                "Yerel çalışır · çevrimdışı dayanıklıdır",
                "Mali kayıtları dondurur, denetim izi bırakır",
                "Kadeh satışını stoktan doğru düşer",
                "Yapay zekâyı yardımcı yapar, yetkili değil",
                "Kişisel veriyi şifreler ve maskeler",
            ],
            "meta": f"Sürüm {VERSION} · 2026",
        },
    ],
}

# ---------------------------------------------------------------------------
# ENGLISH
# ---------------------------------------------------------------------------
EN: dict[str, Any] = {
    "lang": "en",
    "deck_title": "Wine House — Introduction",
    "product": "Wine House",
    "tagline": "Smart Wine Restaurant Management System",
    "footer": "Wine House · Aziz Şekerdil · 2026",
    "labels": {
        "slide": "Slide",
        "of": "/",
        "swipe": "Swipe to navigate · ← → keys",
        "close": "Close",
    },
    "slides": [
        {
            "type": "title",
            "title": "Wine House",
            "subtitle": "Smart Wine Restaurant Management System",
            "meta": f"Version {VERSION} · Introduction · 2026",
            "note": "Runs locally · offline-resilient · role-based",
        },
        {
            "type": "stats",
            "title": "At a glance",
            "subtitle": "Measured, tested, working software",
            "items": [
                ("16", "Django apps"),
                ("129", "database tables"),
                ("19", "user roles"),
                ("13", "built-in reports"),
                ("380", "automated tests · all passing"),
                ("73%", "line coverage (all code)"),
                ("0", "known runtime vulnerabilities"),
                ("29", "runtime dependencies"),
            ],
        },
        {
            "type": "bullets",
            "title": "Why is a wine restaurant different?",
            "subtitle": "What generic POS software cannot solve",
            "items": [
                "Wine sells in **two units** — bottle and glass — but stock is held in one.",
                "An opened bottle **starts to deteriorate**; when it was opened and how it is preserved matters.",
                "The gap between expected and **actual** glasses per bottle is direct lost profit.",
                "Wine has a **drink window**; a bottle not sold in time loses value.",
                "A few degrees of cellar temperature drift can damage **thousands in inventory**.",
                "A sommelier's recommendation must be limited to what is **actually in stock**.",
            ],
        },
        {
            "type": "bullets",
            "title": "What does Wine House do?",
            "subtitle": "One application, one database",
            "items": [
                "**Floor operations** — table map, reservations, orders, kitchen display, payment, day close",
                "**Digital wine cellar** — identity, layout, lot tracking, by-the-glass service, yield analysis",
                "**Menu and costing** — recipes, portion cost, allergens, dynamic pricing",
                "**Inventory and purchasing** — FIFO/FEFO, expiry, waste, suppliers, quotation comparison",
                "**Customers and staff** — GDPR-compliant CRM, loyalty, shifts, performance",
                "**Reporting** — 13 reports, PDF / Excel / CSV",
                "**Artificial intelligence** — sommelier assistant, provider-agnostic, privacy-preserving",
            ],
        },
        {
            "type": "table",
            "title": "Design principles",
            "subtitle": "Every decision has a rationale",
            "columns": ["Principle", "What it means"],
            "rows": [
                ["Local-first", "The restaurant keeps working when the internet drops"],
                ["AI is optional", "All core functions work fully with AI disabled"],
                ["Financial records are frozen", "Changing a menu price never alters a past bill"],
                ["Trace instead of delete", "Corrections use reversing entries; the audit trail survives"],
                ["Safe by default", "Dangerous features ship switched off"],
                ["Least privilege", "Each user sees only their own job"],
            ],
        },
        {"type": "section", "title": "Floor Operations", "subtitle": "From table to till"},
        {
            "type": "bullets",
            "title": "Table map",
            "subtitle": "The whole floor at a glance",
            "items": [
                "Section-based layout: main room, terrace, bar, cellar room",
                "Eight table states coded by colour **and text** — readable in low light",
                "Open order number and current total shown on the table",
                "Click a table to jump straight to its order",
                "44-pixel touch targets for POS terminals",
            ],
        },
        {
            "type": "flow",
            "title": "Reservation conflict detection",
            "subtitle": "The same table cannot be double-booked",
            "steps": [
                "Create reservation",
                "Assign table",
                "Do the time windows overlap?",
                "Is capacity sufficient?",
                "Accept or reject",
            ],
            "note": "On conflict the system refuses the assignment and names the clashing reservation.",
        },
        {
            "type": "compare",
            "title": "Orders: why freeze the price?",
            "subtitle": "The foundation of financial accuracy",
            "left_title": "If it were not frozen",
            "left": [
                "The menu price changes today",
                "Yesterday's bill total changes too",
                "Accounts no longer reconcile with the till",
                "A historical report returns different numbers each run",
            ],
            "right_title": "In Wine House",
            "right": [
                "Price, tax, cost and item name are **copied** at line creation",
                "Later menu changes never touch a past bill",
                "A report run a year later returns the same result",
                "Day-close totals are frozen a second time",
            ],
        },
        {
            "type": "bullets",
            "title": "Kitchen order tickets and displays",
            "subtitle": "KOT generation and KDS flow",
            "items": [
                "Sending an order produces **one ticket per station**",
                "Food to the kitchen, drinks to the bar, wine to the sommelier — automatically",
                "Ticket colour follows elapsed time: grey → amber → **red (overdue)**",
                "Allergen warnings appear as a red line on the ticket",
                "Ticket flow: Queued → Preparing → Ready → Served",
                "A sent line is never sent twice",
            ],
        },
        {
            "type": "bullets",
            "title": "Bill splitting and payment",
            "subtitle": "Seat-based splitting, multi-method payment",
            "items": [
                "Automatic split by seat number — each seat becomes its own order",
                "Order merging: when two tables join, so do their bills",
                "Cash, card, meal card, transfer, voucher, loyalty points",
                "Partial payments supported; the outstanding balance is always visible",
                "Card commission is calculated automatically and reported net",
                "**Sandbox mode:** no real money moves in this release",
            ],
        },
        {
            "type": "bullets",
            "title": "Day close and cash reconciliation",
            "subtitle": "Closed once, then frozen",
            "items": [
                "The day **cannot close** while orders are open — no missing bill slips through",
                "Expected cash is compared with counted cash and the variance shown",
                "Payment-method breakdown, voids and refunds are computed",
                "All totals are **frozen** into a daily snapshot",
                "Reports read from that snapshot — history never shifts",
            ],
        },
        {"type": "section", "title": "Digital Wine Cellar", "subtitle": "The distinguishing core"},
        {
            "type": "bullets",
            "title": "Wine identity",
            "subtitle": "Everything a sommelier wants to know",
            "items": [
                "Producer, vineyard, country → region → appellation hierarchy",
                "Grape composition with percentages — 60% Öküzgözü, 40% Boğazkere",
                "Vintage, alcohol, bottle size, sulphite and vegan information",
                "Tasting profile: body · acidity · tannin · sweetness (0–5 scale)",
                "Aroma notes, serving temperature, decanting time, glass type",
                "Drink window: from · peak · until",
                "Barcode, internal QR code, label photograph",
            ],
        },
        {
            "type": "bullets",
            "title": "Cellar layout and storage conditions",
            "subtitle": "The physical reality of inventory",
            "items": [
                "Hierarchical layout: cellar → cabinet → rack → bin → display",
                "Target temperature, humidity and tolerance per location",
                "Readings are recorded; out-of-range drift **raises an alert**",
                "Occupancy rate and bottles stored are shown live",
                "Private-cellar clients' bottles are kept separate and **excluded from house valuation**",
            ],
        },
        {
            "type": "bullets",
            "title": "Lot tracking and FEFO",
            "subtitle": "Which bottle should leave first?",
            "items": [
                "Every purchase lot is tracked separately: receipt date, unit cost, supplier, location",
                "**FEFO** — the lot that must be consumed first is opened first",
                "Lot-level cost is the basis of accurate profitability",
                "Invoice reference and supplier linkage are preserved",
                "Remaining bottles can never exceed received bottles (database constraint)",
            ],
        },
        {
            "type": "flow",
            "title": "How a glass leaves stock",
            "subtitle": "The system's finest business rule",
            "steps": [
                "Pour a glass (150 ml)",
                "Is there an open bottle with enough volume?",
                "If not: pick lot by FEFO → deduct 1 bottle from stock",
                "Reduce the open bottle by 150 ml",
                "Write the pour record (sale / tasting / comp / spillage)",
            ],
            "note": "When less than half a glass remains, the bottle is marked finished automatically. "
            "Two waiters cannot open the last bottle simultaneously — row locking prevents it.",
        },
        {
            "type": "stats",
            "title": "Yield analysis",
            "subtitle": "750 ml bottle · 150 ml pour · 5 glasses in theory",
            "items": [
                ("5", "expected glasses"),
                ("4", "actual glasses"),
                ("600 ml", "served"),
                ("80%", "realised yield"),
                ("150 ml", "lost"),
                ("1 glass", "missed revenue · per bottle"),
            ],
            "note": "The gap between theoretical and actual points to spillage or over-pouring. "
            "The glass-vs-bottle report shows this bottle by bottle.",
        },
        {
            "type": "bullets",
            "title": "Open bottles and fault tracking",
            "subtitle": "Where is the loss occurring?",
            "items": [
                "Freshness window by method: standard 48 h · preservation 1 week · needle system 30 days",
                "Bottles past their window are flagged on screen",
                "Fault records: cork taint (TCA), oxidation, reduction, heat damage, spillage, breakage",
                "Each fault deducts stock and computes the **estimated loss**",
                "Resolution is tracked: supplier claim · written off · replaced for the guest",
            ],
        },
        {
            "type": "bullets",
            "title": "Drink window and cellar valuation",
            "subtitle": "Inventory is an asset that changes over time",
            "items": [
                "Each wine gets a status: too young · ready · **at peak** · drink soon · past peak",
                "Bottles approaching the end of their window move to a priority list",
                "Cellar valuation: cost value, retail value, potential margin",
                "Remaining volume in open bottles counts towards valuation",
                "Wines below their minimum bottle count raise a critical-stock alert",
            ],
        },
        {
            "type": "bullets",
            "title": "Duplicate and anomaly detection",
            "subtitle": "Data quality does not maintain itself",
            "items": [
                "The same barcode used on two different records",
                "Same producer + very similar name + same vintage (fuzzy match)",
                "Implausible vintage — a future year or more than 120 years old",
                "Price anomaly — selling price below purchase price",
                "**The system never deletes or merges anything on its own** — it only raises a review flag",
            ],
        },
        {"type": "section", "title": "Menu, Inventory and Costing", "subtitle": "The arithmetic of profit"},
        {
            "type": "bullets",
            "title": "Recipes and portion costing",
            "subtitle": "The real cost of every plate",
            "items": [
                "Recipe lines link to stock items",
                "Portion cost is derived from the **weighted average** unit cost of stock",
                "A waste allowance percentage is added to the cost",
                "Gross margin, margin percentage and **food-cost ratio** are automatic",
                "Allergen and dietary tags (vegetarian, vegan, gluten-free) attach to items",
                "Dynamic pricing: happy hour, campaigns, windows that cross midnight",
            ],
        },
        {
            "type": "table",
            "title": "Menu engineering",
            "subtitle": "What stays, what changes?",
            "columns": ["Quadrant", "Popularity", "Margin", "Action"],
            "rows": [
                ["Star", "High", "High", "Protect and promote"],
                ["Plowhorse", "High", "Low", "Reduce cost or revisit price"],
                ["Puzzle", "Low", "High", "Promote; add to sommelier picks"],
                ["Dog", "Low", "Low", "Consider removing from the menu"],
            ],
            "note": "Kasavana-Smith method · computed automatically from sales data",
        },
        {
            "type": "bullets",
            "title": "Inventory, purchasing and waste",
            "subtitle": "Full traceability from receipt to issue",
            "items": [
                "FIFO or FEFO — chosen per item",
                "Alerts for lots approaching their expiry date",
                "Goods receipt: partial rejection, cold-chain check, automatic lot creation",
                "Stock counts: system versus counted, variance posted as a **movement**",
                "Waste records with 11 reasons: spoilage, expiry, breakage, spillage, staff meals…",
                "Reorder suggestions from minimum levels — **the system suggests, never orders**",
                "Quotation comparison: cheapest and fastest flagged separately",
            ],
        },
        {
            "type": "bullets",
            "title": "Stock movements are immutable",
            "subtitle": "The balance is always verifiable",
            "items": [
                "Every receipt and issue creates its own movement record",
                "Once written it **cannot be updated or deleted** — enforced in code",
                "Corrections are made with a reversing movement",
                "Stock balance can always be reconciled against the sum of movements",
                "The same immutability applies to loyalty points and the audit log",
            ],
        },
        {"type": "section", "title": "Customers, Staff and Reports"},
        {
            "type": "bullets",
            "title": "GDPR-compliant customer management",
            "subtitle": "Data protection is not an afterthought",
            "items": [
                "Phone, email and identity data are stored **encrypted**",
                "Search over encrypted fields uses an irreversible HMAC digest",
                "**Separate consent per purpose**: service, email, SMS, profiling, AI processing",
                "Withdrawing consent does not delete the record — a withdrawal timestamp is written for proof",
                "Data portability: a customer's entire record exports in one click",
                "Right to erasure: personal data is anonymised, **financial records retained by law**",
                "Birth **year** is not stored — only day and month (data minimisation)",
            ],
        },
        {
            "type": "bullets",
            "title": "13 reports · 3 formats",
            "subtitle": "With guaranteed Turkish character rendering",
            "items": [
                "Sales: daily summary · products and categories · payment mix · forecast",
                "Wine: profitability · glass vs bottle · cellar valuation",
                "Inventory: waste analysis · stock valuation",
                "Operations: table turnover · staff performance · menu engineering",
                "AI: cost and token usage",
                "**PDF · Excel · CSV** — ç ğ ı İ ö ş ü render correctly in all three",
            ],
        },
        {
            "type": "table",
            "title": "How Turkish characters are guaranteed",
            "subtitle": "Where most systems break silently",
            "columns": ["Format", "The problem", "Wine House solution"],
            "rows": [
                ["CSV", "Excel opens the file with the wrong encoding", "Written with a UTF-8 BOM; survives a double-click"],
                ["Excel", "Numbers written as text", "Numbers stay numeric; locale-aware number and date formats"],
                ["PDF", "Built-in fonts do not cover Turkish", "A system TrueType font is located and **embedded**"],
                ["PDF (no font)", "Silently corrupt output", "An explicit error is raised — no broken PDF is produced"],
            ],
        },
        {"type": "section", "title": "Artificial Intelligence", "subtitle": "An assistant, not an authority"},
        {
            "type": "bullets",
            "title": "Provider-agnostic architecture",
            "subtitle": "Never locked to a single vendor",
            "items": [
                "**LM Studio** (local) · **Anthropic Claude** · **NVIDIA** · **Mock** (offline testing)",
                "Model names are never hard-coded — always read **live** from the provider",
                "Task-aware model selection: chat, coding, vision, analytical, embedding",
                "Timeouts, retries, exponential backoff, request cancellation",
                "Fallback chain: if one provider fails, the next is tried",
                "**Mock always sits last** — the AI flow never brings the app down",
            ],
        },
        {
            "type": "compare",
            "title": "Privacy: what reaches the cloud?",
            "subtitle": "The user always sees it",
            "left_title": "Default behaviour",
            "left": [
                "The default provider is **local** LM Studio",
                "Customer data never leaves the premises",
                "`Local only` mode disables the cloud entirely",
                "Exceeding the monthly cost cap blocks cloud calls",
            ],
            "right_title": "If a cloud call is needed",
            "right": [
                "Email, phone, national ID, IBAN, card number are **masked**",
                "API keys are never transmitted under any circumstance",
                "The user sees **exactly what was sent** on screen",
                "A summary reports how many items of each type were masked",
            ],
        },
        {
            "type": "bullets",
            "title": "AI cannot write to the database",
            "subtitle": "A hard boundary",
            "items": [
                "Every suggestion is **persisted as a record** and awaits human approval",
                "No price, stock, menu item or pairing changes without that approval",
                "Sommelier suggestions are drawn only from wines **currently in stock**",
                "The system prompt explicitly forbids health claims and medical advice",
                "The 18+ limit and responsible consumption appear on every suggestion screen",
                "Every call is logged: provider, model, tokens, cost, latency, outcome",
            ],
        },
        {"type": "section", "title": "Security and Quality"},
        {
            "type": "table",
            "title": "19 roles · least privilege",
            "subtitle": "Everyone sees only their own job",
            "columns": ["Role", "Permissions", "Cannot do"],
            "rows": [
                ["Waiter", "18", "Cellar management · user creation · day close"],
                ["Sommelier", "41", "Day close · taking payment · staff management"],
                ["Cashier", "12", "Menu changes · stock adjustments"],
                ["Auditor", "101", "**No write operations at all**"],
                ["System administrator", "519", "—"],
            ],
        },
        {
            "type": "bullets",
            "title": "Second approval and audit log",
            "subtitle": "Separation of duties",
            "items": [
                "Critical operations need approval: voids, refunds, over-limit discounts, comps, stock adjustments, restores",
                "**A user cannot approve their own request**",
                "Without approval the operation is not applied — a request is raised and the process stops",
                "The audit log is **immutable and undeletable** — enforced in code",
                "Permission denials are logged too; unauthorised attempts are traceable",
                "Records past their retention period are archived before removal",
            ],
        },
        {
            "type": "bullets",
            "title": "Backup and restore",
            "subtitle": "A backup is not a backup until a restore is proven",
            "items": [
                "Encrypted ZIP archive + SHA-256 integrity digest",
                "Every backup is **verified automatically** after creation",
                "Restores require second approval",
                "An **automatic safety backup** is taken before writing to the live database",
                "The default target is the test database — drills are possible",
                "The retention policy **always keeps at least three backups**",
                "Daily automated backup via Windows Task Scheduler",
            ],
        },
        {
            "type": "stats",
            "title": "Quality indicators",
            "subtitle": "Measured and reported",
            "items": [
                ("380", "tests · all passing"),
                ("73%", "line coverage (all code)"),
                ("0", "known runtime dependency vulnerabilities"),
                ("0", "high/medium static-analysis findings"),
                ("0", "secret-scan findings"),
                ("23", "database migrations"),
            ],
            "note": "All figures are measured from the repository at release time: "
            "pytest, coverage, pip-audit/osv-scanner (runtime dependencies), bandit and "
            "semgrep (medium+), gitleaks. Details: PUBLIC_RELEASE_MANIFEST.json",
        },
        {
            "type": "table",
            "title": "Technical profile",
            "columns": ["Layer", "Choice"],
            "rows": [
                ["Language / framework", "Python 3.11+ · Django 5.2 · Django REST Framework"],
                ["Database", "SQLite (WAL) · optional PostgreSQL"],
                ["Interface", "Bootstrap 5.3 + HTMX — **bundled locally, no CDN**"],
                ["Encryption", "Fernet (AES-128-CBC + HMAC-SHA256)"],
                ["Reporting", "ReportLab (PDF) · openpyxl (Excel)"],
                ["Artificial intelligence", "Custom httpx-based adapter layer"],
                ["Installation", "A single PowerShell script · double-clickable .bat files"],
            ],
        },
        {
            "type": "compare",
            "title": "An honest status report",
            "subtitle": "No unfinished feature is presented as finished",
            "left_title": "Ready and working",
            "left": [
                "Floor operations · KDS · payment · day close",
                "Wine cellar · by-the-glass service · yield analysis",
                "Inventory · purchasing · waste · stock counts",
                "CRM · GDPR · staff · 13 reports",
                "AI layer · backups · 19 roles",
            ],
            "right_title": "Experimental or planned",
            "right": [
                "Live payment and e-invoicing (adapter only)",
                "Thermal printer driver",
                "Bulk email/SMS dispatch",
                "Cellar sensor integration",
                "Label image analysis · multi-terminal sync",
            ],
            "note": "Every feature carries a badge in the application: Ready · Experimental · Planned",
        },
        {
            "type": "closing",
            "title": "Wine House",
            "subtitle": "Smart Wine Restaurant Management System",
            "items": [
                "Runs locally · resilient offline",
                "Freezes financial records and leaves an audit trail",
                "Deducts by-the-glass sales from stock correctly",
                "Makes AI an assistant, never an authority",
                "Encrypts and masks personal data",
            ],
            "meta": f"Version {VERSION} · 2026",
        },
    ],
}

# ---------------------------------------------------------------------------
# EKRAN GÖRÜNTÜSÜ GALERİSİ
# ---------------------------------------------------------------------------
# Görseller ``docs/screenshots/`` altındadır ve gerçek arayüzden
# ``scripts/capture_screenshots.py`` ile sentetik demo verisi kullanılarak
# alınmıştır. Galeri, kapanış slaytından hemen önce her iki desteye eklenir.

_SHOTS: list[tuple[str, str, str, str, str]] = [
    # (dosya, TR başlık, TR açıklama, EN başlık, EN açıklama)
    (
        "login",
        "Giriş ekranı",
        "Parola veya hızlı PIN girişi · rol tabanlı yetkilendirme 19 rolle başlar",
        "Sign-in screen",
        "Password or quick PIN sign-in · role-based access starts with 19 roles",
    ),
    (
        "dashboard",
        "Ana panel",
        "Masa durumu, açık adisyon, rezervasyon, kav ve satış özetleri tek bakışta; "
        "deneysel özellikler açıkça rozetlenir",
        "Main dashboard",
        "Tables, open orders, reservations, cellar and sales at a glance; "
        "experimental features are clearly badged",
    ),
    (
        "masa-plani",
        "Masa planı",
        "Bölüm bazlı canlı masa durumu ve açık adisyon bağlantıları",
        "Table map",
        "Live table status by section with links to open orders",
    ),
    (
        "adisyonlar",
        "Adisyonlar",
        "Fiyat dondurma, satır iptali, indirim/ikram ve onay akışıyla sipariş yönetimi",
        "Orders",
        "Order management with price freezing, line voids, discounts and approvals",
    ),
    (
        "rezervasyonlar",
        "Rezervasyonlar",
        "Çakışma denetimi, kapasite kontrolü ve bekleme listesi",
        "Reservations",
        "Conflict checking, capacity control and waitlist",
    ),
    (
        "kds-mutfak",
        "Mutfak ekranı (KDS)",
        "İstasyon ayrımı, fiş ilerletme, gecikme uyarısı ve alerjen gösterimi",
        "Kitchen display (KDS)",
        "Station separation, ticket progression, delay warnings and allergen flags",
    ),
    (
        "sarap-kavi",
        "Şarap kavı",
        "Şişe/kadeh stoğu, içim aralığı ve fiyatlandırma; sorumlu servis uyarısı her listede",
        "Wine cellar",
        "Bottle and by-the-glass stock, drinking windows and pricing",
    ),
    (
        "kav-degerleme",
        "Kav değerlemesi",
        "Maliyet ve satış değeri üzerinden kavın anlık finansal görünümü",
        "Cellar valuation",
        "Financial snapshot of the cellar at cost and list value",
    ),
    (
        "menu",
        "Menü ve reçete",
        "Porsiyon maliyeti, alerjen ve beslenme etiketiyle menü yönetimi",
        "Menu and recipes",
        "Menu management with portion cost, allergens and nutrition labels",
    ),
    (
        "stok",
        "Stok ve satın alma",
        "FIFO/FEFO parti takibi, mal kabul, sayım ve fire akışları",
        "Inventory and purchasing",
        "FIFO/FEFO lot tracking, receiving, stock counts and waste flows",
    ),
    (
        "crm",
        "Müşteri ilişkileri",
        "Rıza yönetimi, dışa aktarım, anonimleştirme ve sadakat — KVKK akışları yerleşik",
        "Customer relations",
        "Consent management, export, anonymisation and loyalty — GDPR flows built in",
    ),
    (
        "raporlar",
        "Raporlar",
        "13 hazır rapor · PDF, Excel ve CSV dışa aktarım",
        "Reports",
        "13 ready-made reports · PDF, Excel and CSV export",
    ),
    (
        "yapay-zeka",
        "Yapay zekâ asistanı",
        "Yerel öncelikli sağlayıcılar, maskeleme ve bütçe denetimi; öneri üretir, karar vermez",
        "AI assistant",
        "Local-first providers, masking and budget control; it advises, never decides",
    ),
    (
        "egitim",
        "Eğitim merkezi",
        "Rol bazlı modül ve ders yapısıyla personel eğitimi",
        "Training centre",
        "Role-based staff training modules and lessons",
    ),
]

_GALLERY_SECTION = {
    "tr": {
        "type": "section",
        "title": "Uygulamadan Ekranlar",
        "subtitle": "Gerçek arayüz · sentetik demo verisi · v" + VERSION,
    },
    "en": {
        "type": "section",
        "title": "Screens from the Application",
        "subtitle": "Real interface · synthetic demo data · v" + VERSION
        + " · UI shown in Turkish (EN toggle built in)",
    },
}


def _gallery(lang: str) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = [_GALLERY_SECTION[lang]]
    for stem, title_tr, caption_tr, title_en, caption_en in _SHOTS:
        slides.append(
            {
                "type": "screenshot",
                "title": title_tr if lang == "tr" else title_en,
                "image": f"docs/screenshots/{stem}.png",
                "caption": caption_tr if lang == "tr" else caption_en,
            }
        )
    return slides


TR["slides"][-1:-1] = _gallery("tr")
EN["slides"][-1:-1] = _gallery("en")

DECKS = {"tr": TR, "en": EN}
