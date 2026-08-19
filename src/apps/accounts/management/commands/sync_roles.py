"""Rol kataloğunu veritabanıyla eşitler."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts.services import sync_roles


class Command(BaseCommand):
    help = "Rol tanımlarını (apps.accounts.roles) Django gruplarıyla eşitler."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--quiet", action="store_true", help="Yalnızca özet satırı yazdırır.")

    def handle(self, *args: Any, **options: Any) -> None:
        report = sync_roles(verbose=False)

        if options.get("quiet"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"{len(report.created_groups)} rol oluşturuldu, "
                    f"{len(report.updated_groups)} rol güncellendi."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS("Rol eşitleme tamamlandı."))
        self.stdout.write(report.as_text())

        if report.unmatched_patterns:
            self.stdout.write(
                self.style.WARNING(
                    "\nNot: Eşleşmeyen desenler ilgili modülün henüz izin tanımı "
                    "olmadığını gösterir; modül eklendiğinde komutu tekrar çalıştırın."
                )
            )
