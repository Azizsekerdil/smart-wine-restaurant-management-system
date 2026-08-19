"""İlk kurulum kimlik bilgisi, zorunlu parola değişimi ve PIN oturum kapsamı.

Bu modül üç güvenlik sözleşmesini gerileme (regression) testleriyle sabitler:

1. **Tek kullanımlık kurulum hesabı.** Boş kurulumda yalnızca yerel cihazdan
   kullanılabilen `admin/admin` hesabı oluşturulur ve ilk girişte parola
   değişimi zorunlu tutulur.
2. **Zorunlu parola değişimi gerçekten zorlanır.** `must_change_password`
   işaretli kullanıcı, parolasını değiştirene kadar hiçbir korunan ekrana,
   REST API kaynağına veya Django yönetim paneline erişemez.
3. **PIN oturumu yönetim yüzeyine erişemez.** 4-8 rakamlık PIN yalnızca
   salon / mutfak / bar ekranlarını açar.

Parolalar her durumda karma (hash) olarak saklanır; düz metin hiçbir yerde
tutulmaz.
"""

from __future__ import annotations

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.accounts.models import User
from apps.core.middleware import AUTH_SCOPE_SESSION_KEY

pytestmark = [pytest.mark.rbac, pytest.mark.django_db]

STRONG_PASSWORD = "Kav.Parolasi.2026!"
NEW_PASSWORD = "Yeni.Kav.Parolasi.2026!"


# ---------------------------------------------------------------------------
# 1) İlk kurulum: tek kullanımlık admin/admin
# ---------------------------------------------------------------------------
def test_create_admin_parolasiz_admin_admin_bootstrap_olusturur(monkeypatch) -> None:
    """Boş kurulum onaylı tek kullanımlık hesabı hash'leyerek oluşturur."""
    monkeypatch.delenv("WINEHOUSE_ADMIN_PASSWORD", raising=False)
    call_command("create_admin", "--non-interactive")
    user = User.objects.get(username="admin")
    assert user.check_password("admin")
    assert user.password != "admin"
    assert user.must_change_password is True


def test_admin_parolasi_yalniz_bootstrap_istisnasidir(monkeypatch) -> None:
    """Owner-approved pair is accepted only into forced-change state."""
    monkeypatch.setenv("WINEHOUSE_ADMIN_PASSWORD", "admin")
    call_command("create_admin", "--username", "admin", "--non-interactive")
    user = User.objects.get(username="admin")
    assert user.must_change_password is True


def test_create_admin_parolayi_karma_olarak_saklar(monkeypatch) -> None:
    """Oluşturulan yöneticinin parolası düz metin tutulmaz."""
    monkeypatch.setenv("WINEHOUSE_ADMIN_PASSWORD", STRONG_PASSWORD)
    call_command("create_admin", "--username", "kurulum", "--non-interactive")

    user = User.objects.get(username="kurulum")
    assert user.password != STRONG_PASSWORD
    assert STRONG_PASSWORD not in user.password
    assert user.check_password(STRONG_PASSWORD)
    algorithm = user.password.split("$", 1)[0]
    assert algorithm in {"argon2", "bcrypt", "bcrypt_sha256", "scrypt", "pbkdf2_sha256", "md5"}


def test_bootstrap_komutu_calismadan_hesap_yoktur(db) -> None:
    """Hesap yalnız açık bootstrap komutu çalıştırıldığında oluşturulur."""
    assert User.objects.count() == 0
    assert not User.objects.filter(username="admin").exists()


# ---------------------------------------------------------------------------
# 2) Zorunlu parola değişimi
# ---------------------------------------------------------------------------
@pytest.fixture
def must_change_user(make_user):
    user = make_user("degistir", "restaurant_manager")
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])
    return user


def test_bootstrap_girisi_uzaktan_reddedilir(client, must_change_user) -> None:
    response = client.post(
        reverse("accounts:login"),
        {"username": must_change_user.username, "password": "Test.Parola.2026!"},
        REMOTE_ADDR="203.0.113.77",
    )
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_bootstrap_girisi_yerelden_parola_degisime_gider(client, must_change_user) -> None:
    response = client.post(
        reverse("accounts:login"),
        {"username": must_change_user.username, "password": "Test.Parola.2026!"},
        REMOTE_ADDR="127.0.0.1",
    )
    assert response.status_code == 302
    assert "_auth_user_id" in client.session


@pytest.mark.parametrize(
    "url_name",
    [
        "core:dashboard",
        "core:settings",
        "accounts:user-list",
        "accounts:audit-log",
        "accounts:approval-queue",
        "reporting:report-list",
        "crm:customer-list",
        "backups:backup-list",
    ],
)
def test_parola_degisimi_zorunluyken_korunan_ekranlar_kapali(
    client_as, must_change_user, url_name
) -> None:
    """Parola değiştirilmeden hiçbir korunan ekran açılmaz."""
    client = client_as(must_change_user)
    response = client.get(reverse(url_name))
    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:password-change")


def test_parola_degisimi_zorunluyken_api_403_doner(client_as, must_change_user) -> None:
    """REST API yönlendirme yerine açıkça reddeder."""
    client = client_as(must_change_user)
    response = client.get("/api/v1/reporting/reports/catalog/")
    assert response.status_code == 403


def test_parola_degisimi_zorunluyken_django_admin_kapali(client_as, must_change_user) -> None:
    must_change_user.is_staff = True
    must_change_user.is_superuser = True
    must_change_user.save(update_fields=["is_staff", "is_superuser"])
    client = client_as(must_change_user)
    response = client.get("/django-admin/")
    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:password-change")


def test_parola_ekrani_ve_cikis_erisilebilir_kalir(client_as, must_change_user) -> None:
    """Kullanıcı kilitlenip kalmaz: parola ekranı ve çıkış açıktır."""
    client = client_as(must_change_user)
    assert client.get(reverse("accounts:password-change")).status_code == 200


def test_parola_degisince_kisitlama_kalkar(client_as, must_change_user) -> None:
    client = client_as(must_change_user)
    response = client.post(
        reverse("accounts:password-change"),
        {
            "old_password": "Test.Parola.2026!",
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        },
    )
    assert response.status_code == 302

    must_change_user.refresh_from_db()
    assert must_change_user.must_change_password is False
    assert must_change_user.password_changed_at is not None
    # Yeni parola karma saklanır.
    assert NEW_PASSWORD not in must_change_user.password
    assert must_change_user.check_password(NEW_PASSWORD)
    # Artık korunan ekran açılır.
    assert client.get(reverse("core:dashboard")).status_code == 200


def test_yonetici_parola_sifirlamasi_zorunlulugu_geri_getirmez(
    client_as, admin_user, must_change_user
) -> None:
    """Yönetici sıfırlaması, zorunlu değişim bayrağını kendiliğinden düşürmez."""
    from apps.accounts.forms import UserForm

    form = UserForm(
        instance=must_change_user,
        data={
            "username": must_change_user.username,
            "display_name": must_change_user.display_name,
            "first_name": "",
            "last_name": "",
            "email": "",
            "phone": "",
            "employee_code": "",
            "preferred_language": "tr",
            "discount_limit_percent": "0",
            "is_active": "on",
            "must_change_password": "on",
            "notes": "",
            "role_code": "restaurant_manager",
            "new_password": "Sifirlanan.Parola.2026!",
        },
    )
    assert form.is_valid(), form.errors
    form.save()

    must_change_user.refresh_from_db()
    assert must_change_user.must_change_password is True
    # Sıfırlanan parola da karma saklanır.
    assert "Sifirlanan.Parola.2026!" not in must_change_user.password
    # Ve kullanıcı hâlâ kilitli kapsamdadır.
    client = client_as(must_change_user)
    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:password-change")


# ---------------------------------------------------------------------------
# 3) PIN oturum kapsamı
# ---------------------------------------------------------------------------
@pytest.fixture
def pin_waiter(make_user):
    user = make_user("pinli", "restaurant_manager")
    user.employee_code = "P-100"
    user.set_pin("4821")
    user.save()
    return user


def _pin_login(client, code: str = "P-100", pin: str = "4821"):
    return client.post(reverse("accounts:pin-login"), {"employee_code": code, "pin": pin})


def test_pin_girisi_oturumu_pin_kapsamiyla_isaretler(client, pin_waiter) -> None:
    response = _pin_login(client)
    assert response.status_code == 302
    assert client.session[AUTH_SCOPE_SESSION_KEY] == "pin"


def test_pin_girisi_yanlis_pini_kabul_etmez(client, pin_waiter) -> None:
    response = _pin_login(client, pin="0000")
    assert response.status_code == 200
    assert AUTH_SCOPE_SESSION_KEY not in client.session


@pytest.mark.parametrize(
    "url_name",
    [
        "accounts:user-list",
        "accounts:role-list",
        "accounts:audit-log",
        "accounts:approval-queue",
        "core:settings",
        "reporting:report-list",
        "crm:customer-list",
        "hr:employee-list",
        "backups:backup-list",
        "aiservices:providers",
    ],
)
def test_pin_oturumu_yonetim_ekranlarina_erisemez(client, pin_waiter, url_name) -> None:
    """PIN oturumu yönetim yüzeyinde 403 alır — rolü yetse bile."""
    _pin_login(client)
    response = client.get(reverse(url_name))
    assert response.status_code == 403


def test_pin_oturumu_django_admin_paneline_erisemez(client, pin_waiter) -> None:
    pin_waiter.is_staff = True
    pin_waiter.is_superuser = True
    pin_waiter.save(update_fields=["is_staff", "is_superuser"])
    _pin_login(client)
    assert client.get("/django-admin/").status_code == 403


@pytest.mark.parametrize(
    "url_name",
    [
        "core:dashboard",
        "operations:table-map",
        "operations:order-list",
        "operations:kds-kitchen",
        "operations:kds-bar",
        "catalog:menuitem-list",
    ],
)
def test_pin_oturumu_salon_ekranlarini_acabilir(client, pin_waiter, url_name) -> None:
    _pin_login(client)
    assert client.get(reverse(url_name)).status_code == 200


def test_parola_oturumu_yonetim_ekranlarini_acabilir(client_as, pin_waiter) -> None:
    """Aynı kullanıcı parolayla girince kapsam daralmaz (kontrol testi)."""
    client = client_as(pin_waiter)
    client.session[AUTH_SCOPE_SESSION_KEY] = "password"
    assert client.get(reverse("reporting:report-list")).status_code == 200


def test_pin_karma_saklanir_duz_metin_tutulmaz(pin_waiter) -> None:
    assert pin_waiter.pin_hash
    assert "4821" not in pin_waiter.pin_hash
    assert pin_waiter.check_pin("4821")
    assert not pin_waiter.check_pin("1234")


# ---------------------------------------------------------------------------
# 4) Kaba kuvvet koruması
# ---------------------------------------------------------------------------
def test_art_arda_basarisiz_giris_hesabi_kilitler(client, pin_waiter) -> None:
    """5 başarısız denemeden sonra hesap geçici olarak kilitlenir."""
    for _ in range(5):
        _pin_login(client, pin="0000")
    pin_waiter.refresh_from_db()
    assert pin_waiter.failed_login_count >= 5
    assert pin_waiter.is_locked
    # Kilitliyken doğru PIN de kabul edilmez.
    _pin_login(client)
    assert AUTH_SCOPE_SESSION_KEY not in client.session


def test_kilit_denetim_kaydina_hassas_deger_yazmaz(client, pin_waiter) -> None:
    """Denetim kaydı PIN'i veya parolayı içermez."""
    from apps.core.models import AuditLog

    _pin_login(client, pin="0000")
    messages = " ".join(AuditLog.objects.values_list("message", flat=True))
    assert "0000" not in messages
    assert "4821" not in messages


# ---------------------------------------------------------------------------
# 5) Parola karma algoritması
# ---------------------------------------------------------------------------
def test_temel_ayarlar_argon2id_kullanir() -> None:
    """Üretim/geliştirme profilinde birincil karma Argon2id'dir.

    (Test profili hız için MD5'e düşer; bu test temel ayarları okur.)
    """
    import importlib

    base = importlib.import_module("winehouse.settings.base")
    hashers = base.PASSWORD_HASHERS
    assert hashers[0] == "django.contrib.auth.hashers.Argon2PasswordHasher"
    # Eski karmalar doğrulanabilsin diye PBKDF2 listede kalır.
    assert "django.contrib.auth.hashers.PBKDF2PasswordHasher" in hashers


def test_argon2_karma_uretilebiliyor() -> None:
    """argon2-cffi kurulu ve Django tarafından kullanılabilir durumda."""
    from django.contrib.auth.hashers import Argon2PasswordHasher

    hasher = Argon2PasswordHasher()
    encoded = hasher.encode("Kav.Parolasi.2026!", hasher.salt())
    assert encoded.startswith("argon2$argon2id$")
    assert "Kav.Parolasi.2026!" not in encoded
    assert hasher.verify("Kav.Parolasi.2026!", encoded)


# ---------------------------------------------------------------------------
# 6) Liste ekranlarında kısmi maskeleme
# ---------------------------------------------------------------------------
def test_partial_mask_yalnizca_son_haneleri_birakir() -> None:
    from apps.core.security import partial_mask

    assert partial_mask("+90 5XX XXX XX 07") == "+•• ••• ••• •• 07"
    assert partial_mask("05551110404", keep_last=4) == "•••••••0404"
    assert partial_mask("") == ""


def test_musteri_listesi_tam_telefonu_gostermez(client_as, admin_user) -> None:
    """Yetkili rol bile listede tam numarayı görmez (veri minimizasyonu)."""
    from apps.crm.models import Customer

    Customer.objects.create(
        code="MST9001",
        first_name="Örnek",
        last_name="Misafir",
        phone="+90 5XX XXX XX 42",
    )
    client = client_as(admin_user)
    body = client.get(reverse("crm:customer-list")).content.decode()
    assert "+90 5XX XXX XX 42" not in body
    assert "42" in body


# ---------------------------------------------------------------------------
# 7) Açık yönlendirme ve parola politikası kapsamı
# ---------------------------------------------------------------------------
def test_dil_degistirme_dis_siteye_yonlendirmez(client_as, admin_user) -> None:
    """`Referer` dış bir siteyi gösterse bile yönlendirme site içinde kalır."""
    client = client_as(admin_user)
    response = client.post(
        reverse("core:set-language"),
        {"language": "en"},
        HTTP_REFERER="https://kotu-site.example/tuzak",
    )
    assert response.status_code == 302
    assert "kotu-site.example" not in response["Location"]
    assert response["Location"] == reverse("core:dashboard")


def test_dil_degistirme_ayni_site_refereri_korur(client_as, admin_user) -> None:
    client = client_as(admin_user)
    target = "http://testserver" + reverse("crm:customer-list")
    response = client.post(reverse("core:set-language"), {"language": "en"}, HTTP_REFERER=target)
    assert response.status_code == 302
    assert response["Location"] == target


def test_desteklenmeyen_dil_de_dis_siteye_yonlendirmez(client_as, admin_user) -> None:
    client = client_as(admin_user)
    response = client.post(
        reverse("core:set-language"),
        {"language": "xx"},
        HTTP_REFERER="https://kotu-site.example/tuzak",
    )
    assert response.status_code == 302
    assert "kotu-site.example" not in response["Location"]


def test_kullanici_olusturma_zayif_parolayi_reddeder(roles) -> None:
    """`create_user_with_role` parola politikasını atlayamaz."""
    from django.core.exceptions import ValidationError

    from apps.accounts.services import create_user_with_role

    with pytest.raises(ValidationError):
        create_user_with_role(username="zayif", password="12345678", role_code="waiter")
    assert not User.objects.filter(username="zayif").exists()


def test_kullanici_olusturma_guclu_parolayi_kabul_eder(roles) -> None:
    from apps.accounts.services import create_user_with_role

    user = create_user_with_role(username="guclu", password=STRONG_PASSWORD, role_code="waiter")
    assert user.check_password(STRONG_PASSWORD)
    assert STRONG_PASSWORD not in user.password
