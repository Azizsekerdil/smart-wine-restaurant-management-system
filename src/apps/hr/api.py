"""İnsan kaynakları REST API'si.

GİZLİLİK: Kimlik numarası, IBAN ve adres gibi özel nitelikli veriler
yalnızca ``hr.view_employee_sensitive`` iznine sahip kullanıcılara döner.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers, viewsets

from apps.hr.models import (
    Employee,
    LeaveRequest,
    PerformanceMetric,
    Shift,
    ShiftAssignment,
)


class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    leave_days_remaining = serializers.IntegerField(read_only=True)
    sensitive = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id",
            "user",
            "employee_code",
            "first_name",
            "last_name",
            "full_name",
            "job_title",
            "department",
            "employment_type",
            "status",
            "hired_on",
            "terminated_on",
            "annual_leave_days",
            "leave_days_remaining",
            "notes",
            "sensitive",
        ]

    def get_sensitive(self, obj: Employee) -> dict[str, Any] | None:
        request = self.context.get("request")
        if request is None:
            return None
        if not (request.user.has_perm("hr.view_employee_sensitive") or request.user.is_superuser):
            return None
        return {
            "national_id": obj.national_id,
            "phone": obj.phone,
            "email": obj.email,
            "emergency_contact": obj.emergency_contact,
            "address": obj.address,
            "iban": obj.iban,
            "hourly_rate": str(obj.hourly_rate),
        }


class ShiftSerializer(serializers.ModelSerializer):
    assigned_count = serializers.IntegerField(read_only=True)
    is_understaffed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Shift
        fields = [
            "id",
            "template",
            "shift_date",
            "starts_at",
            "ends_at",
            "status",
            "required_staff",
            "assigned_count",
            "is_understaffed",
            "notes",
        ]


class ShiftAssignmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    worked_hours = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = ShiftAssignment
        fields = [
            "id",
            "shift",
            "employee",
            "employee_name",
            "role_code",
            "section",
            "assigned_tables",
            "clock_in_at",
            "clock_out_at",
            "is_cancelled",
            "note",
            "worked_hours",
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    day_count = serializers.IntegerField(read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "employee_name",
            "leave_type",
            "start_date",
            "end_date",
            "status",
            "reason",
            "reviewed_by",
            "review_note",
            "day_count",
        ]
        read_only_fields = ["reviewed_by"]


class PerformanceMetricSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = PerformanceMetric
        fields = "__all__"


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.filter(is_deleted=False).select_related("user")
    serializer_class = EmployeeSerializer
    search_fields = ["employee_code", "first_name", "last_name", "job_title"]

    def get_queryset(self):  # type: ignore[override]
        queryset = super().get_queryset()
        department = self.request.query_params.get("department")
        if department:
            queryset = queryset.filter(department=department)
        if self.request.query_params.get("active") == "1":
            queryset = queryset.filter(status=Employee.Status.ACTIVE)
        return queryset


class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.select_related("template").prefetch_related("assignments")
    serializer_class = ShiftSerializer


class ShiftAssignmentViewSet(viewsets.ModelViewSet):
    queryset = ShiftAssignment.objects.select_related("shift", "employee", "section")
    serializer_class = ShiftAssignmentSerializer


class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.select_related("employee", "reviewed_by")
    serializer_class = LeaveRequestSerializer


class PerformanceMetricViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PerformanceMetric.objects.select_related("employee")
    serializer_class = PerformanceMetricSerializer
