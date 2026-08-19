"""Personel, vardiya, izin ve performans modelleri."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.fields import EncryptedCharField
from apps.core.models import SoftDeleteModel, TimeStampedModel


class Employee(SoftDeleteModel):
    """Personel kartı.

    Kimlik ve iletişim bilgileri özel nitelikli kişisel veri sayıldığından
    şifreli saklanır ve yalnızca İK rolü görüntüleyebilir.
    """

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", _("Tam zamanlı")
        PART_TIME = "part_time", _("Yarı zamanlı")
        SEASONAL = "seasonal", _("Sezonluk")
        INTERN = "intern", _("Stajyer")
        CONTRACTOR = "contractor", _("Sözleşmeli")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Çalışıyor")
        ON_LEAVE = "on_leave", _("İzinde")
        SUSPENDED = "suspended", _("Askıda")
        TERMINATED = "terminated", _("Ayrıldı")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Sistem kullanıcısı"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employee",
    )
    employee_code = models.CharField(_("Personel kodu"), max_length=20, unique=True, db_index=True)
    first_name = models.CharField(_("Ad"), max_length=100)
    last_name = models.CharField(_("Soyad"), max_length=100)
    job_title = models.CharField(_("Görev"), max_length=120)
    department = models.CharField(
        _("Departman"),
        max_length=40,
        choices=[
            ("service", _("Servis")),
            ("kitchen", _("Mutfak")),
            ("bar", _("Bar")),
            ("cellar", _("Kav")),
            ("management", _("Yönetim")),
            ("back_office", _("Arka ofis")),
        ],
        default="service",
    )
    employment_type = models.CharField(
        _("Çalışma şekli"),
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )

    # --- Şifreli kişisel veriler ---
    national_id = EncryptedCharField(_("Kimlik numarası"), blank=True, default="")
    phone = EncryptedCharField(_("Telefon"), blank=True, default="")
    email = EncryptedCharField(_("E-posta"), blank=True, default="")
    emergency_contact = EncryptedCharField(_("Acil durum iletişim"), blank=True, default="")
    address = EncryptedCharField(_("Adres"), blank=True, default="")
    iban = EncryptedCharField(_("IBAN"), blank=True, default="")

    hired_on = models.DateField(_("İşe giriş"), default=timezone.localdate)
    terminated_on = models.DateField(_("Çıkış tarihi"), null=True, blank=True)
    hourly_rate = models.DecimalField(
        _("Saatlik ücret"), max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    annual_leave_days = models.PositiveSmallIntegerField(_("Yıllık izin hakkı (gün)"), default=14)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Personel")
        verbose_name_plural = _("Personel")
        ordering = ["last_name", "first_name"]
        permissions = [
            ("view_employee_sensitive", _("Personel hassas bilgilerini görebilir")),
            ("can_manage_payroll", _("Bordro bilgilerini yönetebilir")),
        ]

    def __str__(self) -> str:
        return f"{self.employee_code} · {self.full_name}"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def leave_days_used(self) -> int:
        return sum(
            request.day_count
            for request in self.leave_requests.filter(
                status=LeaveRequest.Status.APPROVED,
                leave_type=LeaveRequest.LeaveType.ANNUAL,
                start_date__year=timezone.localdate().year,
            )
        )

    @property
    def leave_days_remaining(self) -> int:
        return max(0, self.annual_leave_days - self.leave_days_used)


class ShiftTemplate(TimeStampedModel):
    """Vardiya şablonu (sabah, akşam, kapanış)."""

    code = models.CharField(_("Kod"), max_length=30, unique=True)
    name = models.CharField(_("Ad"), max_length=100)
    starts_at = models.TimeField(_("Başlangıç saati"))
    ends_at = models.TimeField(_("Bitiş saati"))
    break_minutes = models.PositiveSmallIntegerField(_("Mola (dk)"), default=30)
    is_active = models.BooleanField(_("Etkin"), default=True)

    class Meta:
        verbose_name = _("Vardiya şablonu")
        verbose_name_plural = _("Vardiya şablonları")
        ordering = ["starts_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.starts_at:%H:%M}-{self.ends_at:%H:%M})"


class Shift(TimeStampedModel):
    """Belirli bir güne ait vardiya."""

    class Status(models.TextChoices):
        PLANNED = "planned", _("Planlandı")
        PUBLISHED = "published", _("Yayınlandı")
        COMPLETED = "completed", _("Tamamlandı")
        CANCELLED = "cancelled", _("İptal")

    template = models.ForeignKey(
        ShiftTemplate,
        verbose_name=_("Şablon"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="shifts",
    )
    shift_date = models.DateField(_("Tarih"), db_index=True)
    starts_at = models.DateTimeField(_("Başlangıç"))
    ends_at = models.DateTimeField(_("Bitiş"))
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.PLANNED
    )
    required_staff = models.PositiveSmallIntegerField(_("Gerekli personel"), default=1)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Vardiya")
        verbose_name_plural = _("Vardiyalar")
        ordering = ["-shift_date", "starts_at"]

    def __str__(self) -> str:
        return f"{self.shift_date:%d.%m.%Y} · {self.starts_at:%H:%M}-{self.ends_at:%H:%M}"

    @property
    def assigned_count(self) -> int:
        return self.assignments.filter(is_cancelled=False).count()

    @property
    def is_understaffed(self) -> bool:
        return self.assigned_count < self.required_staff


class ShiftAssignment(TimeStampedModel):
    """Personelin vardiyaya ve bölgeye atanması."""

    shift = models.ForeignKey(
        Shift, verbose_name=_("Vardiya"), on_delete=models.CASCADE, related_name="assignments"
    )
    employee = models.ForeignKey(
        Employee,
        verbose_name=_("Personel"),
        on_delete=models.PROTECT,
        related_name="shift_assignments",
    )
    role_code = models.CharField(_("Görev rolü"), max_length=40, blank=True)
    section = models.ForeignKey(
        "operations.FloorSection",
        verbose_name=_("Bölge"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shift_assignments",
    )
    assigned_tables = models.ManyToManyField(
        "operations.DiningTable",
        verbose_name=_("Atanan masalar"),
        blank=True,
        related_name="shift_assignments",
    )
    clock_in_at = models.DateTimeField(_("Giriş saati"), null=True, blank=True)
    clock_out_at = models.DateTimeField(_("Çıkış saati"), null=True, blank=True)
    is_cancelled = models.BooleanField(_("İptal"), default=False)
    note = models.CharField(_("Not"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Vardiya ataması")
        verbose_name_plural = _("Vardiya atamaları")
        ordering = ["shift__shift_date"]
        constraints = [
            models.UniqueConstraint(fields=["shift", "employee"], name="uniq_shift_employee")
        ]

    def __str__(self) -> str:
        return f"{self.employee.full_name} · {self.shift}"

    @property
    def worked_hours(self) -> Decimal:
        if not (self.clock_in_at and self.clock_out_at):
            return Decimal("0.00")
        seconds = (self.clock_out_at - self.clock_in_at).total_seconds()
        break_seconds = (self.shift.template.break_minutes * 60) if self.shift.template else 0
        return (Decimal(max(0, seconds - break_seconds)) / Decimal(3600)).quantize(Decimal("0.01"))


class LeaveRequest(TimeStampedModel):
    """İzin talebi."""

    class LeaveType(models.TextChoices):
        ANNUAL = "annual", _("Yıllık izin")
        SICK = "sick", _("Hastalık izni")
        UNPAID = "unpaid", _("Ücretsiz izin")
        MATERNITY = "maternity", _("Doğum izni")
        BEREAVEMENT = "bereavement", _("Ölüm izni")
        OTHER = "other", _("Diğer")

    class Status(models.TextChoices):
        PENDING = "pending", _("Onay bekliyor")
        APPROVED = "approved", _("Onaylandı")
        REJECTED = "rejected", _("Reddedildi")
        CANCELLED = "cancelled", _("İptal")

    employee = models.ForeignKey(
        Employee,
        verbose_name=_("Personel"),
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    leave_type = models.CharField(_("İzin türü"), max_length=20, choices=LeaveType.choices)
    start_date = models.DateField(_("Başlangıç"))
    end_date = models.DateField(_("Bitiş"))
    status = models.CharField(
        _("Durum"), max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reason = models.TextField(_("Gerekçe"), blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Karar veren"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_leaves",
    )
    review_note = models.CharField(_("Karar notu"), max_length=250, blank=True)

    class Meta:
        verbose_name = _("İzin talebi")
        verbose_name_plural = _("İzin talepleri")
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="leave_end_after_start",
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee.full_name} · {self.get_leave_type_display()}"

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1


class PerformanceMetric(TimeStampedModel):
    """Dönemsel personel performans göstergesi.

    Ölçümler satış verisinden türetilir; sübjektif değerlendirme ayrı
    ``manager_score`` alanında tutulur ve karıştırılmaz.
    """

    employee = models.ForeignKey(
        Employee,
        verbose_name=_("Personel"),
        on_delete=models.CASCADE,
        related_name="performance_metrics",
    )
    period_start = models.DateField(_("Dönem başı"))
    period_end = models.DateField(_("Dönem sonu"))

    orders_served = models.PositiveIntegerField(_("Adisyon sayısı"), default=0)
    guests_served = models.PositiveIntegerField(_("Misafir sayısı"), default=0)
    total_sales = models.DecimalField(_("Toplam satış"), max_digits=14, decimal_places=2, default=0)
    average_check = models.DecimalField(
        _("Ortalama adisyon"), max_digits=12, decimal_places=2, default=0
    )
    wine_sales = models.DecimalField(_("Şarap satışı"), max_digits=14, decimal_places=2, default=0)
    wine_attach_rate = models.DecimalField(
        _("Şarap ekleme oranı (%)"),
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text=_("Şarap içeren adisyonların toplam adisyona oranı."),
    )
    void_count = models.PositiveIntegerField(_("İptal sayısı"), default=0)
    discount_total = models.DecimalField(
        _("Verilen indirim"), max_digits=14, decimal_places=2, default=0
    )
    average_service_minutes = models.DecimalField(
        _("Ortalama servis süresi (dk)"), max_digits=6, decimal_places=2, default=0
    )
    manager_score = models.PositiveSmallIntegerField(
        _("Yönetici değerlendirmesi (1-5)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    manager_comment = models.TextField(_("Yönetici yorumu"), blank=True)

    class Meta:
        verbose_name = _("Performans göstergesi")
        verbose_name_plural = _("Performans göstergeleri")
        ordering = ["-period_end"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "period_start", "period_end"], name="uniq_employee_period"
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee.full_name} · {self.period_start} → {self.period_end}"


class EmployeeTrainingRecord(TimeStampedModel):
    """Personelin tamamladığı eğitim kaydı."""

    class Result(models.TextChoices):
        COMPLETED = "completed", _("Tamamlandı")
        IN_PROGRESS = "in_progress", _("Devam ediyor")
        FAILED = "failed", _("Başarısız")

    employee = models.ForeignKey(
        Employee,
        verbose_name=_("Personel"),
        on_delete=models.CASCADE,
        related_name="training_records",
    )
    module = models.ForeignKey(
        "training.TrainingModule",
        verbose_name=_("Eğitim modülü"),
        on_delete=models.PROTECT,
        related_name="employee_records",
    )
    started_on = models.DateField(_("Başlangıç"), default=timezone.localdate)
    completed_on = models.DateField(_("Tamamlanma"), null=True, blank=True)
    result = models.CharField(
        _("Sonuç"), max_length=20, choices=Result.choices, default=Result.IN_PROGRESS
    )
    score = models.PositiveSmallIntegerField(_("Puan"), null=True, blank=True)
    certificate_number = models.CharField(_("Sertifika no"), max_length=40, blank=True)
    notes = models.TextField(_("Notlar"), blank=True)

    class Meta:
        verbose_name = _("Eğitim kaydı")
        verbose_name_plural = _("Eğitim kayıtları")
        ordering = ["-started_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "module"], name="uniq_employee_training_module"
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee.full_name} · {self.module}"
