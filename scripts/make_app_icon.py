"""Generate the Mission Control app icon (tennis ball, Hermes palette).
Outputs src/dashboard/static/icon.ico (multi-size) + icon.png (favicon)."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "static"

CLAY = (199, 90, 42, 255)      # --accent-2 terra battuta
INK = (26, 26, 18, 255)        # --ink
SEAM = (247, 241, 224, 255)    # --surface


def ball(size: int) -> Image.Image:
    ss = 4  # supersample for smooth edges
    s = size * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = s * 0.03
    d.ellipse([m, m, s - m, s - m], fill=CLAY, outline=INK, width=max(ss, s // 26))

    # tennis seams: two arcs from circles centered outside left/right
    w = max(ss, s // 14)
    r = s * 0.78
    d.arc([-r * 1.05, s / 2 - r, r * 0.55, s / 2 + r], -62, 62, fill=SEAM, width=w)
    d.arc([s - r * 0.55, s / 2 - r, s + r * 1.05, s / 2 + r], 118, 242, fill=SEAM, width=w)
    return img.resize((size, size), Image.LANCZOS)


def main():
    big = ball(256)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    big.save(OUT / "icon.ico", format="ICO", sizes=sizes)
    ball(64).save(OUT / "icon.png", format="PNG")
    print("icon.ico + icon.png ->", OUT)


if __name__ == "__main__":
    main()
