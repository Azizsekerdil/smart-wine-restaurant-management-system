"""Gizlilik odaklı şablon filtreleri.

Liste ekranlarında kişisel tanımlayıcıların tamamı gösterilmez. Tam değer
yalnızca yetkili rolün açtığı detay ekranındadır. Bu, hem veri minimizasyonu
ilkesini uygular hem de ekran görüntüsü / sunum / ekran paylaşımı yoluyla
sızıntıyı önler.
"""

from __future__ import annotations

from django import template

from apps.core.security import partial_mask

register = template.Library()


@register.filter(name="mask_identifier")
def mask_identifier(value: str, keep_last: int = 2) -> str:
    """Telefon, e-posta veya benzeri tanımlayıcıyı kısmen maskeler."""
    return partial_mask(str(value or ""), keep_last=int(keep_last))
