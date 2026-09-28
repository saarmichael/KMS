import os, io, json, math, shutil
import cairo
from PIL import Image
from logo import draw_logo, W as LW0, H as LH0
from icons import *

OUT = "sift-web-assets"
shutil.rmtree(OUT, ignore_errors=True)
for d in ("favicon", "logo", "lockup", "social"): os.makedirs(f"{OUT}/{d}")

def png(path, w, h, draw, scale=1.0, bg=None):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(round(w*scale)), int(round(h*scale))); c = cairo.Context(s)
    if bg: c.set_source_rgba(*bg); c.paint()
    c.scale(scale, scale); draw(c); s.write_to_png(path)
def svg(path, w, h, draw):
    s = cairo.SVGSurface(path, w, h)
    try: s.set_document_unit(cairo.SVGUnit.PX)
    except Exception: pass
    c = cairo.Context(s); draw(c); s.finish()
def alpha_bbox(draw, w, h, scale=1.0, pad=0):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w*scale), int(h*scale)); c = cairo.Context(s); c.scale(scale, scale); draw(c)
    buf = io.BytesIO(); s.write_to_png(buf); im = Image.open(buf)
    x0, y0, x1, y1 = im.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()
    return (x0/scale - pad, y0/scale - pad, x1/scale + pad, y1/scale + pad)

# ---------------- full logo ----------------
for theme in ("dark", "light"):
    f = lambda c, t=theme: draw_logo(c, t, False)
    png(f"{OUT}/logo/sift-logo-{theme}-bg.png", LW0, LH0, f, scale=3.0)
    png(f"{OUT}/logo/sift-logo-{theme}-bg-1200.png", LW0, LH0, f, scale=1200/LH0)
    svg(f"{OUT}/logo/sift-logo-{theme}-bg.svg", LW0, LH0, f)
    # transparent, tightly cropped; "on-dark" uses light ink, "on-light" uses dark ink
    name = "on-dark" if theme == "dark" else "on-light"
    ft = lambda c, t=theme: draw_logo(c, t, True)
    bx0, by0, bx1, by1 = alpha_bbox(ft, LW0, LH0, 1.0, pad=16)
    bw, bh = bx1 - bx0, by1 - by0
    fc = lambda c, ft=ft: (c.translate(-bx0, -by0), ft(c))
    png(f"{OUT}/logo/sift-logo-{name}.png", bw, bh, fc, scale=3.0)
    png(f"{OUT}/logo/sift-logo-{name}-800.png", bw, bh, fc, scale=800/bh)
    svg(f"{OUT}/logo/sift-logo-{name}.svg", bw, bh, fc)

# ---------------- lockups ----------------
(x0, y0, x1, y1), _ = word_metrics()
def lockup_def(kind):
    if kind == "full":
        MX, MW, WH, WB = -21, 62, 46, 71      # mark shift, mark width, word ascender, baseline
        mk = lambda c, t: mark(c, t, glow=False)
    else:
        MX, MW, WH, WB = -20, 62, 52, 76
        mk = lambda c, t: simple_mark(c, t)
    ww = (x1 - x0)/y1*WH; gap = 10
    width = MW + gap + ww + 2
    def draw(c, t):
        c.save(); c.translate(MX, 0); mk(c, t); c.restore()
        wordmark(c, MW + gap, WB, WH, t)
    return width, draw
for kind, suffix in (("full", ""), ("compact", "-compact")):
    lw, ld = lockup_def(kind)
    for theme in ("dark", "light"):
        name = "on-dark" if theme == "dark" else "on-light"
        d = lambda c, t=theme, ld=ld: ld(c, t)
        bx0, by0, bx1, by1 = alpha_bbox(d, lw, 100, 4.0, pad=2)
        bw, bh = bx1 - bx0, by1 - by0
        dc = lambda c, d=d, bx0=bx0, by0=by0: (c.translate(-bx0, -by0), d(c))
        svg(f"{OUT}/lockup/sift-lockup{suffix}-{name}.svg", bw, bh, dc)
        for hpx in (48, 96, 192):
            png(f"{OUT}/lockup/sift-lockup{suffix}-{name}-h{hpx}.png", bw, bh, dc, scale=hpx/bh)
# standalone wordmark
for theme in ("dark", "light"):
    name = "on-dark" if theme == "dark" else "on-light"
    ww = (x1 - x0)/y1*100
    d = lambda c, t=theme: wordmark(c, 2, 102, 100, t)
    bx0, by0, bx1, by1 = alpha_bbox(d, ww + 4, 110, 4.0, pad=2)
    dc = lambda c, d=d, bx0=bx0, by0=by0: (c.translate(-bx0, -by0), d(c))
    svg(f"{OUT}/lockup/sift-wordmark-{name}.svg", bx1-bx0, by1-by0, dc)
    png(f"{OUT}/lockup/sift-wordmark-{name}-h96.png", bx1-bx0, by1-by0, dc, scale=96/(by1-by0))

# ---------------- favicons & app icons ----------------
def tile_simple(c): tile(c); simple_mark(c, "dark")
def tile_detail(c): tile(c); mark(c, "dark")
def square_bg(c):
    g = cairo.RadialGradient(50, 42, 4, 50, 50, 80); g.add_color_stop_rgba(0, *TILE_IN); g.add_color_stop_rgba(1, *TILE_OUT)
    c.set_source(g); c.paint()
ico_imgs = []
for n in (16, 32, 48):
    p = f"{OUT}/favicon/favicon-{n}x{n}.png"
    png(p, 100, 100, tile_simple, scale=n/100); ico_imgs.append(Image.open(p))
os.remove(f"{OUT}/favicon/favicon-48x48.png")
ico_imgs[2].save(f"{OUT}/favicon/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=ico_imgs[:2])
svg(f"{OUT}/favicon/favicon.svg", 100, 100, tile_simple)
png(f"{OUT}/favicon/apple-touch-icon.png", 100, 100, lambda c: (square_bg(c), c.translate(50, 50), c.scale(1.08, 1.08), c.translate(-50, -50), mark(c, "dark")), scale=1.8)
for n in (192, 512):
    png(f"{OUT}/favicon/android-chrome-{n}x{n}.png", 100, 100, tile_detail, scale=n/100)
png(f"{OUT}/favicon/maskable-icon-512x512.png", 100, 100, lambda c: (square_bg(c), c.translate(50, 50), c.scale(0.76, 0.76), c.translate(-50, -50), mark(c, "dark")), scale=5.12)
json.dump({
    "name": "Sift", "short_name": "Sift",
    "icons": [
        {"src": "/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "/maskable-icon-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
    ],
    "theme_color": "#0E151C", "background_color": "#0E151C", "display": "standalone", "start_url": "/"
}, open(f"{OUT}/favicon/site.webmanifest", "w"), indent=2)

# ---------------- social card ----------------
from fontTools.ttLib import TTFont
def text(c, fontfile, s, x, yb, size, col):
    f = TTFont(fontfile); gs = f.getGlyphSet(); cm = f.getBestCmap(); hm = f['hmtx']; upm = f['head'].unitsPerEm
    k = size/upm; c.new_path(); adv = 0
    for ch in s:
        n = cm[ord(ch)]; gs[n].draw(TransformPen(CairoPen(gs, c), (k, 0, 0, -k, x + adv*k, yb))); adv += hm[n][0]
    c.set_source_rgba(*col); c.fill(); return adv*k
FB = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FR = "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf"
def og(c):
    g = cairo.RadialGradient(820, 330, 40, 820, 330, 900); g.add_color_stop_rgba(0, *hexc('#1B2733')); g.add_color_stop_rgba(1, *hexc('#0A1016'))
    c.set_source(g); c.paint()
    c.save(); sc = 600/LH0; c.translate(1200 - 70 - LW0*sc, 15); c.scale(sc, sc); draw_logo(c, "dark", True); c.restore()
    INK = hexc('#ECE5D6'); SUB = hexc('#ECE5D6', 0.62)
    text(c, FB, "Upload anything.", 80, 268, 62, INK)
    text(c, FB, "Find it by meaning.", 80, 348, 62, ORANGE)
    text(c, FR, "Text and images, searchable by what they contain.", 82, 420, 23, SUB)
png(f"{OUT}/social/og-image.png", 1200, 630, og)

# ---------------- head snippet + readme ----------------
open(f"{OUT}/head.html", "w").write("""<!-- Sift: favicons & social. Copy the files in favicon/ to your site root and social/og-image.png to /og-image.png -->
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32x32.png" type="image/png" sizes="32x32">
<link rel="icon" href="/favicon-16x16.png" type="image/png" sizes="16x16">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#0E151C">

<meta property="og:title" content="Sift">
<meta property="og:description" content="Upload text and images. Find them by what they contain.">
<meta property="og:image" content="https://YOUR-DOMAIN/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://YOUR-DOMAIN/og-image.png">
""")
print("done")
