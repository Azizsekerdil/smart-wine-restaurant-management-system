#!/usr/bin/env python
"""Wine House — Django yönetim aracı / Django management utility.

Kaynak kodu `src/` altında bulunur; bu betik `src/` dizinini Python yoluna
ekleyerek `winehouse` ve `apps` paketlerinin bulunmasını sağlar.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> None:
    """Komut satırı yönetim görevlerini çalıştırır."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "winehouse.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - kurulum hatası yolu
        raise ImportError(
            "Django içe aktarılamadı. Sanal ortamın etkin olduğundan ve "
            "bağımlılıkların kurulduğundan emin olun:\n"
            "    .venv\\Scripts\\activate\n"
            "    pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
