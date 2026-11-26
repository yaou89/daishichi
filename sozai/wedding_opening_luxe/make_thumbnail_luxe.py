"""ココナラ出品用サムネイル（1220×1240）を stills/ から作る:  python3 make_thumbnail_luxe.py"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import make_movie_luxe as mm

HERE = os.path.dirname(os.path.abspath(__file__))
TW, TH = 1220, 1240


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGBA" if a.shape[-1] == 4 else "RGB")


def paste_c(base, rgba, cx, cy):
    im = to_img(rgba)
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def framed(base, img, x, y, frame_mask):
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([x + 6, y + 16, x + img.width + 6, y + img.height + 16], fill=(0, 0, 0, 150))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    base.paste(img, (x, y))
    if frame_mask is not None:
        paste_c(base, mm.gold(frame_mask, glow=False, bevel=0.2), x + img.width / 2, y + img.height / 2)


def main():
    mm.FOIL = mm.make_foil()
    st = os.path.join(HERE, "stills")
    # 背景：ネイビーのベルベット＋光のボケ
    bg = mm.make_background()
    bg += mm.make_rays(11) * 1.2
    bg += mm.disk_field(mm.W, mm.H, 40, 30, 90, [mm.hexc("#E8B86A"), mm.hexc("#F3D49A")], 0.03, 0.08, 5, 6)
    base = to_img(np.clip(bg, 0, 1)).resize((TW, TH), Image.LANCZOS).convert("RGBA")

    paste_c(base, mm.gold(mm.mask_text("Luxury Wedding Opening Movie", "script", 74), glow_k=0.4), TW / 2, 92)
    paste_c(base, mm.colorize(mm.mask_text("結婚式オープニングムービー", "mincho", 70, tracking=0.08), mm.IVORY), TW / 2, 198)
    paste_c(base, mm.colorize(mm.mask_text("ネイビー × ゴールド箔 ／ フルHD ／ オリジナルBGM", "mincho", 30, tracking=0.12), mm.CHAMP), TW / 2, 268)
    paste_c(base, mm.gold(mm.ornament_line(420), glow=True, glow_k=0.3, bevel=0.3), TW / 2, 312)

    big = Image.open(os.path.join(st, "09_final.jpg")).resize((960, 540), Image.LANCZOS)
    framed(base, big, (TW - 960) // 2, 350, mm.deco_frame(960, 540, off=10, corner=40))
    sw, sh_ = 352, 198
    gap = (TW - 3 * sw) // 4
    for i, s in enumerate(["01_crest.jpg", "03_groom.jpg", "05_story.jpg"]):
        im = Image.open(os.path.join(st, s)).resize((sw, sh_), Image.LANCZOS)
        framed(base, im, gap + i * (sw + gap), 948, None)
        d = ImageDraw.Draw(base)
        x, y = gap + i * (sw + gap), 948
        d.rectangle([x - 1, y - 1, x + sw, y + sh_], outline=tuple(int(v * 255) for v in mm.GOLD), width=1)

    d = ImageDraw.Draw(base)
    for i, b in enumerate(["金箔の質感と光の演出", "映画のようなストーリー", "オリジナルBGM付き"]):
        cx, cy = gap + i * (sw + gap) + sw / 2, 1190
        d.rounded_rectangle([cx - sw / 2, cy - 28, cx + sw / 2, cy + 28], radius=6, outline=tuple(int(v * 255) for v in mm.GOLD), width=2,
                            fill=(10, 16, 30, 255))
        paste_c(base, mm.colorize(mm.mask_text(b, "mincho_regular", 26, tracking=0.08), mm.GOLD_L), cx, cy)
    out = os.path.join(HERE, "coconala_thumbnail_luxe.jpg")
    base.convert("RGB").save(out, quality=94)
    print("wrote", out)


if __name__ == "__main__":
    main()
