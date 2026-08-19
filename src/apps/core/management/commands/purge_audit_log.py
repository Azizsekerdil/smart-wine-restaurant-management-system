"""Saklama süresi dolan denetim kayıtlarını arşivler."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import AuditLog


class Command(BaseCommand):
    help = (
        "Saklama süresi dolan denetim kayıtlarını JSONL dosyasına arşivler ve "
        "veritabanından kaldırır. Arşiv dosyası oluşturulmadan hiçbir kayıt silinmez."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--days", type=int, default=None, help="Saklama süresi (gün).")
        parser.add_argument(
            "--dry-run", action="store_true", help="Yalnızca sayıyı gösterir, silmez."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days = options["days"] or settings.DATA_RETENTION_DAYS["audit_log"]
        cutoff = timezone.now() - timezone.timedelta(days=days)
        queryset = AuditLog.objects.filter(timestamp__lt=cutoff).order_by("timestamp")
        total = queryset.count()

        if total == 0:
            self.stdout.write(f"Saklama süresi ({days} gün) dolan kayıt yok.")
            return

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"{total} kayıt arşivlenecek (deneme modu, silinmedi).")
            )
            return

        archive_dir = Path(settings.BASE_DIR) / "var" / "audit-archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"audit-{timezone.now():%Y%m%d-%H%M%S}.jsonl"

        with archive_path.open("w", encoding="utf-8") as handle:
            for entry in queryset.iterator(chunk_size=500):
                handle.write(
                    json.dumps(
                        {
                            "timestamp": entry.timestamp.isoformat(),
                            "actor": entry.actor_label,
                            "action": entry.action,
                            "severity": entry.severity,
                            "object_type": entry.object_type,
                            "object_id": entry.object_id,
                            "object_repr": entry.object_repr,
                            "changes": entry.changes,
                            "message": entry.message,
                            "ip_address": entry.ip_address,
                            "success": entry.success,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        # Model seviyesinde silme engellidir; toplu sorgu ile kaldırılır.
        AuditLog.objects.filter(pk__in=list(queryset.values_list("pk", flat=True))).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"{total} denetim kaydı arşivlendi → {archive_path} ve veritabanından kaldırıldı."
            )
        )
