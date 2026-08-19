"""Yapay zekâ orkestrasyon servisi.

Bu modül uygulamanın yapay zekâ ile konuştuğu **tek kapıdır**. Sorumlulukları:

  1. **Gizlilik** — bulut sağlayıcıya gitmeden önce kişisel verileri maskeler
     ve kullanıcıya *tam olarak neyin gönderildiğini* gösterir.
  2. **Maliyet denetimi** — aylık bütçe aşıldığında bulut çağrılarını engeller.
  3. **Yedekleme (fallback)** — bir sağlayıcı çalışmazsa yapılandırılmış sıraya
     göre bir sonrakine geçer; en sonda mock bulunduğu için akış hiç çökmez.
  4. **İzlenebilirlik** — her çağrı ``AICallLog`` ve gerektiğinde ``AuditLog``
     kaydı üretir.

Kullanım::

    result = ask(
        user=request.user,
        feature=AIFeature.PAIRING,
        prompt="Kuzu tandır için şarap öner",
        system_prompt=SOMMELIER_SYSTEM_PROMPT,
    )
    result.response.text
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.aiservices.models import (
    AIBudget,
    AICallLog,
    AIConversation,
    AIFeature,
    AIMessage,
    ProviderPricing,
)
from apps.aiservices.providers.base import (
    AIProviderError,
    CancellationToken,
    ChatMessage,
    ChatResponse,
    CostLimitExceededError,
    RequestCancelledError,
    TokenUsage,
)
from apps.aiservices.registry import build_fallback_chain, get_provider
from apps.core.audit import record
from apps.core.models import AuditAction, AuditSeverity
from apps.core.security import MaskingResult, mask_pii
from apps.hsp.gateway import evaluate_ai_request, record_outcome

logger = logging.getLogger("winehouse.ai")


# ---------------------------------------------------------------------------
# Sistem istemleri
# ---------------------------------------------------------------------------
RESPONSIBLE_SERVICE_CLAUSE = (
    "Sorumlu servis kuralları: Alkollü içecek önerirken asla sağlık iddiasında "
    "bulunma, tıbbi tavsiye verme ve alkolü sağlıklı/faydalı olarak sunma. "
    "Alerji sorulursa kesin güvence verme; işletmenin doğrulaması gerektiğini "
    "belirt. 18 yaş sınırını ve sorumlu tüketimi gözet."
)

SOMMELIER_SYSTEM_PROMPT = (
    "Sen bir şarap restoranında çalışan deneyimli bir sommelier asistanısın. "
    "Yanıtların kısa, somut ve uygulanabilir olsun. Elindeki kav bilgisi "
    "dışına çıkma; bilmediğin bir şarabı uydurma. Türkçe sorulara Türkçe, "
    "İngilizce sorulara İngilizce yanıt ver.\n" + RESPONSIBLE_SERVICE_CLAUSE
)

REPORT_ANALYST_SYSTEM_PROMPT = (
    "Sen bir restoran yönetim sistemine bağlı analiz asistanısın. Yalnızca "
    "sana verilen sayısal verilere dayanarak yorum yap. Veri yoksa 'veri yok' "
    "de; tahmin uydurma. Para birimini ve tarihleri kullanıcının dilinde biçimlendir."
)

OPERATIONS_SYSTEM_PROMPT = (
    "Sen bir restoran operasyon asistanısın. Önerilerini gerekçeleriyle ver. "
    "Hiçbir öneri otomatik uygulanmaz; kullanıcı onayı gerekir. Kesin "
    "olmayan konularda belirsizliği açıkça belirt."
)

FEATURE_SYSTEM_PROMPTS: dict[str, str] = {
    AIFeature.SOMMELIER: SOMMELIER_SYSTEM_PROMPT,
    AIFeature.PAIRING: SOMMELIER_SYSTEM_PROMPT,
    AIFeature.VISION: SOMMELIER_SYSTEM_PROMPT,
    AIFeature.REPORT_QUERY: REPORT_ANALYST_SYSTEM_PROMPT,
    AIFeature.FORECAST: REPORT_ANALYST_SYSTEM_PROMPT,
    AIFeature.DAY_SUMMARY: REPORT_ANALYST_SYSTEM_PROMPT,
    AIFeature.ANOMALY: REPORT_ANALYST_SYSTEM_PROMPT,
    AIFeature.INVENTORY: OPERATIONS_SYSTEM_PROMPT,
    AIFeature.WASTE: OPERATIONS_SYSTEM_PROMPT,
    AIFeature.DECISION: OPERATIONS_SYSTEM_PROMPT,
}


# ---------------------------------------------------------------------------
# Sonuç yapıları
# ---------------------------------------------------------------------------
@dataclass
class AIResult:
    """``ask()`` çağrısının tam sonucu."""

    response: ChatResponse
    call_log: AICallLog
    masking: MaskingResult | None = None
    attempted_providers: list[str] = field(default_factory=list)
    used_fallback: bool = False
    is_mock: bool = False

    @property
    def text(self) -> str:
        return self.response.text

    @property
    def privacy_notice(self) -> str:
        """Kullanıcıya gösterilecek gizlilik bildirimi."""
        if self.masking is None:
            return "Yerel sağlayıcı kullanıldı; veri işletme dışına çıkmadı."
        if not self.masking.was_masked:
            return "Bulut sağlayıcısına gönderildi. Kişisel veri tespit edilmedi."
        return f"Bulut sağlayıcısına gönderildi. {self.masking.summary()}"


class AIUnavailableError(RuntimeError):
    """Hiçbir sağlayıcı yanıt veremediğinde yükseltilir."""


# ---------------------------------------------------------------------------
# Bütçe
# ---------------------------------------------------------------------------
def current_budget() -> AIBudget:
    """Bu ayın bütçe kaydını döndürür (yoksa ayarlardan oluşturur)."""
    today = timezone.localdate()
    limit = Decimal(str(settings.AI_SETTINGS.get("MONTHLY_COST_LIMIT_USD", 10)))
    budget, _created = AIBudget.objects.get_or_create(
        period_year=today.year,
        period_month=today.month,
        defaults={"limit_usd": limit},
    )
    return budget


def estimate_cost(provider: str, model: str, usage: TokenUsage) -> Decimal:
    """Tanımlı fiyatlandırmaya göre maliyeti hesaplar.

    Fiyat tanımlı değilse ``0`` döner — uygulama hiçbir fiyatı varsaymaz.
    """
    pricing = (
        ProviderPricing.objects.filter(provider=provider, model=model, is_active=True)
        .order_by("-effective_from")
        .first()
    )
    if pricing is None:
        return Decimal("0.000000")
    return usage.estimated_cost_usd(
        input_per_million=pricing.input_usd_per_million,
        output_per_million=pricing.output_usd_per_million,
    )


# ---------------------------------------------------------------------------
# Gizlilik
# ---------------------------------------------------------------------------
def prepare_prompt_for_provider(
    prompt: str,
    *,
    is_local_provider: bool,
    extra_terms: list[str] | None = None,
) -> tuple[str, MaskingResult | None]:
    """İstemi sağlayıcıya göre hazırlar.

    * Yerel sağlayıcı + gizlilik modu kapalı → metin olduğu gibi gider.
    * Bulut sağlayıcı **veya** gizlilik modu açık → kişisel veriler maskelenir.

    Returns:
        ``(gönderilecek_metin, maskeleme_sonucu)``. Maskeleme yapılmadıysa
        ikinci değer ``None``'dır.
    """
    privacy_mode = bool(settings.AI_SETTINGS.get("PRIVACY_MODE", True))

    if is_local_provider and not privacy_mode:
        return prompt, None

    result = mask_pii(prompt, extra_terms=extra_terms)
    return result.text, result


# ---------------------------------------------------------------------------
# Ana giriş noktası
# ---------------------------------------------------------------------------
def ask(
    *,
    user: Any,
    feature: str,
    prompt: str,
    system_prompt: str = "",
    history: list[ChatMessage] | None = None,
    provider_code: str = "",
    model: str = "",
    temperature: float = 0.4,
    max_tokens: int = 1024,
    conversation: AIConversation | None = None,
    cancellation: CancellationToken | None = None,
    pii_terms: list[str] | None = None,
    allow_cloud: bool = True,
) -> AIResult:
    """Yapay zekâya soru sorar ve yanıtı döndürür.

    Args:
        user: İsteği yapan kullanıcı (denetim ve maliyet takibi için).
        feature: ``AIFeature`` değerlerinden biri.
        prompt: Kullanıcının sorusu.
        system_prompt: Boşsa işleve göre varsayılan sistem istemi kullanılır.
        history: Önceki mesajlar (sohbet bağlamı).
        provider_code: Belirli bir sağlayıcı zorlanmak isteniyorsa.
        conversation: Kayıt altına alınacak sohbet oturumu.
        cancellation: Kullanıcı iptali için işaret.
        pii_terms: Ek olarak maskelenecek serbest metinler (ör. müşteri adı).
        allow_cloud: ``False`` ise yalnızca yerel sağlayıcılar denenir.

    Raises:
        AIUnavailableError: Hiçbir sağlayıcı yanıt veremediyse.
        CostLimitExceededError: Bütçe kesin sınırı aşıldıysa.
    """
    resolved_system = system_prompt or FEATURE_SYSTEM_PROMPTS.get(feature, OPERATIONS_SYSTEM_PROMPT)
    actor_label = getattr(user, "username", "") or ""

    # --- HSP pre-action değerlendirmesi: DENY kararında burada durur ---
    hsp_evaluation = evaluate_ai_request(feature=feature, actor_label=actor_label)
    if not hsp_evaluation.cloud_allowed:
        allow_cloud = False

    chain = build_fallback_chain(preferred=provider_code)
    providers_config = settings.AI_SETTINGS.get("PROVIDERS", {})

    if not allow_cloud:
        chain = [code for code in chain if providers_config.get(code, {}).get("is_local")]
        if "mock" not in chain:
            chain.append("mock")

    budget = current_budget()
    attempted: list[str] = []
    last_error: Exception | None = None

    for index, code in enumerate(chain):
        attempted.append(code)
        is_local = bool(providers_config.get(code, {}).get("is_local"))

        # --- Bütçe denetimi: yalnızca bulut sağlayıcıları maliyet üretir ---
        if not is_local and budget.is_hard_limit and budget.is_exceeded:
            logger.warning(
                "Bulut sağlayıcı atlandı (bütçe aşıldı): %s · %s/%s USD",
                code,
                budget.spent_usd,
                budget.limit_usd,
            )
            _log_call(
                user=user,
                conversation=conversation,
                feature=feature,
                provider=code,
                model=model,
                is_local=is_local,
                outcome=AICallLog.Outcome.BLOCKED,
                error_type="CostLimitExceeded",
                error_message=(
                    f"Aylık yapay zekâ bütçesi aşıldı "
                    f"({budget.spent_usd}/{budget.limit_usd} USD)."
                ),
            )
            last_error = CostLimitExceededError(
                f"Aylık yapay zekâ bütçesi aşıldı ({budget.spent_usd}/{budget.limit_usd} USD). "
                "Ayarlar → Yapay Zekâ ekranından sınırı güncelleyebilirsiniz.",
                provider=code,
            )
            continue

        # --- Gizlilik: buluta gitmeden önce maskele ---
        outgoing_prompt, masking = prepare_prompt_for_provider(
            prompt, is_local_provider=is_local, extra_terms=pii_terms
        )

        messages: list[ChatMessage] = []
        if resolved_system:
            messages.append(ChatMessage("system", resolved_system))
        messages.extend(history or [])
        messages.append(ChatMessage("user", outgoing_prompt))

        try:
            provider = get_provider(code)
            response = provider.chat(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                cancellation=cancellation,
            )
        except RequestCancelledError as exc:
            _log_call(
                user=user,
                conversation=conversation,
                feature=feature,
                provider=code,
                model=model,
                is_local=is_local,
                outcome=AICallLog.Outcome.CANCELLED,
                error_type=type(exc).__name__,
                error_message=exc.user_message(),
            )
            raise
        except AIProviderError as exc:
            last_error = exc
            logger.warning(
                "AI sağlayıcı başarısız (%s): %s — sıradaki sağlayıcıya geçiliyor.",
                code,
                type(exc).__name__,
            )
            _log_call(
                user=user,
                conversation=conversation,
                feature=feature,
                provider=code,
                model=model,
                is_local=is_local,
                outcome=(
                    AICallLog.Outcome.FALLBACK
                    if index < len(chain) - 1
                    else AICallLog.Outcome.FAILED
                ),
                error_type=type(exc).__name__,
                error_message=exc.user_message(),
                masking=masking,
            )
            if not exc.should_fallback:
                raise
            continue
        except Exception as exc:  # pragma: no cover - beklenmeyen hata yolu
            last_error = exc
            logger.exception("AI sağlayıcıda beklenmeyen hata (%s).", code)
            _log_call(
                user=user,
                conversation=conversation,
                feature=feature,
                provider=code,
                model=model,
                is_local=is_local,
                outcome=AICallLog.Outcome.FAILED,
                error_type=type(exc).__name__,
                error_message="Beklenmeyen hata.",
                masking=masking,
            )
            continue

        # --- Başarılı ---
        cost = estimate_cost(code, response.model, response.usage)
        call_log = _log_call(
            user=user,
            conversation=conversation,
            feature=feature,
            provider=code,
            model=response.model,
            is_local=is_local,
            outcome=AICallLog.Outcome.SUCCESS,
            usage=response.usage,
            latency_ms=response.latency_ms,
            cost=cost,
            masking=masking,
        )

        if cost > 0:
            budget.spent_usd = budget.spent_usd + cost
            budget.save(update_fields=["spent_usd", "updated_at"])

        if conversation is not None:
            _persist_messages(conversation, prompt, outgoing_prompt, masking, response)

        record_outcome(
            hsp_evaluation,
            actor_label=actor_label,
            provider=code,
            model=response.model,
            outcome="success",
            masking_applied=bool(masking and masking.was_masked),
        )

        if not is_local:
            record(
                action=AuditAction.AI_REQUEST,
                message=(
                    f"Bulut yapay zekâ çağrısı: sağlayıcı={code}, model={response.model}, "
                    f"işlev={feature}, maskeleme={'evet' if (masking and masking.was_masked) else 'hayır'}"
                ),
                severity=AuditSeverity.NOTICE,
                actor=user,
            )

        return AIResult(
            response=response,
            call_log=call_log,
            masking=masking,
            attempted_providers=attempted,
            used_fallback=index > 0,
            is_mock=(code == "mock"),
        )

    message = "Hiçbir yapay zekâ sağlayıcısı yanıt veremedi."
    if last_error is not None:
        detail = getattr(last_error, "user_message", lambda: str(last_error))()
        message = f"{message} Son hata: {detail}"
    raise AIUnavailableError(message)


def _persist_messages(
    conversation: AIConversation,
    original_prompt: str,
    outgoing_prompt: str,
    masking: MaskingResult | None,
    response: ChatResponse,
) -> None:
    """Sohbet mesajlarını kaydeder."""
    next_sequence = conversation.messages.count()
    AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.USER,
        content=original_prompt,
        masked_content=outgoing_prompt if masking else "",
        masking_summary=masking.summary() if masking else "",
        sequence=next_sequence,
    )
    AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.ASSISTANT,
        content=response.text,
        sequence=next_sequence + 1,
    )
    conversation.provider = response.provider
    conversation.model = response.model
    if not conversation.title:
        conversation.title = original_prompt.strip()[:80]
    conversation.save(update_fields=["provider", "model", "title", "updated_at"])


def _log_call(
    *,
    user: Any,
    conversation: AIConversation | None,
    feature: str,
    provider: str,
    model: str,
    is_local: bool,
    outcome: str,
    usage: TokenUsage | None = None,
    latency_ms: int = 0,
    cost: Decimal | None = None,
    error_type: str = "",
    error_message: str = "",
    masking: MaskingResult | None = None,
) -> AICallLog:
    """Çağrı kaydını oluşturur (hata durumunda bile iş akışını bozmaz)."""
    from apps.core.security import mask_secrets

    usage = usage or TokenUsage()
    resolved_user = user if getattr(user, "is_authenticated", False) else None

    try:
        return AICallLog.objects.create(
            conversation=conversation,
            user=resolved_user,
            feature=feature,
            provider=provider,
            model=model or "",
            is_local_provider=is_local,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            estimated_cost_usd=cost or Decimal("0.000000"),
            latency_ms=latency_ms,
            outcome=outcome,
            error_type=error_type[:80],
            error_message=mask_secrets(error_message)[:2000],
            pii_masked=bool(masking and masking.was_masked),
            masking_summary=(masking.summary() if masking else "")[:250],
        )
    except Exception:  # pragma: no cover - günlükleme iş akışını bozmamalı
        logger.exception("AI çağrı kaydı yazılamadı.")
        return AICallLog(provider=provider, feature=feature, outcome=outcome)


# ---------------------------------------------------------------------------
# İşleve özel yardımcılar
# ---------------------------------------------------------------------------
def suggest_wine_pairing(
    *,
    user: Any,
    dish_description: str,
    available_wines: list[str],
    language: str = "tr",
    provider_code: str = "",
) -> AIResult:
    """Yemek için kavdaki şaraplardan eşleştirme önerir.

    Model yalnızca *verilen* şarap listesinden seçim yapmaya yönlendirilir;
    böylece kavda olmayan bir şarap önerilmesi engellenir.
    """
    wine_list = "\n".join(f"- {name}" for name in available_wines[:60])
    prompt = (
        f"Yemek: {dish_description}\n\n"
        f"Kavdaki şaraplar (YALNIZCA bu listeden seç):\n{wine_list}\n\n"
        "Görev: En uygun 3 şarabı sırala. Her biri için tek cümlelik gerekçe ver. "
        "Listede uygun şarap yoksa bunu açıkça söyle ve hangi tarzın aranması "
        "gerektiğini belirt. Yanıt dili: " + ("Türkçe" if language == "tr" else "İngilizce") + "."
    )
    return ask(
        user=user,
        feature=AIFeature.PAIRING,
        prompt=prompt,
        provider_code=provider_code,
        temperature=0.3,
        max_tokens=700,
    )


def summarize_business_day(
    *, user: Any, snapshot_data: dict[str, Any], language: str = "tr", provider_code: str = ""
) -> AIResult:
    """Gün sonu verilerinden yönetici özeti üretir."""
    lines = "\n".join(f"- {key}: {value}" for key, value in snapshot_data.items())
    prompt = (
        "Aşağıdaki gün sonu verilerinden bir yönetici özeti çıkar.\n\n"
        f"{lines}\n\n"
        "İstenen: 4 maddelik özet, 2 maddelik dikkat çeken nokta, 2 maddelik "
        "önerilen aksiyon. Yalnızca verilen sayılara dayan; ek veri uydurma. "
        "Yanıt dili: " + ("Türkçe" if language == "tr" else "İngilizce") + "."
    )
    return ask(
        user=user,
        feature=AIFeature.DAY_SUMMARY,
        prompt=prompt,
        provider_code=provider_code,
        temperature=0.2,
        max_tokens=800,
    )
