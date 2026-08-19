"""Yedekleme ve geri yükleme servisleri.

Tasarım:
  * Yedek, veritabanı dosyasının (SQLite) veya ``dumpdata`` çıktısının
    ZIP arşividir; arşiv isteğe bağlı olarak Fernet ile şifrelenir.
  * Her yedek için SHA-256 özeti hesaplanır ve geri yüklemeden önce
    doğrulanır. Özet uyuşmazsa geri yükleme **yapılmaz**.
  * Geri yükleme kritik işlemdir: onay gerektirir ve öncesinde otomatik
    güvenlik yedeği alınır.
  * Varsayılan geri yükleme hedefi **test veritabanıdır**; canlı veritabanına
    yazmak ayrıca seçilmelidir.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import zipfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from apps.backups.models import BackupRecord, RestoreRecord
from apps.core.audit import record
from apps.core.models import AuditAction, AuditSeverity
from winehouse import __version__

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024


class BackupError(RuntimeError):
    """Yedekleme veya geri yükleme hatası."""


@dataclass
class VerificationResult:
    """Yedek doğrulama sonucu."""

    is_valid: bool
    message: str
    computed_checksum: str = ""
    details: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def compute_sha256(path: Path) -> str:
    """Dosyanın SHA-256 özetini hesaplar."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_directory() -> Path:
    """Yedek klasörünü döndürür (yoksa oluşturur)."""
    directory = Path(settings.BACKUP_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _record_counts() -> dict[str, int]:
    """Doğrulama için tablo kayıt sayılarını toplar."""
    from django.apps import apps

    counts: dict[str, int] = {}
    for model in apps.get_models():
        if model._meta.app_label not in {
            "core",
            "accounts",
            "catalog",
            "cellar",
            "inventory",
            "operations",
            "crm",
            "hr",
            "reporting",
            "aiservices",
            "backups",
            "training",
            "caio",
            "devstudio",
        }:
            continue
        try:
            counts[model._meta.label] = model.objects.count()
        except Exception:  # pragma: no cover - erişilemeyen tablo
            # Sayılamayan tablo yedeği durdurmaz ama sessizce yutulmaz.
            logger.warning("Kayıt sayısı okunamadı: %s", model._meta.label, exc_info=True)
            continue
    return counts


def _encrypt_file(source: Path, target: Path) -> None:
    """Dosyayı Fernet ile şifreler."""
    from apps.core.security import encryption_available

    if not encryption_available():
        raise BackupError(
            "Yedek şifrelemesi istendi ancak WINEHOUSE_FIELD_ENCRYPTION_KEY tanımlı "
            "değil. Anahtarı ayarlayın veya şifrelemeyi kapatın."
        )

    import base64

    from apps.core.security import _get_fernet

    fernet = _get_fernet()
    payload = source.read_bytes()
    target.write_bytes(fernet.encrypt(base64.b64encode(payload)))


def _decrypt_file(source: Path, target: Path) -> None:
    """Şifreli yedeği çözer."""
    import base64

    from apps.core.security import _get_fernet

    fernet = _get_fernet()
    try:
        decrypted = fernet.decrypt(source.read_bytes())
    except Exception as exc:
        raise BackupError(
            "Yedek çözülemedi. Şifreleme anahtarı yedeğin alındığı anahtarla " "aynı olmalıdır."
        ) from exc
    target.write_bytes(base64.b64decode(decrypted))


# ---------------------------------------------------------------------------
# Yedek alma
# ---------------------------------------------------------------------------
def create_backup(
    *,
    user: Any,
    kind: str = BackupRecord.Kind.MANUAL,
    destination: Path | None = None,
    encrypt: bool | None = None,
    notes: str = "",
) -> BackupRecord:
    """Yedek alır ve kaydını oluşturur.

    Yedek içeriği:
      * ``data.json``     — tüm uygulama verisi (dumpdata, doğal anahtarlı)
      * ``manifest.json`` — sürüm, tarih, kayıt sayıları, veritabanı motoru
      * ``database.sqlite3`` — SQLite kullanılıyorsa ham dosya kopyası
    """
    directory = Path(destination) if destination else backup_directory()
    directory.mkdir(parents=True, exist_ok=True)

    should_encrypt = settings.BACKUP_ENCRYPTION if encrypt is None else encrypt
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    base_name = f"winehouse-backup-{stamp}"
    archive_path = directory / f"{base_name}.zip"

    backup = BackupRecord.objects.create(
        file_name=archive_path.name,
        file_path=str(archive_path),
        kind=kind,
        status=BackupRecord.Status.RUNNING,
        is_encrypted=bool(should_encrypt),
        created_by=user if getattr(user, "pk", None) else None,
        app_version=__version__,
        database_engine=connection.vendor,
        notes=notes,
    )

    try:
        counts = _record_counts()
        manifest = {
            "app": "Wine House",
            "version": __version__,
            "created_at": timezone.now().isoformat(),
            "database_engine": connection.vendor,
            "record_counts": counts,
            "encrypted": bool(should_encrypt),
            "created_by": getattr(user, "username", "sistem"),
        }

        buffer = StringIO()
        call_command(
            "dumpdata",
            "--natural-foreign",
            "--natural-primary",
            "--exclude=contenttypes",
            "--exclude=auth.permission",
            "--exclude=sessions",
            indent=2,
            stdout=buffer,
        )
        data_payload = buffer.getvalue()

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr("data.json", data_payload)

            if connection.vendor == "sqlite":
                db_path = Path(settings.DATABASES["default"]["NAME"])
                if db_path.exists():
                    # WAL kayıtlarını ana dosyaya yaz; tutarlı kopya sağlar
                    with connection.cursor() as cursor:
                        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    archive.write(db_path, "database.sqlite3")

        if should_encrypt:
            encrypted_path = directory / f"{base_name}.zip.enc"
            _encrypt_file(archive_path, encrypted_path)
            archive_path.unlink()
            archive_path = encrypted_path
            backup.file_name = archive_path.name
            backup.file_path = str(archive_path)

        backup.size_bytes = archive_path.stat().st_size
        backup.checksum_sha256 = compute_sha256(archive_path)
        backup.record_counts = counts
        backup.status = BackupRecord.Status.SUCCESS
        backup.finished_at = timezone.now()
        backup.save()

        record(
            action=AuditAction.BACKUP,
            obj=backup,
            message=(
                f"Yedek alındı: {backup.file_name} · {backup.size_mb} MB · "
                f"{'şifreli' if should_encrypt else 'şifresiz'}"
            ),
            severity=AuditSeverity.NOTICE,
            actor=user,
        )
        return backup

    except Exception as exc:
        backup.status = BackupRecord.Status.FAILED
        backup.error_message = str(exc)[:2000]
        backup.finished_at = timezone.now()
        backup.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        logger.exception("Yedekleme başarısız.")
        raise BackupError(f"Yedekleme başarısız: {exc}") from exc


# ---------------------------------------------------------------------------
# Doğrulama
# ---------------------------------------------------------------------------
def verify_backup(*, backup: BackupRecord, user: Any = None) -> VerificationResult:
    """Yedeğin bütünlüğünü doğrular.

    Kontroller:
      1. Dosya var mı?
      2. SHA-256 özeti kayıtla eşleşiyor mu?
      3. Arşiv açılabiliyor mu ve ``manifest.json`` okunabiliyor mu?
      4. ``data.json`` geçerli JSON mu?
    """
    path = Path(backup.file_path)
    if not path.exists():
        return VerificationResult(False, f"Yedek dosyası bulunamadı: {path}")

    computed = compute_sha256(path)
    if backup.checksum_sha256 and computed != backup.checksum_sha256:
        backup.status = BackupRecord.Status.CORRUPT
        backup.save(update_fields=["status", "updated_at"])
        return VerificationResult(
            False,
            "Bütünlük hatası: dosya özeti kayıtla eşleşmiyor. Yedek bozulmuş olabilir.",
            computed_checksum=computed,
        )

    work_path = path
    temporary: Path | None = None
    try:
        if backup.is_encrypted:
            temporary = path.with_suffix(".verify.zip")
            _decrypt_file(path, temporary)
            work_path = temporary

        with zipfile.ZipFile(work_path) as archive:
            names = archive.namelist()
            if "manifest.json" not in names:
                return VerificationResult(False, "Arşivde manifest.json yok.")
            if "data.json" not in names:
                return VerificationResult(False, "Arşivde data.json yok.")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            records = json.loads(archive.read("data.json").decode("utf-8"))

        details = {
            "manifest_version": manifest.get("version"),
            "object_count": len(records),
            "has_sqlite_copy": "database.sqlite3" in names,
            "record_counts": manifest.get("record_counts", {}),
        }

        backup.status = BackupRecord.Status.VERIFIED
        backup.verified_at = timezone.now()
        backup.save(update_fields=["status", "verified_at", "updated_at"])

        if user is not None:
            record(
                action=AuditAction.BACKUP,
                obj=backup,
                message=f"Yedek doğrulandı: {backup.file_name} · {len(records)} nesne",
                actor=user,
            )

        return VerificationResult(
            True,
            f"Yedek geçerli. {len(records)} nesne, sürüm {manifest.get('version')}.",
            computed_checksum=computed,
            details=details,
        )

    except (zipfile.BadZipFile, json.JSONDecodeError, BackupError) as exc:
        backup.status = BackupRecord.Status.CORRUPT
        backup.save(update_fields=["status", "updated_at"])
        return VerificationResult(False, f"Yedek okunamadı: {exc}", computed_checksum=computed)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


# ---------------------------------------------------------------------------
# Geri yükleme
# ---------------------------------------------------------------------------
def restore_backup(*, restore: RestoreRecord, user: Any) -> RestoreRecord:
    """Yedeği hedef veritabanına geri yükler.

    Güvenlik kuralları:
      * Onay zorunludur (``restore.approval`` onaylanmış olmalıdır).
      * Yedek önce doğrulanır; bozuksa işlem yapılmaz.
      * Canlı veritabanına yükleme öncesi otomatik güvenlik yedeği alınır.
    """
    if restore.approval is None or restore.approval.status != "approved":
        raise BackupError("Geri yükleme ikinci onay gerektirir. Önce onay talebini onaylatın.")

    verification = verify_backup(backup=restore.backup)
    if not verification.is_valid:
        restore.status = RestoreRecord.Status.FAILED
        restore.error_message = verification.message
        restore.save(update_fields=["status", "error_message", "updated_at"])
        raise BackupError(f"Yedek doğrulanamadı: {verification.message}")

    restore.status = RestoreRecord.Status.RUNNING
    restore.started_at = timezone.now()
    restore.save(update_fields=["status", "started_at", "updated_at"])

    try:
        if restore.target == RestoreRecord.Target.PRODUCTION:
            safety = create_backup(
                user=user,
                kind=BackupRecord.Kind.PRE_RESTORE,
                notes=f"{restore.backup.file_name} geri yüklenmeden önce alındı.",
            )
            restore.safety_backup = safety
            restore.save(update_fields=["safety_backup", "updated_at"])

        source = Path(restore.backup.file_path)
        work_path = source
        temporary: Path | None = None

        if restore.backup.is_encrypted:
            temporary = source.with_suffix(".restore.zip")
            _decrypt_file(source, temporary)
            work_path = temporary

        target_path = Path(
            restore.target_path
            or (
                settings.DATABASES["default"]["NAME"]
                if restore.target == RestoreRecord.Target.PRODUCTION
                else Path(settings.BASE_DIR) / "var" / "restore-test.sqlite3"
            )
        )

        produced_path = target_path
        with zipfile.ZipFile(work_path) as archive:
            names = archive.namelist()
            if "database.sqlite3" in names and connection.vendor == "sqlite":
                # Yedekte ham veritabanı dosyası var: doğrudan kopyalanır.
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open("database.sqlite3") as member, target_path.open("wb") as out:
                    shutil.copyfileobj(member, out)
                method = "sqlite-file-copy"
            else:
                # Ham dosya yok (ör. PostgreSQL veya bellek içi veritabanı):
                # veri JSON olarak çıkarılır.
                method = "loaddata"
                extracted = target_path.with_suffix(".data.json")
                extracted.parent.mkdir(parents=True, exist_ok=True)
                extracted.write_bytes(archive.read("data.json"))
                if restore.target == RestoreRecord.Target.PRODUCTION:
                    call_command("loaddata", str(extracted))
                    extracted.unlink()
                    produced_path = target_path
                else:
                    # Test hedefinde veri yüklenmez; incelenmek üzere dosyaya yazılır.
                    # Rapor gerçekten üretilen dosyayı göstermelidir.
                    produced_path = extracted

            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))

        if temporary is not None and temporary.exists():
            temporary.unlink()

        restore.status = RestoreRecord.Status.SUCCESS
        restore.finished_at = timezone.now()
        restore.target_path = str(produced_path)
        restore.verification_report = {
            "method": method,
            "expected_counts": manifest.get("record_counts", {}),
            "restored_to": str(produced_path),
            "data_loaded": restore.target == RestoreRecord.Target.PRODUCTION
            or method == "sqlite-file-copy",
            "verified_checksum": verification.computed_checksum,
        }
        restore.save()

        record(
            action=AuditAction.RESTORE,
            obj=restore,
            message=(
                f"Yedek geri yüklendi: {restore.backup.file_name} → "
                f"{restore.get_target_display()} ({target_path})"
            ),
            severity=AuditSeverity.CRITICAL,
            actor=user,
        )
        return restore

    except Exception as exc:
        restore.status = RestoreRecord.Status.FAILED
        restore.error_message = str(exc)[:2000]
        restore.finished_at = timezone.now()
        restore.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        logger.exception("Geri yükleme başarısız.")
        raise BackupError(f"Geri yükleme başarısız: {exc}") from exc


def apply_retention_policy(*, user: Any = None) -> list[str]:
    """Saklama süresi dolan yedekleri arşivden çıkarır.

    Güvenlik: En az **3 yedek** her zaman korunur; politika süreye baksa bile
    bu alt sınırın altına inilmez.
    """
    retention_days = settings.BACKUP_RETENTION_DAYS
    if retention_days <= 0:
        return []

    backups = list(
        BackupRecord.objects.filter(
            status__in=[BackupRecord.Status.SUCCESS, BackupRecord.Status.VERIFIED]
        ).order_by("-started_at")
    )
    if len(backups) <= 3:
        return []

    removed: list[str] = []
    for backup in backups[3:]:
        if backup.age_days <= retention_days:
            continue
        path = Path(backup.file_path)
        if path.exists():
            path.unlink()
            removed.append(backup.file_name)
            backup.notes = (
                f"{backup.notes}\nSaklama politikası gereği dosya silindi "
                f"({retention_days} gün)."
            ).strip()
            backup.save(update_fields=["notes", "updated_at"])

    if removed and user is not None:
        record(
            action=AuditAction.BACKUP,
            message=f"Saklama politikası uygulandı: {len(removed)} yedek dosyası silindi.",
            severity=AuditSeverity.NOTICE,
            actor=user,
        )
    return removed
