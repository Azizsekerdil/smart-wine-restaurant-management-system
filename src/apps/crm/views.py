"""Müşteri ilişkileri görünümleri."""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.crm.models import Campaign, ConsentRecord, Customer, DataErasureRequest


class CustomerListView(AuditedPermissionMixin, ListView):
    """Müşteri listesi."""

    template_name = "crm/customer_list.html"
    context_object_name = "customers"
    paginate_by = 50
    required_permissions = ["crm.view_customer"]

    def get_queryset(self) -> QuerySet[Customer]:
        queryset = Customer.objects.filter(is_deleted=False)
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(company_name__icontains=query)
                | Q(code__icontains=query)
            )
        # Telefonla arama: şifreli alan üzerinde HMAC özeti ile
        phone = self.request.GET.get("phone", "").strip()
        if phone:
            from apps.core.fields import blind_index

            queryset = queryset.filter(phone_index=blind_index(phone))
        segment = self.request.GET.get("segment", "").strip()
        if segment:
            queryset = queryset.filter(segment=segment)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["segments"] = Customer.Segment.choices
        context["filters"] = {
            "q": self.request.GET.get("q", ""),
            "phone": self.request.GET.get("phone", ""),
            "segment": self.request.GET.get("segment", ""),
        }
        context["can_view_contact"] = self.request.user.has_perm("crm.view_customer_contact")
        return context


class CustomerDetailView(AuditedPermissionMixin, DetailView):
    """Müşteri kartı: tercihler, ziyaretler, rızalar."""

    template_name = "crm/customer_detail.html"
    context_object_name = "customer"
    required_permissions = ["crm.view_customer"]

    def get_queryset(self) -> QuerySet[Customer]:
        return Customer.objects.filter(is_deleted=False).prefetch_related(
            "consents", "favorite_wines", "favorite_menu_items"
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        customer: Customer = self.object
        context["orders"] = customer.orders.filter(status="paid").order_by("-opened_at")[:20]
        context["reservations"] = customer.reservations.order_by("-reserved_for")[:20]
        context["visit_notes"] = customer.visit_notes.all()[:20]
        context["loyalty"] = getattr(customer, "loyalty_account", None)
        context["consent_purposes"] = ConsentRecord.Purpose.choices
        context["can_view_contact"] = self.request.user.has_perm("crm.view_customer_contact")
        context["can_export"] = self.request.user.has_perm("crm.can_export_customer_data")
        return context


class CampaignListView(AuditedPermissionMixin, ListView):
    """Kampanyalar.

    NOT: Toplu e-posta/SMS gönderimi bu sürümde **Planlandı** durumundadır;
    kampanya tanımı ve hedef kitle hesabı çalışır.
    """

    template_name = "crm/campaign_list.html"
    context_object_name = "campaigns"
    required_permissions = ["crm.view_campaign"]

    def get_queryset(self) -> QuerySet[Campaign]:
        return Campaign.objects.select_related("price_rule")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dispatch_status"] = "planned"
        context["dispatch_note"] = (
            "Toplu e-posta/SMS gönderimi bu sürümde etkin değildir (Planlandı). "
            "Kampanya tanımı, hedef kitle ve rıza denetimi çalışmaktadır."
        )
        return context


class PrivacyCenterView(AuditedPermissionMixin, TemplateView):
    """KVKK/GDPR merkezi: rıza durumu ve silme talepleri."""

    template_name = "crm/privacy_center.html"
    required_permissions = ["crm.view_customer"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        from django.conf import settings

        context = super().get_context_data(**kwargs)
        context["erasure_requests"] = DataErasureRequest.objects.select_related(
            "customer", "approval"
        ).order_by("-requested_on")[:50]

        consent_summary = []
        for value, label in ConsentRecord.Purpose.choices:
            granted = ConsentRecord.objects.filter(
                purpose=value, is_granted=True, withdrawn_at__isnull=True
            ).count()
            withdrawn = ConsentRecord.objects.filter(
                purpose=value, withdrawn_at__isnull=False
            ).count()
            consent_summary.append({"purpose": label, "granted": granted, "withdrawn": withdrawn})
        context["consent_summary"] = consent_summary
        context["retention_policy"] = settings.DATA_RETENTION_DAYS
        context["ai_privacy_mode"] = settings.AI_SETTINGS.get("PRIVACY_MODE", True)
        context["ai_local_only"] = settings.AI_SETTINGS.get("LOCAL_ONLY", False)
        context["encryption_enabled"] = bool(settings.FIELD_ENCRYPTION_KEY)
        return context
