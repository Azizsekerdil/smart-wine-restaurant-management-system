from django.utils import translation


def test_english_catalog_translates_core_navigation() -> None:
    with translation.override("en"):
        assert translation.gettext("Giriş yap") == "Log in"
        assert translation.gettext("Kaydet") == "Save"
        assert translation.gettext("Kişisel bilgiler") == "Personal information"


def test_turkish_source_language_remains_available() -> None:
    with translation.override("tr"):
        assert translation.gettext("Giriş yap") == "Giriş yap"
        assert translation.gettext("Kaydet") == "Kaydet"
