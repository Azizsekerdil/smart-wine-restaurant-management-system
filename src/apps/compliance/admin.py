"""Uyum motoru yönetim ekranları.

Kural paketleri yalnızca "Yürürlüğe al" aksiyonuyla ACTIVE olur; onay
checksum + imza üretir ve denetim kaydı düşer. Onaydan sonra kural içeriği
değişirse imza tutmaz ve motor paketi kullanmaz.
"""

from django.contrib import admin

from apps.compliance.models import LegalRule, LegalRulePack, LegalSource
from apps.compliance.rulepacks import approve_pack, verify_pack


@admin.register(LegalSource)
class LegalSourceAdmin(admin.ModelAdmin):
    list_display = ("title", "jurisdiction", "authority", "article", "retrieved_on")
    list_filter = ("jurisdiction", "authority")
    search_fields = ("title", "url")


class LegalRuleInline(admin.TabularInline):
    model = LegalRule
    extra = 0
    fields = ("rule_code", "title_tr", "severity", "deadline_value", "deadline_unit", "source")


@admin.register(LegalRulePack)
class LegalRulePackAdmin(admin.ModelAdmin):
    list_display = (
        "regulation_code",
        "jurisdiction",
        "version",
        "status",
        "rule_count",
        "signature_valid",
        "approved_by",
        "approved_at",
    )
    list_filter = ("jurisdiction", "regulation_code", "status")
    inlines = [LegalRuleInline]
    actions = ["activate_packs"]

    @admin.display(description="Kural sayısı")
    def rule_count(self, obj):
        return obj.rules.count()

    @admin.display(description="İmza geçerli", boolean=True)
    def signature_valid(self, obj):
        if obj.status != LegalRulePack.Status.ACTIVE:
            return None
        return verify_pack(obj)

    @admin.action(description="Yürürlüğe al (onay + imza)")
    def activate_packs(self, request, queryset):
        count = 0
        for pack in queryset.filter(status=LegalRulePack.Status.DRAFT):
            try:
                approve_pack(pack, approved_by=request.user)
            except ValueError as exc:
                self.message_user(request, f"{pack}: {exc}", level="error")
                continue
            count += 1
        self.message_user(request, f"{count} paket yürürlüğe alındı.")


@admin.register(LegalRule)
class LegalRuleAdmin(admin.ModelAdmin):
    list_display = ("rule_code", "pack", "severity", "deadline_value", "deadline_unit", "source")
    list_filter = ("pack__regulation_code", "severity")
    search_fields = ("rule_code", "title_tr", "title_en")
