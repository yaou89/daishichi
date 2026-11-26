"""ココナラ出品用サムネイル（1220×1240）を stills/ から作る:  python3 make_thumbnail.py"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import make_movie as mm

HERE = os.path.dirname(os.path.abspath(__file__))
TW, TH = 1220, 1240


def rgb(c):
    return tuple(int(v * 255) for v in c)


def paste_shadowed(base, img, xy, radius=0):
    x, y = xy
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([x + 8, y + 14, x + img.width + 8, y + img.height + 14], fill=(90, 70, 60, 70))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))
    frame = Image.new("RGBA", (img.width + 16, img.height + 16), (255, 253, 249, 255))
    frame.paste(img, (8, 8))
    base.alpha_composite(frame, (x - 8, y - 8))


def text(d, xy, s, kind, size, color, anchor="mm", tracking=0.0):
    f = mm.font(kind, size)
    if not tracking:
        d.text(xy, s, font=f, fill=color, anchor=anchor)
        return
    widths = [f.getlength(c) for c in s]
    total = sum(widths) + tracking * size * (len(s) - 1)
    x = xy[0] - total / 2
    for c, w in zip(s, widths):
        d.text((x, xy[1]), c, font=f, fill=color, anchor="lm")
        x += w + tracking * size


def main():
    st = os.path.join(HERE, "stills")
    bg = mm.make_background()
    base = Image.fromarray((bg * 255).astype(np.uint8)).resize((TW, TH), Image.LANCZOS).convert("RGBA")
    bq = Image.fromarray((mm.make_bouquet(11) * 255).astype(np.uint8), "RGBA").resize((520, 520))
    base.alpha_composite(bq, (-60, -70))
    bq2 = Image.fromarray((mm.make_bouquet(23)[::-1, ::-1] * 255).astype(np.uint8), "RGBA").resize((520, 520))
    base.alpha_composite(bq2, (TW - 460, TH - 450))
    d = ImageDraw.Draw(base)

    text(d, (TW / 2, 95), "Wedding Opening Movie", "script", 84, rgb(mm.GOLD))
    text(d, (TW / 2, 200), "結婚式オープニングムービー", "mincho", 70, rgb(mm.TEXT), tracking=0.06)
    text(d, (TW / 2, 282), "くすみカラー × ナチュラル ／ フルHD", "mincho", 34, rgb(mm.SUB), tracking=0.1)

    big = Image.open(os.path.join(st, "08_final.jpg")).resize((900, 506), Image.LANCZOS)
    paste_shadowed(base, big, ((TW - 900) // 2, 340))
    smalls = ["03_groom.jpg", "05_story.jpg", "07_countdown.jpg"]
    sw, shh = 340, 191
    gap = (TW - 3 * sw) // 4
    for i, s in enumerate(smalls):
        im = Image.open(os.path.join(st, s)).resize((sw, shh), Image.LANCZOS)
        paste_shadowed(base, im, (gap + i * (sw + gap), 890))

    # 特徴バッジ
    d = ImageDraw.Draw(base)
    badges = ["写真とテキストを送るだけ", "修正2回まで無料", "BGM付き・著作権OK"]
    bw = 340
    for i, b in enumerate(badges):
        cx = gap + i * (sw + gap) + sw / 2
        cy = 1150
        d.rounded_rectangle([cx - bw / 2, cy - 34, cx + bw / 2, cy + 34], radius=34, fill=rgb(mm.hexc("#FFFDF9")), outline=rgb(mm.GOLD), width=2)
        text(d, (cx, cy), b, "mincho", 26, rgb(mm.TEXT))

    out = os.path.join(HERE, "coconala_thumbnail.jpg")
    base.convert("RGB").save(out, quality=93)
    print("wrote", out)


if __name__ == "__main__":
    main()
