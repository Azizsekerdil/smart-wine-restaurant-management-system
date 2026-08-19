"""Sentetik demo verisi yükler.

TÜM VERİLER UYDURMADIR. Gerçek müşteri, personel veya tedarikçi bilgisi
içermez; geliştirme ve kabul testleri içindir.

Kullanım::

    python manage.py seed_demo            # temel veri
    python manage.py seed_demo --with-sales  # geçmiş satış hareketi de üretir
"""

from __future__ import annotations

import contextlib
import random
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

SEED = 20260818  # Belirlenimci veri için sabit tohum

# ---------------------------------------------------------------------------
# Örnek iletişim bilgileri
# ---------------------------------------------------------------------------
# Örnek veri hiçbir gerçek kişiye ait değildir ve ARANAMAZ. Numaralar bilerek
# geçersiz biçimdedir (abone hanelerinde "X" bulunur), böylece ekran
# görüntüsü, sunum veya demo veritabanı paylaşıldığında yanlışlıkla gerçek
# bir aboneye ulaşılamaz.
DEMO_PHONE_PREFIX = "+90 5XX XXX"
DEMO_SUPPLIER_PHONE = f"{DEMO_PHONE_PREFIX} XX 00"


def demo_phone(index: int) -> str:
    """Örnek müşteri için aranamaz, açıkça kurgusal telefon üretir."""
    return f"{DEMO_PHONE_PREFIX} XX {index:02d}"


class Command(BaseCommand):
    help = "Geliştirme ve test için sentetik örnek veri yükler (gerçek veri içermez)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--with-sales",
            action="store_true",
            help="Geçmiş adisyon ve satış hareketleri de üretir.",
        )
        parser.add_argument(
            "--days", type=int, default=14, help="Kaç günlük satış geçmişi üretilsin."
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        random.seed(SEED)
        self.stdout.write(self.style.MIGRATE_HEADING("Sentetik demo verisi yükleniyor…"))

        self._seed_feature_flags()
        units = self._seed_units()
        warehouse = self._seed_warehouses()
        suppliers = self._seed_suppliers()
        allergens, tags = self._seed_allergens()
        categories = self._seed_menu_categories()
        stock_items = self._seed_stock_items(units, suppliers, warehouse)
        regions, grapes, producers = self._seed_wine_reference()
        locations = self._seed_storage_locations()
        wines = self._seed_wines(regions, grapes, producers, suppliers, locations)
        self._seed_menu_items(categories, allergens, tags, stock_items, wines)
        self._seed_floor()
        self._seed_payment_methods()
        self._seed_customers()
        self._seed_reporting_definitions()

        if options["with_sales"]:
            self._seed_sales(days=options["days"])

        self.stdout.write(self.style.SUCCESS("\nDemo verisi yüklendi."))
        self.stdout.write(
            "UYARI: Bu veriler tamamen sentetiktir ve gerçek kişi/kurum bilgisi içermez."
        )

    # -- Özellik bayrakları -------------------------------------------------
    def _seed_feature_flags(self) -> None:
        from apps.core.models import FeatureFlag

        flags = [
            ("table-map", "Masa planı", "operations", FeatureFlag.Status.READY),
            (
                "reservations",
                "Rezervasyon ve bekleme listesi",
                "operations",
                FeatureFlag.Status.READY,
            ),
            ("kds", "Mutfak ekranı (KDS)", "operations", FeatureFlag.Status.READY),
            ("order-flow", "Sipariş ve KOT akışı", "operations", FeatureFlag.Status.READY),
            ("split-bill", "Hesap bölme", "operations", FeatureFlag.Status.READY),
            ("payments-sandbox", "Ödeme (sandbox)", "operations", FeatureFlag.Status.EXPERIMENTAL),
            ("payments-live", "Canlı ödeme entegrasyonu", "operations", FeatureFlag.Status.PLANNED),
            (
                "einvoice",
                "e-Fatura / e-Arşiv entegrasyonu",
                "operations",
                FeatureFlag.Status.PLANNED,
            ),
            ("thermal-printer", "Termal yazıcı adaptörü", "operations", FeatureFlag.Status.PLANNED),
            (
                "offline-sync",
                "Çok terminalli çevrimdışı senkronizasyon",
                "operations",
                FeatureFlag.Status.EXPERIMENTAL,
            ),
            ("cellar", "Dijital şarap kavı", "cellar", FeatureFlag.Status.READY),
            ("glass-pour", "Kadeh servisi ve verim takibi", "cellar", FeatureFlag.Status.READY),
            ("wine-faults", "Şarap kusuru kaydı", "cellar", FeatureFlag.Status.READY),
            ("duplicate-detection", "Mükerrer kayıt tespiti", "cellar", FeatureFlag.Status.READY),
            ("storage-sensors", "Kav sensör entegrasyonu", "cellar", FeatureFlag.Status.PLANNED),
            ("inventory", "Stok ve FEFO", "inventory", FeatureFlag.Status.READY),
            (
                "purchasing",
                "Satın alma ve teklif karşılaştırma",
                "inventory",
                FeatureFlag.Status.READY,
            ),
            ("reports", "Raporlar ve dışa aktarım", "reporting", FeatureFlag.Status.READY),
            ("forecast", "Satış tahmini", "reporting", FeatureFlag.Status.EXPERIMENTAL),
            ("ai-local", "LM Studio yerel yapay zekâ", "ai", FeatureFlag.Status.READY),
            ("ai-cloud", "Bulut yapay zekâ (Claude/NVIDIA)", "ai", FeatureFlag.Status.EXPERIMENTAL),
            ("ai-vision", "Etiket görsel analizi", "ai", FeatureFlag.Status.PLANNED),
            ("devstudio", "AI Development Studio", "devstudio", FeatureFlag.Status.EXPERIMENTAL),
            ("caio", "CAIO kalite ajanı", "caio", FeatureFlag.Status.EXPERIMENTAL),
            ("backup", "Yedekleme ve geri yükleme", "backups", FeatureFlag.Status.READY),
            ("training", "Eğitim merkezi", "training", FeatureFlag.Status.READY),
            ("campaign-dispatch", "Toplu e-posta/SMS gönderimi", "crm", FeatureFlag.Status.PLANNED),
        ]
        for code, name, module, status in flags:
            FeatureFlag.objects.update_or_create(
                code=code, defaults={"name": name, "module": module, "status": status}
            )
        self.stdout.write(f"  · {len(flags)} özellik bayrağı")

    # -- Stok referansları --------------------------------------------------
    def _seed_units(self) -> dict[str, Any]:
        from apps.inventory.models import UnitOfMeasure

        definitions = [
            ("g", "Gram", "mass", "1"),
            ("kg", "Kilogram", "mass", "1000"),
            ("ml", "Mililitre", "volume", "1"),
            ("lt", "Litre", "volume", "1000"),
            ("adet", "Adet", "count", "1"),
            ("şişe", "Şişe", "count", "1"),
        ]
        units = {}
        for code, name, dimension, factor in definitions:
            unit, _ = UnitOfMeasure.objects.update_or_create(
                code=code,
                defaults={"name": name, "dimension": dimension, "factor_to_base": Decimal(factor)},
            )
            units[code] = unit
        return units

    def _seed_warehouses(self) -> Any:
        from apps.inventory.models import Warehouse

        main, _ = Warehouse.objects.update_or_create(
            code="ANA", defaults={"name": "Ana Depo", "is_default": True}
        )
        Warehouse.objects.update_or_create(code="MUTFAK", defaults={"name": "Mutfak Deposu"})
        Warehouse.objects.update_or_create(code="BAR", defaults={"name": "Bar Deposu"})
        Warehouse.objects.update_or_create(code="KAV", defaults={"name": "Şarap Kavı"})
        return main

    def _seed_suppliers(self) -> list[Any]:
        from apps.inventory.models import Supplier

        data = [
            ("TED001", "Anadolu Gıda Tedarik A.Ş.", False, 30, 2),
            ("TED002", "Ege Sebze Meyve Ltd.", False, 15, 1),
            ("TED003", "Trakya Şarap İthalat A.Ş.", True, 45, 5),
            ("TED004", "Kapadokya Bağcılık Koop.", True, 30, 7),
            ("TED005", "Deniz Ürünleri Tedarik", False, 7, 1),
        ]
        suppliers = []
        for code, name, wine, terms, lead in data:
            supplier, _ = Supplier.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "supplies_wine": wine,
                    "payment_terms_days": terms,
                    "lead_time_days": lead,
                    "contact_person": "Yetkili Kişi",
                    "phone": DEMO_SUPPLIER_PHONE,
                    "email": f"{code.lower()}@ornek-tedarikci.test",
                },
            )
            suppliers.append(supplier)
        self.stdout.write(f"  · {len(suppliers)} tedarikçi")
        return suppliers

    def _seed_allergens(self) -> tuple[dict[str, Any], dict[str, Any]]:
        from apps.catalog.models import Allergen, DietaryTag

        allergen_data = [
            ("gluten", "Gluten", "Gluten", "🌾"),
            ("sut", "Süt ürünleri", "Milk", "🥛"),
            ("yumurta", "Yumurta", "Egg", "🥚"),
            ("kabuklu-deniz", "Kabuklu deniz ürünleri", "Crustaceans", "🦐"),
            ("balik", "Balık", "Fish", "🐟"),
            ("findik-fistik", "Sert kabuklu yemişler", "Tree nuts", "🥜"),
            ("soya", "Soya", "Soy", "🫘"),
            ("susam", "Susam", "Sesame", "🌰"),
            ("sulfit", "Sülfit", "Sulphites", "🍷"),
            ("hardal", "Hardal", "Mustard", "🌭"),
        ]
        allergens = {}
        for code, name_tr, name_en, icon in allergen_data:
            obj, _ = Allergen.objects.update_or_create(
                code=code, defaults={"name_tr": name_tr, "name_en": name_en, "icon": icon}
            )
            allergens[code] = obj

        tag_data = [
            ("vejetaryen", "Vejetaryen", "Vegetarian", "bg-success"),
            ("vegan", "Vegan", "Vegan", "bg-success"),
            ("glutensiz", "Glutensiz", "Gluten-free", "bg-info text-dark"),
            ("laktozsuz", "Laktozsuz", "Lactose-free", "bg-info text-dark"),
            ("aci", "Acı", "Spicy", "bg-danger"),
        ]
        tags = {}
        for code, name_tr, name_en, badge in tag_data:
            obj, _ = DietaryTag.objects.update_or_create(
                code=code,
                defaults={"name_tr": name_tr, "name_en": name_en, "badge_class": badge},
            )
            tags[code] = obj

        self.stdout.write(f"  · {len(allergens)} alerjen, {len(tags)} beslenme etiketi")
        return allergens, tags

    def _seed_menu_categories(self) -> dict[str, Any]:
        from apps.catalog.models import MenuCategory

        data = [
            ("baslangic", "Başlangıçlar", "Starters", "kitchen", 10),
            ("corba", "Çorbalar", "Soups", "kitchen", 20),
            ("ana-yemek", "Ana Yemekler", "Main Courses", "kitchen", 30),
            ("deniz", "Deniz Ürünleri", "Seafood", "kitchen", 40),
            ("tatli", "Tatlılar", "Desserts", "kitchen", 50),
            ("sarap-kirmizi", "Kırmızı Şaraplar", "Red Wines", "wine", 60),
            ("sarap-beyaz", "Beyaz Şaraplar", "White Wines", "wine", 70),
            ("sarap-kadeh", "Kadeh Şaraplar", "Wines by the Glass", "wine", 80),
            ("icecek", "İçecekler", "Beverages", "bar", 90),
            ("servis", "Servis Kalemleri", "Service Items", "none", 100),
        ]
        categories = {}
        for code, name_tr, name_en, station, order in data:
            obj, _ = MenuCategory.objects.update_or_create(
                code=code,
                defaults={
                    "name_tr": name_tr,
                    "name_en": name_en,
                    "preparation_station": station,
                    "sort_order": order,
                },
            )
            categories[code] = obj
        return categories

    def _seed_stock_items(self, units: dict, suppliers: list, warehouse: Any) -> dict[str, Any]:
        from apps.inventory.models import StockItem, StockItemCategory
        from apps.inventory.services import receive_stock

        category_data = [
            ("et", "Et ve Tavuk"),
            ("sebze", "Sebze ve Meyve"),
            ("sut", "Süt Ürünleri"),
            ("kuru", "Kuru Gıda"),
            ("deniz", "Deniz Ürünleri"),
            ("icecek", "İçecek"),
        ]
        categories = {}
        for code, name in category_data:
            obj, _ = StockItemCategory.objects.update_or_create(code=code, defaults={"name": name})
            categories[code] = obj

        item_data = [
            ("HM001", "Dana bonfile", "et", "g", "4.50", 5000, 30),
            ("HM002", "Kuzu but", "et", "g", "3.20", 4000, 20),
            ("HM003", "Tavuk göğsü", "et", "g", "1.80", 3000, 10),
            ("HM004", "Levrek", "deniz", "g", "3.80", 2000, 5),
            ("HM005", "Karides", "deniz", "g", "5.50", 1500, 5),
            ("HM006", "Tereyağı", "sut", "g", "0.85", 3000, 90),
            ("HM007", "Krema", "sut", "ml", "0.42", 4000, 30),
            ("HM008", "Parmesan", "sut", "g", "2.90", 1500, 180),
            ("HM009", "Domates", "sebze", "g", "0.28", 8000, 10),
            ("HM010", "Soğan", "sebze", "g", "0.18", 10000, 60),
            ("HM011", "Sarımsak", "sebze", "g", "0.55", 1000, 60),
            ("HM012", "Zeytinyağı", "kuru", "ml", "0.38", 10000, 365),
            ("HM013", "Un", "kuru", "g", "0.09", 20000, 180),
            ("HM014", "Pirinç", "kuru", "g", "0.14", 15000, 365),
            ("HM015", "Roka", "sebze", "g", "0.65", 1500, 5),
        ]

        items = {}
        for code, name, category, unit, cost, quantity, shelf_life in item_data:
            item, _ = StockItem.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": categories[category],
                    "unit": units[unit],
                    "minimum_quantity": Decimal(str(quantity)) * Decimal("0.2"),
                    "reorder_quantity": Decimal(str(quantity)),
                    "shelf_life_days": shelf_life,
                    "default_supplier": suppliers[0] if category != "deniz" else suppliers[4],
                    "tracking_mode": StockItem.TrackingMode.FEFO,
                },
            )
            items[code] = item
            if not item.lots.exists():
                receive_stock(
                    stock_item=item,
                    warehouse=warehouse,
                    quantity=Decimal(str(quantity)),
                    unit_cost=Decimal(cost),
                    user=None,
                    lot_code=f"DEMO-{code}",
                    supplier=item.default_supplier,
                )

        self.stdout.write(f"  · {len(items)} stok kalemi (açılış stoğuyla)")
        return items

    # -- Şarap referansları -------------------------------------------------
    def _seed_wine_reference(self) -> tuple[dict, dict, dict]:
        from apps.cellar.models import GrapeVariety, WineProducer, WineRegion

        turkey, _ = WineRegion.objects.get_or_create(
            name="Türkiye", parent=None, defaults={"level": "country", "country_code": "TR"}
        )
        france, _ = WineRegion.objects.get_or_create(
            name="Fransa", parent=None, defaults={"level": "country", "country_code": "FR"}
        )
        italy, _ = WineRegion.objects.get_or_create(
            name="İtalya", parent=None, defaults={"level": "country", "country_code": "IT"}
        )

        regions = {"tr": turkey, "fr": france, "it": italy}
        for key, name, parent in [
            ("trakya", "Trakya", turkey),
            ("ege", "Ege", turkey),
            ("kapadokya", "Kapadokya", turkey),
            ("elazig", "Elazığ-Diyarbakır", turkey),
            ("bordeaux", "Bordeaux", france),
            ("bourgogne", "Bourgogne", france),
            ("toscana", "Toscana", italy),
        ]:
            regions[key], _ = WineRegion.objects.get_or_create(
                name=name, parent=parent, defaults={"level": "region"}
            )

        grape_data = [
            ("Öküzgözü", "red", True),
            ("Boğazkere", "red", True),
            ("Kalecik Karası", "red", True),
            ("Narince", "white", True),
            ("Emir", "white", True),
            ("Cabernet Sauvignon", "red", False),
            ("Merlot", "red", False),
            ("Syrah", "red", False),
            ("Chardonnay", "white", False),
            ("Sauvignon Blanc", "white", False),
            ("Sangiovese", "red", False),
            ("Pinot Noir", "red", False),
        ]
        grapes = {}
        for name, color, indigenous in grape_data:
            grapes[name], _ = GrapeVariety.objects.get_or_create(
                name=name,
                defaults={"color": color, "is_indigenous_turkish": indigenous},
            )

        producer_data = [
            ("Bağ Evi Şarapçılık", "trakya"),
            ("Anadolu Terroir", "elazig"),
            ("Kapadokya Mahzen", "kapadokya"),
            ("Ege Tepeleri Bağları", "ege"),
            ("Château Demo", "bordeaux"),
            ("Domaine Örnek", "bourgogne"),
            ("Tenuta Esempio", "toscana"),
        ]
        producers = {}
        for name, region_key in producer_data:
            producers[name], _ = WineProducer.objects.get_or_create(
                name=name, region=regions[region_key]
            )

        return regions, grapes, producers

    def _seed_storage_locations(self) -> dict[str, Any]:
        from apps.cellar.models import StorageReading, WineStorageLocation

        cellar, _ = WineStorageLocation.objects.update_or_create(
            code="KAV",
            defaults={
                "name": "Ana Kav",
                "location_type": "cellar",
                "capacity_bottles": 1200,
                "target_temp_c": Decimal("13.0"),
                "target_humidity_percent": 70,
            },
        )
        locations = {"KAV": cellar}
        for code, name, kind, capacity, temp in [
            ("KAV-A", "A Rafı (Kırmızı)", "rack", 400, "14.0"),
            ("KAV-B", "B Rafı (Beyaz)", "rack", 300, "10.0"),
            ("KAV-C", "C Rafı (Köpüklü)", "rack", 150, "8.0"),
            ("VITRIN", "Salon Vitrini", "display", 60, "16.0"),
            ("SERVIS", "Servis Dolabı", "service", 40, "12.0"),
        ]:
            locations[code], _ = WineStorageLocation.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "location_type": kind,
                    "parent": cellar,
                    "capacity_bottles": capacity,
                    "target_temp_c": Decimal(temp),
                    "target_humidity_percent": 70,
                },
            )

        # Son 7 günün ölçümleri (biri kasıtlı olarak aralık dışında)
        now = timezone.now()
        for location in locations.values():
            for day in range(7):
                drift = Decimal(str(round(random.uniform(-1.2, 1.2), 1)))
                if day == 2 and location.code == "KAV-A":
                    drift = Decimal("4.5")  # uyarı üretecek sapma
                StorageReading.objects.get_or_create(
                    location=location,
                    recorded_at=now - timezone.timedelta(days=day, hours=8),
                    defaults={
                        "temperature_c": location.target_temp_c + drift,
                        "humidity_percent": Decimal(str(random.randint(62, 78))),
                        "source": "manual",
                    },
                )
        self.stdout.write(f"  · {len(locations)} kav konumu ve sıcaklık ölçümleri")
        return locations

    def _seed_wines(
        self, regions: dict, grapes: dict, producers: dict, suppliers: list, locations: dict
    ) -> list[Any]:
        from apps.cellar.models import BottleLot, Wine, WineGrapeComposition

        data = [
            # (sku, ad, üretici, bölge, rekolte, tür, alkol, alış, şişe, kadeh, kadeh_satış, üzümler, konum)
            (
                "SR001",
                "Öküzgözü Rezerv",
                "Anadolu Terroir",
                "elazig",
                2020,
                "red",
                "13.5",
                "320",
                "1250",
                "260",
                True,
                [("Öküzgözü", 100)],
                "KAV-A",
            ),
            (
                "SR002",
                "Boğazkere Klasik",
                "Anadolu Terroir",
                "elazig",
                2019,
                "red",
                "14.0",
                "380",
                "1450",
                "0",
                False,
                [("Boğazkere", 100)],
                "KAV-A",
            ),
            (
                "SR003",
                "Kalecik Karası",
                "Kapadokya Mahzen",
                "kapadokya",
                2021,
                "red",
                "13.0",
                "240",
                "980",
                "210",
                True,
                [("Kalecik Karası", 100)],
                "KAV-A",
            ),
            (
                "SR004",
                "Narince Fıçı",
                "Kapadokya Mahzen",
                "kapadokya",
                2022,
                "white",
                "12.5",
                "260",
                "1050",
                "230",
                True,
                [("Narince", 100)],
                "KAV-B",
            ),
            (
                "SR005",
                "Emir Taze",
                "Kapadokya Mahzen",
                "kapadokya",
                2023,
                "white",
                "12.0",
                "180",
                "760",
                "170",
                True,
                [("Emir", 100)],
                "KAV-B",
            ),
            (
                "SR006",
                "Trakya Kupaj",
                "Bağ Evi Şarapçılık",
                "trakya",
                2020,
                "red",
                "13.8",
                "290",
                "1180",
                "0",
                False,
                [("Cabernet Sauvignon", 60), ("Merlot", 40)],
                "KAV-A",
            ),
            (
                "SR007",
                "Ege Beyaz",
                "Ege Tepeleri Bağları",
                "ege",
                2022,
                "white",
                "12.8",
                "220",
                "890",
                "195",
                True,
                [("Sauvignon Blanc", 70), ("Chardonnay", 30)],
                "KAV-B",
            ),
            (
                "SR008",
                "Bordeaux Rouge",
                "Château Demo",
                "bordeaux",
                2018,
                "red",
                "13.5",
                "820",
                "3200",
                "0",
                False,
                [("Cabernet Sauvignon", 55), ("Merlot", 45)],
                "KAV-A",
            ),
            (
                "SR009",
                "Bourgogne Blanc",
                "Domaine Örnek",
                "bourgogne",
                2021,
                "white",
                "13.0",
                "760",
                "2950",
                "0",
                False,
                [("Chardonnay", 100)],
                "KAV-B",
            ),
            (
                "SR010",
                "Chianti Classico",
                "Tenuta Esempio",
                "toscana",
                2020,
                "red",
                "13.5",
                "540",
                "2100",
                "440",
                True,
                [("Sangiovese", 100)],
                "KAV-A",
            ),
            (
                "SR011",
                "Roze Yaz",
                "Bağ Evi Şarapçılık",
                "trakya",
                2023,
                "rose",
                "12.5",
                "200",
                "820",
                "180",
                True,
                [("Öküzgözü", 60), ("Merlot", 40)],
                "KAV-B",
            ),
            (
                "SR012",
                "Köpüklü Brut",
                "Bağ Evi Şarapçılık",
                "trakya",
                None,
                "sparkling",
                "12.0",
                "340",
                "1380",
                "290",
                True,
                [("Chardonnay", 50), ("Pinot Noir", 50)],
                "KAV-C",
            ),
        ]

        wine_supplier = next((s for s in suppliers if s.supplies_wine), suppliers[0])
        wines = []

        for (
            sku,
            name,
            producer,
            region,
            vintage,
            wine_type,
            alcohol,
            purchase,
            bottle,
            glass,
            by_glass,
            composition,
            location_code,
        ) in data:
            serving = {
                "red": ("16", "18"),
                "white": ("8", "12"),
                "rose": ("8", "10"),
                "sparkling": ("6", "8"),
            }.get(wine_type, ("12", "16"))

            wine, _ = Wine.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "producer": producers[producer],
                    "region": regions[region],
                    "vintage": vintage,
                    "wine_type": wine_type,
                    "alcohol_percent": Decimal(alcohol),
                    "purchase_price": Decimal(purchase),
                    "bottle_price": Decimal(bottle),
                    "glass_price": Decimal(glass),
                    "sold_by_glass": by_glass,
                    "glass_pour_ml": 150,
                    "serving_temp_min_c": Decimal(serving[0]),
                    "serving_temp_max_c": Decimal(serving[1]),
                    "decant_minutes": 45 if wine_type == "red" and (vintage or 2024) < 2021 else 0,
                    "body": 4 if wine_type == "red" else 2,
                    "acidity": 3 if wine_type == "red" else 4,
                    "tannin": 4 if wine_type == "red" else 1,
                    "drink_from_year": (vintage + 2) if vintage else None,
                    "drink_until_year": (vintage + 8) if vintage else None,
                    "peak_year": (vintage + 5) if vintage else None,
                    "minimum_bottles": 6,
                    "barcode": f"869{sku[2:]}00000",
                    "aroma_profile": (
                        ["kırmızı meyve", "baharat", "vanilya"]
                        if wine_type == "red"
                        else ["turunçgil", "beyaz çiçek", "mineral"]
                    ),
                },
            )
            for grape_name, percentage in composition:
                WineGrapeComposition.objects.update_or_create(
                    wine=wine,
                    grape=grapes[grape_name],
                    defaults={"percentage": Decimal(str(percentage))},
                )
            BottleLot.objects.update_or_create(
                wine=wine,
                lot_code=f"LOT-{sku}",
                defaults={
                    "supplier": wine_supplier,
                    "location": locations.get(location_code),
                    "bottles_received": 24,
                    "bottles_remaining": 24,
                    "unit_cost": Decimal(purchase),
                    "received_on": timezone.localdate() - timezone.timedelta(days=90),
                },
            )
            wines.append(wine)

        self.stdout.write(f"  · {len(wines)} şarap (her biri 24 şişe stoklu)")
        return wines

    def _seed_menu_items(
        self, categories: dict, allergens: dict, tags: dict, stock_items: dict, wines: list
    ) -> None:
        from apps.catalog.models import MenuItem, Recipe, RecipeLine

        food_data = [
            (
                "YMK001",
                "Mevsim Salatası",
                "baslangic",
                "180",
                10,
                ["vejetaryen", "glutensiz"],
                [],
                [("HM015", 120), ("HM009", 80), ("HM012", 15)],
            ),
            (
                "YMK002",
                "Karides Güveç",
                "baslangic",
                "420",
                18,
                [],
                ["kabuklu-deniz", "sut"],
                [("HM005", 150), ("HM006", 30), ("HM011", 10)],
            ),
            (
                "YMK003",
                "Mercimek Çorbası",
                "corba",
                "160",
                8,
                ["vejetaryen"],
                ["gluten"],
                [("HM010", 60), ("HM013", 20)],
            ),
            (
                "YMK004",
                "Dana Bonfile",
                "ana-yemek",
                "890",
                25,
                [],
                ["sut"],
                [("HM001", 220), ("HM006", 40)],
            ),
            (
                "YMK005",
                "Kuzu Tandır",
                "ana-yemek",
                "760",
                35,
                [],
                [],
                [("HM002", 280), ("HM010", 100)],
            ),
            (
                "YMK006",
                "Tavuk Sote",
                "ana-yemek",
                "480",
                20,
                [],
                ["sut"],
                [("HM003", 200), ("HM007", 60)],
            ),
            (
                "YMK007",
                "Fırında Levrek",
                "deniz",
                "720",
                22,
                [],
                ["balik"],
                [("HM004", 250), ("HM012", 20)],
            ),
            (
                "YMK008",
                "Risotto",
                "ana-yemek",
                "520",
                25,
                ["vejetaryen"],
                ["sut"],
                [("HM014", 150), ("HM008", 40), ("HM006", 30)],
            ),
            (
                "YMK009",
                "Sufle",
                "tatli",
                "260",
                15,
                ["vejetaryen"],
                ["gluten", "sut", "yumurta"],
                [("HM006", 40), ("HM013", 50)],
            ),
            ("YMK010", "Kahve", "icecek", "120", 5, ["vegan"], [], []),
        ]

        for (
            code,
            name,
            category,
            price,
            minutes,
            tag_codes,
            allergen_codes,
            recipe_lines,
        ) in food_data:
            item, _ = MenuItem.objects.update_or_create(
                code=code,
                defaults={
                    "name_tr": name,
                    "category": categories[category],
                    "item_type": "drink" if category == "icecek" else "food",
                    "base_price": Decimal(price),
                    "tax_rate": Decimal("10.00"),
                    "preparation_minutes": minutes,
                    "is_chef_recommendation": code in {"YMK004", "YMK007"},
                },
            )
            item.dietary_tags.set([tags[code_] for code_ in tag_codes if code_ in tags])
            item.allergens.set([allergens[code_] for code_ in allergen_codes if code_ in allergens])

            if recipe_lines:
                recipe, _ = Recipe.objects.update_or_create(
                    menu_item=item, defaults={"yield_portions": Decimal("1.00")}
                )
                for stock_code, quantity in recipe_lines:
                    RecipeLine.objects.update_or_create(
                        recipe=recipe,
                        stock_item=stock_items[stock_code],
                        defaults={"quantity": Decimal(str(quantity))},
                    )
                item.recalculate_cost()

        # Şarap menü kalemleri
        for wine in wines:
            category = (
                categories["sarap-kirmizi"]
                if wine.wine_type == "red"
                else categories["sarap-beyaz"]
            )
            MenuItem.objects.update_or_create(
                code=f"SM-{wine.sku}",
                defaults={
                    "name_tr": f"{wine.producer.name} {wine.name} {wine.display_vintage}",
                    "category": category,
                    "item_type": "wine",
                    "wine": wine,
                    "base_price": wine.bottle_price,
                    "tax_rate": Decimal("20.00"),
                    "cost_price": wine.purchase_price,
                    "cost_is_manual": True,
                    "tracks_stock": False,
                    "is_sommelier_recommendation": wine.sku in {"SR001", "SR010"},
                },
            )
            if wine.sold_by_glass:
                MenuItem.objects.update_or_create(
                    code=f"SK-{wine.sku}",
                    defaults={
                        "name_tr": f"{wine.name} {wine.display_vintage} (kadeh)",
                        "category": categories["sarap-kadeh"],
                        "item_type": "wine_glass",
                        "wine": wine,
                        "base_price": wine.glass_price,
                        "tax_rate": Decimal("20.00"),
                        "cost_price": (
                            wine.purchase_price
                            * Decimal(wine.glass_pour_ml)
                            / Decimal(wine.bottle_size_ml)
                        ).quantize(Decimal("0.01")),
                        "cost_is_manual": True,
                        "tracks_stock": False,
                    },
                )

        self.stdout.write(f"  · {MenuItem.objects.count()} menü ürünü (reçeteli)")

    def _seed_floor(self) -> None:
        from apps.operations.models import DiningTable, FloorSection

        sections = [
            ("SALON", "Ana Salon", False, 12),
            ("TERAS", "Teras", True, 8),
            ("KAV-ODA", "Kav Odası", False, 3),
            ("BAR", "Bar", False, 6),
        ]
        total = 0
        for index, (code, name, outdoor, table_count) in enumerate(sections):
            section, _ = FloorSection.objects.update_or_create(
                code=code,
                defaults={"name": name, "is_outdoor": outdoor, "sort_order": index * 10},
            )
            for number in range(1, table_count + 1):
                DiningTable.objects.update_or_create(
                    section=section,
                    number=f"{code[0]}{number}",
                    defaults={
                        "seats": random.choice([2, 2, 4, 4, 4, 6, 8]),
                        "position_x": Decimal(str(round((number % 4) * 24 + 8, 2))),
                        "position_y": Decimal(str(round((number // 4) * 22 + 10, 2))),
                        "shape": random.choice(["square", "round", "rect"]),
                        "qr_token": f"qr-{code.lower()}-{number}",
                    },
                )
                total += 1
        self.stdout.write(f"  · {len(sections)} salon bölümü, {total} masa")

    def _seed_payment_methods(self) -> None:
        from apps.operations.models import PaymentMethod

        data = [
            ("NAKIT", "Nakit", "cash", False, True, "0.00", 10),
            ("KART", "Kredi/Banka Kartı", "card", True, False, "1.80", 20),
            ("YEMEK", "Yemek Kartı", "meal_card", True, False, "4.50", 30),
            ("HAVALE", "Havale/EFT", "transfer", True, False, "0.00", 40),
            ("HEDIYE", "Hediye Çeki", "voucher", True, False, "0.00", 50),
            ("PUAN", "Sadakat Puanı", "loyalty", False, False, "0.00", 60),
        ]
        for code, name, kind, reference, drawer, commission, order in data:
            PaymentMethod.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "kind": kind,
                    "requires_reference": reference,
                    "opens_cash_drawer": drawer,
                    "commission_percent": Decimal(commission),
                    "sort_order": order,
                },
            )
        self.stdout.write(f"  · {len(data)} ödeme yöntemi")

    def _seed_customers(self) -> None:
        from apps.crm.models import ConsentRecord, Customer, LoyaltyAccount, LoyaltyProgram

        program, _ = LoyaltyProgram.objects.update_or_create(
            name="Wine House Kulüp",
            defaults={
                "points_per_currency": Decimal("1.0000"),
                "currency_per_point": Decimal("0.0100"),
                "minimum_redeem_points": 500,
            },
        )

        names = [
            ("Deniz", "Yılmaz", "vip"),
            ("Ayla", "Demir", "regular"),
            ("Kerem", "Şahin", "regular"),
            ("Elif", "Çelik", "new"),
            ("Mert", "Kaya", "corporate"),
            ("Zeynep", "Aydın", "vip"),
            ("Burak", "Öztürk", "regular"),
            ("Selin", "Arslan", "new"),
        ]
        for index, (first, last, segment) in enumerate(names, start=1):
            customer, _ = Customer.objects.update_or_create(
                code=f"MST{index:04d}",
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "segment": segment,
                    "is_vip": segment == "vip",
                    "phone": demo_phone(index),
                    "email": f"ornek{index}@ornek-musteri.test",
                    "birth_day": random.randint(1, 28),
                    "birth_month": random.randint(1, 12),
                    "first_visit_on": timezone.localdate()
                    - timezone.timedelta(days=random.randint(30, 600)),
                    "last_visit_on": timezone.localdate()
                    - timezone.timedelta(days=random.randint(1, 60)),
                },
            )
            ConsentRecord.objects.get_or_create(
                customer=customer,
                purpose=ConsentRecord.Purpose.SERVICE,
                withdrawn_at=None,
                defaults={
                    "is_granted": True,
                    "granted_at": timezone.now(),
                    "collection_method": "Dijital form (demo)",
                    "policy_version": "1.0",
                },
            )
            if segment in {"vip", "regular"}:
                LoyaltyAccount.objects.update_or_create(
                    customer=customer,
                    defaults={
                        "program": program,
                        "card_number": f"WH{index:06d}",
                        "points_balance": random.randint(0, 3000),
                    },
                )
        self.stdout.write(f"  · {len(names)} sentetik müşteri (rıza kayıtlarıyla)")

    def _seed_reporting_definitions(self) -> None:
        from apps.reporting import reports
        from apps.reporting.models import ReportDefinition

        for spec in reports.REGISTRY.values():
            ReportDefinition.objects.update_or_create(
                code=spec.code,
                defaults={
                    "name_tr": spec.name_tr,
                    "name_en": spec.name_en,
                    "category": spec.category,
                    "description": spec.description,
                    "is_experimental": spec.is_experimental,
                },
            )
        self.stdout.write(f"  · {len(reports.REGISTRY)} rapor tanımı")

    # -- Satış geçmişi ------------------------------------------------------
    def _seed_sales(self, *, days: int) -> None:
        """Geçmiş adisyonlar ve gün sonu özetleri üretir."""
        from apps.accounts.models import User
        from apps.catalog.models import MenuItem
        from apps.operations import services
        from apps.operations.models import DiningTable, PaymentMethod

        server = User.objects.filter(is_active=True).order_by("pk").first()
        if server is None:
            self.stdout.write(
                self.style.WARNING(
                    "  · Satış geçmişi atlandı: önce 'create_admin' ile kullanıcı oluşturun."
                )
            )
            return

        tables = list(DiningTable.objects.filter(is_active=True)[:20])
        food_items = list(MenuItem.objects.filter(is_active=True, item_type__in=["food", "drink"]))
        glass_items = list(MenuItem.objects.filter(item_type="wine_glass"))
        bottle_items = list(MenuItem.objects.filter(item_type="wine"))
        cash = PaymentMethod.objects.get(code="NAKIT")
        card = PaymentMethod.objects.get(code="KART")

        if not (tables and food_items):
            self.stdout.write(self.style.WARNING("  · Satış geçmişi atlandı: veri eksik."))
            return

        created = 0
        for day_offset in range(days, 0, -1):
            business_date = timezone.localdate() - timezone.timedelta(days=day_offset)
            order_count = random.randint(6, 14)

            for _ in range(order_count):
                table = random.choice(tables)
                guests = random.randint(1, min(6, table.seats))
                opened = timezone.make_aware(
                    timezone.datetime.combine(
                        business_date,
                        timezone.datetime.min.time().replace(
                            hour=random.randint(12, 22), minute=random.choice([0, 15, 30, 45])
                        ),
                    )
                )

                order = services.open_order(
                    user=server,
                    table=None,  # geçmiş veri için masa kilidi kullanılmaz
                    channel="dine_in",
                    guest_count=guests,
                    service_charge_percent=Decimal("0.00"),
                )
                order.opened_at = opened
                order.table = table
                order.save(update_fields=["opened_at", "table"])

                for _ in range(random.randint(1, guests + 1)):
                    services.add_line(
                        order=order,
                        menu_item=random.choice(food_items),
                        user=server,
                        quantity=1,
                    )
                if glass_items and random.random() < 0.55:
                    services.add_line(
                        order=order,
                        menu_item=random.choice(glass_items),
                        user=server,
                        quantity=random.randint(1, 2),
                        service_unit="glass",
                    )
                if bottle_items and random.random() < 0.25:
                    services.add_line(
                        order=order,
                        menu_item=random.choice(bottle_items),
                        user=server,
                        quantity=1,
                        service_unit="bottle",
                    )

                order.refresh_from_db()
                order.recalculate()
                method = card if random.random() < 0.65 else cash
                services.take_payment(
                    order=order,
                    method=method,
                    amount=order.amount_due,
                    user=server,
                    reference="DEMO-REF" if method.requires_reference else "",
                )
                order.refresh_from_db()
                order.closed_at = opened + timezone.timedelta(minutes=random.randint(45, 130))
                order.save(update_fields=["closed_at"])
                created += 1

            day = services.get_or_open_business_day(server, business_date)
            if day.status != day.Status.CLOSED:
                # Zaten kapanmis ya da kapatilamayan gun demo akisini durdurmaz.
                with contextlib.suppress(services.OperationsError):
                    services.close_business_day(
                        business_day=day, user=server, cash_counted=day.cash_expected
                    )

        # Masaları tekrar boşalt
        DiningTable.objects.update(status=DiningTable.Status.FREE)
        self.stdout.write(f"  · {created} geçmiş adisyon ve {days} gün sonu özeti")
