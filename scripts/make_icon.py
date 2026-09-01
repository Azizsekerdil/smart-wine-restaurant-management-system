"""Uygulama ikonu üretir (Windows .exe için .ico).

Harici görsel dosyasına bağımlı olmamak için ikon programatik çizilir
(Pillow ile) ve `src/static/img/favicon.svg` ile aynı görsel dili kullanır:
bordo zemin üzerinde altın kadeh.

Kullanım:
    .venv\\Scripts\\python.exe scripts\\make_icon.py
Çıktı:
    assets/winehouse.ico   (16, 32, 48, 64, 128, 256 piksel)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "winehouse.ico"

# favicon.svg ile aynı renkler
BURGUNDY = (74, 28, 46)  # #4a1c2e zemin
GOLD = (200, 164, 92)  # #c8a45c kadeh


def rounded_background(size: int) -> Image.Image:
    """Köşeleri yuvarlatılmış bordo zemin (favicon'daki rx=6/32 oranıyla)."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    radius = max(int(size * 6 / 32), 2)
    ImageDraw.Draw(image).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=BURGUNDY + (255,)
    )
    return image


def draw_goblet(image: Image.Image, size: int) -> None:
    """Altın kadehi çizer: çanak + sap + taban (favicon.svg geometrisi)."""
    draw = ImageDraw.Draw(image)
    unit = size / 32.0  # favicon viewBox 32x32

    def u(value: float) -> float:
        return value * unit

    # --- Çanak: üstte düz kenar, altta yarım elips ---
    # favicon: M10 6 h12 l-1.2 8.2 a5 5 ... 16 18.5 ... l10 6z
    top_y = u(6.0)
    rim_left, rim_right = u(10.0), u(22.0)
    waist_left, waist_right = u(11.2), u(20.8)
    waist_y = u(14.2)
    bowl_bottom = u(18.5)

    # Gövde (yamuk) + alt yarım elips birleşimi
    draw.polygon(
        [
            (rim_left, top_y),
            (rim_right, top_y),
            (waist_right, waist_y),
            (waist_left, waist_y),
        ],
        fill=GOLD + (255,),
    )
    draw.ellipse(
        [waist_left, waist_y - (bowl_bottom - waist_y), waist_right, bowl_bottom],
        fill=GOLD + (255,),
    )

    # --- Sap ---
    stem_w = max(int(u(2.0)), 1)
    draw.line([(u(16), bowl_bottom), (u(16), u(24))], fill=GOLD + (255,), width=stem_w)

    # --- Taban ---
    draw.line([(u(12), u(26)), (u(20), u(26))], fill=GOLD + (255,), width=stem_w)


def build() -> Path:
    sizes = [256, 128, 64, 48, 32, 16]
    frames = []
    for size in sizes:
        # Kenar yumuşatma için büyük çizip küçült
        scale = 4 if size >= 32 else 8
        canvas = rounded_background(size * scale)
        draw_goblet(canvas, size * scale)
        frames.append(canvas.resize((size, size), Image.LANCZOS))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(OUTPUT, format="ICO", sizes=[(s, s) for s in sizes])
    return OUTPUT


if __name__ == "__main__":
    path = build()
    print(f"Ikon olusturuldu: {path}  ({path.stat().st_size} bayt)")
