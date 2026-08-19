"""Müşteri ilişkileri REST API'si.

GİZLİLİK: Müşteri iletişim bilgileri (telefon, e-posta) yalnızca
``crm.view_customer_contact`` iznine sahip kullanıcılara döndürülür.
Diğer kullanıcılar maskelenmiş değer görür.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.security import redact_key
from apps.crm.models import (
    Campaign,
    ConsentRecord,
    Customer,
    CustomerVisitNote,
    DataErasureRequest,
    LoyaltyAccount,
    LoyaltyProgram,
    LoyaltyTransaction,
)


class ConsentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentRecord
        fields = [
            "id",
            "customer",
            "purpose",
            "is_granted",
            "granted_at",
            "withdrawn_at",
            "collection_method",
            "policy_version",
            "note",
        ]


class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    visit_count = serializers.IntegerField(read_only=True)
    lifetime_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    average_spend = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    phone = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    consents = ConsentRecordSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "code",
            "first_name",
            "last_name",
            "full_name",
            "company_name",
            "phone",
            "email",
            "birth_day",
            "birth_month",
            "segment",
            "preferred_language",
            "dietary_notes",
            "allergy_notes",
            "notes",
            "is_vip",
            "is_blacklisted",
            "first_visit_on",
            "last_visit_on",
            "visit_count",
            "lifetime_value",
            "average_spend",
            "consents",
        ]

    def _can_view_contact(self) -> bool:
        request = self.context.get("request")
        if request is None:
            return False
        return bool(request.user.has_perm("crm.view_customer_contact") or request.user.is_superuser)

    def get_phone(self, obj: Customer) -> str:
        return obj.phone if self._can_view_contact() else redact_key(obj.phone, keep=2)

    def get_email(self, obj: Customer) -> str:
        return obj.email if self._can_view_contact() else redact_key(obj.email, keep=2)


class LoyaltyAccountSerializer(serializers.ModelSerializer):
    redeemable_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = LoyaltyAccount
        fields = [
            "id",
            "customer",
            "program",
            "card_number",
            "points_balance",
            "tier",
            "joined_on",
            "is_active",
            "redeemable_amount",
        ]
        read_only_fields = ["points_balance"]


class LoyaltyTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyTransaction
        fields = ["id", "account", "kind", "points", "order", "occurred_at", "expires_on", "note"]
        read_only_fields = ["occurred_at"]


class LoyaltyProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyProgram
        fields = "__all__"


class CampaignSerializer(serializers.ModelSerializer):
    eligible_count = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "name",
            "description",
            "channel",
            "status",
            "starts_on",
            "ends_on",
            "target_segments",
            "price_rule",
            "requires_consent",
            "eligible_count",
        ]

    def get_eligible_count(self, obj: Campaign) -> int:
        return obj.eligible_customers().count()


class VisitNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerVisitNote
        fields = ["id", "customer", "order", "kind", "note", "recorded_by", "is_resolved"]
        read_only_fields = ["recorded_by"]


class DataErasureRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataErasureRequest
        fields = [
            "id",
            "customer",
            "requested_on",
            "status",
            "completed_at",
            "rejection_reason",
            "retained_records_note",
        ]


# ---------------------------------------------------------------------------
# Görünüm kümeleri
# ---------------------------------------------------------------------------
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.filter(is_deleted=False).prefetch_related("consents")
    serializer_class = CustomerSerializer
    search_fields = ["code", "first_name", "last_name", "company_name"]
    ordering_fields = ["last_name", "last_visit_on"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        segment = self.request.query_params.get("segment")
        if segment:
            queryset = queryset.filter(segment=segment)
        if self.request.query_params.get("vip") == "1":
            queryset = queryset.filter(is_vip=True)
        # Şifreli alanda arama: geri döndürülemez HMAC özeti üzerinden
        phone = self.request.query_params.get("phone")
        if phone:
            from apps.core.fields import blind_index

            queryset = queryset.filter(phone_index=blind_index(phone))
        return queryset

    @action(detail=True, methods=["get"])
    def export_data(self, request: Request, pk: str | None = None) -> Response:
        """KVKK veri taşınabilirliği: müşterinin tüm verisini dışa aktarır."""
        if not request.user.has_perm("crm.can_export_customer_data"):
            return Response({"detail": "Yetkiniz yok."}, status=status.HTTP_403_FORBIDDEN)

        from apps.crm.services import export_customer_data

        customer = self.get_object()
        return Response(export_customer_data(customer=customer, user=request.user))

    @action(detail=True, methods=["post"])
    def request_erasure(self, request: Request, pk: str | None = None) -> Response:
        """KVKK silme talebi oluşturur (uygulanması onaya bağlıdır)."""
        customer = self.get_object()
        erasure = DataErasureRequest.objects.create(customer=customer, created_by=request.user)
        return Response(DataErasureRequestSerializer(erasure).data, status=status.HTTP_201_CREATED)


class ConsentRecordViewSet(viewsets.ModelViewSet):
    queryset = ConsentRecord.objects.select_related("customer")
    serializer_class = ConsentRecordSerializer

    def perform_create(self, serializer: Any) -> None:
        from django.utils import timezone

        from apps.core.audit import record
        from apps.core.models import AuditAction

        consent = serializer.save(
            collected_by=self.request.user,
            granted_at=timezone.now() if serializer.validated_data.get("is_granted") else None,
            created_by=self.request.user,
        )
        record(
            action=AuditAction.CONSENT,
            obj=consent,
            message=(
                f"Rıza kaydedildi: {consent.get_purpose_display()} · "
                f"{'verildi' if consent.is_granted else 'reddedildi'}"
            ),
            actor=self.request.user,
        )


class LoyaltyAccountViewSet(viewsets.ModelViewSet):
    queryset = LoyaltyAccount.objects.select_related("customer", "program")
    serializer_class = LoyaltyAccountSerializer
    search_fields = ["card_number"]


class LoyaltyTransactionViewSet(viewsets.ModelViewSet):
    queryset = LoyaltyTransaction.objects.select_related("account")
    serializer_class = LoyaltyTransactionSerializer


class LoyaltyProgramViewSet(viewsets.ModelViewSet):
    queryset = LoyaltyProgram.objects.all()
    serializer_class = LoyaltyProgramSerializer


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.select_related("price_rule")
    serializer_class = CampaignSerializer


class VisitNoteViewSet(viewsets.ModelViewSet):
    queryset = CustomerVisitNote.objects.select_related("customer", "order")
    serializer_class = VisitNoteSerializer

    def perform_create(self, serializer: Any) -> None:
        serializer.save(recorded_by=self.request.user)
