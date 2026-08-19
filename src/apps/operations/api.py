"""Salon operasyonu REST API'si."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.operations import services
from apps.operations.models import (
    BusinessDay,
    DiningTable,
    FloorSection,
    Order,
    OrderLine,
    Payment,
    PaymentMethod,
    PrepTicket,
    Reservation,
    WaitlistEntry,
)


class FloorSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FloorSection
        fields = ["id", "code", "name", "name_en", "is_outdoor", "is_private", "is_active"]


class DiningTableSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source="section.name", read_only=True)
    status_badge_class = serializers.CharField(read_only=True)

    class Meta:
        model = DiningTable
        fields = [
            "id",
            "section",
            "section_name",
            "number",
            "name",
            "seats",
            "status",
            "status_badge_class",
            "position_x",
            "position_y",
            "shape",
            "is_combinable",
            "is_active",
        ]


class OrderLineSerializer(serializers.ModelSerializer):
    gross_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    discount_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    net_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = OrderLine
        fields = [
            "id",
            "order",
            "menu_item",
            "wine",
            "service_unit",
            "item_name",
            "quantity",
            "unit_price",
            "tax_rate",
            "discount_percent",
            "discount_reason",
            "is_comp",
            "seat_number",
            "course",
            "special_instructions",
            "is_voided",
            "sent_at",
            "served_at",
            "gross_amount",
            "discount_amount",
            "net_amount",
            "tax_amount",
            "total_amount",
        ]
        read_only_fields = ["item_name", "unit_price", "tax_rate", "sent_at", "served_at"]


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    amount_due = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    table_label = serializers.CharField(source="table.label", read_only=True, default="")

    class Meta:
        model = Order
        fields = [
            "id",
            "number",
            "channel",
            "table",
            "table_label",
            "reservation",
            "customer",
            "guest_count",
            "server",
            "status",
            "opened_at",
            "closed_at",
            "subtotal",
            "discount_total",
            "service_charge",
            "service_charge_percent",
            "tax_total",
            "grand_total",
            "amount_paid",
            "amount_due",
            "notes",
            "lines",
        ]
        read_only_fields = [
            "number",
            "subtotal",
            "discount_total",
            "service_charge",
            "tax_total",
            "grand_total",
            "closed_at",
        ]


class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            "id",
            "code",
            "customer",
            "guest_name",
            "guest_count",
            "reserved_for",
            "duration_minutes",
            "tables",
            "section_preference",
            "status",
            "source",
            "special_requests",
            "allergy_notes",
            "occasion",
            "deposit_amount",
            "seated_at",
        ]
        read_only_fields = ["code", "seated_at"]


class WaitlistEntrySerializer(serializers.ModelSerializer):
    waiting_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = WaitlistEntry
        fields = [
            "id",
            "guest_name",
            "guest_count",
            "customer",
            "joined_at",
            "quoted_wait_minutes",
            "status",
            "notified_at",
            "seated_at",
            "note",
            "waiting_minutes",
        ]


class PrepTicketSerializer(serializers.ModelSerializer):
    elapsed_minutes = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    urgency_class = serializers.CharField(read_only=True)
    order_number = serializers.CharField(source="order.number", read_only=True)
    table_label = serializers.CharField(source="order.table.label", read_only=True, default="")
    lines = serializers.SerializerMethodField()

    class Meta:
        model = PrepTicket
        fields = [
            "id",
            "order",
            "order_number",
            "table_label",
            "ticket_number",
            "station",
            "status",
            "priority",
            "course",
            "sent_at",
            "started_at",
            "ready_at",
            "served_at",
            "target_minutes",
            "elapsed_minutes",
            "is_overdue",
            "urgency_class",
            "note",
            "lines",
        ]

    def get_lines(self, obj: PrepTicket) -> list[dict[str, Any]]:
        return [
            {
                "id": line.pk,
                "item_name": line.item_name,
                "quantity": str(line.quantity),
                "special_instructions": line.special_instructions,
                "allergen_warning": line.allergen_warning,
                "is_done": line.is_done,
            }
            for line in obj.lines.all()
        ]


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "code",
            "name",
            "kind",
            "requires_reference",
            "opens_cash_drawer",
            "commission_percent",
            "is_active",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    method_name = serializers.CharField(source="method.name", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "method",
            "method_name",
            "amount",
            "tip_amount",
            "received_at",
            "received_by",
            "reference",
            "gateway_mode",
            "split_label",
            "is_voided",
        ]
        read_only_fields = ["gateway_mode", "received_by"]


class BusinessDaySerializer(serializers.ModelSerializer):
    cash_variance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = BusinessDay
        fields = "__all__"


# ---------------------------------------------------------------------------
# Görünüm kümeleri
# ---------------------------------------------------------------------------
class FloorSectionViewSet(viewsets.ModelViewSet):
    queryset = FloorSection.objects.all()
    serializer_class = FloorSectionSerializer


class DiningTableViewSet(viewsets.ModelViewSet):
    queryset = DiningTable.objects.select_related("section").filter(is_active=True)
    serializer_class = DiningTableSerializer
    search_fields = ["number", "name"]


class OrderViewSet(viewsets.ModelViewSet):
    queryset = (
        Order.objects.filter(is_deleted=False)
        .select_related("table", "customer", "server")
        .prefetch_related("lines", "payments")
    )
    serializer_class = OrderSerializer
    search_fields = ["number"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        if self.request.query_params.get("open") == "1":
            queryset = queryset.filter(status__in=Order.OPEN_STATUSES)
        table = self.request.query_params.get("table")
        if table:
            queryset = queryset.filter(table_id=table)
        return queryset

    @action(detail=True, methods=["post"])
    def add_line(self, request: Request, pk: str | None = None) -> Response:
        """Adisyona satır ekler."""
        from apps.catalog.models import MenuItem

        order = self.get_object()
        menu_item = MenuItem.objects.filter(
            pk=request.data.get("menu_item"), is_deleted=False
        ).first()
        if menu_item is None:
            return Response({"detail": "Menü ürünü bulunamadı."}, status=status.HTTP_404_NOT_FOUND)
        try:
            line = services.add_line(
                order=order,
                menu_item=menu_item,
                user=request.user,
                quantity=request.data.get("quantity", 1),
                service_unit=request.data.get("service_unit", OrderLine.ServiceUnit.PORTION),
                seat_number=request.data.get("seat_number"),
                course=int(request.data.get("course", 1)),
                special_instructions=request.data.get("special_instructions", ""),
            )
        except services.OperationsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderLineSerializer(line).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def send(self, request: Request, pk: str | None = None) -> Response:
        """Bekleyen satırları istasyonlara gönderir (KOT üretir)."""
        order = self.get_object()
        tickets = services.send_to_stations(order=order, user=request.user)
        return Response(
            {"tickets": PrepTicketSerializer(tickets, many=True).data, "count": len(tickets)}
        )

    @action(detail=True, methods=["post"])
    def split(self, request: Request, pk: str | None = None) -> Response:
        """Hesabı koltuk bazında böler."""
        order = self.get_object()
        try:
            result = services.split_order_by_seat(order=order, user=request.user)
        except services.OperationsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "source": OrderSerializer(result.source).data,
                "created": OrderSerializer(result.created, many=True).data,
            }
        )

    @action(detail=True, methods=["post"])
    def pay(self, request: Request, pk: str | None = None) -> Response:
        """Tahsilat kaydeder (sandbox)."""
        order = self.get_object()
        method = PaymentMethod.objects.filter(pk=request.data.get("method"), is_active=True).first()
        if method is None:
            return Response(
                {"detail": "Ödeme yöntemi bulunamadı."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            payment = services.take_payment(
                order=order,
                method=method,
                amount=Decimal(str(request.data.get("amount", "0"))),
                user=request.user,
                tip_amount=request.data.get("tip_amount"),
                reference=request.data.get("reference", ""),
                split_label=request.data.get("split_label", ""),
            )
        except (services.OperationsError, ArithmeticError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "amount_due": str(order.amount_due),
                "order_status": order.status,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def void(self, request: Request, pk: str | None = None) -> Response:
        """Adisyonu iptal eder (onay gerekebilir)."""
        order = self.get_object()
        try:
            services.void_order(
                order=order, user=request.user, reason=request.data.get("reason", "")
            )
        except services.ApprovalRequiredError as exc:
            return Response(
                {"detail": str(exc), "approval_id": exc.approval.pk},
                status=status.HTTP_202_ACCEPTED,
            )
        except services.OperationsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        return Response(OrderSerializer(order).data)


class PrepTicketViewSet(viewsets.ModelViewSet):
    queryset = PrepTicket.objects.select_related("order", "order__table").prefetch_related("lines")
    serializer_class = PrepTicketSerializer

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        station = self.request.query_params.get("station")
        if station:
            queryset = queryset.filter(station=station)
        if self.request.query_params.get("active") == "1":
            queryset = queryset.filter(
                status__in=[
                    PrepTicket.Status.QUEUED,
                    PrepTicket.Status.PREPARING,
                    PrepTicket.Status.READY,
                ]
            )
        return queryset

    @action(detail=True, methods=["post"])
    def bump(self, request: Request, pk: str | None = None) -> Response:
        """Fişi bir sonraki duruma ilerletir."""
        ticket = self.get_object()
        try:
            updated = services.bump_ticket(
                ticket=ticket, user=request.user, target_status=request.data.get("status", "")
            )
        except services.OperationsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PrepTicketSerializer(updated).data)


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.filter(is_deleted=False).prefetch_related("tables")
    serializer_class = ReservationSerializer
    search_fields = ["code", "guest_name"]

    def perform_create(self, serializer: Any) -> None:
        code = services._next_sequence(Reservation, "code", "RZV")
        serializer.save(code=code, created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def assign_tables(self, request: Request, pk: str | None = None) -> Response:
        """Rezervasyona masa atar; çakışma varsa reddeder."""
        reservation = self.get_object()
        tables = list(DiningTable.objects.filter(pk__in=request.data.get("tables", [])))
        try:
            services.assign_tables(reservation=reservation, tables=tables, user=request.user)
        except services.OperationsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(ReservationSerializer(reservation).data)


class WaitlistEntryViewSet(viewsets.ModelViewSet):
    queryset = WaitlistEntry.objects.select_related("customer")
    serializer_class = WaitlistEntrySerializer


class PaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = PaymentMethod.objects.filter(is_active=True)
    serializer_class = PaymentMethodSerializer


class BusinessDayViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BusinessDay.objects.all()
    serializer_class = BusinessDaySerializer

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: str | None = None) -> Response:
        """Gün sonu kapanışı."""
        day = self.get_object()
        if not request.user.has_perm("operations.can_close_day"):
            return Response({"detail": "Yetkiniz yok."}, status=status.HTTP_403_FORBIDDEN)
        try:
            closed = services.close_business_day(
                business_day=day,
                user=request.user,
                cash_counted=Decimal(str(request.data.get("cash_counted", "0"))),
            )
        except (services.OperationsError, ArithmeticError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BusinessDaySerializer(closed).data)
