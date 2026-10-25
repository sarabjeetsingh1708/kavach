"""Draw the Kavach shield app icons (one-off; needs Pillow). Run from kavach/: python -m eval.make_icons"""
from PIL import Image, ImageDraw

from app import config

OUT = config.ROOT / "web" / "icons"
GREEN, CREAM, WHITE = (47, 93, 80), (251, 247, 240), (255, 255, 255)
# shield path from the page logo (40x40 viewBox), as a polygon approximation
SHIELD = [(20, 3), (34, 8.5), (34, 18.7), (32.5, 25.5), (28.5, 31), (24, 35), (20, 37), (16, 35), (11.5, 31),
          (7.5, 25.5), (6, 18.7), (6, 8.5)]
CHECK = [(13.5, 20), (18, 24.5), (26.5, 15.5)]


def draw(size: int, maskable: bool) -> Image.Image:
    s = 4  # supersample for smooth edges
    img = Image.new("RGB", (size * s, size * s), GREEN if maskable else CREAM)
    d = ImageDraw.Draw(img)
    # maskable icons must keep content inside the central 80% safe zone
    scale = size * s / 40 * (0.62 if maskable else 0.9)
    off = (size * s - 40 * scale) / 2
    pt = lambda x, y: (off + x * scale, off + y * scale)
    d.polygon([pt(*p) for p in SHIELD], fill=WHITE if maskable else GREEN)
    d.line([pt(*p) for p in CHECK], fill=GREEN if maskable else WHITE, width=int(3.2 * scale), joint="curve")
    for x, y in (CHECK[0], CHECK[-1]):  # round line caps
        r = 1.6 * scale
        cx, cy = pt(x, y)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN if maskable else WHITE)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, size, maskable in [("icon-192.png", 192, False), ("icon-512.png", 512, False),
                                 ("maskable-512.png", 512, True), ("apple-touch-icon.png", 180, True)]:
        draw(size, maskable).save(OUT / name)
        print("wrote", name)
