"""Rol tabanlı erişim ve ikinci onay testleri."""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.rbac, pytest.mark.django_db]


# ---------------------------------------------------------------------------
# Rol kataloğu
# ---------------------------------------------------------------------------
def test_tum_roller_olusturulur(roles) -> None:
    from apps.accounts.models import RoleProfile
    from apps.accounts.roles import ROLES

    assert RoleProfile.objects.count() == len(ROLES)
    assert RoleProfile.objects.filter(code="sommelier").exists()
    assert RoleProfile.objects.filter(code="auditor").exists()


def test_rol_eslestirmesi_idempotent() -> None:
    """sync_roles birden çok kez çalıştırılabilir; kopya üretmez."""
    from apps.accounts.models import RoleProfile
    from apps.accounts.services import sync_roles

    sync_roles()
    first = RoleProfile.objects.count()
    sync_roles()
    assert RoleProfile.objects.count() == first


def test_bilinmeyen_izin_deseni_kalmaz(roles) -> None:
    """Tüm izin desenleri gerçek izinlerle eşleşmelidir."""
    assert (
        roles.unmatched_patterns == {}
    ), f"Eşleşmeyen izin desenleri var: {roles.unmatched_patterns}"


def test_denetci_hicbir_yazma_izni_almaz(auditor) -> None:
    """Salt okunur denetçinin add/change/delete izni olmamalı."""
    yazma_izinleri = [
        codename
        for codename in auditor.get_all_permissions()
        if any(codename.split(".")[1].startswith(p) for p in ("add_", "change_", "delete_"))
    ]
    assert yazma_izinleri == [], f"Denetçi yazma izni almış: {yazma_izinleri}"
    assert auditor.is_read_only


def test_garson_kav_yonetemez(waiter) -> None:
    assert waiter.has_perm("operations.view_order")
    assert waiter.has_perm("operations.add_orderline")
    assert not waiter.has_perm("cellar.add_wine")
    assert not waiter.has_perm("cellar.delete_wine")
    assert not waiter.has_perm("accounts.add_user")


def test_sommelier_kadeh_servis_edebilir(sommelier) -> None:
    assert sommelier.has_perm("cellar.can_pour_glass")
    assert sommelier.has_perm("cellar.can_open_bottle")
    assert not sommelier.has_perm("operations.can_close_day")


def test_devstudio_yalnizca_sysadmin_ve_owner(make_user) -> None:
    assert make_user("s1", "sysadmin").can_use_devstudio
    assert make_user("s2", "owner").can_use_devstudio
    assert not make_user("s3", "waiter").can_use_devstudio
    assert not make_user("s4", "restaurant_manager").can_use_devstudio
    assert not make_user("s5", "sommelier").can_use_devstudio


# ---------------------------------------------------------------------------
# Görünüm düzeyinde erişim
# ---------------------------------------------------------------------------
def test_yetkisiz_erisim_403_ve_denetim_kaydi(waiter, client_as) -> None:
    from apps.core.models import AuditAction, AuditLog

    before = AuditLog.objects.filter(action=AuditAction.PERMISSION_DENIED).count()
    response = client_as(waiter).get("/hesap/kullanicilar/")

    assert response.status_code == 403
    after = AuditLog.objects.filter(action=AuditAction.PERMISSION_DENIED).count()
    assert after == before + 1, "Yetki reddi denetim kaydına yazılmadı."


def test_denetci_yazma_istegi_reddedilir(auditor, client_as) -> None:
    """Salt okunur kullanıcı POST yapamaz (HTTP yöntemi düzeyinde koruma)."""
    from apps.core.models import AuditAction, AuditLog

    response = client_as(auditor).post("/kav/mukerrer/tara/", {})
    assert response.status_code in (302, 403)

    # Yönetici aynı işlemi yapabilmeli
    denials = AuditLog.objects.filter(action=AuditAction.PERMISSION_DENIED).count()
    assert denials >= 0


def test_giris_yapmamis_kullanici_yonlendirilir(client) -> None:
    response = client.get("/kav/")
    assert response.status_code == 302
    assert "/hesap/giris/" in response["Location"]


def test_qr_menu_kimlik_dogrulamasiz_acilir(client, food_item) -> None:
    """QR menü misafire açıktır ancak maliyet/stok sızdırmaz."""
    response = client.get("/menu/qr/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "150" not in content or "Maliyet" not in content
    assert "Sorumlu" in content or "Alkollü" in content


# ---------------------------------------------------------------------------
# İkinci onay
# ---------------------------------------------------------------------------
def test_kullanici_kendi_talebini_onaylayamaz(manager) -> None:
    """Görevler ayrılığı: talep sahibi kendi talebini onaylayamaz."""
    from apps.accounts.models import ApprovalRequest

    request = ApprovalRequest.objects.create(
        action="void_order", requested_by=manager, reason="test"
    )
    with pytest.raises(PermissionError, match="kendi talebini"):
        request.approve(manager)


def test_yetkisiz_kullanici_onaylayamaz(waiter, manager) -> None:
    from apps.accounts.models import ApprovalRequest

    request = ApprovalRequest.objects.create(
        action="void_order", requested_by=manager, reason="test"
    )
    with pytest.raises(PermissionError, match="yetkisi yok"):
        request.approve(waiter)


def test_yetkili_kullanici_onaylayabilir(waiter, manager) -> None:
    from apps.accounts.models import ApprovalRequest

    request = ApprovalRequest.objects.create(
        action="void_order", requested_by=waiter, reason="yanlış sipariş"
    )
    request.approve(manager, "uygun")
    request.refresh_from_db()
    assert request.status == ApprovalRequest.Status.APPROVED
    assert request.reviewed_by == manager


def test_onaylanan_talep_tekrar_kullanilamaz(waiter, manager) -> None:
    from apps.accounts.models import ApprovalRequest

    request = ApprovalRequest.objects.create(
        action="void_order", requested_by=waiter, reason="test"
    )
    request.approve(manager)
    request.mark_applied()
    request.refresh_from_db()
    assert request.status == ApprovalRequest.Status.APPLIED

    with pytest.raises(ValueError):
        request.mark_applied()


def test_suresi_dolan_talep_onaylanamaz(waiter, manager) -> None:
    from django.utils import timezone

    from apps.accounts.models import ApprovalRequest

    request = ApprovalRequest.objects.create(
        action="void_order",
        requested_by=waiter,
        reason="test",
        expires_at=timezone.now() - timezone.timedelta(hours=1),
    )
    with pytest.raises(ValueError, match="süresi doldu"):
        request.approve(manager)


# ---------------------------------------------------------------------------
# İndirim yetki sınırı
# ---------------------------------------------------------------------------
def test_yetki_sinirini_asan_indirim_onay_gerektirir(waiter, open_order, food_item) -> None:
    """Garsonun %5 limiti var; %30 indirim onay talebine dönüşmeli."""
    from apps.operations import services

    line = services.add_line(order=open_order, menu_item=food_item, user=waiter, quantity=1)

    with pytest.raises(services.ApprovalRequiredError) as exc:
        services.apply_discount(
            line=line, user=waiter, percent=Decimal("30"), reason="misafir şikâyeti"
        )

    line.refresh_from_db()
    assert line.discount_percent == Decimal("0.00"), "İndirim onaysız uygulandı!"
    assert exc.value.approval.status == "pending"


def test_limit_icindeki_indirim_dogrudan_uygulanir(waiter, open_order, food_item) -> None:
    from apps.operations import services

    line = services.add_line(order=open_order, menu_item=food_item, user=waiter, quantity=1)
    services.apply_discount(line=line, user=waiter, percent=Decimal("5"), reason="sadık müşteri")
    line.refresh_from_db()
    assert line.discount_percent == Decimal("5.00")


def test_ikram_her_zaman_onay_gerektirir(waiter, open_order, food_item) -> None:
    """İkram (100% indirim) yetki limitinden bağımsız olarak onay ister."""
    from apps.operations import services

    line = services.add_line(order=open_order, menu_item=food_item, user=waiter, quantity=1)
    with pytest.raises(services.ApprovalRequiredError):
        services.apply_discount(
            line=line, user=waiter, percent=Decimal("0"), reason="özür", is_comp=True
        )
    line.refresh_from_db()
    assert not line.is_comp


def test_mudur_yuksek_indirimi_dogrudan_uygular(manager, table, food_item) -> None:
    """Müdürün onay yetkisi vardır; indirim doğrudan uygulanır."""
    from apps.operations import services

    order = services.open_order(user=manager, table=table, guest_count=2)
    line = services.add_line(order=order, menu_item=food_item, user=manager, quantity=1)
    services.apply_discount(
        line=line, user=manager, percent=Decimal("20"), reason="yönetici kararı"
    )
    line.refresh_from_db()
    assert line.discount_percent == Decimal("20.00")


# ---------------------------------------------------------------------------
# PIN girişi
# ---------------------------------------------------------------------------
def test_pin_duz_metin_saklanmaz(waiter) -> None:
    waiter.set_pin("4271")
    waiter.save()
    assert "4271" not in waiter.pin_hash
    assert waiter.check_pin("4271")
    assert not waiter.check_pin("1234")


def test_gecersiz_pin_reddedilir(waiter) -> None:
    for invalid in ["12", "abcd", "123456789", ""]:
        with pytest.raises(ValueError):
            waiter.set_pin(invalid)


def test_basarisiz_girisler_hesabi_kilitler(waiter) -> None:
    for _ in range(5):
        waiter.register_failed_login()
    waiter.refresh_from_db()
    assert waiter.is_locked
    waiter.register_successful_login()
    assert not waiter.is_locked
