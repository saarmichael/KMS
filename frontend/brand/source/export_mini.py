import os, io, json, math, shutil, cairo
from PIL import Image
from mini import *
from fontTools.ttLib import TTFont
from shapely.geometry import box as sbox

OUT = "sift-web-assets"
shutil.rmtree(OUT, ignore_errors=True)
for d in ("favicon", "logo", "mark", "social", "alternates"): os.makedirs(f"{OUT}/{d}")
V = 'b'
NIGHT = BGS['dark']; PAPER = BGS['light']

def surf_png(path, w, h, draw, scale):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, int(round(w*scale))), max(1, int(round(h*scale)))); c = cairo.Context(s)
    c.scale(scale, scale); draw(c); s.write_to_png(path)
def surf_svg(path, w, h, draw):
    s = cairo.SVGSurface(path, w, h)
    try: s.set_document_unit(cairo.SVGUnit.PX)
    except Exception: pass
    c = cairo.Context(s); draw(c); s.finish()
def bbox_of(draw, w, h, scale=2.0):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w*scale), int(h*scale)); c = cairo.Context(s); c.scale(scale, scale); draw(c)
    buf = io.BytesIO(); s.write_to_png(buf); a = Image.open(buf).getchannel('A').point(lambda v: 255 if v > 4 else 0)
    x0, y0, x1, y1 = a.getbbox(); return x0/scale, y0/scale, x1/scale, y1/scale
def export_cropped(stem, draw, w, h, pad, heights, bg=None):
    bx0, by0, bx1, by1 = bbox_of(draw, w, h)
    bx0 -= pad; by0 -= pad; bx1 += pad; by1 += pad; bw, bh = bx1-bx0, by1-by0
    def d(c):
        if bg: c.set_source_rgba(*bg); c.rectangle(0, 0, bw, bh); c.fill()
        c.translate(-bx0, -by0); draw(c)
    surf_svg(stem + ".svg", bw, bh, d)
    for hp in heights: surf_png(f"{stem}-h{hp}.png", bw, bh, d, hp/bh)

# ---------- wordmark (k = 0.1 px per font unit -> ~90 px tall canvas) ----------
K = 0.1; WW, WH = 200, 110
for theme, name in (("dark", "on-dark"), ("light", "on-light")):
    dr = lambda c, t=theme: wordmark(c, t, V, 5, 100, K)
    export_cropped(f"{OUT}/logo/sift-logo-{name}", dr, WW, WH, 1.0, (48, 96, 192, 512, 1024))
    bgc = NIGHT if theme == "dark" else PAPER
    export_cropped(f"{OUT}/logo/sift-logo-{theme}-bg", dr, WW, WH, 22, (512, 1024), bg=bgc)
for v, lbl in (('a', 'A-all-ink'), ('c', 'C-stem-filling')):
    for theme, name in (("dark", "on-dark"), ("light", "on-light")):
        dr = lambda c, t=theme, v=v: wordmark(c, t, v, 5, 100, K)
        export_cropped(f"{OUT}/alternates/sift-logo-{lbl}-{name}", dr, WW, WH, 1.0, (192,))

# ---------- the i mark alone ----------
def i_mark(c, theme, k, ox, oy, variant=V):
    c.save(); c.translate(ox, oy); c.scale(k, -k)
    for g, role in i_parts(variant): fill_geom(c, g, ORANGE if role == 'acc' else INKS[theme])
    c.restore()
for theme, name in (("dark", "on-dark"), ("light", "on-light")):
    dr = lambda c, t=theme: i_mark(c, t, 0.1, 0, 95)
    export_cropped(f"{OUT}/mark/sift-mark-{name}", dr, 40, 100, 0.8, (64, 128, 512))

# ---------- icons ----------
def rounded(c, x, y, s, r):
    c.new_path(); c.arc(x+s-r, y+r, r, -math.pi/2, 0); c.arc(x+s-r, y+s-r, r, 0, math.pi/2)
    c.arc(x+r, y+s-r, r, math.pi/2, math.pi); c.arc(x+r, y+r, r, math.pi, 1.5*math.pi); c.close_path()
def full_i_icon(c, size=100, shape="round", fill=0.78):
    if shape == "round": rounded(c, 0, 0, size, size*0.22); c.set_source_rgba(*NIGHT); c.fill()
    else: c.set_source_rgba(*NIGHT); c.paint()
    k = size*fill/886; i_mark(c, "dark", k, size/2 - 160.5*k, size*(1-fill)/2 + 886*k)
def db_icon(c, size=100, shape="round"):
    """small sizes: just the database dot crumbling into two bits"""
    if shape == "round": rounded(c, 0, 0, size, size*0.22); c.set_source_rgba(*NIGHT); c.fill()
    # region of the i from y=590 (below the lowest bits kept) to 886; x 45..276
    parts = [(g, r) for g, r in i_parts(V) if g.bounds[1] > 590]
    y0, y1, x0, x1 = 590, 886, 40, 281
    k = size*0.74/max(y1-y0, x1-x0)
    cxm = (x0+x1)/2; cym = (y0+y1)/2
    c.save(); c.translate(size/2 - cxm*k, size/2 + cym*k); c.scale(k, -k)
    for g, role in parts: fill_geom(c, g, ORANGE if role == 'acc' else INKS["dark"])
    c.restore()
imgs = []
for n in (16, 32, 48):
    p = f"{OUT}/favicon/favicon-{n}x{n}.png"; surf_png(p, 100, 100, db_icon, n/100); imgs.append(Image.open(p))
os.remove(f"{OUT}/favicon/favicon-48x48.png")
imgs[2].save(f"{OUT}/favicon/favicon.ico", sizes=[(16,16),(32,32),(48,48)], append_images=imgs[:2])
surf_svg(f"{OUT}/favicon/favicon.svg", 100, 100, db_icon)
surf_png(f"{OUT}/favicon/apple-touch-icon.png", 100, 100, lambda c: full_i_icon(c, 100, "square", 0.74), 1.8)
for n in (192, 512): surf_png(f"{OUT}/favicon/android-chrome-{n}x{n}.png", 100, 100, full_i_icon, n/100)
surf_png(f"{OUT}/favicon/maskable-icon-512x512.png", 100, 100, lambda c: full_i_icon(c, 100, "square", 0.62), 5.12)
surf_svg(f"{OUT}/favicon/app-icon.svg", 100, 100, full_i_icon)
json.dump({"name": "Sift", "short_name": "Sift",
  "icons": [{"src": "/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/maskable-icon-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
  "theme_color": "#0F161D", "background_color": "#0F161D", "display": "standalone", "start_url": "/"},
  open(f"{OUT}/favicon/site.webmanifest", "w"), indent=2)

# ---------- social card ----------
def text(c, file, s, x, yb, size, col):
    f = TTFont(file); gs = f.getGlyphSet(); cm = f.getBestCmap(); hm = f['hmtx']; k = size/f['head'].unitsPerEm; adv = 0
    c.new_path()
    for ch in s:
        n = cm[ord(ch)]; c.save(); c.translate(x + adv*k, yb); c.scale(k, -k); gs[n].draw(CP(gs, c)); c.restore(); adv += hm[n][0]
    c.set_source_rgba(*col); c.fill(); return adv*k
FR = "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf"
def og(c):
    c.set_source_rgba(*NIGHT); c.paint()
    k = 0.38; ww = 475/0.30*k
    wordmark(c, "dark", V, (1200-ww)/2, 408, k)
    tmp = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10))
    tw = text(tmp, FR, "Upload anything. Find it by meaning.", 0, 0, 34, (0,0,0,0))
    text(c, FR, "Upload anything. Find it by meaning.", (1200-tw)/2, 505, 34, hexc('#EFE9DC', 0.72))
surf_png(f"{OUT}/social/og-image.png", 1200, 630, og, 1.0)

# ---------- head + readme + sources ----------
open(f"{OUT}/head.html", "w").write("""<!-- Sift: copy everything in favicon/ to your site root, and social/og-image.png to /og-image.png -->
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32x32.png" type="image/png" sizes="32x32">
<link rel="icon" href="/favicon-16x16.png" type="image/png" sizes="16x16">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#0F161D">

<meta property="og:title" content="Sift">
<meta property="og:description" content="Upload text and images. Find them by what they contain.">
<meta property="og:image" content="https://YOUR-DOMAIN/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://YOUR-DOMAIN/og-image.png">
""")
open(f"{OUT}/README.md", "w").write("""# Sift: website assets

The logo is the word **sift**. The dot of the i is a small database (orange top) whose bottom disk
crumbles into bits; the bits fall and stack up to form the top of the i's stem.

## logo/
- `sift-logo-on-light.*`: dark ink, transparent background, for light pages.
- `sift-logo-on-dark.*`: light ink, transparent background, for dark pages.
- `sift-logo-{light,dark}-bg.*`: the same on its own background.
- `.svg` is vector (use this on the web). PNGs are named by pixel height (`-h96` = 96 px tall, so 2x of a 48 px header).

## mark/
The i on its own, for tight spaces (avatars, loading states, watermark).

## favicon/  (copy to your site root)
| File | Use |
|---|---|
| favicon.ico, favicon.svg, favicon-16x16.png, favicon-32x32.png | Browser tab. At these sizes the full i is too thin, so they use just the crumbling database dot. |
| apple-touch-icon.png | iOS home screen, 180 px, square (iOS rounds the corners) |
| android-chrome-192x192.png, android-chrome-512x512.png | Android / PWA, full i on a rounded tile |
| maskable-icon-512x512.png | Android adaptive icon, artwork kept inside the safe zone |
| app-icon.svg | Vector version of the rounded app icon |
| site.webmanifest | Web app manifest |

## social/
`og-image.png` (1200 x 630) for link previews. The tagline is a placeholder based on the project brief; change it in `source/export_mini.py`.

## alternates/
The two other variants: A (all-ink database) and C (stem still filling).

## head.html
Paste into your `<head>` and replace `YOUR-DOMAIN` with the deployed URL (og:image needs an absolute URL).

## Palette & type
| Token | Hex |
|---|---|
| Ink | #16202A |
| Paper | #F7F3EC |
| Night | #0F161D |
| Bone (ink on dark) | #EFE9DC |
| Sift orange | #F0763A |

Typeface: Poppins Bold (wordmark), Poppins Regular (supporting text).

## source/
`python3 export_mini.py` regenerates everything (needs pycairo, shapely, fonttools, pillow and Poppins).
""")
os.makedirs(f"{OUT}/source"); shutil.copy("mini.py", f"{OUT}/source/"); shutil.copy("export_mini.py", f"{OUT}/source/")
print("done")
