"""``manage.py seed_rulepacks`` — KVKK/GDPR başlangıç kural paketlerini yükler.

Paketler **DRAFT** olarak oluşturulur; yürürlüğe alma (onay + imza) bilinçli
olarak insan eylemidir: Django admin → Hukuki kural paketleri → "Yürürlüğe al"
veya ``apps.compliance.rulepacks.approve_pack``.

Komut idempotenttir: mevcut kayıtlar çoğaltılmaz. Kaynak URL'leri prompt §34
resmî seed listesinden gelir; ``retrieved_on`` alanı bilinçli boştur — kaynak
metin arşivlenip doğrulanana kadar güncellik iddia edilmez.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.compliance.models import Jurisdiction, LegalRule, LegalRulePack, LegalSource

SOURCES = [
    {
        "key": "kvkk-kanun",
        "jurisdiction": Jurisdiction.TR,
        "title": "6698 sayılı Kişisel Verilerin Korunması Kanunu",
        "url": "https://www.kvkk.gov.tr/Icerik/2097/Kanun-doc",
        "authority": "KVKK",
    },
    {
        "key": "kvkk-ihlal",
        "jurisdiction": Jurisdiction.TR,
        "title": "KVKK Veri İhlali Bildirimi (Kurul kararı 2019/10)",
        "url": "https://www.kvkk.gov.tr/Icerik/5362/Veri-Ihlali-Bildirimi",
        "authority": "KVKK",
        "article": "Kurul kararı 2019/10",
    },
    {
        "key": "kvkk-riza-ayrimi",
        "jurisdiction": Jurisdiction.TR,
        "title": "Açık rıza ve aydınlatma metinlerinin ayrı düzenlenmesi (2026/347)",
        "url": (
            "https://www.kvkk.gov.tr/Icerik/8710/veri-sorumlulari-tarafindan-acik-riza-ve-"
            "aydinlatma-metinlerinin-ayri-ayri-duzenlenmesi-gerektigi-hakkinda-kisisel-"
            "verileri-koruma-kurulunun-18-02-2026-tarihli-ve-2026-347-sayili-ilke-kararina-"
            "iliskin-kamuoyu-duyurusu"
        ),
        "authority": "KVKK",
        "article": "İlke kararı 2026/347",
    },
    {
        "key": "gdpr",
        "jurisdiction": Jurisdiction.EU,
        "title": "General Data Protection Regulation (EU) 2016/679",
        "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
        "authority": "EUR-Lex",
    },
]

RULES = {
    ("TR", "KVKK"): [
        {
            "rule_code": "KVKK-DSR-RESPONSE-30D",
            "title_tr": "İlgili kişi başvurusuna en geç 30 gün içinde yanıt",
            "title_en": "Respond to data subject application within 30 days",
            "description": (
                "Veri sorumlusu, ilgili kişi başvurusunu en kısa sürede ve en geç "
                "otuz gün içinde ücretsiz olarak sonuçlandırır."
            ),
            "source": "kvkk-kanun",
            "article": "m.13/2",
            "severity": "critical",
            "deadline_value": 30,
            "deadline_unit": "days",
            "evidence_requirements": ["başvuru kaydı", "yanıt kanıtı", "kimlik doğrulama kaydı"],
        },
        {
            "rule_code": "KVKK-BREACH-NOTIFY-72H",
            "title_tr": "Veri ihlalinin Kurula 72 saat içinde bildirilmesi",
            "title_en": "Notify the Board of a data breach within 72 hours",
            "description": (
                "Veri ihlalinin öğrenilmesinden itibaren gecikmeksizin ve en geç "
                "72 saat içinde Kurula bildirim yapılır (Kurul kararı 2019/10)."
            ),
            "source": "kvkk-ihlal",
            "article": "Kurul kararı 2019/10",
            "severity": "critical",
            "deadline_value": 72,
            "deadline_unit": "hours",
            "evidence_requirements": [
                "öğrenme anı kaydı",
                "bildirim taslağı",
                "etki değerlendirmesi",
            ],
        },
        {
            "rule_code": "KVKK-CONSENT-SEPARATE",
            "title_tr": "Açık rıza ve aydınlatma metinlerinin ayrı düzenlenmesi",
            "title_en": "Consent and privacy notice must be managed separately",
            "description": (
                "Açık rıza ile aydınlatma yükümlülüğü ayrı metin, ayrı eylem ve "
                "ayrı kanıt olarak yönetilir (İlke kararı 2026/347)."
            ),
            "source": "kvkk-riza-ayrimi",
            "article": "İlke kararı 2026/347",
            "severity": "high",
            "evidence_requirements": ["aydınlatma metni sürümü", "ayrı rıza kaydı"],
        },
    ],
    ("EU", "GDPR"): [
        {
            "rule_code": "GDPR-DSR-RESPONSE-1M",
            "title_tr": "İlgili kişi talebine bir ay içinde yanıt",
            "title_en": "Respond to data subject request within one month",
            "description": (
                "Controller shall provide information on action taken without undue "
                "delay and within one month of receipt (extendable by two months)."
            ),
            "source": "gdpr",
            "article": "Art. 12(3)",
            "severity": "critical",
            "deadline_value": 1,
            "deadline_unit": "months",
            "evidence_requirements": [
                "request log",
                "response evidence",
                "extension notice if used",
            ],
        },
        {
            "rule_code": "GDPR-BREACH-NOTIFY-72H",
            "title_tr": "İhlalin denetim otoritesine 72 saat içinde bildirimi",
            "title_en": "Notify supervisory authority of a breach within 72 hours",
            "description": (
                "Notification not later than 72 hours after having become aware of "
                "the personal data breach, unless unlikely to result in a risk."
            ),
            "source": "gdpr",
            "article": "Art. 33(1)",
            "severity": "critical",
            "deadline_value": 72,
            "deadline_unit": "hours",
            "evidence_requirements": [
                "awareness time record",
                "notification draft",
                "risk assessment",
            ],
        },
    ],
}


class Command(BaseCommand):
    help = "KVKK ve GDPR başlangıç kural paketlerini DRAFT olarak yükler (idempotent)."

    def handle(self, *args, **options):
        sources: dict[str, LegalSource] = {}
        for spec in SOURCES:
            source, _created = LegalSource.objects.get_or_create(
                url=spec["url"],
                defaults={
                    "jurisdiction": spec["jurisdiction"],
                    "title": spec["title"],
                    "authority": spec["authority"],
                    "article": spec.get("article", ""),
                },
            )
            sources[spec["key"]] = source

        created_rules = 0
        for (jurisdiction, regulation), rules in RULES.items():
            pack, _created = LegalRulePack.objects.get_or_create(
                jurisdiction=jurisdiction,
                regulation_code=regulation,
                version=1,
                defaults={"release_note": "Başlangıç seed paketi (insan onayı bekliyor)."},
            )
            for spec in rules:
                _rule, rule_created = LegalRule.objects.get_or_create(
                    pack=pack,
                    rule_code=spec["rule_code"],
                    defaults={
                        "title_tr": spec["title_tr"],
                        "title_en": spec["title_en"],
                        "description": spec["description"],
                        "source": sources[spec["source"]],
                        "article": spec.get("article", ""),
                        "severity": spec.get("severity", "high"),
                        "deadline_value": spec.get("deadline_value"),
                        "deadline_unit": spec.get("deadline_unit", ""),
                        "evidence_requirements": spec.get("evidence_requirements", []),
                    },
                )
                created_rules += int(rule_created)

        pending = LegalRulePack.objects.filter(status=LegalRulePack.Status.DRAFT).count()
        self.stdout.write(
            f"Seed tamam: {LegalSource.objects.count()} kaynak, "
            f"{LegalRulePack.objects.count()} paket, yeni kural: {created_rules}."
        )
        if pending:
            self.stdout.write(
                self.style.WARNING(
                    f"{pending} paket DRAFT durumda - yürürlük için insan onayı gerekiyor "
                    "(admin > Hukuki kural paketleri > 'Yürürlüğe al')."
                )
            )
