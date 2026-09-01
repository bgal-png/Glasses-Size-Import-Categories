r"""Generate desktop/app_icon.ico — a pair of glasses with a teal measure badge.

Deliberately the same drawing as the Glasses Validator Desktop and Glasses
Import Filler icons (bgal-png/Glasses-Validator-Desktop/make_icon.py,
bgal-png/Glasses-Import-Filler/desktop/make_icon.py) so the three apps read as
one family: identical slate-blue glasses, identical badge position and size.
Only the badge differs — green disc + white check for the validator, amber
disc + white pencil for the filler, teal disc + white measuring mark here
(validate / fill / size-import).

Drawn at high resolution and downsampled so the small sizes stay smooth.
Re-run only when the icon should change:
    "C:\gv\Scripts\python.exe" desktop\make_icon.py
"""
import os

from PIL import Image, ImageDraw

S = 1024                       # working canvas
FRAME = (43, 90, 158, 255)     # slate blue   — same as the validator
MEASURE = (0, 150, 145, 255)   # teal         — "size/measure" badge
LENS = (120, 170, 225, 70)     # faint glass tint
WHITE = (255, 255, 255, 255)

HERE = os.path.dirname(os.path.abspath(__file__))


def rounded(draw, box, r, **kw):
    draw.rounded_rectangle(box, radius=r, **kw)


def build(size=S):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = size / 1024.0                       # scale helper
    w = int(58 * u)                         # stroke width

    # ---- glasses (unchanged from the validator) ----
    top, h = int(340 * u), int(310 * u)
    lens_w = int(350 * u)
    inset = int(96 * u)                     # room for the temple stubs
    left = (inset, top, inset + lens_w, top + h)
    right = (size - inset - lens_w, top, size - inset, top + h)
    for box in (left, right):
        rounded(d, box, int(85 * u), fill=LENS, outline=FRAME, width=w)

    # bridge
    d.arc((left[2] - int(20 * u), top + int(30 * u),
           right[0] + int(20 * u), top + int(180 * u)),
          start=200, end=340, fill=FRAME, width=w)

    # temple stubs — short, near-horizontal, hugging the frame
    ty = top + int(70 * u)
    d.line((left[0], ty, int(10 * u), ty - int(34 * u)), fill=FRAME, width=w)
    d.line((right[2], ty, size - int(10 * u), ty - int(34 * u)), fill=FRAME, width=w)

    # ---- measuring-mark badge (same disc as the validator's check / filler's pencil) ----
    cx, cy, r = int(720 * u), int(730 * u), int(250 * u)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=MEASURE)

    # A horizontal rounded bar across the disc — the ruler edge — with three
    # short ticks descending from it, like graduation marks on a tape measure.
    bar_hw = 130 * u                        # bar half-width
    bar_y = cy - 60 * u
    bar_th = 26 * u
    rounded(
        d,
        (cx - bar_hw, bar_y - bar_th / 2, cx + bar_hw, bar_y + bar_th / 2),
        int(bar_th / 2),
        fill=WHITE,
    )

    tick_w = 26 * u                         # same stroke width family as the bar
    tick_len = 130 * u
    for tx in (cx - 100 * u, cx, cx + 100 * u):
        rounded(
            d,
            (tx - tick_w / 2, bar_y, tx + tick_w / 2, bar_y + tick_len),
            int(tick_w / 2),
            fill=WHITE,
        )

    return img


def main():
    base = build()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [base.resize((s, s), Image.LANCZOS) for s in sizes]
    ico = os.path.join(HERE, "app_icon.ico")
    png = os.path.join(HERE, "app_icon.png")
    frames[-1].save(ico, format="ICO", sizes=[(s, s) for s in sizes])
    base.resize((256, 256), Image.LANCZOS).save(png)
    print(f"wrote {ico} and {png}")


if __name__ == "__main__":
    main()
