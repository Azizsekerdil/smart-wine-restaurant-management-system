"""CAIO gözlem ve bulgu üretimi.

CAIO yalnızca **gözlemler ve önerir**. Hiçbir koşulda üretim kodunu
değiştirmez, dal birleştirmez, sürüm yayınlamaz veya kullanıcı verisini
buluta göndermez.
"""

from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from apps.caio.models import Finding, ObservationRun

logger = logging.getLogger(__name__)


def _fingerprint(*parts: str) -> str:
    """Bulgu için kararlı parmak izi üretir (kopya bulgu oluşmaz)."""
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:64]


def _record_finding(
    *,
    run: ObservationRun,
    category: str,
    severity: str,
    title: str,
    description: str,
    recommendation: str,
    evidence: dict[str, Any],
    key: str,
) -> Finding:
    """Bulguyu oluşturur veya var olanın sayacını artırır."""
    fingerprint = _fingerprint(category, key)
    now = timezone.now()

    finding = Finding.objects.filter(fingerprint=fingerprint).first()
    if finding is not None:
        finding.occurrence_count += 1
        finding.last_seen_at = now
        finding.severity = severity
        finding.description = description
        finding.evidence = evidence
        finding.recommendation = recommendation
        if finding.status == Finding.Status.RESOLVED:
            finding.status = Finding.Status.OPEN
        finding.save(
            update_fields=[
                "occurrence_count",
                "last_seen_at",
                "severity",
                "description",
                "evidence",
                "recommendation",
                "status",
                "updated_at",
            ]
        )
        return finding

    return Finding.objects.create(
        run=run,
        category=category,
        severity=severity,
        title=title,
        description=description,
        recommendation=recommendation,
        evidence=evidence,
        fingerprint=fingerprint,
        first_seen_at=now,
        last_seen_at=now,
    )


@transaction.atomic
def run_observation(
    *, user: Any, days: int = 7, trigger: str = ObservationRun.Trigger.MANUAL
) -> ObservationRun:
    """Belirtilen dönem için gözlem koşumu yapar ve bulgular üretir."""
    from apps.aiservices.models import AICallLog, AIQualityFeedback

    end = timezone.now()
    start = end - timezone.timedelta(days=days)

    run = ObservationRun.objects.create(
        trigger=trigger,
        status=ObservationRun.Status.RUNNING,
        period_start=start,
        period_end=end,
        started_by=user if getattr(user, "pk", None) else None,
        created_by=user if getattr(user, "pk", None) else None,
    )

    calls = AICallLog.objects.filter(occurred_at__gte=start, occurred_at__lte=end)
    stats = calls.aggregate(
        total=Count("id"),
        tokens=Sum("prompt_tokens") + Sum("completion_tokens"),
        cost=Sum("estimated_cost_usd"),
        latency=Avg("latency_ms"),
    )
    failed = calls.filter(outcome=AICallLog.Outcome.FAILED).count()
    fallback = calls.filter(outcome=AICallLog.Outcome.FALLBACK).count()
    low_rated = AIQualityFeedback.objects.filter(created_at__gte=start, rating__lte=2).count()

    run.ai_calls_examined = stats["total"] or 0
    run.failed_calls = failed
    run.fallback_calls = fallback
    run.low_rated_responses = low_rated
    run.total_tokens = stats["tokens"] or 0
    run.total_cost_usd = stats["cost"] or Decimal("0")
    run.average_latency_ms = int(stats["latency"] or 0)

    findings: list[Finding] = []

    # --- 1) Sağlayıcı güvenilirliği ---
    if run.ai_calls_examined >= 10 and run.failure_rate > Decimal("20.00"):
        findings.append(
            _record_finding(
                run=run,
                category=Finding.Category.AI_RELIABILITY,
                severity=Finding.Severity.HIGH,
                title="Yapay zekâ çağrılarında yüksek başarısızlık oranı",
                description=(
                    f"Son {days} günde {run.ai_calls_examined} çağrının "
                    f"{failed} tanesi başarısız oldu (%{run.failure_rate})."
                ),
                recommendation=(
                    "LM Studio sunucusunun açık ve model yüklü olduğunu doğrulayın. "
                    "Bulut sağlayıcı kullanılıyorsa API anahtarı ve kota durumunu "
                    "kontrol edin. Zaman aşımı süresini artırmayı değerlendirin."
                ),
                evidence={"total": run.ai_calls_examined, "failed": failed},
                key="ai_failure_rate",
            )
        )

    # --- 2) Sık yedeğe düşme ---
    if run.ai_calls_examined >= 10 and fallback > run.ai_calls_examined * 0.3:
        findings.append(
            _record_finding(
                run=run,
                category=Finding.Category.AI_RELIABILITY,
                severity=Finding.Severity.MEDIUM,
                title="Birincil sağlayıcı sık sık yedeğe düşüyor",
                description=(
                    f"{fallback} çağrı yedek sağlayıcıya yönlendirildi. Birincil "
                    "sağlayıcı kararsız çalışıyor olabilir."
                ),
                recommendation=(
                    "Birincil sağlayıcının sağlık kontrolünü çalıştırın ve varsayılan "
                    "sağlayıcı seçimini gözden geçirin."
                ),
                evidence={"fallback": fallback, "total": run.ai_calls_examined},
                key="ai_fallback_rate",
            )
        )

    # --- 3) Bütçe ---
    from apps.aiservices.services import current_budget

    budget = current_budget()
    if budget.should_warn:
        findings.append(
            _record_finding(
                run=run,
                category=Finding.Category.AI_COST,
                severity=(Finding.Severity.HIGH if budget.is_exceeded else Finding.Severity.MEDIUM),
                title="Yapay zekâ bütçesi eşiğe yaklaştı",
                description=(
                    f"Bu ay {budget.spent_usd} USD harcandı; sınır {budget.limit_usd} USD "
                    f"(%{budget.usage_percent})."
                ),
                recommendation=(
                    "Yerel model kullanımını artırın veya aylık sınırı gözden geçirin. "
                    "En yüksek maliyetli işlevleri maliyet panosundan inceleyin."
                ),
                evidence={
                    "spent": str(budget.spent_usd),
                    "limit": str(budget.limit_usd),
                },
                key=f"ai_budget_{budget.period_year}_{budget.period_month}",
            )
        )

    # --- 4) Yanıt kalitesi ---
    if low_rated >= 3:
        findings.append(
            _record_finding(
                run=run,
                category=Finding.Category.AI_QUALITY,
                severity=Finding.Severity.MEDIUM,
                title="Düşük puanlı yapay zekâ yanıtları birikti",
                description=f"{low_rated} yanıt 2 veya altında puanlandı.",
                recommendation=(
                    "İlgili işlevlerin sistem istemlerini gözden geçirin; gerekirse "
                    "daha güçlü bir model seçin veya bağlam bilgisini genişletin."
                ),
                evidence={"low_rated": low_rated},
                key="ai_low_quality",
            )
        )

    # --- 5) Gecikme ---
    if run.average_latency_ms > 20000:
        findings.append(
            _record_finding(
                run=run,
                category=Finding.Category.PERFORMANCE,
                severity=Finding.Severity.LOW,
                title="Yapay zekâ yanıt süreleri yüksek",
                description=f"Ortalama gecikme {run.average_latency_ms} ms.",
                recommendation=(
                    "Daha küçük bir model seçin, max_tokens değerini düşürün veya "
                    "akış (streaming) kullanın."
                ),
                evidence={"average_latency_ms": run.average_latency_ms},
                key="ai_latency",
            )
        )

    # --- 6) Veri kalitesi: mükerrer şarap kayıtları ---
    from apps.cellar.models import WineDuplicateAlert

    open_alerts = WineDuplicateAlert.objects.filter(status=WineDuplicateAlert.Status.OPEN).count()
    if open_alerts:
        findings.append(
            _record_finding(
                run=run,
                category=Finding.Category.DATA_QUALITY,
                severity=Finding.Severity.LOW,
                title="İncelenmemiş mükerrer şarap kaydı uyarısı var",
                description=f"{open_alerts} uyarı inceleme bekliyor.",
                recommendation="Kav → Mükerrer Kayıtlar ekranından uyarıları inceleyin.",
                evidence={"open_alerts": open_alerts},
                key="cellar_duplicates",
            )
        )

    # --- 7) Güvenlik: yetki reddi yoğunluğu ---
    from apps.core.models import AuditAction, AuditLog

    denials = AuditLog.objects.filter(
        action=AuditAction.PERMISSION_DENIED, timestamp__gte=start
    ).count()
    if denials >= 10:
        findings.append(
            _record_finding(
                run=run,
                category=Finding.Category.SECURITY,
                severity=Finding.Severity.MEDIUM,
                title="Yetkisiz erişim denemeleri arttı",
                description=f"Son {days} günde {denials} yetki reddi kaydedildi.",
                recommendation=(
                    "Denetim kaydını inceleyin. Personel rollerinin görevleriyle "
                    "uyumlu olup olmadığını kontrol edin."
                ),
                evidence={"denials": denials, "days": days},
                key="security_denials",
            )
        )

    # --- 8) Şifreleme yapılandırması ---
    from django.conf import settings as django_settings

    if not django_settings.FIELD_ENCRYPTION_KEY:
        findings.append(
            _record_finding(
                run=run,
                category=Finding.Category.SECURITY,
                severity=Finding.Severity.HIGH,
                title="Hassas alan şifrelemesi kapalı",
                description=(
                    "WINEHOUSE_FIELD_ENCRYPTION_KEY tanımlı değil; müşteri ve "
                    "personel iletişim bilgileri düz metin saklanıyor."
                ),
                recommendation=(
                    "Bir Fernet anahtarı üretip .env dosyasına ekleyin ve uygulamayı "
                    "yeniden başlatın."
                ),
                evidence={"setting": "WINEHOUSE_FIELD_ENCRYPTION_KEY"},
                key="encryption_disabled",
            )
        )

    run.findings_count = len(findings)
    run.status = ObservationRun.Status.COMPLETED
    run.finished_at = timezone.now()
    run.summary = (
        f"{run.ai_calls_examined} yapay zekâ çağrısı incelendi; {len(findings)} bulgu "
        f"üretildi. Toplam belirteç: {run.total_tokens}, maliyet: {run.total_cost_usd} USD."
    )
    run.save()

    logger.info("CAIO gözlemi tamamlandı: %s bulgu", len(findings))
    return run


def generate_improvement_tasks(*, run: ObservationRun, user: Any) -> list[Any]:
    """Açık bulgulardan geliştirme görevi taslakları üretir.

    Görevler ``backlog`` durumunda oluşturulur; insan onayı olmadan
    uygulanmaz.
    """
    from apps.caio.models import ImprovementTask

    severity_priority = {
        Finding.Severity.CRITICAL: ImprovementTask.Priority.URGENT,
        Finding.Severity.HIGH: ImprovementTask.Priority.HIGH,
        Finding.Severity.MEDIUM: ImprovementTask.Priority.NORMAL,
        Finding.Severity.LOW: ImprovementTask.Priority.LOW,
        Finding.Severity.INFO: ImprovementTask.Priority.LOW,
    }

    tasks = []
    for finding in run.findings.filter(status=Finding.Status.OPEN):
        if finding.tasks.exists():
            continue
        task = ImprovementTask.objects.create(
            title=finding.title,
            description=f"{finding.description}\n\nÖneri: {finding.recommendation}",
            priority=severity_priority.get(
                Finding.Severity(finding.severity), ImprovementTask.Priority.NORMAL
            ),
            status=ImprovementTask.Status.BACKLOG,
            created_by=user if getattr(user, "pk", None) else None,
        )
        task.findings.add(finding)
        tasks.append(task)
    return tasks
