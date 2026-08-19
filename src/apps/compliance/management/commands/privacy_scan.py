"""``manage.py privacy_scan`` — kişisel veri keşfi, envanter diff'i ve ROPA hazırlığı.

Örnekler::

    python manage.py privacy_scan                       # tablo çıktısı
    python manage.py privacy_scan --json
    python manage.py privacy_scan --ropa docs/privacy/ROPA_PREP.md
    python manage.py privacy_scan --update-baseline     # envanteri kabul et
    python manage.py privacy_scan --gate                # CI: envantere işlenmemiş
                                                        # yeni PII alanı → exit 1

Gate mantığı: baseline (``docs/privacy/pii-baseline.json``) bilinen ve gözden
geçirilmiş kişisel veri envanteridir. Yeni bir model alanı kişisel veri adayı
olarak tespit edilir ama baseline'da yoksa, envanter güncellenmeden release
edilmemelidir.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.compliance.privacy import build_ropa_markdown, diff_against_baseline, scan_models

DEFAULT_BASELINE = "docs/privacy/pii-baseline.json"


class Command(BaseCommand):
    help = "Model alanlarında kişisel veri adaylarını tarar; ROPA hazırlığı ve gate üretir."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="JSON çıktısı üret")
        parser.add_argument(
            "--ropa", default="", help="ROPA hazırlık Markdown dosya yolu (yazılır)"
        )
        parser.add_argument(
            "--baseline", default=DEFAULT_BASELINE, help="Envanter baseline JSON yolu"
        )
        parser.add_argument(
            "--update-baseline",
            action="store_true",
            help="Geçerli taramayı gözden geçirilmiş envanter olarak kaydet",
        )
        parser.add_argument(
            "--gate",
            action="store_true",
            help="Baseline'da olmayan yeni PII adayı varsa 1 çıkış koduyla sonlan",
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        result = scan_models()

        if options["json"]:
            payload = [finding.__dict__ for finding in result.findings]
            self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            for f in result.findings:
                special = " [OZEL NITELIKLI]" if f.special_category else ""
                encrypted = " [SIFRELI]" if f.encrypted else ""
                self.stdout.write(
                    f"{f.confidence:6} {f.app}.{f.model}.{f.fld}"
                    f" · {f.category}{special}{encrypted} · özne: {f.subject}"
                )
            self.stdout.write(
                f"\n{result.scanned_models} model · {result.scanned_fields} alan tarandı · "
                f"{len(result.findings)} kişisel veri adayı "
                f"(özel nitelikli aday: {sum(1 for f in result.findings if f.special_category)})"
            )
            self.stdout.write("(Sonuçlar adaydır; hukuki sınıflandırma DPO incelemesine tabidir.)")

        if options["ropa"]:
            ropa_path = Path(options["ropa"])
            if not ropa_path.is_absolute():
                ropa_path = base_dir / ropa_path
            ropa_path.parent.mkdir(parents=True, exist_ok=True)
            retention = dict(getattr(settings, "DATA_RETENTION_DAYS", {}))
            ropa_path.write_text(build_ropa_markdown(result, retention) + "\n", encoding="utf-8")
            self.stdout.write(f"ROPA hazırlık çıktısı yazıldı: {ropa_path}")

        baseline_path = Path(options["baseline"])
        if not baseline_path.is_absolute():
            baseline_path = base_dir / baseline_path

        if options["update_baseline"]:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "note": (
                    "Gözden geçirilmiş kişisel veri envanteri. Yeni alanlar DPO "
                    "incelemesinden sonra --update-baseline ile eklenir."
                ),
                "fields": {f.key: f.category for f in result.findings},
            }
            baseline_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.stdout.write(
                f"Baseline güncellendi: {baseline_path} ({len(result.findings)} alan)"
            )
            return

        baseline_keys: set[str] = set()
        if baseline_path.exists():
            data = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline_keys = set(data.get("fields", {}))
        elif options["gate"]:
            self.stdout.write(self.style.ERROR(f"Baseline bulunamadı: {baseline_path}"))
            raise SystemExit(1)

        if baseline_keys or options["gate"]:
            new, removed = diff_against_baseline(result, baseline_keys)
            for key in sorted(removed):
                self.stdout.write(f"Kaldırılmış envanter kaydı: {key}")
            if new:
                self.stdout.write(
                    self.style.WARNING("\nEnvantere işlenmemiş yeni kişisel veri adayları:")
                )
                for f in new:
                    self.stdout.write(f"  {f.key} · {f.category} · {f.evidence}")
            if options["gate"]:
                if new:
                    self.stdout.write(self.style.ERROR("Privacy gate BAŞARISIZ."))
                    raise SystemExit(1)
                self.stdout.write(self.style.SUCCESS("Privacy gate geçti."))
