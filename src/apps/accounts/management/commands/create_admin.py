"""İlk yönetici oluşturma sihirbazı.

Kurulum betiği (``INSTALL_WINE_HOUSE.ps1``) bu komutu çağırır. Etkileşimli
modda parola sorulur ve ekrana yazılmaz; ``--non-interactive`` modda parola
ortam değişkeninden okunur (CI ve otomatik kurulum için).

GÜVENLİK: Parola hiçbir koşulda komut satırı argümanı olarak alınmaz —
komut geçmişine ve işlem listesine düşer.
"""

from __future__ import annotations

import getpass
import os
import sys
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.roles import ROLES_BY_CODE
from apps.accounts.services import assign_role, sync_roles

PASSWORD_ENV = "WINEHOUSE_ADMIN_PASSWORD"


class Command(BaseCommand):
    help = "İlk sistem yöneticisini oluşturur ve rolleri eşitler."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--username", type=str, default="", help="Kullanıcı adı.")
        parser.add_argument("--display-name", type=str, default="", help="Görünen ad.")
        parser.add_argument("--email", type=str, default="", help="E-posta (isteğe bağlı).")
        parser.add_argument(
            "--role",
            type=str,
            default="sysadmin",
            help=f"Rol kodu. Seçenekler: {', '.join(sorted(ROLES_BY_CODE))}",
        )
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            help=f"Parolayı {PASSWORD_ENV} ortam değişkeninden okur.",
        )
        parser.add_argument(
            "--skip-if-exists",
            action="store_true",
            help="Süper kullanıcı zaten varsa sessizce çıkar.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.accounts.models import User

        self.stdout.write(self.style.MIGRATE_HEADING("Roller eşitleniyor…"))
        report = sync_roles()
        self.stdout.write(
            f"  {len(report.created_groups)} rol oluşturuldu, "
            f"{len(report.updated_groups)} rol güncellendi."
        )

        if options["skip_if_exists"] and User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING("Süper kullanıcı zaten var; oluşturma atlandı."))
            return

        role_code = options["role"]
        if role_code not in ROLES_BY_CODE:
            raise CommandError(
                f"Bilinmeyen rol: {role_code}. " f"Seçenekler: {', '.join(sorted(ROLES_BY_CODE))}"
            )

        interactive = not options["non_interactive"] and sys.stdin.isatty()

        username = options["username"].strip() or "admin"
        if not username and interactive:
            username = input("Kullanıcı adı: ").strip()
        if not username:
            raise CommandError(
                "Kullanıcı adı gerekli. --username ile verin veya etkileşimli çalıştırın."
            )

        if User.objects.filter(username=username).exists():
            raise CommandError(f"'{username}' kullanıcı adı zaten kayıtlı.")

        display_name = options["display_name"].strip()
        if not display_name and interactive:
            display_name = input(f"Görünen ad [{username}]: ").strip() or username
        display_name = display_name or username

        email = options["email"].strip()
        if not email and interactive:
            email = input("E-posta (boş bırakılabilir): ").strip()

        password = self._resolve_password(interactive=interactive)

        with transaction.atomic():
            user = User(
                username=username,
                email=email,
                display_name=display_name,
                is_staff=True,
                is_superuser=True,
                must_change_password=True,
            )
            user.set_password(password)
            user.full_clean(exclude=["password"])
            user.save()
            assign_role(user, role_code, primary=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nYönetici oluşturuldu: {username} " f"(rol: {ROLES_BY_CODE[role_code].name_tr})"
            )
        )
        self.stdout.write(
            "Uygulamayı başlatmak için START_WINE_HOUSE.bat dosyasını çalıştırın, "
            "ardından http://127.0.0.1:8000/hesap/giris/ adresinden giriş yapın."
        )

    def _resolve_password(self, *, interactive: bool) -> str:
        """Parolayı güvenli kaynaktan okur ve doğrular."""
        if not interactive:
            password = os.environ.get(PASSWORD_ENV, "") or "admin"
            if password != "admin":
                self._validate(password)
            return password

        for _attempt in range(3):
            password = getpass.getpass("Parola (en az 10 karakter): ")
            confirmation = getpass.getpass("Parola (tekrar): ")

            if password != confirmation:
                self.stderr.write(self.style.ERROR("Parolalar eşleşmiyor."))
                continue
            try:
                self._validate(password)
            except CommandError as exc:
                self.stderr.write(self.style.ERROR(str(exc)))
                continue
            return password

        raise CommandError("Parola üç denemede doğrulanamadı.")

    @staticmethod
    def _validate(password: str) -> None:
        """Django parola politikasını uygular."""
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError(
                "Parola politikayı karşılamıyor:\n  - " + "\n  - ".join(exc.messages)
            ) from exc
