"""Müşteri verisi servisleri: sadakat, dışa aktarım ve KVKK silme."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.audit import record
from apps.core.models import AuditAction, AuditSeverity
from apps.crm.models import (
    Customer,
    DataErasureRequest,
    LoyaltyAccount,
    LoyaltyTransaction,
)

logger = logging.getLogger(__name__)


class CrmError(RuntimeError):
    """Müşteri işlemi iş kuralı ihlali."""


# ---------------------------------------------------------------------------
# Sadakat
# ---------------------------------------------------------------------------
@transaction.atomic
def award_points(*, order: Any, user: Any) -> LoyaltyTransaction | None:
    """Ödenen adisyon için sadakat puanı kazandırır.

    Rıza kontrolü: profil analizi rızası olmayan müşteri için puan
    kazanımı yapılmaz (veri işleme temeli yok).
    """
    if order.customer_id is None:
        return None

    account = (
        LoyaltyAccount.objects.filter(customer=order.customer, is_active=True)
        .select_related("program")
        .first()
    )
    if account is None or not account.program.is_active:
        return None

    points = int(order.grand_total * account.program.points_per_currency)
    if points <= 0:
        return None

    expires = None
    if account.program.points_expire_days:
        expires = timezone.localdate() + timezone.timedelta(days=account.program.points_expire_days)

    entry = LoyaltyTransaction.objects.create(
        account=account,
        kind=LoyaltyTransaction.Kind.EARN,
        points=points,
        order=order,
        expires_on=expires,
        note=f"Adisyon {order.number}",
    )
    account.points_balance += points
    account.save(update_fields=["points_balance", "updated_at"])

    return entry


@transaction.atomic
def redeem_points(
    *, account: LoyaltyAccount, points: int, user: Any, order: Any = None
) -> LoyaltyTransaction:
    """Puan kullandırır."""
    if points <= 0:
        raise CrmError("Kullanılacak puan sıfırdan büyük olmalıdır.")
    if points > account.points_balance:
        raise CrmError(f"Yetersiz puan. Bakiye: {account.points_balance}, istenen: {points}.")
    if points < account.program.minimum_redeem_points:
        raise CrmError(f"Asgari kullanım puanı {account.program.minimum_redeem_points}.")

    entry = LoyaltyTransaction.objects.create(
        account=account,
        kind=LoyaltyTransaction.Kind.REDEEM,
        points=-points,
        order=order,
        note="Puan kullanımı",
    )
    account.points_balance -= points
    account.save(update_fields=["points_balance", "updated_at"])

    record(
        action=AuditAction.UPDATE,
        obj=entry,
        message=f"Sadakat puanı kullanıldı: {points} puan · kart {account.card_number}",
        actor=user,
    )
    return entry


# ---------------------------------------------------------------------------
# KVKK: dışa aktarım
# ---------------------------------------------------------------------------
def export_customer_data(*, customer: Customer, user: Any) -> dict[str, Any]:
    """Müşterinin tüm kişisel verisini yapılandırılmış olarak döndürür.

    KVKK md. 11 ve GDPR md. 20 (veri taşınabilirliği) kapsamındadır.
    """
    payload: dict[str, Any] = {
        "musteri": {
            "kod": customer.code,
            "ad": customer.first_name,
            "soyad": customer.last_name,
            "firma": customer.company_name,
            "telefon": customer.phone,
            "eposta": customer.email,
            "dogum_gun_ay": (
                f"{customer.birth_day:02d}.{customer.birth_month:02d}"
                if customer.birth_day and customer.birth_month
                else None
            ),
            "segment": customer.get_segment_display(),
            "dil": customer.preferred_language,
            "beslenme_notlari": customer.dietary_notes,
            "alerji_notlari": customer.allergy_notes,
            "ilk_ziyaret": customer.first_visit_on,
            "son_ziyaret": customer.last_visit_on,
        },
        "rizalar": [
            {
                "amac": consent.get_purpose_display(),
                "verildi": consent.is_granted,
                "verilme_zamani": consent.granted_at,
                "geri_cekilme": consent.withdrawn_at,
                "yontem": consent.collection_method,
            }
            for consent in customer.consents.all()
        ],
        "ziyaretler": [
            {
                "adisyon": order.number,
                "tarih": order.opened_at,
                "tutar": str(order.grand_total),
                "kisi": order.guest_count,
            }
            for order in customer.orders.filter(status="paid").order_by("-opened_at")[:200]
        ],
        "favori_saraplar": [str(wine) for wine in customer.favorite_wines.all()],
        "favori_yemekler": [item.name_tr for item in customer.favorite_menu_items.all()],
        "notlar": [
            {"tur": note.get_kind_display(), "not": note.note, "tarih": note.created_at}
            for note in customer.visit_notes.all()[:100]
        ],
        "sadakat": None,
        "olusturulma_zamani": timezone.now(),
    }

    account = getattr(customer, "loyalty_account", None)
    if account is not None:
        payload["sadakat"] = {
            "kart_no": account.card_number,
            "puan": account.points_balance,
            "kademe": account.tier,
            "hareketler": [
                {
                    "tur": entry.get_kind_display(),
                    "puan": entry.points,
                    "tarih": entry.occurred_at,
                }
                for entry in account.transactions.all()[:200]
            ],
        }

    record(
        action=AuditAction.EXPORT,
        obj=customer,
        message=f"Müşteri verisi dışa aktarıldı (KVKK): {customer.code}",
        severity=AuditSeverity.NOTICE,
        actor=user,
    )
    return payload


# ---------------------------------------------------------------------------
# KVKK: silme / anonimleştirme
# ---------------------------------------------------------------------------
@transaction.atomic
def anonymize_customer(*, erasure: DataErasureRequest, user: Any) -> Customer:
    """Müşterinin kişisel verilerini anonimleştirir.

    Mali kayıtlar (adisyon tutarları, ödemeler) **silinmez**; yasal saklama
    yükümlülüğü gereği korunur ve müşteri bağlantısı koparılır.

    Onay zorunludur: ``erasure.approval`` onaylanmış olmalıdır.
    """
    if erasure.status == DataErasureRequest.Status.COMPLETED:
        raise CrmError("Silme talebi zaten tamamlanmış.")
    if erasure.approval is None or erasure.approval.status != "approved":
        raise CrmError("Veri silme işlemi ikinci onay gerektirir. Önce onay talebini onaylatın.")

    customer = erasure.customer
    anonymous_code = f"ANON-{customer.pk}"

    retained = {
        "adisyon_sayisi": customer.orders.count(),
        "rezervasyon_sayisi": customer.reservations.count(),
    }

    # Mali kayıtlarla bağı kopar
    customer.orders.update(customer=None)
    customer.reservations.update(customer=None)

    # Kişisel alanları temizle
    customer.first_name = "Anonimleştirilmiş"
    customer.last_name = ""
    customer.company_name = ""
    customer.phone = ""
    customer.email = ""
    customer.birth_date = ""
    customer.birth_day = None
    customer.birth_month = None
    customer.dietary_notes = ""
    customer.allergy_notes = ""
    customer.notes = ""
    customer.code = anonymous_code
    customer.is_deleted = True
    customer.deleted_at = timezone.now()
    customer.save()

    customer.favorite_wines.clear()
    customer.favorite_menu_items.clear()
    customer.visit_notes.all().delete()
    customer.consents.update(withdrawn_at=timezone.now(), is_granted=False)

    erasure.status = DataErasureRequest.Status.COMPLETED
    erasure.completed_at = timezone.now()
    erasure.retained_records_note = (
        "Yasal saklama yükümlülüğü nedeniyle mali kayıtlar korunmuştur "
        f"(kişi bağlantısı kaldırıldı): {retained}"
    )
    erasure.save(update_fields=["status", "completed_at", "retained_records_note", "updated_at"])

    record(
        action=AuditAction.DATA_ERASURE,
        obj=erasure,
        message=(
            f"Müşteri verisi anonimleştirildi (KVKK): {anonymous_code} · "
            f"korunan mali kayıtlar: {retained}"
        ),
        severity=AuditSeverity.CRITICAL,
        actor=user,
    )
    return customer


def customers_missing_consent(purpose: str) -> list[Customer]:
    """Belirtilen amaç için geçerli rızası olmayan müşteriler."""
    return [
        customer
        for customer in Customer.objects.filter(is_deleted=False)
        if not customer.has_consent(purpose)
    ]


def segment_customers() -> dict[str, int]:
    """Müşterileri harcama ve ziyaret sıklığına göre yeniden sınıflandırır.

    Bu işlem yalnızca *önerilen* segmenti hesaplar; kaydı değiştirmez.
    """
    counts: dict[str, int] = {}
    for customer in Customer.objects.filter(is_deleted=False):
        value = customer.lifetime_value
        visits = customer.visit_count
        if customer.is_vip or value >= Decimal("50000"):
            suggested = Customer.Segment.VIP
        elif customer.company_name:
            suggested = Customer.Segment.CORPORATE
        elif visits >= 5:
            suggested = Customer.Segment.REGULAR
        elif visits == 0:
            suggested = Customer.Segment.NEW
        else:
            suggested = Customer.Segment.NEW
        counts[suggested] = counts.get(suggested, 0) + 1
    return counts
