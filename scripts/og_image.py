"""
og_image.py
Builds the 1200x630 Open Graph card shared on LinkedIn/X/Facebook.

Why this exists: every post used to point at one static blog/og-blog.jpg, so a
year of shares looked identical in the feed, and the badge in the top-left was
an empty white pill — a slot designed to hold the issue label that nothing ever
filled. This draws the same card per issue with that badge populated.

Pure Pillow, no network, no headless browser. Liberation Sans is metric
compatible with Arial and ships in the GitHub Actions image; DejaVu is the
fallback. If neither resolves, callers should fall back to the static card
rather than shipping a broken og:image (see renderer.build_og_for_post).
"""

import os
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630          # LinkedIn/OG large-card spec (1.91:1)

# Site palette, same stops as the header gradient and the brand mark.
C0 = (17, 48, 76)                  # #11304c navy
C1 = (31, 59, 77)                  # #1f3b4d
C2 = (138, 109, 11)                # #8a6d0b dark gold
BG = (239, 246, 255)               # #eff6ff, the Business share-card ground
NAVY = C0
GOLD = (201, 162, 39)              # #c9a227
GOLD_TEXT = C2
GREY = (75, 85, 99)

_FONT_DIRS = (
    "/usr/share/fonts/truetype/liberation/LiberationSans-{}.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans{}.ttf",
)


def _font(size, bold=False):
    for i, pattern in enumerate(_FONT_DIRS):
        path = pattern.format(("Bold" if bold else "Regular") if i == 0
                              else ("-Bold" if bold else ""))
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    raise RuntimeError("no usable TrueType font found")


def _gradient():
    """Diagonal blue -> cyan. Built small and scaled up: interpolating 64x34
    pixels and resampling is both faster and smoother than looping over 756k."""
    sw, sh = 64, 34
    small = Image.new("RGB", (sw, sh))
    px = small.load()
    for y in range(sh):
        for x in range(sw):
            t = (x / (sw - 1) + y / (sh - 1)) / 2
            if t < 0.55:
                k = t / 0.55
                a, b = C0, C1
            else:
                k = (t - 0.55) / 0.45
                a, b = C1, C2
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
    return small.resize((WIDTH, HEIGHT), Image.LANCZOS)


def _decor(img):
    """Faint outlined circles, echoing the original card's quiet texture."""
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for cx, cy, r in ((1060, 60, 140), (1100, 560, 90), (150, 585, 85)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  outline=(255, 255, 255, 28), width=3)
    img.alpha_composite(layer)


def build_og_image(out_path, issue_label, headline="AI with Robert",
                   subhead="for Business"):
    """Render the card in the Business site's share-card style: pale blue ground, the Business logo
    on the left, navy and gold text on the right. `issue_label` fills the badge, e.g. 'AUGUST 2026'."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo = Image.open(os.path.join(here, "blog", "logo-512.png")).convert("RGBA")
    logo = logo.resize((380, 380), Image.LANCZOS)
    img.alpha_composite(logo, (95, 125))
    d = ImageDraw.Draw(img)
    x = 540

    label = (issue_label or "").upper().strip()
    if label:
        f_badge = _font(21, bold=True)
        spaced = " ".join(label)
        tw = d.textlength(spaced, font=f_badge)
        pad_x, pad_y, y0 = 22, 11, 118
        d.rounded_rectangle([x, y0, x + tw + pad_x * 2, y0 + 21 + pad_y * 2], radius=24, fill=NAVY)
        d.text((x + pad_x, y0 + pad_y - 2), spaced, font=f_badge, fill=GOLD)

    d.text((x, 195), headline, font=_font(78, bold=True), fill=NAVY)
    d.text((x, 295), subhead, font=_font(48, bold=True), fill=GOLD_TEXT)
    d.text((x, 365), "The Briefing", font=_font(34, bold=True), fill=NAVY)
    d.text((x, 420), "What your AI plan can do now,", font=_font(26), fill=GREY)
    d.text((x, 455), "and what to try next", font=_font(26), fill=GREY)
    d.text((x, 520), "by Robert Simon   \u2022   imetrobert.com/blog", font=_font(24), fill=GREY)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.convert("RGB").save(out_path, "JPEG", quality=90, optimize=True)
    return out_path


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "og-preview.jpg"
    label = sys.argv[2] if len(sys.argv) > 2 else "AUGUST 2026"
    print(build_og_image(out, label))
