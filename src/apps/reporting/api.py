"""Raporlama REST API'si."""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.reporting import reports
from apps.reporting.models import DailySalesSnapshot, ReportDefinition, ReportRun, SalesForecast


class ReportDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportDefinition
        fields = "__all__"


class ReportRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportRun
        fields = "__all__"


class DailySalesSnapshotSerializer(serializers.ModelSerializer):
    average_check = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    average_per_guest = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    gross_margin_percent = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    wine_share_percent = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    no_show_rate = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = DailySalesSnapshot
        fields = "__all__"


class SalesForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesForecast
        fields = "__all__"


class ReportViewSet(viewsets.ReadOnlyModelViewSet):
    """Kayıtlı rapor tanımları ve çalıştırma."""

    queryset = ReportDefinition.objects.filter(is_active=True)
    serializer_class = ReportDefinitionSerializer

    @action(detail=False, methods=["get"])
    def catalog(self, request: Request) -> Response:
        """Kullanıcının erişebildiği raporların kataloğu."""
        specs = reports.available_reports(request.user)
        return Response(
            [
                {
                    "code": spec.code,
                    "name_tr": spec.name_tr,
                    "name_en": spec.name_en,
                    "category": spec.category,
                    "is_experimental": spec.is_experimental,
                    "description": spec.description,
                }
                for spec in specs
            ]
        )

    @action(detail=False, methods=["get"], url_path=r"run/(?P<code>[\w-]+)")
    def run(self, request: Request, code: str = "") -> Response:
        """Raporu JSON olarak çalıştırır."""
        try:
            spec = reports.get_report(code)
        except KeyError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        if spec.permission and not (
            request.user.has_perm(spec.permission) or request.user.is_superuser
        ):
            return Response({"detail": "Yetkiniz yok."}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        try:
            start = (
                date.fromisoformat(request.query_params.get("start", ""))
                if request.query_params.get("start")
                else today - timedelta(days=29)
            )
            end = (
                date.fromisoformat(request.query_params.get("end", ""))
                if request.query_params.get("end")
                else today
            )
        except ValueError:
            return Response(
                {"detail": "Tarih biçimi geçersiz (YYYY-AA-GG bekleniyor)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        table = spec.generator(reports.ReportParams(start_date=start, end_date=end))
        return Response(
            {
                "title": table.title,
                "subtitle": table.subtitle,
                "columns": table.columns,
                "rows": [[str(cell) for cell in row] for row in table.rows],
                "totals": [str(cell) for cell in table.totals] if table.totals else None,
                "row_count": len(table.rows),
            }
        )


class ReportRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReportRun.objects.select_related("definition", "run_by")
    serializer_class = ReportRunSerializer


class DailySalesSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailySalesSnapshot.objects.all()
    serializer_class = DailySalesSnapshotSerializer


class SalesForecastViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SalesForecast.objects.all()
    serializer_class = SalesForecastSerializer
