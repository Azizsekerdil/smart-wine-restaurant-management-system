"""Paketlenmiş uygulamanın giriş noktası (PyInstaller).

Bu dosya `.exe` içinde çalışmak üzere tasarlanmıştır. Görevleri:

1. Yazılabilir veri dizinini hazırlar (exe'nin yanı — bkz. settings/base.py)
2. İlk çalıştırmada `.env` üretir (gizli anahtar + alan şifreleme anahtarı)
3. Veritabanını hazırlar ve ilk kurulum sihirbazını sunar
4. WSGI sunucusunu (çok iş parçacıklı, stdlib) başlatır
5. Tarayıcıyı açar ve konsolda anlaşılır durum bilgisi gösterir

Geliştirme sırasında bu dosyaya gerek yoktur; `manage.py runserver` kullanın.
Paketlenmiş uygulama ÜRETİM ayarlarıyla çalışır (DEBUG kapalı).
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

APP_NAME = "Wine House — Akıllı Şarap Restoranı Yönetim Sistemi"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
HEALTH_PATH = "/api/v1/health/"

IS_FROZEN = bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")

# Paketlenmemiş çalıştırmada src/ yerleşimini görünür kıl (manage.py gibi).
if not IS_FROZEN:
    _SRC = Path(__file__).resolve().parent / "src"
    if _SRC.is_dir() and str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))


# ------------------------------------------------------------------
#  Konsol yardımcıları
# ------------------------------------------------------------------
def _make_console_tolerant() -> None:
    """Konsolun kodlayamadığı bir karakter uygulamayı düşürmesin.

    Windows konsolu Türkçe sistemlerde cp1254/cp857 kullanır. Çıktıdaki bir
    işaret bu tabloda yoksa Python ``UnicodeEncodeError`` yükseltir ve
    uygulama kurulumun ortasında kapanabilir. Kodlamayı değiştirmiyoruz —
    yalnızca hata davranışını "yerine soru işareti koy"a çekiyoruz.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


_make_console_tolerant()


def _supports_unicode() -> bool:
    try:
        "═".encode(sys.stdout.encoding or "utf-8")
        return True
    except (UnicodeEncodeError, LookupError, TypeError):
        return False


BOX = "═" if _supports_unicode() else "="


def banner(text: str) -> None:
    line = BOX * 62
    print()
    print(f"  {line}")
    print(f"    {text}")
    print(f"  {line}")
    print()


def step(text: str) -> None:
    print(f"  [*] {text}")


def ok(text: str) -> None:
    print(f"  [OK] {text}")


def warn(text: str) -> None:
    print(f"  [!]  {text}")


def fail(text: str) -> None:
    print(f"  [X]  {text}")


def pause_before_exit(message: str = "Kapatmak için Enter'a basın...") -> None:
    """Konsol penceresi hata mesajı okunamadan kapanmasın.

    stdin yoksa (ör. otomatik test) beklemeden devam eder.
    """
    try:
        input(f"  {message}")
    except (EOFError, KeyboardInterrupt, OSError):
        pass


# ------------------------------------------------------------------
#  Yollar
# ------------------------------------------------------------------
def resource_dir() -> Path:
    """Salt okunur kaynakların kökü (paketli: geçici açılma dizini)."""
    if IS_FROZEN:
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    """Yazılabilir veri dizini (paketli: exe'nin yanı)."""
    override = os.environ.get("WINEHOUSE_DATA_DIR", "").strip()
    if override:
        return Path(override).resolve()
    if IS_FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# ------------------------------------------------------------------
#  İlk çalıştırma: .env üretimi
# ------------------------------------------------------------------
def ensure_env_file(target_dir: Path) -> None:
    """İlk çalıştırmada `.env` dosyasını üretir.

    Üretim ayarları (prod.py) gizli anahtar olmadan başlamayı reddeder;
    bu yüzden anahtarlar burada güvenli biçimde üretilip dosyaya yazılır.
    Kullanıcı daha sonra bu dosyayı düzenleyerek ayarları değiştirebilir.
    """
    env_file = target_dir / ".env"
    if env_file.exists():
        return

    import secrets

    sample = resource_dir() / ".env.example"
    if sample.is_file():
        content = sample.read_text(encoding="utf-8")
    else:  # örnek dosya pakete girmediyse asgari içerik
        content = (
            "DJANGO_SECRET_KEY=\nWINEHOUSE_ENV=dev\nDJANGO_DEBUG=True\n"
            "WINEHOUSE_FIELD_ENCRYPTION_KEY=\n"
        )

    content = content.replace(
        "DJANGO_SECRET_KEY=",
        f"DJANGO_SECRET_KEY={secrets.token_urlsafe(64)}",
        1,
    )
    content = content.replace("WINEHOUSE_ENV=dev", "WINEHOUSE_ENV=prod", 1)
    content = content.replace("DJANGO_DEBUG=True", "DJANGO_DEBUG=False", 1)
    # Geliştirme makinesine özgü örnek yol, kullanıcı makinesinde anlamsız.
    content = content.replace(
        "WINEHOUSE_DEVSTUDIO_WORKSPACE=D:\\Wine_House",
        f"WINEHOUSE_DEVSTUDIO_WORKSPACE={target_dir}",
        1,
    )
    try:
        from cryptography.fernet import Fernet

        content = content.replace(
            "WINEHOUSE_FIELD_ENCRYPTION_KEY=",
            f"WINEHOUSE_FIELD_ENCRYPTION_KEY={Fernet.generate_key().decode('ascii')}",
            1,
        )
    except Exception:
        # Şifreleme anahtarı üretilemezse uygulama uyarı vererek yine çalışır.
        pass

    env_file.write_text(content, encoding="utf-8")
    ok(f"Ayar dosyası oluşturuldu: {env_file}")


# ------------------------------------------------------------------
#  Ağ
# ------------------------------------------------------------------
def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def find_free_port(host: str, start: int, attempts: int = 20) -> int | None:
    for offset in range(attempts):
        candidate = start + offset
        if not port_in_use(host, candidate):
            return candidate
    return None


def is_our_app(host: str, port: int) -> bool:
    """Porttaki sunucu bu uygulama mı?

    Port dolu olması tek başına "program zaten açık" demek değildir;
    bambaşka bir yazılım da o portu kullanıyor olabilir. Sağlık uç
    noktasına bakarak emin oluruz.
    """
    import json
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(  # noqa: S310 - sabit, yerel adres
            f"http://{host}:{port}{HEALTH_PATH}", timeout=2
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return "status" in payload and "database" in payload
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return False


def open_browser_when_ready(url: str, host: str, port: int) -> None:
    """Sunucu gerçekten yanıt vermeye başlayınca tarayıcıyı açar."""
    for _ in range(60):
        time.sleep(0.5)
        if port_in_use(host, port):
            time.sleep(0.8)  # ilk isteğin hazır olması için kısa pay
            try:
                webbrowser.open(url)
            except Exception:
                warn(f"Tarayıcı açılamadı. Elle açın: {url}")
            return


# ------------------------------------------------------------------
#  Django kurulumu
# ------------------------------------------------------------------
def prepare_database() -> int:
    """Veritabanını hazırlar; toplam kullanıcı sayısını döndürür."""
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    step("Veritabanı hazırlanıyor...")
    call_command("migrate", interactive=False, verbosity=0)
    ok("Veritabanı hazır")

    return get_user_model().objects.count()


def first_run_wizard() -> None:
    """Hiç kullanıcı yokken çalışan basit kurulum sihirbazı.

    Etkileşimli olmayan ortamda (stdin yok / boru) sormadan atlar; böylece
    otomatik testler ve betikler ilk açılışta takılı kalmaz. Ayrıca
    ``WINEHOUSE_FIRST_RUN=skip`` ortam değişkeni sihirbazı tamamen kapatır
    (görünmez pencerede başlatılan süreçlerde konsol "etkileşimli" görünür
    ama kimse yanıt veremez — duman testi bu anahtarı kullanır).
    """
    from django.core.management import call_command

    if os.environ.get("WINEHOUSE_FIRST_RUN", "").strip().lower() in {"skip", "atla"}:
        warn("İlk kurulum sihirbazı atlandı (WINEHOUSE_FIRST_RUN=skip).")
        return

    print()
    warn("Sistemde henüz kullanıcı yok — giriş yapamazsınız.")
    print()
    print("      1) Yönetici hesabı oluştur (önerilen)")
    print("      2) Yönetici hesabı + örnek veri (menü, kav, masa planı)")
    print("      3) Atla (daha sonra kurarım)")
    print()

    interactive = sys.stdin is not None and sys.stdin.isatty()
    if not interactive:
        warn("Etkileşimli konsol yok; kurulum atlandı.")
        return

    try:
        choice = input("  Seçiminiz [1/2/3] (varsayılan 1): ").strip() or "1"
    except (EOFError, KeyboardInterrupt, OSError):
        choice = "3"

    if choice in {"1", "2"}:
        print()
        print("  Yönetici hesabı oluşturuluyor.")
        print("  (Parola en az 10 karakter olmalı; ekranda görünmez.)")
        print()
        try:
            call_command("create_admin")
        except Exception as exc:
            fail(f"Yönetici oluşturulamadı: {exc}")
            warn("Daha sonra yeniden deneyebilirsiniz.")
            return
        if choice == "2":
            step("Örnek veri yükleniyor, bu biraz sürebilir...")
            try:
                call_command("seed_demo", "--with-sales", verbosity=0)
                ok("Örnek veri hazır.")
                warn("Gerçek kullanıma geçmeden önce örnek veriyi temizleyin.")
            except Exception as exc:
                fail(f"Örnek veri yüklenemedi: {exc}")
    else:
        warn("Atlandı. Kullanıcı oluşturmadan giriş yapamazsınız.")


# ------------------------------------------------------------------
#  Sunucu (çok iş parçacıklı WSGI — stdlib, ek bağımlılık yok)
# ------------------------------------------------------------------
def run_server(host: str, port: int) -> None:
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

    from winehouse.wsgi import application

    class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
        daemon_threads = True
        allow_reuse_address = True

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, *args: object) -> None:  # istek gürültüsü olmasın
            pass

    httpd = make_server(
        host,
        port,
        application,
        server_class=ThreadedWSGIServer,
        handler_class=QuietHandler,
    )
    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        httpd.server_close()


# ------------------------------------------------------------------
#  Ana akış
# ------------------------------------------------------------------
def main() -> int:
    # Paketlenmiş uygulama üretim gibi davranır: hata ayıklama kapalı.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "winehouse.settings.prod")
    os.environ.setdefault("DJANGO_DEBUG", "False")

    banner(APP_NAME)

    target_dir = data_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Veri klasörü : {target_dir}")

    # İlk çalıştırmada .env oluştur ki üretim ayarları anahtar bulabilsin.
    ensure_env_file(target_dir)
    env_file = target_dir / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)

    # ---------- port ----------
    # Port, ayarlar yüklenmeden ÖNCE kesinleşmeli: CSRF_TRUSTED_ORIGINS
    # WINEHOUSE_PORT ortam değişkeninden üretilir (bkz. settings/base.py).
    host = os.environ.get("WINEHOUSE_HOST", DEFAULT_HOST)
    try:
        port = int(os.environ.get("WINEHOUSE_PORT", str(DEFAULT_PORT)))
    except ValueError:
        port = DEFAULT_PORT

    if port_in_use(host, port):
        if is_our_app(host, port):
            url = f"http://{host}:{port}/"
            ok("Program zaten çalışıyor.")
            print(f"       Tarayıcı açılıyor: {url}")
            webbrowser.open(url)
            time.sleep(2)
            return 0

        # Portu başka bir yazılım tutuyor; ona tarayıcı açmak yanlış olur.
        warn(f"{port} portunu başka bir program kullanıyor.")
        free = find_free_port(host, port + 1)
        if free is None:
            fail("Boş port bulunamadı.")
            pause_before_exit()
            return 1
        port = free
        print(f"       Bunun yerine {port} portu kullanılacak.")

    os.environ["WINEHOUSE_PORT"] = str(port)

    # ---------- Django ----------
    import django

    django.setup()

    try:
        user_count = prepare_database()
    except Exception as exc:  # pragma: no cover
        fail(f"Veritabanı hazırlanamadı: {exc}")
        print()
        print(f"  Ayrıntı için: {target_dir / 'logs' / 'winehouse.log'}")
        pause_before_exit()
        return 1

    if user_count == 0:
        first_run_wizard()

    url = f"http://{host}:{port}/"

    print()
    ok("Sunucu başlatılıyor")
    print()
    print(f"      Adres  : {url}")
    print("      Durdur : Bu pencerede Ctrl+C  (veya pencereyi kapatın)")
    print()
    print(f"  {'-' * 60}")
    print()

    threading.Thread(
        target=open_browser_when_ready, args=(url, host, port), daemon=True
    ).start()

    try:
        run_server(host, port)
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # pragma: no cover
        print()
        fail(f"Sunucu hatası: {exc}")
        pause_before_exit()
        return 1

    print()
    print("  Sunucu durduruldu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
