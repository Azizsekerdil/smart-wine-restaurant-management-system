"""Salon operasyonu testleri: sipariş, KDS, hesap bölme, ödeme, gün sonu.

Kabul senaryosu #6–#11'in otomatik karşılığı.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Adisyon açma
# ---------------------------------------------------------------------------
def test_masa_acilinca_durumu_degisir(waiter, table) -> None:
    from apps.operations import services
    from apps.operations.models import DiningTable

    order = services.open_order(user=waiter, table=table, guest_count=3)
    table.refresh_from_db()

    assert order.number.startswith("ADS-")
    assert table.status == DiningTable.Status.SEATED
    assert order.guest_count == 3


def test_ayni_masaya_iki_acik_adisyon_olamaz(waiter, table) -> None:
    from apps.operations import services

    services.open_order(user=waiter, table=table)
    with pytest.raises(services.OperationsError, match="zaten açık adisyon"):
        services.open_order(user=waiter, table=table)


def test_servis_disi_masa_acilamaz(waiter, table) -> None:
    from apps.operations import services
    from apps.operations.models import DiningTable

    table.status = DiningTable.Status.OUT_OF_SERVICE
    table.save()
    with pytest.raises(services.OperationsError, match="servis dışı"):
        services.open_order(user=waiter, table=table)


# ---------------------------------------------------------------------------
# Satır ekleme ve fiyat dondurma
# ---------------------------------------------------------------------------
def test_satir_fiyati_dondurulur(waiter, open_order, food_item) -> None:
    """Menü fiyatı sonradan değişse bile geçmiş adisyon değişmez."""
    from apps.operations import services

    line = services.add_line(order=open_order, menu_item=food_item, user=waiter, quantity=2)
    assert line.unit_price == Decimal("500.00")
    assert line.item_name == "Kuzu Tandır"

    food_item.base_price = Decimal("900.00")
    food_item.save()

    line.refresh_from_db()
    assert line.unit_price == Decimal("500.00"), "Geçmiş fiyat değişti!"


def test_satir_tutarlari_dogru_hesaplanir(waiter, open_order, food_item) -> None:
    from apps.operations import services

    line = services.add_line(order=open_order, menu_item=food_item, user=waiter, quantity=2)
    assert line.gross_amount == Decimal("1000.00")
    assert line.discount_amount == Decimal("0.00")
    assert line.net_amount == Decimal("1000.00")
    assert line.tax_amount == Decimal("100.00")  # %10
    assert line.total_amount == Decimal("1100.00")
    assert line.cost_amount == Decimal("300.00")
    assert line.margin_amount == Decimal("700.00")


def test_ikram_satiri_tam_indirimlidir(manager, table, food_item) -> None:
    from apps.operations import services

    order = services.open_order(user=manager, table=table)
    line = services.add_line(order=order, menu_item=food_item, user=manager, quantity=1)
    services.apply_discount(
        line=line, user=manager, percent=Decimal("0"), reason="özür", is_comp=True
    )
    line.refresh_from_db()
    assert line.discount_amount == line.gross_amount
    assert line.net_amount == Decimal("0.00")


def test_serviste_olmayan_urun_eklenemez(waiter, open_order, food_item) -> None:
    from apps.operations import services

    food_item.is_available = False
    food_item.save()
    with pytest.raises(services.OperationsError, match="serviste değil"):
        services.add_line(order=open_order, menu_item=food_item, user=waiter)


def test_kadeh_sarap_satirinda_kadeh_fiyati_kullanilir(waiter, open_order, wine_glass_item) -> None:
    from apps.operations import services
    from apps.operations.models import OrderLine

    line = services.add_line(
        order=open_order,
        menu_item=wine_glass_item,
        user=waiter,
        service_unit=OrderLine.ServiceUnit.GLASS,
    )
    assert line.unit_price == Decimal("250.00")
    assert line.wine_id == wine_glass_item.wine_id


def test_satir_iptali_toplami_dusurur(waiter, open_order, food_item) -> None:
    from apps.operations import services

    line = services.add_line(order=open_order, menu_item=food_item, user=waiter)
    open_order.refresh_from_db()
    before = open_order.grand_total

    services.void_line(line=line, user=waiter, reason="yanlış giriş")
    open_order.refresh_from_db()

    assert before > Decimal("0")
    assert open_order.grand_total == Decimal("0.00")
    line.refresh_from_db()
    assert line.is_voided


def test_gerekcesiz_iptal_reddedilir(waiter, open_order, food_item) -> None:
    from apps.operations import services

    line = services.add_line(order=open_order, menu_item=food_item, user=waiter)
    with pytest.raises(services.OperationsError, match="gerekçesi zorunlu"):
        services.void_line(line=line, user=waiter, reason="  ")


# ---------------------------------------------------------------------------
# KOT / KDS
# ---------------------------------------------------------------------------
def test_yemek_mutfaga_sarap_sommeliere_duser(
    waiter, open_order, food_item, wine_glass_item
) -> None:
    """Kabul senaryosu #7."""
    from apps.operations import services
    from apps.operations.models import OrderLine, PrepTicket

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    services.add_line(
        order=open_order,
        menu_item=wine_glass_item,
        user=waiter,
        service_unit=OrderLine.ServiceUnit.GLASS,
    )

    tickets = services.send_to_stations(order=open_order, user=waiter)
    stations = {ticket.station for ticket in tickets}

    assert PrepTicket.Station.KITCHEN in stations
    assert PrepTicket.Station.WINE in stations


def test_gonderilmis_satir_tekrar_gonderilmez(waiter, open_order, food_item) -> None:
    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    first = services.send_to_stations(order=open_order, user=waiter)
    second = services.send_to_stations(order=open_order, user=waiter)

    assert len(first) == 1
    assert second == []


def test_alerjen_uyarisi_fise_yazilir(waiter, open_order, food_item, db) -> None:
    from apps.catalog.models import Allergen
    from apps.operations import services

    allergen = Allergen.objects.create(code="sut", name_tr="Süt", name_en="Milk")
    food_item.allergens.add(allergen)

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    tickets = services.send_to_stations(order=open_order, user=waiter)

    assert "Süt" in tickets[0].lines.first().allergen_warning


def test_fis_durumu_ilerletilir(waiter, open_order, food_item) -> None:
    from apps.operations import services
    from apps.operations.models import PrepTicket

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    ticket = services.send_to_stations(order=open_order, user=waiter)[0]

    assert ticket.status == PrepTicket.Status.QUEUED
    services.bump_ticket(ticket=ticket, user=waiter)
    assert ticket.status == PrepTicket.Status.PREPARING
    services.bump_ticket(ticket=ticket, user=waiter)
    assert ticket.status == PrepTicket.Status.READY
    services.bump_ticket(ticket=ticket, user=waiter)
    assert ticket.status == PrepTicket.Status.SERVED
    assert ticket.served_at is not None

    with pytest.raises(services.OperationsError, match="son durumda"):
        services.bump_ticket(ticket=ticket, user=waiter)


def test_geciken_fis_isaretlenir(waiter, open_order, food_item) -> None:
    from django.utils import timezone

    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    ticket = services.send_to_stations(order=open_order, user=waiter)[0]

    ticket.sent_at = timezone.now() - timezone.timedelta(minutes=90)
    ticket.save()
    assert ticket.is_overdue
    assert "danger" in ticket.urgency_class


# ---------------------------------------------------------------------------
# Hesap bölme ve birleştirme
# ---------------------------------------------------------------------------
def test_hesap_koltuga_gore_bolunur(waiter, open_order, food_item) -> None:
    """Kabul senaryosu #10."""
    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter, seat_number=1)
    services.add_line(order=open_order, menu_item=food_item, user=waiter, seat_number=2, quantity=2)

    result = services.split_order_by_seat(order=open_order, user=waiter)

    assert len(result.created) == 2
    assert result.created[0].grand_total == Decimal("550.00")
    assert result.created[1].grand_total == Decimal("1100.00")
    open_order.refresh_from_db()
    assert open_order.grand_total == Decimal("0.00")


def test_koltuk_numarasiz_hesap_bolunemez(waiter, open_order, food_item) -> None:
    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    with pytest.raises(services.OperationsError, match="koltuk numarası"):
        services.split_order_by_seat(order=open_order, user=waiter)


def test_odeme_alinmis_hesap_bolunemez(waiter, open_order, food_item, cash_method) -> None:
    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter, seat_number=1)
    open_order.refresh_from_db()
    services.take_payment(
        order=open_order, method=cash_method, amount=Decimal("100.00"), user=waiter
    )
    with pytest.raises(services.OperationsError, match="Kısmi ödeme"):
        services.split_order_by_seat(order=open_order, user=waiter)


def test_adisyonlar_birlestirilir(waiter, table, second_table, food_item) -> None:
    from apps.operations import services
    from apps.operations.models import Order

    hedef = services.open_order(user=waiter, table=table, guest_count=2)
    kaynak = services.open_order(user=waiter, table=second_table, guest_count=3)
    services.add_line(order=hedef, menu_item=food_item, user=waiter)
    services.add_line(order=kaynak, menu_item=food_item, user=waiter)

    services.merge_orders(target=hedef, sources=[kaynak], user=waiter)

    hedef.refresh_from_db()
    kaynak.refresh_from_db()
    assert hedef.lines.count() == 2
    assert hedef.guest_count == 5
    assert kaynak.status == Order.Status.VOID
    assert kaynak.merged_into_id == hedef.pk


# ---------------------------------------------------------------------------
# Ödeme
# ---------------------------------------------------------------------------
def test_odeme_sandbox_modunda_kaydedilir(waiter, open_order, food_item, cash_method) -> None:
    from apps.operations import services
    from apps.operations.models import Payment

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    open_order.refresh_from_db()

    payment = services.take_payment(
        order=open_order,
        method=cash_method,
        amount=open_order.grand_total,
        user=waiter,
    )
    open_order.refresh_from_db()

    assert payment.gateway_mode == Payment.GatewayMode.SANDBOX
    assert open_order.status == "paid"
    assert open_order.amount_due == Decimal("0.00")


def test_fazla_odeme_reddedilir(waiter, open_order, food_item, cash_method) -> None:
    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    open_order.refresh_from_db()

    with pytest.raises(services.OperationsError, match="kalan borçtan"):
        services.take_payment(
            order=open_order,
            method=cash_method,
            amount=open_order.grand_total + Decimal("100"),
            user=waiter,
        )


def test_kart_odemesi_referans_ister(waiter, open_order, food_item, card_method) -> None:
    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    open_order.refresh_from_db()

    with pytest.raises(services.OperationsError, match="referans"):
        services.take_payment(
            order=open_order,
            method=card_method,
            amount=Decimal("100.00"),
            user=waiter,
            reference="",
        )


def test_kismi_odeme_kalan_borcu_dusurur(waiter, open_order, food_item, cash_method) -> None:
    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter, quantity=2)
    open_order.refresh_from_db()
    total = open_order.grand_total

    services.take_payment(
        order=open_order, method=cash_method, amount=Decimal("500.00"), user=waiter
    )
    open_order.refresh_from_db()

    assert open_order.amount_due == total - Decimal("500.00")
    assert open_order.status != "paid"


def test_komisyon_hesaplanir(waiter, open_order, food_item, card_method) -> None:
    """Kart komisyonu tahsilat tutarı üzerinden hesaplanır (%1.80)."""
    from apps.operations import services

    # 2 porsiyon × 500 ₺ + %10 KDV = 1.100 ₺
    services.add_line(order=open_order, menu_item=food_item, user=waiter, quantity=2)
    open_order.refresh_from_db()
    assert open_order.grand_total == Decimal("1100.00")

    payment = services.take_payment(
        order=open_order,
        method=card_method,
        amount=open_order.grand_total,
        user=waiter,
        reference="REF-1",
    )
    assert payment.commission_amount == Decimal("19.80")
    assert payment.net_amount == Decimal("1080.20")


# ---------------------------------------------------------------------------
# İptal
# ---------------------------------------------------------------------------
def test_adisyon_iptali_onay_gerektirir(waiter, open_order, food_item) -> None:
    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    with pytest.raises(services.ApprovalRequiredError):
        services.void_order(order=open_order, user=waiter, reason="misafir ayrıldı")

    open_order.refresh_from_db()
    assert open_order.status != "void", "Adisyon onaysız iptal edildi!"


def test_mudur_adisyonu_dogrudan_iptal_eder(manager, table, food_item) -> None:
    from apps.operations import services
    from apps.operations.models import DiningTable, Order

    order = services.open_order(user=manager, table=table)
    services.add_line(order=order, menu_item=food_item, user=manager)
    services.void_order(order=order, user=manager, reason="mutfak hatası")

    order.refresh_from_db()
    table.refresh_from_db()
    assert order.status == Order.Status.VOID
    assert table.status == DiningTable.Status.FREE


# ---------------------------------------------------------------------------
# Rezervasyon çakışması
# ---------------------------------------------------------------------------
def test_ayni_masada_zaman_cakismasi_reddedilir(waiter, table) -> None:
    from django.utils import timezone

    from apps.operations import services
    from apps.operations.models import Reservation

    now = timezone.now().replace(hour=19, minute=0, second=0, microsecond=0)

    first = Reservation.objects.create(
        code="RZV-1", guest_name="A", guest_count=2, reserved_for=now, duration_minutes=120
    )
    services.assign_tables(reservation=first, tables=[table], user=waiter)

    second = Reservation.objects.create(
        code="RZV-2",
        guest_name="B",
        guest_count=2,
        reserved_for=now + timezone.timedelta(minutes=60),
        duration_minutes=120,
    )
    with pytest.raises(services.OperationsError, match="çakışması"):
        services.assign_tables(reservation=second, tables=[table], user=waiter)


def test_cakismayan_rezervasyon_kabul_edilir(waiter, table) -> None:
    from django.utils import timezone

    from apps.operations import services
    from apps.operations.models import Reservation

    now = timezone.now().replace(hour=19, minute=0, second=0, microsecond=0)
    first = Reservation.objects.create(
        code="RZV-3", guest_name="A", guest_count=2, reserved_for=now, duration_minutes=90
    )
    services.assign_tables(reservation=first, tables=[table], user=waiter)

    second = Reservation.objects.create(
        code="RZV-4",
        guest_name="B",
        guest_count=2,
        reserved_for=now + timezone.timedelta(minutes=120),
        duration_minutes=90,
    )
    services.assign_tables(reservation=second, tables=[table], user=waiter)
    assert second.tables.count() == 1


def test_kapasite_yetersizse_masa_atanamaz(waiter, table) -> None:
    from django.utils import timezone

    from apps.operations import services
    from apps.operations.models import Reservation

    reservation = Reservation.objects.create(
        code="RZV-5", guest_name="Kalabalık", guest_count=12, reserved_for=timezone.now()
    )
    with pytest.raises(services.OperationsError, match="kapasitesi"):
        services.assign_tables(reservation=reservation, tables=[table], user=waiter)


# ---------------------------------------------------------------------------
# Gün sonu
# ---------------------------------------------------------------------------
def test_acik_adisyon_varken_gun_kapanmaz(waiter, open_order, food_item, admin_user) -> None:
    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    day = services.get_or_open_business_day(admin_user)

    with pytest.raises(services.OperationsError, match="Kapanmamış adisyonlar"):
        services.close_business_day(business_day=day, user=admin_user, cash_counted=Decimal("0"))


def test_gun_sonu_ozeti_dondurulur(waiter, open_order, food_item, cash_method, admin_user) -> None:
    """Kabul senaryosu #11."""
    from apps.operations import services
    from apps.reporting.models import DailySalesSnapshot

    services.add_line(order=open_order, menu_item=food_item, user=waiter, quantity=2)
    open_order.refresh_from_db()
    services.take_payment(
        order=open_order,
        method=cash_method,
        amount=open_order.grand_total,
        user=waiter,
    )

    day = services.get_or_open_business_day(admin_user)
    closed = services.close_business_day(
        business_day=day, user=admin_user, cash_counted=open_order.grand_total
    )

    assert closed.status == "closed"
    assert closed.total_orders == 1
    assert closed.total_guests == 2
    assert closed.cash_variance == Decimal("0.00")

    snapshot = DailySalesSnapshot.objects.get(business_date=day.business_date)
    assert snapshot.order_count == 1
    assert snapshot.food_sales == Decimal("1100.00")


def test_kasa_farki_hesaplanir(waiter, open_order, food_item, cash_method, admin_user) -> None:
    from apps.operations import services

    services.add_line(order=open_order, menu_item=food_item, user=waiter)
    open_order.refresh_from_db()
    services.take_payment(
        order=open_order,
        method=cash_method,
        amount=open_order.grand_total,
        user=waiter,
    )

    day = services.get_or_open_business_day(admin_user)
    closed = services.close_business_day(
        business_day=day,
        user=admin_user,
        cash_counted=open_order.grand_total - Decimal("50.00"),
    )
    assert closed.cash_variance == Decimal("-50.00")


def test_kapanmis_gun_tekrar_kapanmaz(admin_user) -> None:
    from apps.operations import services

    day = services.get_or_open_business_day(admin_user)
    services.close_business_day(business_day=day, user=admin_user, cash_counted=Decimal("0"))
    with pytest.raises(services.OperationsError, match="zaten kapatılmış"):
        services.close_business_day(business_day=day, user=admin_user, cash_counted=Decimal("0"))


# ---------------------------------------------------------------------------
# UÇTAN UCA
# ---------------------------------------------------------------------------
@pytest.mark.e2e
def test_uctan_uca_masa_siparis_kds_odeme(
    waiter, admin_user, table, food_item, wine_glass_item, wine, cash_method
) -> None:
    """Kabul senaryoları #6–#12 tek akışta.

    Masa aç → sipariş gir → KOT üret → kadeh servis et (stok düşsün) →
    fişleri ilerlet → ödeme al → gün sonu kapat.
    """
    from apps.cellar import services as cellar
    from apps.operations import services
    from apps.operations.models import DiningTable, Order, OrderLine, PrepTicket

    # 1) Masa açılışı
    order = services.open_order(user=waiter, table=table, guest_count=2)

    # 2) Sipariş
    services.add_line(order=order, menu_item=food_item, user=waiter, quantity=2)
    services.add_line(
        order=order,
        menu_item=wine_glass_item,
        user=waiter,
        quantity=2,
        service_unit=OrderLine.ServiceUnit.GLASS,
    )

    # 3) Mutfağa/şarap istasyonuna gönder
    tickets = services.send_to_stations(order=order, user=waiter)
    assert len(tickets) == 2
    order.refresh_from_db()
    assert order.status == Order.Status.SENT

    # 4) Kadeh servisi — stok düşmeli
    bottles_before = wine.bottles_on_hand
    for _ in range(2):
        cellar.pour_glass(wine=wine, user=waiter)
    wine.refresh_from_db()
    assert wine.bottles_on_hand == bottles_before - 1  # 2 kadeh = 1 şişe açıldı

    # 5) Fişleri servise kadar ilerlet
    for ticket in tickets:
        for _ in range(3):
            services.bump_ticket(ticket=ticket, user=waiter)
    order.refresh_from_db()
    assert order.status == Order.Status.SERVED
    assert all(t.status == PrepTicket.Status.SERVED for t in PrepTicket.objects.all())

    # 6) Ödeme
    order.recalculate()
    beklenen = Decimal("1100.00") + Decimal("600.00")  # yemek KDV%10, şarap KDV%20
    assert order.grand_total == beklenen

    services.take_payment(order=order, method=cash_method, amount=order.grand_total, user=waiter)
    order.refresh_from_db()
    table.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert order.amount_due == Decimal("0.00")
    assert table.status == DiningTable.Status.CLEANING

    # 7) Gün sonu
    day = services.get_or_open_business_day(admin_user)
    closed = services.close_business_day(business_day=day, user=admin_user, cash_counted=beklenen)
    assert closed.total_orders == 1
    assert closed.cash_variance == Decimal("0.00")
