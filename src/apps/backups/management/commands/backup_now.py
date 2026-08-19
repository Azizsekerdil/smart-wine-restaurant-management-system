"""Komut satırından yedek alır (Windows Görev Zamanlayıcı için)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.backups import services


class Command(BaseCommand):
    help = "Yedek alır, doğrular ve saklama politikasını uygular."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--destination", type=str, default="", help="Hedef klasör.")
        parser.add_argument("--no-encrypt", action="store_true", help="Şifrelemeyi kapatır.")
        parser.add_argument("--no-verify", action="store_true", help="Doğrulamayı atlar.")
        parser.add_argument(
            "--apply-retention", action="store_true", help="Saklama politikasını uygular."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        destination = Path(options["destination"]) if options["destination"] else None

        try:
            backup = services.create_backup(
                user=None,
                kind="scheduled",
                destination=destination,
                encrypt=not options["no_encrypt"],
                notes="Komut satırından alındı.",
            )
        except services.BackupError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(f"Yedek alındı: {backup.file_path} ({backup.size_mb} MB)")
        )

        if not options["no_verify"]:
            result = services.verify_backup(backup=backup)
            if result.is_valid:
                self.stdout.write(self.style.SUCCESS(f"Doğrulama: {result.message}"))
            else:
                raise CommandError(f"Doğrulama başarısız: {result.message}")

        if options["apply_retention"]:
            removed = services.apply_retention_policy()
            self.stdout.write(f"Saklama politikası: {len(removed)} eski yedek silindi.")
