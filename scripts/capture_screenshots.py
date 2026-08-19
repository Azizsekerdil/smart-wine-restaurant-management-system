"""Wine House arayüz ekran görüntüsü yakalayıcı.

Tanıtım sunumu için uygulamanın gerçek sayfalarını PNG olarak kaydeder.

Gereksinim (yalnızca bu betik için, CI'da gerekmez)::

    .venv\\Scripts\\python.exe -m pip install playwright
    .venv\\Scripts\\python.exe -m playwright install chromium

Kullanım::

    .venv\\Scripts\\python.exe scripts\\capture_screenshots.py

Ne yapar:

1. Geçici bir tanıtım kullanıcısı (``tanitim_bot``) oluşturur — sentetik,
   yalnızca yereldir ve betik sonunda silinir.
2. Django geliştirme sunucusunu 127.0.0.1:8765 üzerinde başlatır.
3. Ana ekranları gezerek ``docs/screenshots/`` altına PNG kaydeder.
4. Sunucuyu kapatır ve geçici kullanıcıyı siler.

Gerçek kişisel veri kullanılmaz; ekranlar sentetik demo verisini gösterir.
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "winehouse.settings.dev")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

HOST, PORT = "127.0.0.1", 8765
BASE = f"http://{HOST}:{PORT}"
OUT_DIR = PROJECT_ROOT / "docs" / "screenshots"
BOT_USERNAME = "tanitim_bot"

#: (dosya adı, yol, tam sayfa mı)
PAGES: list[tuple[str, str, bool]] = [
    ("login", "/hesap/giris/", False),
    ("dashboard", "/", True),
    ("masa-plani", "/operasyon/", True),
    ("adisyonlar", "/operasyon/adisyonlar/", True),
    ("rezervasyonlar", "/operasyon/rezervasyonlar/", True),
    ("kds-mutfak", "/operasyon/mutfak/", True),
    ("sarap-kavi", "/kav/", True),
    ("kav-degerleme", "/kav/degerleme/", True),
    ("menu", "/menu/", True),
    ("stok", "/stok/", True),
    ("crm", "/musteri/", True),
    ("raporlar", "/rapor/", True),
    ("yapay-zeka", "/yapay-zeka/", True),
    ("egitim", "/egitim/", True),
]


def wait_for_server(timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                return
        except OSError:
            time.sleep(0.4)
    raise RuntimeError("Geliştirme sunucusu açılmadı.")


def main() -> int:
    User = get_user_model()
    password = secrets.token_urlsafe(16)
    User.objects.filter(username=BOT_USERNAME).delete()
    User.objects.create_superuser(
        username=BOT_USERNAME,
        email="",
        password=password,
        display_name="Yönetici",
        primary_role="general_manager",
    )

    server = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "manage.py"), "runserver", f"{HOST}:{PORT}", "--noreload"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_server()
        OUT_DIR.mkdir(parents=True, exist_ok=True)

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1.5,
                locale="tr-TR",
            )
            page = context.new_page()

            # Giriş ekranı (oturum açmadan)
            page.goto(f"{BASE}/hesap/giris/", wait_until="networkidle")
            page.screenshot(path=str(OUT_DIR / "login.png"))
            print("login.png")

            # Oturum aç
            page.fill('input[name="username"]', BOT_USERNAME)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state("networkidle")

            for name, path, _full in PAGES:
                if name == "login":
                    continue
                page.goto(f"{BASE}{path}", wait_until="networkidle")
                page.wait_for_timeout(400)
                page.screenshot(path=str(OUT_DIR / f"{name}.png"))
                print(f"{name}.png")

            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        User.objects.filter(username=BOT_USERNAME).delete()
        print("Geçici kullanıcı silindi; sunucu kapatıldı.")

    count = len(list(OUT_DIR.glob("*.png")))
    print(f"\n{count} ekran görüntüsü: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
