"""İnsan kaynakları görünümleri."""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from apps.accounts.permissions import AuditedPermissionMixin
from apps.hr.models import Employee, LeaveRequest, PerformanceMetric, Shift


class EmployeeListView(AuditedPermissionMixin, ListView):
    """Personel listesi."""

    template_name = "hr/employee_list.html"
    context_object_name = "employees"
    paginate_by = 50
    required_permissions = ["hr.view_employee"]

    def get_queryset(self) -> QuerySet[Employee]:
        queryset = Employee.objects.filter(is_deleted=False).select_related("user")
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(employee_code__icontains=query)
            )
        department = self.request.GET.get("department", "").strip()
        if department:
            queryset = queryset.filter(department=department)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["departments"] = Employee._meta.get_field("department").choices
        context["filters"] = {
            "q": self.request.GET.get("q", ""),
            "department": self.request.GET.get("department", ""),
        }
        return context


class EmployeeDetailView(AuditedPermissionMixin, DetailView):
    """Personel kartı."""

    template_name = "hr/employee_detail.html"
    context_object_name = "employee"
    required_permissions = ["hr.view_employee"]

    def get_queryset(self) -> QuerySet[Employee]:
        return Employee.objects.filter(is_deleted=False).select_related("user")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        employee: Employee = self.object
        context["assignments"] = employee.shift_assignments.select_related(
            "shift", "section"
        ).order_by("-shift__shift_date")[:20]
        context["leaves"] = employee.leave_requests.order_by("-start_date")[:20]
        context["metrics"] = employee.performance_metrics.order_by("-period_end")[:12]
        context["training"] = employee.training_records.select_related("module")
        context["can_view_sensitive"] = self.request.user.has_perm("hr.view_employee_sensitive")
        return context


class ShiftListView(AuditedPermissionMixin, ListView):
    """Vardiya planı."""

    template_name = "hr/shift_list.html"
    context_object_name = "shifts"
    paginate_by = 60
    required_permissions = ["hr.view_shift"]

    def get_queryset(self) -> QuerySet[Shift]:
        return (
            Shift.objects.select_related("template")
            .prefetch_related("assignments__employee")
            .filter(shift_date__gte=timezone.localdate() - timezone.timedelta(days=7))
            .order_by("shift_date", "starts_at")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        shifts = list(context["shifts"])
        context["understaffed"] = [shift for shift in shifts if shift.is_understaffed]
        return context


class LeaveRequestListView(AuditedPermissionMixin, ListView):
    """İzin talepleri."""

    template_name = "hr/leave_list.html"
    context_object_name = "leaves"
    paginate_by = 50
    required_permissions = ["hr.view_leaverequest"]

    def get_queryset(self) -> QuerySet[LeaveRequest]:
        queryset = LeaveRequest.objects.select_related("employee", "reviewed_by")
        status_filter = self.request.GET.get("status", "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["status_choices"] = LeaveRequest.Status.choices
        context["selected_status"] = self.request.GET.get("status", "")
        context["pending_count"] = LeaveRequest.objects.filter(
            status=LeaveRequest.Status.PENDING
        ).count()
        return context


class PerformanceView(AuditedPermissionMixin, TemplateView):
    """Personel performans göstergeleri."""

    template_name = "hr/performance.html"
    required_permissions = ["hr.view_performancemetric"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        metrics = PerformanceMetric.objects.select_related("employee").order_by(
            "-period_end", "-total_sales"
        )[:100]
        context["metrics"] = metrics
        context["has_data"] = bool(metrics)
        context["note"] = (
            "Göstergeler satış verisinden türetilir. Yönetici değerlendirmesi "
            "ayrı alanda tutulur ve otomatik hesaplanan verilerle karıştırılmaz."
        )
        return context
