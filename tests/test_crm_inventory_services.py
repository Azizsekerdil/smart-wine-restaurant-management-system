"""CRM ve stok servis katmanı testleri.

KVKK veri taşınabilirliği/silme, sadakat puanı ve satın alma akışları.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Düzenek
# ---------------------------------------------------------------------------
@pytest.fixture
def customer(db):
    from apps.crm.models import Customer

    return Customer.objects.create(
        code="MST-1",
        first_name="Deniz",
        last_name="Yılmaz",
        phone="+90 555 111 22 33",
        email="deniz@ornek.test",
        birth_day=14,
        birth_month=3,
        segment=Customer.Segment.REGULAR,
    )


@pytest.fixture
def loyalty_account(db, customer):
    from apps.crm.models import LoyaltyAccount, LoyaltyProgram

    program = LoyaltyProgram.objects.create(
        name="Kulüp",
        points_per_currency=Decimal("1.0000"),
        currency_per_point=Decimal("0.0100"),
        minimum_redeem_points=100,
        points_expire_days=365,
    )
    return LoyaltyAccount.objects.create(
        customer=customer, program=program, card_number="WH000001", points_balance=0
    )


# ---------------------------------------------------------------------------
# Sadakat
# ---------------------------------------------------------------------------
def test_odenen_adisyon_puan_kazandirir(
    waiter, table, food_item, cash_method, customer, loyalty_account
) -> None:
    from apps.crm.services import award_points
    from apps.operations import services

    order = services.open_order(user=waiter, table=table, customer=customer)
    services.add_line(order=order, menu_item=food_item, user=waiter, quantity=2)
    order.refresh_from_db()
    services.take_payment(order=order, method=cash_method, amount=order.grand_total, user=waiter)
    order.refresh_from_db()

    entry = award_points(order=order, user=waiter)
    loyalty_account.refresh_from_db()

    assert entry is not None
    assert entry.points == int(order.grand_total)
    assert loyalty_account.points_balance == entry.points
    assert entry.expires_on is not None


def test_musterisiz_adisyon_puan_kazandirmaz(waiter, open_order) -> None:
    from apps.crm.services import award_points

    assert award_points(order=open_order, user=waiter) is None


def test_hesabi_olmayan_musteri_puan_kazanmaz(waiter, table, customer) -> None:
    from apps.crm.services import award_points
    from apps.operations import services

    order = services.open_order(user=waiter, table=table, customer=customer)
    assert award_points(order=order, user=waiter) is None


def test_puan_kullanimi_bakiyeyi_dusurur(loyalty_account, manager) -> None:
    from apps.crm.services import redeem_points

    loyalty_account.points_balance = 500
    loyalty_account.save()

    entry = redeem_points(account=loyalty_account, points=300, user=manager)
    loyalty_account.refresh_from_db()

    assert entry.points == -300
    assert loyalty_account.points_balance == 200


def test_yetersiz_puan_kullanilamaz(loyalty_account, manager) -> None:
    from apps.crm.services import CrmError, redeem_points

    loyalty_account.points_balance = 50
    loyalty_account.save()
    with pytest.raises(CrmError, match="Yetersiz puan"):
        redeem_points(account=loyalty_account, points=100, user=manager)


def test_asgari_kullanim_puani_zorunlu(loyalty_account, manager) -> None:
    from apps.crm.services import CrmError, redeem_points

    loyalty_account.points_balance = 500
    loyalty_account.save()
    with pytest.raises(CrmError, match="Asgari kullanım"):
        redeem_points(account=loyalty_account, points=50, user=manager)


def test_negatif_puan_kullanilamaz(loyalty_account, manager) -> None:
    from apps.crm.services import CrmError, redeem_points

    with pytest.raises(CrmError, match="sıfırdan büyük"):
        redeem_points(account=loyalty_account, points=-10, user=manager)


def test_sadakat_hareketi_degistirilemez(loyalty_account, manager) -> None:
    from apps.crm.services import redeem_points

    loyalty_account.points_balance = 500
    loyalty_account.save()
    entry = redeem_points(account=loyalty_account, points=200, user=manager)
    entry.points = -1
    with pytest.raises(ValueError, match="değiştirilemez"):
        entry.save()


def test_kullanilabilir_tutar_hesaplanir(loyalty_account) -> None:
    loyalty_account.points_balance = 50
    assert loyalty_account.redeemable_amount == Decimal("0.00")  # asgari altında

    loyalty_account.points_balance = 2500
    assert loyalty_account.redeemable_amount == Decimal("25.00")


# ---------------------------------------------------------------------------
# KVKK: dışa aktarım
# ---------------------------------------------------------------------------
def test_musteri_verisi_disa_aktarilir(
    customer, loyalty_account, waiter, table, food_item, cash_method, admin_user
) -> None:
    from apps.crm.services import export_customer_data
    from apps.operations import services

    order = services.open_order(user=waiter, table=table, customer=customer)
    services.add_line(order=order, menu_item=food_item, user=waiter)
    order.refresh_from_db()
    services.take_payment(order=order, method=cash_method, amount=order.grand_total, user=waiter)

    payload = export_customer_data(customer=customer, user=admin_user)

    assert payload["musteri"]["ad"] == "Deniz"
    assert payload["musteri"]["telefon"] == "+90 555 111 22 33"
    assert payload["musteri"]["dogum_gun_ay"] == "14.03"
    assert len(payload["ziyaretler"]) == 1
    assert payload["sadakat"]["kart_no"] == "WH000001"


def test_disa_aktarim_denetime_yazilir(customer, admin_user) -> None:
    from apps.core.models import AuditAction, AuditLog
    from apps.crm.services import export_customer_data

    export_customer_data(customer=customer, user=admin_user)
    assert AuditLog.objects.filter(action=AuditAction.EXPORT).exists()


# ---------------------------------------------------------------------------
# KVKK: silme / anonimleştirme
# ---------------------------------------------------------------------------
def test_onaysiz_silme_reddedilir(customer, admin_user) -> None:
    from apps.crm.models import DataErasureRequest
    from apps.crm.services import CrmError, anonymize_customer

    erasure = DataErasureRequest.objects.create(customer=customer)
    with pytest.raises(CrmError, match="ikinci onay"):
        anonymize_customer(erasure=erasure, user=admin_user)

    customer.refresh_from_db()
    assert customer.first_name == "Deniz", "Onaysız silme uygulandı!"


def test_onayli_silme_kisisel_veriyi_anonimlestirir(
    customer, manager, admin_user, waiter, table, food_item, cash_method
) -> None:
    """Mali kayıtlar korunur, kişisel veri silinir."""
    from apps.accounts.models import ApprovalRequest
    from apps.crm.models import DataErasureRequest
    from apps.crm.services import anonymize_customer
    from apps.operations import services

    order = services.open_order(user=waiter, table=table, customer=customer)
    services.add_line(order=order, menu_item=food_item, user=waiter)
    order.refresh_from_db()
    services.take_payment(order=order, method=cash_method, amount=order.grand_total, user=waiter)
    order_total = order.grand_total

    approval = ApprovalRequest.objects.create(
        action="erase_customer_data", requested_by=manager, reason="müşteri talebi"
    )
    approval.approve(admin_user)

    erasure = DataErasureRequest.objects.create(customer=customer, approval=approval)
    anonymize_customer(erasure=erasure, user=admin_user)

    customer.refresh_from_db()
    order.refresh_from_db()
    erasure.refresh_from_db()

    # Kişisel veri silindi
    assert customer.first_name == "Anonimleştirilmiş"
    assert customer.phone == ""
    assert customer.email == ""
    assert customer.birth_day is None
    assert customer.is_deleted
    assert customer.code.startswith("ANON-")

    # Mali kayıt korundu, kişi bağlantısı koparıldı
    assert order.grand_total == order_total
    assert order.customer_id is None
    assert erasure.status == DataErasureRequest.Status.COMPLETED
    assert "yasal saklama" in erasure.retained_records_note.lower()


def test_ayni_silme_talebi_tekrar_uygulanmaz(customer, manager, admin_user) -> None:
    from apps.accounts.models import ApprovalRequest
    from apps.crm.models import DataErasureRequest
    from apps.crm.services import CrmError, anonymize_customer

    approval = ApprovalRequest.objects.create(
        action="erase_customer_data", requested_by=manager, reason="talep"
    )
    approval.approve(admin_user)
    erasure = DataErasureRequest.objects.create(customer=customer, approval=approval)

    anonymize_customer(erasure=erasure, user=admin_user)
    with pytest.raises(CrmError, match="zaten tamamlanmış"):
        anonymize_customer(erasure=erasure, user=admin_user)


# ---------------------------------------------------------------------------
# Rıza
# ---------------------------------------------------------------------------
def test_riza_verilir_ve_geri_cekilir(customer) -> None:
    from django.utils import timezone

    from apps.crm.models import ConsentRecord

    consent = ConsentRecord.objects.create(
        customer=customer,
        purpose=ConsentRecord.Purpose.MARKETING_EMAIL,
        is_granted=True,
        granted_at=timezone.now(),
    )
    assert customer.has_consent(ConsentRecord.Purpose.MARKETING_EMAIL)

    consent.withdraw()
    assert not customer.has_consent(ConsentRecord.Purpose.MARKETING_EMAIL)


def test_rizasiz_musteriler_listelenir(customer) -> None:
    from apps.crm.models import ConsentRecord
    from apps.crm.services import customers_missing_consent

    eksikler = customers_missing_consent(ConsentRecord.Purpose.MARKETING_SMS)
    assert customer in eksikler


def test_kampanya_yalnizca_rizali_musteriyi_hedefler(customer) -> None:
    from django.utils import timezone

    from apps.crm.models import Campaign, ConsentRecord, Customer

    rizasiz = Customer.objects.create(code="MST-2", first_name="Rızasız")

    ConsentRecord.objects.create(
        customer=customer,
        purpose=ConsentRecord.Purpose.MARKETING_EMAIL,
        is_granted=True,
        granted_at=timezone.now(),
    )

    campaign = Campaign.objects.create(
        name="Yaz kampanyası",
        channel=Campaign.Channel.EMAIL,
        requires_consent=True,
    )
    uygun = list(campaign.eligible_customers())

    assert customer in uygun
    assert rizasiz not in uygun


def test_kara_listedeki_musteri_kampanyaya_girmez(customer) -> None:
    from django.utils import timezone

    from apps.crm.models import Campaign, ConsentRecord

    ConsentRecord.objects.create(
        customer=customer,
        purpose=ConsentRecord.Purpose.MARKETING_EMAIL,
        is_granted=True,
        granted_at=timezone.now(),
    )
    customer.is_blacklisted = True
    customer.save()

    campaign = Campaign.objects.create(name="K", channel=Campaign.Channel.EMAIL)
    assert customer not in list(campaign.eligible_customers())


def test_isletme_ici_kampanya_riza_gerektirmez(customer) -> None:
    from apps.crm.models import Campaign

    campaign = Campaign.objects.create(
        name="Personel bilgilendirmesi", channel=Campaign.Channel.IN_HOUSE
    )
    assert customer in list(campaign.eligible_customers())


def test_musteri_segmentlemesi_hesaplanir(customer) -> None:
    from apps.crm.services import segment_customers

    counts = segment_customers()
    assert sum(counts.values()) >= 1


# ---------------------------------------------------------------------------
# Stok: mal kabul, sayım, transfer, teklif
# ---------------------------------------------------------------------------
def test_mal_kabul_stoga_islenir(stock_item, warehouse, admin_user, db) -> None:
    from django.utils import timezone

    from apps.inventory import services
    from apps.inventory.models import GoodsReceipt, GoodsReceiptLine, Supplier

    supplier = Supplier.objects.create(code="TED-1", name="Test Tedarikçi")
    receipt = GoodsReceipt.objects.create(
        number="MKB-1",
        supplier=supplier,
        warehouse=warehouse,
        received_by=admin_user,
    )
    GoodsReceiptLine.objects.create(
        receipt=receipt,
        stock_item=stock_item,
        quantity=Decimal("40"),
        unit_cost=Decimal("6.00"),
        lot_code="LOT-YENI",
        expires_on=timezone.localdate() + timezone.timedelta(days=30),
    )

    before = stock_item.quantity_on_hand
    lots = services.post_goods_receipt(receipt=receipt, user=admin_user)

    assert len(lots) == 1
    assert stock_item.quantity_on_hand == before + Decimal("40")


def test_reddedilen_miktar_stoga_girmez(stock_item, warehouse, admin_user, db) -> None:
    from apps.inventory import services
    from apps.inventory.models import GoodsReceipt, GoodsReceiptLine, Supplier

    supplier = Supplier.objects.create(code="TED-2", name="T")
    receipt = GoodsReceipt.objects.create(
        number="MKB-2", supplier=supplier, warehouse=warehouse, received_by=admin_user
    )
    GoodsReceiptLine.objects.create(
        receipt=receipt,
        stock_item=stock_item,
        quantity=Decimal("50"),
        rejected_quantity=Decimal("20"),
        unit_cost=Decimal("6.00"),
        lot_code="LOT-KISMI",
        rejection_reason="soğuk zincir kırılmış",
    )

    before = stock_item.quantity_on_hand
    services.post_goods_receipt(receipt=receipt, user=admin_user)
    assert stock_item.quantity_on_hand == before + Decimal("30")


def test_ayni_mal_kabul_iki_kez_islenmez(stock_item, warehouse, admin_user, db) -> None:
    from apps.inventory import services
    from apps.inventory.models import GoodsReceipt, GoodsReceiptLine, Supplier

    supplier = Supplier.objects.create(code="TED-3", name="T")
    receipt = GoodsReceipt.objects.create(
        number="MKB-3", supplier=supplier, warehouse=warehouse, received_by=admin_user
    )
    GoodsReceiptLine.objects.create(
        receipt=receipt,
        stock_item=stock_item,
        quantity=Decimal("10"),
        unit_cost=Decimal("5.00"),
        lot_code="LOT-X",
    )
    services.post_goods_receipt(receipt=receipt, user=admin_user)

    with pytest.raises(services.InventoryError, match="zaten stoğa işlenmiş"):
        services.post_goods_receipt(receipt=receipt, user=admin_user)


def test_sayim_farki_stogu_duzeltir(stock_item, warehouse, admin_user) -> None:
    from apps.inventory import services
    from apps.inventory.models import StockCount, StockCountLine

    count = StockCount.objects.create(number="SAY-1", warehouse=warehouse, counted_by=admin_user)
    StockCountLine.objects.create(
        count=count,
        stock_item=stock_item,
        system_quantity=Decimal("100"),
        counted_quantity=Decimal("94"),  # 6 birim eksik
        unit_cost=Decimal("5.00"),
    )

    services.post_stock_count(count=count, user=admin_user)
    count.refresh_from_db()

    assert count.status == StockCount.Status.POSTED
    assert stock_item.quantity_on_hand == Decimal("94.0000")
    assert count.total_variance_value == Decimal("-30.00")


def test_sayim_fazlasi_stoga_eklenir(stock_item, warehouse, admin_user) -> None:
    from apps.inventory import services
    from apps.inventory.models import StockCount, StockCountLine

    count = StockCount.objects.create(number="SAY-2", warehouse=warehouse, counted_by=admin_user)
    StockCountLine.objects.create(
        count=count,
        stock_item=stock_item,
        system_quantity=Decimal("100"),
        counted_quantity=Decimal("110"),
        unit_cost=Decimal("5.00"),
    )
    services.post_stock_count(count=count, user=admin_user)
    assert stock_item.quantity_on_hand == Decimal("110.0000")


def test_sayim_iki_kez_muhasebelestirilemez(stock_item, warehouse, admin_user) -> None:
    from apps.inventory import services
    from apps.inventory.models import StockCount, StockCountLine

    count = StockCount.objects.create(number="SAY-3", warehouse=warehouse, counted_by=admin_user)
    StockCountLine.objects.create(
        count=count,
        stock_item=stock_item,
        system_quantity=Decimal("100"),
        counted_quantity=Decimal("99"),
        unit_cost=Decimal("5.00"),
    )
    services.post_stock_count(count=count, user=admin_user)
    with pytest.raises(services.InventoryError, match="zaten muhasebeleştirilmiş"):
        services.post_stock_count(count=count, user=admin_user)


def test_teklif_karsilastirmasi_en_ucuz_ve_en_hizliyi_isaretler(warehouse, admin_user, db) -> None:
    from apps.inventory import services
    from apps.inventory.models import PurchaseRequest, Supplier, SupplierQuotation

    request = PurchaseRequest.objects.create(
        number="STL-1", requested_by=admin_user, warehouse=warehouse
    )
    ucuz = Supplier.objects.create(code="U", name="Ucuz Tedarik")
    hizli = Supplier.objects.create(code="H", name="Hızlı Tedarik")

    SupplierQuotation.objects.create(
        request=request, supplier=ucuz, total_amount=Decimal("1000"), delivery_days=7
    )
    SupplierQuotation.objects.create(
        request=request, supplier=hizli, total_amount=Decimal("1200"), delivery_days=1
    )

    comparison = services.compare_quotations(request)

    assert comparison["recommendation"]["cheapest_supplier"] == "Ucuz Tedarik"
    assert comparison["recommendation"]["fastest_supplier"] == "Hızlı Tedarik"
    assert "otomatik sipariş oluşturmaz" in comparison["recommendation"]["note"]


def test_teklifsiz_talep_bos_karsilastirma_dondurur(warehouse, admin_user) -> None:
    from apps.inventory import services
    from apps.inventory.models import PurchaseRequest

    request = PurchaseRequest.objects.create(
        number="STL-2", requested_by=admin_user, warehouse=warehouse
    )
    comparison = services.compare_quotations(request)
    assert comparison["quotations"] == []
    assert comparison["recommendation"] is None


def test_stok_degerlemesi_kategoriye_gore_gruplanir(stock_item) -> None:
    from apps.inventory import services

    valuation = services.stock_valuation()
    assert valuation["total_value"] == Decimal("500.00")  # 100 × 5.00
    assert "Et" in valuation["by_category"]


def test_skt_yaklasan_partiler_listelenir(stock_item, warehouse, admin_user) -> None:
    from django.utils import timezone

    from apps.inventory import services

    services.receive_stock(
        stock_item=stock_item,
        warehouse=warehouse,
        quantity=Decimal("5"),
        unit_cost=Decimal("5.00"),
        user=admin_user,
        lot_code="LOT-SKT",
        expires_on=timezone.localdate() + timezone.timedelta(days=3),
    )
    yaklasanlar = services.expiring_lots(days=7)
    assert any(lot.lot_code == "LOT-SKT" for lot in yaklasanlar)


def test_sifir_miktarli_giris_reddedilir(stock_item, warehouse, admin_user) -> None:
    from apps.inventory import services

    with pytest.raises(services.InventoryError, match="sıfırdan büyük"):
        services.receive_stock(
            stock_item=stock_item,
            warehouse=warehouse,
            quantity=Decimal("0"),
            unit_cost=Decimal("5.00"),
            user=admin_user,
        )


def test_raf_omrunden_skt_otomatik_hesaplanir(stock_item, warehouse, admin_user) -> None:
    from django.utils import timezone

    from apps.inventory import services

    stock_item.shelf_life_days = 30
    stock_item.save()

    lot, _movement = services.receive_stock(
        stock_item=stock_item,
        warehouse=warehouse,
        quantity=Decimal("10"),
        unit_cost=Decimal("5.00"),
        user=admin_user,
        lot_code="LOT-OTO",
    )
    assert lot.expires_on == timezone.localdate() + timezone.timedelta(days=30)


def test_ortalama_maliyet_agirlikli_hesaplanir(stock_item, warehouse, admin_user) -> None:
    """100 × 5,00 + 100 × 9,00 → ağırlıklı ortalama 7,00."""
    from apps.inventory import services

    services.receive_stock(
        stock_item=stock_item,
        warehouse=warehouse,
        quantity=Decimal("100"),
        unit_cost=Decimal("9.00"),
        user=admin_user,
        lot_code="LOT-PAHALI",
    )
    assert stock_item.average_unit_cost == Decimal("7.0000")


def test_belge_numarasi_sirali_uretilir(warehouse, admin_user) -> None:
    from apps.inventory import services
    from apps.inventory.models import PurchaseRequest

    first = services.next_document_number(PurchaseRequest, "number", "STL")
    PurchaseRequest.objects.create(number=first, requested_by=admin_user, warehouse=warehouse)
    second = services.next_document_number(PurchaseRequest, "number", "STL")

    assert first.endswith("-0001")
    assert second.endswith("-0002")
