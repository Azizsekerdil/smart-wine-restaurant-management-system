"""Günlük kayıtlarında gizli değerleri maskeleyen filtreler.

``LOGGING`` yapılandırmasındaki her handler bu filtreyi kullanır; böylece
API anahtarları hiçbir günlük dosyasına düz metin olarak yazılmaz.
"""

from __future__ import annotations

import logging


class SecretMaskingFilter(logging.Filter):
    """Log kaydındaki mesaj ve argümanlardaki gizli değerleri maskeler."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Gecikmeli içe aktarma: Django ayarları yüklenmeden çağrılabilir.
        from apps.core.security import mask_secrets

        if isinstance(record.msg, str):
            record.msg = mask_secrets(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    key: mask_secrets(value) if isinstance(value, str) else value
                    for key, value in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_secrets(value) if isinstance(value, str) else value
                    for value in record.args
                )
        return True
