"""Hesap formları."""

from __future__ import annotations

from typing import Any

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.accounts.roles import role_choices

BOOTSTRAP_INPUT = {"class": "form-control"}
BOOTSTRAP_SELECT = {"class": "form-select"}
BOOTSTRAP_CHECK = {"class": "form-check-input"}


class WineHouseAuthenticationForm(AuthenticationForm):
    """Hesap kilidi kontrolü ekleyen giriş formu."""

    username = forms.CharField(
        label=_("Kullanıcı adı"),
        widget=forms.TextInput(
            attrs={**BOOTSTRAP_INPUT, "autofocus": True, "autocomplete": "username"}
        ),
    )
    password = forms.CharField(
        label=_("Parola"),
        widget=forms.PasswordInput(attrs={**BOOTSTRAP_INPUT, "autocomplete": "current-password"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": _("Kullanıcı adı veya parola hatalı."),
        "inactive": _("Bu hesap devre dışı bırakılmış."),
        "locked": _(
            "Hesap çok sayıda başarısız giriş nedeniyle geçici olarak kilitlendi. "
            "Lütfen %(minutes)s dakika sonra tekrar deneyin."
        ),
    }

    def confirm_login_allowed(self, user: User) -> None:
        super().confirm_login_allowed(user)
        if getattr(user, "is_locked", False):
            remaining = max(1, int((user.locked_until - timezone.now()).total_seconds() // 60) + 1)
            raise forms.ValidationError(
                self.error_messages["locked"],
                code="locked",
                params={"minutes": remaining},
            )


class PinLoginForm(forms.Form):
    """POS terminalinde hızlı PIN girişi."""

    employee_code = forms.CharField(
        label=_("Personel kodu"),
        max_length=20,
        widget=forms.TextInput(attrs={**BOOTSTRAP_INPUT, "autofocus": True, "inputmode": "text"}),
    )
    pin = forms.CharField(
        label=_("PIN"),
        max_length=8,
        widget=forms.PasswordInput(
            attrs={**BOOTSTRAP_INPUT, "inputmode": "numeric", "autocomplete": "off"}
        ),
    )

    def clean_pin(self) -> str:
        pin = self.cleaned_data["pin"].strip()
        if not pin.isdigit():
            raise forms.ValidationError(_("PIN yalnızca rakamlardan oluşmalıdır."))
        return pin


class UserForm(forms.ModelForm):
    """Kullanıcı oluşturma/düzenleme formu."""

    role_code = forms.ChoiceField(
        label=_("Birincil rol"),
        choices=role_choices,
        widget=forms.Select(attrs=BOOTSTRAP_SELECT),
    )
    new_password = forms.CharField(
        label=_("Yeni parola"),
        required=False,
        widget=forms.PasswordInput(attrs={**BOOTSTRAP_INPUT, "autocomplete": "new-password"}),
        help_text=_("Boş bırakılırsa parola değiştirilmez."),
    )
    new_pin = forms.CharField(
        label=_("Yeni PIN (4-8 rakam)"),
        required=False,
        widget=forms.PasswordInput(attrs={**BOOTSTRAP_INPUT, "inputmode": "numeric"}),
        help_text=_("POS terminalinde hızlı giriş için. Boş bırakılırsa değişmez."),
    )

    class Meta:
        model = User
        fields = [
            "username",
            "display_name",
            "first_name",
            "last_name",
            "email",
            "phone",
            "employee_code",
            "preferred_language",
            "discount_limit_percent",
            "is_active",
            "must_change_password",
            "notes",
        ]
        widgets = {
            "username": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "display_name": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "first_name": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "last_name": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "email": forms.EmailInput(attrs=BOOTSTRAP_INPUT),
            "phone": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "employee_code": forms.TextInput(attrs=BOOTSTRAP_INPUT),
            "preferred_language": forms.Select(attrs=BOOTSTRAP_SELECT),
            "discount_limit_percent": forms.NumberInput(
                attrs={**BOOTSTRAP_INPUT, "step": "0.01", "min": "0", "max": "100"}
            ),
            "is_active": forms.CheckboxInput(attrs=BOOTSTRAP_CHECK),
            "must_change_password": forms.CheckboxInput(attrs=BOOTSTRAP_CHECK),
            "notes": forms.Textarea(attrs={**BOOTSTRAP_INPUT, "rows": 3}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.primary_role:
            self.fields["role_code"].initial = self.instance.primary_role
        if not (self.instance and self.instance.pk):
            self.fields["new_password"].required = True
            self.fields["new_password"].help_text = _("En az 10 karakter olmalıdır.")

    def clean_new_pin(self) -> str:
        pin = (self.cleaned_data.get("new_pin") or "").strip()
        if pin and (not pin.isdigit() or not (4 <= len(pin) <= 8)):
            raise forms.ValidationError(_("PIN 4-8 rakamdan oluşmalıdır."))
        return pin

    def clean_new_password(self) -> str:
        from django.contrib.auth.password_validation import validate_password

        password = self.cleaned_data.get("new_password") or ""
        if password:
            validate_password(password, self.instance)
        return password

    def save(self, commit: bool = True) -> User:
        user: User = super().save(commit=False)
        password = self.cleaned_data.get("new_password")
        if password:
            user.set_password(password)
            user.password_changed_at = timezone.now()
        pin = self.cleaned_data.get("new_pin")
        if pin:
            user.set_pin(pin)
        if commit:
            user.save()
            from apps.accounts.services import assign_role

            assign_role(user, self.cleaned_data["role_code"], primary=True, replace=True)
        return user


class ApprovalDecisionForm(forms.Form):
    """Onay talebini onaylama/reddetme formu."""

    decision = forms.ChoiceField(
        label=_("Karar"),
        choices=[("approve", _("Onayla")), ("reject", _("Reddet"))],
        widget=forms.RadioSelect,
    )
    note = forms.CharField(
        label=_("Not"),
        required=False,
        widget=forms.Textarea(attrs={**BOOTSTRAP_INPUT, "rows": 2}),
    )
