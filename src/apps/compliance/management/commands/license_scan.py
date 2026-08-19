"""``manage.py license_scan`` — çalışma zamanı lisans taraması ve gate.

Örnekler::

    python manage.py license_scan                      # tablo çıktısı
    python manage.py license_scan --json               # makine okunur çıktı
    python manage.py license_scan --spdx docs/sbom/spdx-runtime.json
    python manage.py license_scan --gate               # CI: RED/ORANGE/UNKNOWN → exit 1

Gate yalnızca *çalışma zamanı kapanımını* değerlendirir; sonuçlar hukuki
kesinlik değildir (bkz. apps.compliance.licenses).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.compliance.licenses import BLOCKING_CLASSES
from apps.compliance.scanner import scan_runtime_closure
from apps.compliance.spdx import build_spdx_document


class Command(BaseCommand):
    help = "Çalışma zamanı bağımlılıklarının lisanslarını tarar; SPDX SBOM üretebilir."

    def add_arguments(self, parser):
        parser.add_argument(
            "--requirements",
            default="requirements.txt",
            help="Doğrudan bağımlılık dosyası (varsayılan: requirements.txt)",
        )
        parser.add_argument("--json", action="store_true", help="JSON çıktısı üret")
        parser.add_argument("--spdx", default="", help="SPDX 2.3 JSON dosya yolu (yazılır)")
        parser.add_argument(
            "--gate",
            action="store_true",
            help="RED/ORANGE/UNKNOWN sınıfı bileşen varsa 1 çıkış koduyla sonlan",
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        requirements = Path(options["requirements"])
        if not requirements.is_absolute():
            requirements = base_dir / requirements

        records = scan_runtime_closure(requirements)
        counts = Counter(record.classification for record in records)

        if options["spdx"]:
            spdx_path = Path(options["spdx"])
            if not spdx_path.is_absolute():
                spdx_path = base_dir / spdx_path
            spdx_path.parent.mkdir(parents=True, exist_ok=True)
            document = build_spdx_document(records)
            spdx_path.write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            self.stdout.write(f"SPDX SBOM yazıldı: {spdx_path} ({len(records)} paket)")

        if options["json"]:
            payload = [record.__dict__ for record in records]
            self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            width = max((len(r.name) for r in records), default=10) + 2
            for record in records:
                marker = "*" if record.direct else " "
                self.stdout.write(
                    f"{record.classification:8} {marker} {record.name:{width}}"
                    f"{record.version:14} {record.declared_license}"
                    f"  [{record.evidence_source}]"
                )
            summary = " · ".join(f"{cls}={count}" for cls, count in sorted(counts.items()))
            self.stdout.write(f"\nToplam {len(records)} bileşen · {summary}")
            self.stdout.write("(* = doğrudan bağımlılık; sonuçlar hukuki kesinlik değildir)")

        blocking = [r for r in records if r.classification in BLOCKING_CLASSES]
        if blocking:
            self.stdout.write(self.style.WARNING("\nİnceleme gerektiren bileşenler:"))
            for record in blocking:
                self.stdout.write(
                    f"  {record.classification}: {record.name} "
                    f"({record.declared_license or 'lisans kanıtı yok'})"
                )

        if options["gate"] and blocking:
            self.stdout.write(self.style.ERROR("Lisans gate BAŞARISIZ."))
            raise SystemExit(1)
        if options["gate"]:
            self.stdout.write(self.style.SUCCESS("Lisans gate geçti."))
