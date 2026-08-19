"""AI gateway ↔ HSP köprüsü.

``aiservices.services.ask()`` sağlayıcı zincirini kurmadan önce buradaki
:func:`evaluate_ai_request` fonksiyonunu çağırır. Karar:

* ``DENY``       → :class:`HSPDeniedError` yükseltilir (çağrı hiç yapılmaz).
* bulut kapalı   → sağlayıcı zinciri yerellerle sınırlanır.
* diğer          → çağrı sürer; maskeleme kanıtı makbuza yazılır.

Bu modül ``aiservices``'e bağımlıdır ama tersi bağımlılık yalnızca iki küçük
kanca noktasından ibarettir (minimal-invasive entegrasyon).
"""

from __future__ import annotations

import logging

from apps.core.audit import record
from apps.core.models import AuditAction, AuditSeverity
from apps.hsp.models import HSPDecision, HSPReviewRequest
from apps.hsp.policy import HSPEvaluation, evaluate
from apps.hsp.receipts import issue_receipt

logger = logging.getLogger("winehouse.hsp")


class HSPDeniedError(RuntimeError):
    """HSP politikası isteği tümüyle reddettiğinde yükseltilir."""

    def __init__(self, evaluation: HSPEvaluation):
        self.evaluation = evaluation
        super().__init__(
            f"HSP politikası bu isteği reddetti (işlev={evaluation.feature}, "
            f"sınıf={evaluation.data_class}). Gerekçe: {'; '.join(evaluation.reasons)}"
        )


def evaluate_ai_request(*, feature: str, actor_label: str = "") -> HSPEvaluation:
    """AI isteği için pre-action HSP değerlendirmesi yapar.

    ``DENY`` kararında makbuz + denetim kaydı üretir ve hatayı yükseltir;
    diğer kararlarda değerlendirmeyi döndürür (makbuz, sonuç belli olunca
    :func:`record_outcome` ile kesilir).
    """
    evaluation = evaluate(feature)

    if evaluation.blocked:
        issue_receipt(evaluation, actor_label=actor_label, outcome="blocked")
        record(
            action=AuditAction.AI_REQUEST,
            message=(
                f"HSP reddi: işlev={feature}, sınıf={evaluation.data_class}, "
                f"gerekçe={'; '.join(evaluation.reasons)}"
            ),
            severity=AuditSeverity.WARNING,
            success=False,
        )
        raise HSPDeniedError(evaluation)

    if evaluation.decision == HSPDecision.REQUIRE_HUMAN_REVIEW:
        _request, created = HSPReviewRequest.objects.get_or_create(
            feature=feature,
            status=HSPReviewRequest.Status.PENDING,
            defaults={
                "requested_by_label": actor_label[:150],
                "reason": "; ".join(evaluation.reasons)[:255],
            },
        )
        if created:
            record(
                action=AuditAction.AI_REQUEST,
                message=f"HSP inceleme talebi açıldı: işlev={feature}",
                severity=AuditSeverity.NOTICE,
            )

    if not evaluation.cloud_allowed:
        logger.info(
            "HSP: bulut yolu kapalı (işlev=%s, sınıf=%s) — yalnızca yerel sağlayıcılar.",
            feature,
            evaluation.data_class,
        )
    return evaluation


def record_outcome(
    evaluation: HSPEvaluation,
    *,
    actor_label: str = "",
    provider: str = "",
    model: str = "",
    outcome: str = "",
    masking_applied: bool = False,
) -> None:
    """Çağrı sonucu belli olduğunda zincire makbuz ekler (akışı bozmaz)."""
    issue_receipt(
        evaluation,
        actor_label=actor_label,
        provider=provider,
        model=model,
        outcome=outcome,
        masking_applied=masking_applied,
    )
