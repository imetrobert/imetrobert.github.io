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
C0 = (37, 99, 235)                 # #2563eb
C1 = (26, 127, 181)                # #1a7fb5
C2 = (6, 182, 212)                 # #06b6d4

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


def build_og_image(out_path, issue_label, headline="Practical AI",
                   subhead="for Canadian Business"):
    """Render the card. `issue_label` fills the badge, e.g. 'AUGUST 2026'."""
    img = _gradient().convert("RGBA")
    _decor(img)
    d = ImageDraw.Draw(img)

    # --- badge: the pill that used to be empty ---------------------------
    label = (issue_label or "").upper().strip()
    if label:
        f_badge = _font(21, bold=True)
        # Pillow has no letter-spacing, so space the glyphs manually — at this
        # size the tracking is what makes it read as a label, not a word.
        spaced = " ".join(label)
        tw = d.textlength(spaced, font=f_badge)
        pad_x, pad_y, x0, y0 = 22, 11, 80, 74
        d.rounded_rectangle([x0, y0, x0 + tw + pad_x * 2, y0 + 21 + pad_y * 2],
                            radius=24, fill=(255, 255, 255, 235))
        d.text((x0 + pad_x, y0 + pad_y - 2), spaced, font=f_badge, fill=C0)

    # --- masthead --------------------------------------------------------
    d.text((80, 143), headline, font=_font(78, bold=True), fill=(255, 255, 255))
    d.text((80, 238), subhead, font=_font(40, bold=True), fill=(255, 255, 255))
    d.line([80, 306, 480, 306], fill=(255, 255, 255, 150), width=2)

    f_body = _font(26)
    d.text((80, 334), "Monthly AI intelligence for Canadian", font=f_body,
           fill=(255, 255, 255, 225))
    d.text((80, 371), "leaders — from Montreal", font=f_body,
           fill=(255, 255, 255, 225))

    d.text((80, 440), "Robert Simon", font=_font(30, bold=True),
           fill=(255, 255, 255))
    d.text((80, 487), "AI Thought Leader   •   Montreal, QC", font=_font(24),
           fill=(255, 255, 255, 225))

    f_dom = _font(26)
    dom = "imetrobert.com"
    d.text((WIDTH - 80 - d.textlength(dom, font=f_dom), 570), dom, font=f_dom,
           fill=(255, 255, 255, 235))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.convert("RGB").save(out_path, "JPEG", quality=88, optimize=True)
    return out_path


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "og-preview.jpg"
    label = sys.argv[2] if len(sys.argv) > 2 else "AUGUST 2026"
    print(build_og_image(out, label))
