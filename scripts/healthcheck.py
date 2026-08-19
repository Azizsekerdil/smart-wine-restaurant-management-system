"""Wine House sistem sağlık denetimi (Django tarafı).

``scripts/check.ps1`` bu betiği çağırır ve çıktısını gösterir.
Doğrudan da çalıştırılabilir::

    .venv\\Scripts\\python.exe scripts\\healthcheck.py
    .venv\\Scripts\\python.exe scripts\\healthcheck.py --json

Çıktı biçimi (satır başına bir denetim):
    DURUM|BAŞLIK|AYRINTI

DURUM: OK | WARN | FAIL | INFO

GÜVENLİK: Bu betik hiçbir gizli değeri (API anahtarı, parola, şifreleme
anahtarı) yazdırmaz; yalnızca "tanımlı / tanımsız" bilgisini verir.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "winehouse.settings.dev")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

results: list[tuple[str, str, str]] = []


def add(status: str, title: str, detail: str = "") -> None:
    results.append((status, title, detail))


def run_checks() -> None:
    """Tüm denetimleri sırayla çalıştırır."""
    import logging

    try:
        import django

        django.setup()
        logging.disable(logging.CRITICAL)
    except Exception as exc:
        add("FAIL", "Django başlatma", f"{type(exc).__name__}: {exc}")
        return

    from django.conf import settings

    # -- Veritabanı --------------------------------------------------------
    try:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        table_count = len(connection.introspection.table_names())
        add("OK", "Veritabanı bağlantısı", f"{table_count} tablo ({connection.vendor})")
    except Exception as exc:
        add("FAIL", "Veritabanı bağlantısı", f"{type(exc).__name__}: {exc}")
        return

    # -- Bekleyen migration ------------------------------------------------
    try:
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            add("WARN", "Bekleyen migration", f"{len(pending)} adet — 'manage.py migrate' çalıştırın")
        else:
            add("OK", "Migration durumu", "güncel")
    except Exception as exc:
        add("WARN", "Migration denetimi", f"{type(exc).__name__}")

    # -- Roller ve kullanıcılar --------------------------------------------
    try:
        from apps.accounts.models import RoleProfile, User

        role_count = RoleProfile.objects.count()
        if role_count >= 19:
            add("OK", "Roller tanımlı", f"{role_count} rol")
        else:
            add("WARN", "Roller", f"yalnızca {role_count} rol — 'manage.py sync_roles' çalıştırın")

        admin_count = User.objects.filter(is_superuser=True).count()
        if admin_count:
            add("OK", "Yönetici hesabı", f"{admin_count} yönetici")
        else:
            add("FAIL", "Yönetici hesabı", "yok — 'manage.py create_admin' çalıştırın")

        locked = User.objects.filter(locked_until__isnull=False).count()
        if locked:
            add("INFO", "Kilitli hesap", f"{locked} hesap geçici kilitli")
    except Exception as exc:
        add("FAIL", "Kullanıcı denetimi", f"{type(exc).__name__}: {exc}")

    # -- Şifreleme ---------------------------------------------------------
    try:
        from apps.core.security import encryption_available

        if encryption_available():
            add("OK", "Hassas alan şifrelemesi", "etkin")
        else:
            add("WARN", "Hassas alan şifrelemesi", "kapalı — kişisel veriler düz metin saklanır")
    except Exception as exc:
        add("WARN", "Şifreleme denetimi", f"{type(exc).__name__}")

    # -- Mod denetimleri ---------------------------------------------------
    payment = getattr(settings, "PAYMENT_MODE", "sandbox")
    if payment == "sandbox":
        add("OK", "Ödeme modu", "sandbox (gerçek işlem yapılmaz)")
    else:
        add("WARN", "Ödeme modu", f"{payment} — canlı mod açık!")

    einvoice = getattr(settings, "EINVOICE_MODE", "sandbox")
    if einvoice == "sandbox":
        add("OK", "e-Fatura modu", "sandbox")
    else:
        add("WARN", "e-Fatura modu", f"{einvoice} — canlı mod açık!")

    devstudio = getattr(settings, "DEVSTUDIO", {})
    if devstudio.get("ENABLED"):
        add("WARN", "AI Development Studio", "AÇIK — yalnızca geliştirme ortamında kullanın")
    else:
        add("OK", "AI Development Studio", "kapalı (güvenli varsayılan)")

    if devstudio.get("ALLOW_COMMANDS"):
        add("WARN", "Stüdyo komut çalıştırma", "AÇIK")
    else:
        add("OK", "Stüdyo komut çalıştırma", "kapalı (yalnızca öneri üretilir)")

    # -- Django sistem kontrolleri -----------------------------------------
    try:
        from django.core.checks import run_checks as django_run_checks

        messages = django_run_checks()
        errors = [m for m in messages if m.level >= 40]
        warnings = [m for m in messages if 30 <= m.level < 40]
        if errors:
            add("FAIL", "Django sistem kontrolleri", f"{len(errors)} hata")
        elif warnings:
            add("WARN", "Django sistem kontrolleri", f"{len(warnings)} uyarı")
        else:
            add("OK", "Django sistem kontrolleri", "sorun yok")
    except Exception as exc:
        add("WARN", "Django sistem kontrolleri", f"{type(exc).__name__}")

    # -- Yapay zekâ sağlayıcıları -----------------------------------------
    try:
        from apps.aiservices.registry import PROVIDER_LABELS, health_report

        ai_settings = settings.AI_SETTINGS
        add(
            "INFO",
            "Yapay zekâ yapılandırması",
            f"varsayılan={ai_settings.get('DEFAULT_PROVIDER')} · "
            f"gizlilik={'açık' if ai_settings.get('PRIVACY_MODE') else 'kapalı'} · "
            f"yalnızca-yerel={'evet' if ai_settings.get('LOCAL_ONLY') else 'hayır'}",
        )
        for health in health_report():
            label = PROVIDER_LABELS.get(health.provider, health.provider)
            if health.reachable:
                add("OK", f"AI · {label}", f"{health.models_available} model, {health.latency_ms} ms")
            elif health.requires_api_key and not health.api_key_configured:
                add("INFO", f"AI · {label}", "API anahtarı tanımlı değil (isteğe bağlı)")
            else:
                add("INFO", f"AI · {label}", health.message[:90])
    except Exception as exc:
        add("WARN", "Yapay zekâ denetimi", f"{type(exc).__name__}: {exc}")

    # -- Yedekleme ---------------------------------------------------------
    try:
        from apps.backups.models import BackupRecord

        latest = BackupRecord.objects.order_by("-started_at").first()
        if latest is None:
            add("WARN", "Yedekleme", "henüz yedek alınmamış — BACKUP_WINE_HOUSE.bat çalıştırın")
        elif latest.age_days > 7:
            add("WARN", "Son yedek", f"{latest.age_days} gün önce ({latest.file_name})")
        else:
            add(
                "OK",
                "Son yedek",
                f"{latest.file_name} · {latest.age_days} gün önce · {latest.get_status_display()}",
            )

        backup_dir = Path(settings.BACKUP_DIR)
        add("INFO", "Yedek klasörü", str(backup_dir))
    except Exception as exc:
        add("WARN", "Yedekleme denetimi", f"{type(exc).__name__}")

    # -- Veri özeti --------------------------------------------------------
    try:
        from apps.catalog.models import MenuItem
        from apps.cellar.models import Wine
        from apps.operations.models import DiningTable, Order

        add(
            "INFO",
            "Veri özeti",
            f"{Wine.objects.filter(is_deleted=False).count()} şarap · "
            f"{MenuItem.objects.filter(is_deleted=False).count()} menü ürünü · "
            f"{DiningTable.objects.filter(is_active=True).count()} masa · "
            f"{Order.objects.filter(is_deleted=False).count()} adisyon",
        )
    except Exception as exc:
        add("INFO", "Veri özeti", f"okunamadı ({type(exc).__name__})")


def main() -> int:
    run_checks()

    if "--json" in sys.argv:
        payload = [
            {"status": status, "title": title, "detail": detail}
            for status, title, detail in results
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for status, title, detail in results:
            print(f"{status}|{title}|{detail}")

    return 1 if any(status == "FAIL" for status, _t, _d in results) else 0


if __name__ == "__main__":
    sys.exit(main())
