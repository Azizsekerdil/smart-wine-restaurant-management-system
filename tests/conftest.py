"""Ortak test düzeneği (fixtures).

Tüm testler ``winehouse.settings.test`` ile çalışır: bellek içi veritabanı,
yalnızca Mock yapay zekâ sağlayıcısı ve hiçbir ağ çağrısı yok.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

# src/ dizinini Python yoluna ekle
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# Kullanıcılar ve roller
# ---------------------------------------------------------------------------
@pytest.fixture
def roles(db):
    """Rol kataloğunu veritabanına yansıtır."""
    from apps.accounts.services import sync_roles

    return sync_roles()


@pytest.fixture
def make_user(db, roles):
    """Belirtilen rolde kullanıcı üreten fabrika."""
    from apps.accounts.models import User
    from apps.accounts.services import assign_role

    def _make(
        username: str,
        role: str = "waiter",
        *,
        is_superuser: bool = False,
        discount_limit: str = "0",
        **extra,
    ) -> User:
        user = User.objects.create_user(
            username=username,
            password="Test.Parola.2026!",
            display_name=username.title(),
            is_superuser=is_superuser,
            is_staff=is_superuser,
            discount_limit_percent=Decimal(discount_limit),
            **extra,
        )
        assign_role(user, role, primary=True)
        return user

    return _make


@pytest.fixture
def admin_user(make_user):
    return make_user("admin", "sysadmin", is_superuser=True)


@pytest.fixture
def waiter(make_user):
    return make_user("garson", "waiter", discount_limit="5")


@pytest.fixture
def manager(make_user):
    return make_user("mudur", "restaurant_manager", discount_limit="25")


@pytest.fixture
def sommelier(make_user):
    return make_user("sommelier", "sommelier")


@pytest.fixture
def auditor(make_user):
    return make_user("denetci", "auditor")


# ---------------------------------------------------------------------------
# Şarap kavı
# ---------------------------------------------------------------------------
@pytest.fixture
def wine(db):
    """Kadeh satışı yapılan, 10 şişe stoklu bir şarap."""
    from apps.cellar.models import BottleLot, Wine, WineProducer, WineRegion

    region = WineRegion.objects.create(name="Elazığ", level="region")
    producer = WineProducer.objects.create(name="Test Üretici", region=region)
    wine = Wine.objects.create(
        sku="TEST-001",
        name="Öküzgözü Test",
        producer=producer,
        region=region,
        vintage=2020,
        wine_type=Wine.WineType.RED,
        alcohol_percent=Decimal("13.5"),
        bottle_size_ml=750,
        glass_pour_ml=150,
        sold_by_glass=True,
        purchase_price=Decimal("300.00"),
        bottle_price=Decimal("1200.00"),
        glass_price=Decimal("250.00"),
        minimum_bottles=3,
        drink_from_year=2022,
        drink_until_year=2028,
        peak_year=2025,
    )
    BottleLot.objects.create(
        wine=wine,
        lot_code="LOT-TEST-1",
        bottles_received=10,
        bottles_remaining=10,
        unit_cost=Decimal("300.00"),
    )
    return wine


# ---------------------------------------------------------------------------
# Stok ve menü
# ---------------------------------------------------------------------------
@pytest.fixture
def warehouse(db):
    from apps.inventory.models import Warehouse

    return Warehouse.objects.create(code="ANA", name="Ana Depo", is_default=True)


@pytest.fixture
def stock_item(db, warehouse):
    """100 birim açılış stoğu olan bir kalem."""
    from apps.inventory.models import StockItem, StockItemCategory, UnitOfMeasure
    from apps.inventory.services import receive_stock

    unit = UnitOfMeasure.objects.create(code="g", name="Gram", dimension="mass")
    category = StockItemCategory.objects.create(code="et", name="Et")
    item = StockItem.objects.create(
        code="HM-TEST",
        name="Dana Bonfile",
        category=category,
        unit=unit,
        minimum_quantity=Decimal("20"),
        reorder_quantity=Decimal("100"),
        tracking_mode=StockItem.TrackingMode.FEFO,
    )
    receive_stock(
        stock_item=item,
        warehouse=warehouse,
        quantity=Decimal("100"),
        unit_cost=Decimal("5.00"),
        user=None,
        lot_code="LOT-A",
    )
    return item


@pytest.fixture
def menu_category(db):
    from apps.catalog.models import MenuCategory

    return MenuCategory.objects.create(
        code="ana", name_tr="Ana Yemekler", preparation_station="kitchen"
    )


@pytest.fixture
def wine_category(db):
    from apps.catalog.models import MenuCategory

    return MenuCategory.objects.create(code="sarap", name_tr="Şaraplar", preparation_station="wine")


@pytest.fixture
def food_item(db, menu_category):
    from apps.catalog.models import MenuItem

    return MenuItem.objects.create(
        code="YMK-1",
        name_tr="Kuzu Tandır",
        category=menu_category,
        item_type=MenuItem.ItemType.FOOD,
        base_price=Decimal("500.00"),
        tax_rate=Decimal("10.00"),
        cost_price=Decimal("150.00"),
        preparation_minutes=25,
    )


@pytest.fixture
def wine_glass_item(db, wine_category, wine):
    from apps.catalog.models import MenuItem

    return MenuItem.objects.create(
        code="SK-1",
        name_tr="Öküzgözü (kadeh)",
        category=wine_category,
        item_type=MenuItem.ItemType.WINE_BY_GLASS,
        wine=wine,
        base_price=wine.glass_price,
        tax_rate=Decimal("20.00"),
        cost_price=Decimal("60.00"),
        tracks_stock=False,
    )


# ---------------------------------------------------------------------------
# Salon
# ---------------------------------------------------------------------------
@pytest.fixture
def section(db):
    from apps.operations.models import FloorSection

    return FloorSection.objects.create(code="SALON", name="Ana Salon")


@pytest.fixture
def table(db, section):
    from apps.operations.models import DiningTable

    return DiningTable.objects.create(section=section, number="1", seats=4)


@pytest.fixture
def second_table(db, section):
    from apps.operations.models import DiningTable

    return DiningTable.objects.create(section=section, number="2", seats=6)


@pytest.fixture
def cash_method(db):
    from apps.operations.models import PaymentMethod

    return PaymentMethod.objects.create(
        code="NAKIT", name="Nakit", kind="cash", opens_cash_drawer=True
    )


@pytest.fixture
def card_method(db):
    from apps.operations.models import PaymentMethod

    return PaymentMethod.objects.create(
        code="KART",
        name="Kart",
        kind="card",
        requires_reference=True,
        commission_percent=Decimal("1.80"),
    )


@pytest.fixture
def open_order(db, waiter, table):
    """Masaya açılmış boş bir adisyon."""
    from apps.operations import services

    return services.open_order(user=waiter, table=table, guest_count=2)


@pytest.fixture
def client_as(client):
    """Verilen kullanıcıyla oturum açmış test istemcisi döndürür."""

    def _login(user):
        client.force_login(user)
        return client

    return _login
