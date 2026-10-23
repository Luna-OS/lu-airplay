"""Erzeugt das App-Icon (PNG + ICO). Benötigt Pillow:  python scripts/make-icons.py"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "launcher" / "luairplay" / "assets"
SIZE = 1024


def render() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    # Verlauf (oben hell-lila, unten tief-violett) in einem abgerundeten Quadrat
    grad = Image.new("RGBA", (SIZE, SIZE))
    top, bottom = (148, 121, 255), (88, 50, 214)
    gd = ImageDraw.Draw(grad)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        gd.line([(0, y), (SIZE, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([40, 40, SIZE - 40, SIZE - 40], radius=230, fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    w = 64
    # Bildschirm (unten offen)
    left, right, top_y, bottom_y = 230, 794, 250, 660
    pts = [(left + 70, bottom_y), (left, bottom_y), (left, top_y), (right, top_y), (right, bottom_y),
           (right - 70, bottom_y)]
    d.line(pts, fill="white", width=w, joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill="white")
    # Dreieck
    d.polygon([(512, 540), (712, 800), (312, 800)], fill="white")
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    img = render()
    img.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    img.resize((48, 48), Image.LANCZOS).save(OUT / "logo.png")
    img.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Icons geschrieben nach", OUT)


if __name__ == "__main__":
    main()
