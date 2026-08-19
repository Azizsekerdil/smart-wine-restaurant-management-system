"""Human Sovereignty Protocol (HSP) veri modelleri.

İki varlık tutulur:

* :class:`HSPPolicyRule` — sürümlü ve **onay bayraklı** politika kuralı.
  Kurallar varsayılan sınıflandırmayı yalnızca *sıkılaştırabilir*; gevşetme
  kod değişikliği (sürümlü, gözden geçirilen) gerektirir. Onaysız veya pasif
  kural hiçbir karar üretemez.
* :class:`RightsReceipt` — her HSP değerlendirmesi için hash zincirine bağlı
  işlem makbuzu. Ham istem metni veya kişisel veri **içermez**; yalnızca
  karar, sınıf ve bütünlük bilgisi tutar.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class DataClass(models.TextChoices):
    """Veri sınıflandırma etiketi (prompt §12)."""

    PUBLIC = "public", _("Açık")
    INTERNAL = "internal", _("Kurum içi")
    CONFIDENTIAL = "confidential", _("Gizli")
    RESTRICTED = "restricted", _("Kısıtlı")
    UNKNOWN = "unknown", _("Bilinmiyor")


class PersonalDataClass(models.TextChoices):
    """Kişisel veri metadata'sı — veri sınıfından ayrı tutulur."""

    NON_PERSONAL = "non_personal", _("Kişisel değil")
    PERSONAL = "personal", _("Kişisel")
    SENSITIVE = "sensitive", _("Özel nitelikli")
    UNKNOWN = "unknown", _("Bilinmiyor")


class HSPDecision(models.TextChoices):
    """Karar kümesi. Sıralama katılık sırasıdır (ALLOW en gevşek)."""

    ALLOW = "allow", _("İzin")
    ALLOW_WITH_LIMITS = "allow_with_limits", _("Sınırlı izin")
    LOCAL_ONLY = "local_only", _("Yalnızca yerel")
    REQUIRE_HUMAN_REVIEW = "require_human_review", _("İnsan incelemesi gerekli")
    DENY = "deny", _("Red")


#: Katılık sırası — etkin karar, varsayılan ile kuralların en katısıdır.
DECISION_STRICTNESS: dict[str, int] = {
    HSPDecision.ALLOW: 0,
    HSPDecision.ALLOW_WITH_LIMITS: 1,
    HSPDecision.LOCAL_ONLY: 2,
    HSPDecision.REQUIRE_HUMAN_REVIEW: 3,
    HSPDecision.DENY: 4,
}


class HSPPolicyRule(TimeStampedModel):
    """Yönetici tanımlı, sürümlü sıkılaştırma kuralı.

    Bir kural ancak ``is_active`` **ve** onaylanmış (``approved_by`` dolu)
    ise değerlendirmeye katılır. Kural, ilgili işlevin varsayılan kararından
    daha gevşek bir karar dayatamaz — motor her zaman en katı kararı seçer.
    """

    feature = models.CharField(
        _("AI işlevi"),
        max_length=30,
        db_index=True,
        help_text=_("aiservices.AIFeature kodu; '*' tüm işlevler demektir."),
    )
    decision = models.CharField(
        _("Karar"), max_length=32, choices=HSPDecision.choices, default=HSPDecision.LOCAL_ONLY
    )
    reason = models.CharField(_("Gerekçe"), max_length=255, blank=True)
    version = models.PositiveIntegerField(_("Sürüm"), default=1)
    is_active = models.BooleanField(_("Aktif"), default=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Onaylayan"),
        related_name="approved_hsp_rules",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(_("Onay zamanı"), null=True, blank=True)

    class Meta:
        verbose_name = _("HSP politika kuralı")
        verbose_name_plural = _("HSP politika kuralları")
        ordering = ["feature", "-version"]

    def __str__(self) -> str:
        return f"{self.feature} → {self.decision} (v{self.version})"

    @property
    def is_effective(self) -> bool:
        """Kuralın karar üretmeye yetkili olup olmadığı."""
        return bool(self.is_active and self.approved_by_id and self.approved_at)


class HSPReviewRequest(TimeStampedModel):
    """``REQUIRE_HUMAN_REVIEW`` kararı için insan onay kuyruğu kaydı.

    Onaysız istek fail-safe olarak yalnızca yerel çalışır. Geçerli (onaylı ve
    süresi dolmamış) bir kayıt, ilgili işlevin bulut yolunu *sınırlı izinle*
    (``ALLOW_WITH_LIMITS``) açar. Onay süreli ve denetim kayıtlıdır — sessiz
    veya kalıcı yetki oluşturmaz (prompt §17.1).
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Beklemede")
        APPROVED = "approved", _("Onaylandı")
        REJECTED = "rejected", _("Reddedildi")

    feature = models.CharField(_("AI işlevi"), max_length=30, db_index=True)
    requested_by_label = models.CharField(_("Talep eden"), max_length=150, blank=True)
    status = models.CharField(
        _("Durum"), max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reason = models.CharField(_("Gerekçe"), max_length=255, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Karar veren"),
        related_name="decided_hsp_reviews",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(_("Karar zamanı"), null=True, blank=True)
    expires_at = models.DateTimeField(
        _("Onay geçerlilik sonu"),
        null=True,
        blank=True,
        help_text=_("Onay bu andan sonra geçersizdir; yeni inceleme gerekir."),
    )

    class Meta:
        verbose_name = _("HSP inceleme talebi")
        verbose_name_plural = _("HSP inceleme talepleri")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.feature} · {self.status}"

    @property
    def grants_cloud(self) -> bool:
        """Onayın şu an bulut yolunu açıp açmadığı."""
        from django.utils import timezone

        return bool(
            self.status == self.Status.APPROVED
            and self.decided_by_id
            and self.expires_at
            and self.expires_at > timezone.now()
        )


class RightsReceipt(models.Model):
    """Hash zincirine bağlı HSP işlem makbuzu.

    Zincir: ``integrity_hash = SHA-256(prev_hash + kanonik_yük)``. İmza,
    ``SECRET_KEY`` türevli anahtar ile HMAC-SHA256'dır — bu bir *prototip*
    bütünlük mekanizmasıdır; production kriptografi iddiası taşımaz
    (bkz. docs/IMPLEMENTATION_PLAN.md).

    Makbuz ham istem metni, yanıt veya kişisel veri içermez.
    """

    created_at = models.DateTimeField(_("Oluşturma"), auto_now_add=True, db_index=True)
    actor_label = models.CharField(_("Aktör"), max_length=150, blank=True)
    feature = models.CharField(_("AI işlevi"), max_length=30, db_index=True)
    action = models.CharField(_("Eylem"), max_length=30, default="TRANSFER")
    data_class = models.CharField(_("Veri sınıfı"), max_length=16, choices=DataClass.choices)
    personal_class = models.CharField(
        _("Kişisel veri sınıfı"), max_length=16, choices=PersonalDataClass.choices
    )
    decision = models.CharField(_("Karar"), max_length=32, choices=HSPDecision.choices)
    applied_rule_ids = models.JSONField(_("Uygulanan kurallar"), default=list, blank=True)
    enforced_limits = models.JSONField(_("Uygulanan sınırlar"), default=dict, blank=True)
    provider = models.CharField(_("Sağlayıcı"), max_length=40, blank=True)
    model = models.CharField(_("Model"), max_length=120, blank=True)
    outcome = models.CharField(_("Sonuç"), max_length=20, blank=True)
    prev_hash = models.CharField(_("Önceki hash"), max_length=64, blank=True)
    integrity_hash = models.CharField(_("Bütünlük hash'i"), max_length=64, unique=True)
    signature = models.CharField(_("İmza"), max_length=64)

    class Meta:
        verbose_name = _("Haklar makbuzu")
        verbose_name_plural = _("Haklar makbuzları")
        ordering = ["id"]

    def __str__(self) -> str:
        return f"receipt#{self.pk} {self.feature} {self.decision}"
