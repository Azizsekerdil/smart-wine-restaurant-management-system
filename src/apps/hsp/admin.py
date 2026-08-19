"""HSP yönetim ekranları.

Makbuzlar salt-okunurdur; zincir bütünlüğü el ile düzenlemeye izin vermez.
İnceleme talepleri yalnızca onayla/reddet aksiyonlarıyla karara bağlanır;
onay 7 gün geçerlidir ve denetim kaydı üretir.
"""

from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from apps.core.audit import record
from apps.core.models import AuditAction, AuditSeverity
from apps.hsp.models import HSPPolicyRule, HSPReviewRequest, RightsReceipt

#: İnceleme onayının geçerlilik süresi — kalıcı yetki oluşmaz (§17.1).
REVIEW_APPROVAL_VALIDITY = timedelta(days=7)


@admin.register(HSPPolicyRule)
class HSPPolicyRuleAdmin(admin.ModelAdmin):
    list_display = ("feature", "decision", "version", "is_active", "approved_by", "approved_at")
    list_filter = ("decision", "is_active")
    search_fields = ("feature", "reason")


@admin.register(HSPReviewRequest)
class HSPReviewRequestAdmin(admin.ModelAdmin):
    list_display = (
        "feature",
        "status",
        "requested_by_label",
        "created_at",
        "decided_by",
        "expires_at",
    )
    list_filter = ("status", "feature")
    actions = ["approve_requests", "reject_requests"]

    def has_add_permission(self, request):  # noqa: ARG002 - kuyruk yalnızca gateway'den beslenir
        return False

    @admin.action(description="Seçili talepleri ONAYLA (7 gün geçerli)")
    def approve_requests(self, request, queryset):
        now = timezone.now()
        count = 0
        for review in queryset.filter(status=HSPReviewRequest.Status.PENDING):
            review.status = HSPReviewRequest.Status.APPROVED
            review.decided_by = request.user
            review.decided_at = now
            review.expires_at = now + REVIEW_APPROVAL_VALIDITY
            review.save(
                update_fields=["status", "decided_by", "decided_at", "expires_at", "updated_at"]
            )
            record(
                action=AuditAction.AI_REQUEST,
                obj=review,
                message=f"HSP inceleme onayı: işlev={review.feature}, geçerlilik={review.expires_at:%Y-%m-%d %H:%M}",
                severity=AuditSeverity.NOTICE,
                request=request,
            )
            count += 1
        self.message_user(request, f"{count} talep onaylandı (7 gün geçerli).")

    @admin.action(description="Seçili talepleri REDDET")
    def reject_requests(self, request, queryset):
        now = timezone.now()
        count = 0
        for review in queryset.filter(status=HSPReviewRequest.Status.PENDING):
            review.status = HSPReviewRequest.Status.REJECTED
            review.decided_by = request.user
            review.decided_at = now
            review.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
            record(
                action=AuditAction.AI_REQUEST,
                obj=review,
                message=f"HSP inceleme reddi: işlev={review.feature}",
                severity=AuditSeverity.NOTICE,
                request=request,
            )
            count += 1
        self.message_user(request, f"{count} talep reddedildi.")


@admin.register(RightsReceipt)
class RightsReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "feature", "data_class", "decision", "provider", "outcome")
    list_filter = ("decision", "data_class", "feature")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):  # noqa: ARG002
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False
