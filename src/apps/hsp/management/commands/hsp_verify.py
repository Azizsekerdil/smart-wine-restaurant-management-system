"""``manage.py hsp_verify`` — bütünlük zincirlerini doğrular.

İki zinciri denetler:

1. Rights Receipt zinciri (``apps.hsp.receipts.verify_chain``)
2. Denetim kaydı zinciri (``apps.core.integrity.verify_audit_chain``)

Çıkış kodu: her iki zincir de geçerliyse 0, aksi halde 1 (CI gate uyumlu).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.core.integrity import verify_audit_chain
from apps.hsp.models import RightsReceipt
from apps.hsp.receipts import verify_chain


class Command(BaseCommand):
    help = "HSP makbuz zincirini ve denetim kaydı zincirini doğrular."

    def handle(self, *args, **options):
        failed = False

        receipt_count = RightsReceipt.objects.count()
        ok, broken = verify_chain()
        if ok:
            self.stdout.write(
                self.style.SUCCESS(f"Makbuz zinciri geçerli ({receipt_count} makbuz).")
            )
        else:
            failed = True
            self.stdout.write(
                self.style.ERROR(f"Makbuz zinciri BOZUK: ilk bozuk makbuz id={broken}.")
            )

        ok, broken, unchained = verify_audit_chain()
        if ok:
            message = f"Denetim zinciri geçerli (zincirsiz eski kayıt: {unchained})."
            self.stdout.write(self.style.SUCCESS(message))
        else:
            failed = True
            self.stdout.write(
                self.style.ERROR(
                    f"Denetim zinciri BOZUK: ilk bozuk kayıt id={broken} "
                    f"(zincirsiz eski kayıt: {unchained})."
                )
            )

        if failed:
            raise SystemExit(1)
