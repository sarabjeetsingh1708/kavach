"""Kavach logo: drawn with Pillow (4x supersampled), so the app icons can be regenerated without design tools.
Run from kavach/: python -m eval.logo concepts OUT.png   -> the three candidate marks side by side
                  python -m eval.logo icons [A|B|C]       -> web/icons/*.png for the chosen mark"""
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app import config

GREEN_TOP, GREEN_BOTTOM = (62, 142, 115), (24, 66, 55)
SAFFRON, CREAM, WHITE = (232, 131, 58), (251, 247, 240), (255, 255, 255)
SS = 4  # supersampling factor


def bezier(p0, p1, p2, p3, n=40):
    return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0],
             (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1])
            for t in (i / n for i in range(n + 1))]


def shield_points(box):
    """Shield outline in a 100x100 design space, mapped into box=(x, y, size)."""
    x0, y0, s = box
    pts = (bezier((50, 4), (63, 12), (77, 15), (89, 16)) + [(89, 46)]
           + bezier((89, 46), (89, 71), (73, 88), (50, 97)) + bezier((50, 97), (27, 88), (11, 71), (11, 46))
           + [(11, 16)] + bezier((11, 16), (23, 15), (37, 12), (50, 4)))
    return [(x0 + px * s / 100, y0 + py * s / 100) for px, py in pts]


def gradient(size, top, bottom):
    g = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        g.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return g.resize(size)


def devanagari_bold(px):
    for idx in range(4):  # Nirmala.ttc holds several faces; pick the bold one
        try:
            f = ImageFont.truetype("C:/Windows/Fonts/Nirmala.ttc", px, index=idx)
            if "Bold" in " ".join(f.getname()):
                return f
        except OSError:
            break
    return ImageFont.truetype("C:/Windows/Fonts/Nirmala.ttc", px)


def mark(kind: str, size: int) -> Image.Image:
    """The shield mark (transparent background), size x size."""
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    box = (S * 0.06, S * 0.03, S * 0.88)
    shield = shield_points(box)
    # soft drop shadow
    shadow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(shadow).polygon([(x, y + S * 0.02) for x, y in shield], fill=90)
    img.paste((20, 40, 34, 255), (0, 0), shadow.filter(ImageFilter.GaussianBlur(S * 0.02)))
    # gradient body
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(shield, fill=255)
    img.paste(gradient((S, S), GREEN_TOP, GREEN_BOTTOM), (0, 0), mask)
    d = ImageDraw.Draw(img)
    # inner rim: a thin light line just inside the edge
    inner = shield_points((box[0] + box[2] * 0.06, box[1] + box[2] * 0.06, box[2] * 0.88))
    d.line(inner + [inner[0]], fill=(255, 255, 255, 60), width=int(S * 0.012), joint="curve")
    cx, cy, u = S / 2, box[1] + box[2] * 0.50, box[2] / 100

    if kind == "A":  # bold क with a saffron arc beneath it
        r = 27 * u
        d.arc([cx - r, cy - r, cx + r, cy + r], 35, 145, fill=SAFFRON, width=int(5 * u))
        font = devanagari_bold(int(46 * u))
        d.text((cx, cy - 3 * u), "क", font=font, fill=WHITE, anchor="mm")
    elif kind == "B":  # voice waveform: rounded bars, the centre one saffron
        heights, w, gap = [14, 26, 40, 26, 14], 7 * u, 4.5 * u
        x = cx - (len(heights) * w + (len(heights) - 1) * gap) / 2
        for i, h in enumerate(heights):
            d.rounded_rectangle([x, cy - h * u / 2, x + w, cy + h * u / 2], radius=w / 2,
                                fill=SAFFRON if i == 2 else WHITE)
            x += w + gap
    else:  # "C": handset + two sound waves, saffron check badge
        hx, hy = cx - 9 * u, cy + 2 * u
        handset = Image.new("L", (S, S), 0)
        hd = ImageDraw.Draw(handset)
        hd.rounded_rectangle([hx - 6 * u, hy - 20 * u, hx + 6 * u, hy + 20 * u], radius=6 * u, fill=255)
        handset = handset.rotate(35, center=(hx, hy), resample=Image.BICUBIC)
        img.paste(WHITE + (255,), (0, 0), handset)
        for r in (14, 22):
            d.arc([hx - r * u + 6 * u, hy - r * u - 4 * u, hx + r * u + 6 * u, hy + r * u - 4 * u], -70, -10,
                  fill=WHITE, width=int(4 * u))
        bx, by, br = cx + 17 * u, cy + 15 * u, 11 * u
        d.ellipse([bx - br, by - br, bx + br, by + br], fill=SAFFRON, outline=WHITE, width=int(2.5 * u))
        d.line([(bx - 5 * u, by), (bx - 1.5 * u, by + 4 * u), (bx + 5.5 * u, by - 4 * u)], fill=WHITE,
               width=int(3 * u), joint="curve")
    return img.resize((size, size), Image.LANCZOS)


def app_icon(kind: str, size: int, maskable: bool) -> Image.Image:
    """Square app icon. Maskable icons must keep the mark inside the central ~80% safe zone."""
    bg = Image.new("RGBA", (size, size), CREAM + (255,))  # cream, so the green shield stands out when Android crops it
    inner = int(size * (0.66 if maskable else 0.92))
    m = mark(kind, inner)
    bg.alpha_composite(m, ((size - inner) // 2, (size - inner) // 2))
    return bg.convert("RGB")


def concepts(out):
    labels = {"A": "A · monogram", "B": "B · voice waveform", "C": "C · call + check"}
    W, H = 1500, 620
    sheet = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 30)
    for i, k in enumerate("ABC"):
        x = 40 + i * 490
        sheet.paste(app_icon(k, 300, False), (x + 70, 40))
        sheet.paste(app_icon(k, 120, True), (x + 70, 380))             # how Android crops it on the home screen
        sheet.paste(app_icon(k, 48, False).resize((48, 48)), (x + 230, 416))  # small, like a browser tab
        d.text((x + 220, 560), labels[k], font=font, fill=(31, 42, 36), anchor="mm")
    sheet.save(out)
    print("wrote", out)


def icons(kind):
    out = config.ROOT / "web" / "icons"
    for name, size, maskable in [("icon-192.png", 192, False), ("icon-512.png", 512, False),
                                 ("maskable-512.png", 512, True), ("apple-touch-icon.png", 180, True)]:
        app_icon(kind, size, maskable).save(out / name)
        print("wrote", name)
    mark(kind, 256).save(out / "mark-256.png")  # transparent, for the page header
    print("wrote mark-256.png")


if __name__ == "__main__":
    if sys.argv[1] == "concepts":
        concepts(sys.argv[2])
    else:
        icons(sys.argv[2] if len(sys.argv) > 2 else "A")
