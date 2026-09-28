import math, cairo
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

def hexc(h, a=1.0):
    h = h.lstrip('#'); return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255, a)
INKS = {"light": hexc('#16202A'), "dark": hexc('#EFE9DC')}
BGS = {"light": hexc('#F7F3EC'), "dark": hexc('#0F161D')}
ORANGE = hexc('#F0763A')

F = TTFont("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf")
GS = F.getGlyphSet(); HM = F['hmtx']
class CP(BasePen):
    def __init__(s, gs, c): super().__init__(gs); s.c = c
    def _moveTo(s, p): s.c.move_to(*p)
    def _lineTo(s, p): s.c.line_to(*p)
    def _curveToOne(s, a, b, p): s.c.curve_to(*a, *b, *p)
    def _closePath(s): s.c.close_path()

def cyl(cx, ytop, rx, ry, h, n=64):
    """cylinder silhouette in font units (y up): top ellipse at ytop, body down h"""
    top = [(cx + rx*math.cos(2*math.pi*i/n), ytop + ry*math.sin(2*math.pi*i/n)) for i in range(n)]
    bot = [(cx + rx*math.cos(math.pi + math.pi*i/n), ytop - h + ry*math.sin(math.pi + math.pi*i/n)) for i in range(n+1)]
    return unary_union([Polygon(top), Polygon(bot + [(cx+rx, ytop), (cx-rx, ytop)])])
def ellipse(cx, cy, rx, ry, n=64):
    return Polygon([(cx + rx*math.cos(2*math.pi*i/n), cy + ry*math.sin(2*math.pi*i/n)) for i in range(n)])

def fill_geom(c, g, col):
    if g.is_empty: return
    geoms = [g] if g.geom_type == 'Polygon' else [q for q in getattr(g, 'geoms', []) if q.geom_type == 'Polygon' and not q.is_empty]
    c.new_path()
    for p in geoms:
        for ring in [p.exterior] + list(p.interiors):
            pts = list(ring.coords); c.move_to(*pts[0]); [c.line_to(*q) for q in pts[1:]]; c.close_path()
    c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD); c.set_source_rgba(*col); c.fill()

def i_parts(variant):
    """Parts of the i (font units, y up, glyph-local): database dot -> falling bits -> stem built from bits."""
    from shapely.affinity import translate
    SX0, SX1 = 75, 246; SC = (SX0+SX1)/2; XH = 558
    cell = (SX1-SX0)/3; g = cell*0.17; b = cell - g
    parts = []
    # stem: solid, then rows of bits on top (same outer width as the stem)
    rows = {'a': [[1,1,1],[1,1,1],[0,1,0]], 'b': [[1,1,1],[1,1,1],[0,1,0]], 'c': [[1,1,1],[1,0,1],[0,1,0]]}[variant]
    fresh = {(2,1), (1,2)}
    SOLID = XH - len(rows)*cell + g
    parts.append((box(SX0, 0, SX1, SOLID), 'ink'))
    for r, row in enumerate(rows):
        for k, on in enumerate(row):
            if not on: continue
            x = SX0 + k*cell + (g/2 if k else 0); xr = SX0 + (k+1)*cell - (g/2 if k < 2 else 0)
            y = SOLID + g + r*cell
            parts.append((box(x, y, xr, y + b), 'acc' if (r, k) in fresh else 'ink'))
    # database
    RX, RY, BH, GAP = 96, 24, 34, 12
    T1 = 862
    d1 = cyl(SC, T1, RX, RY, BH)
    d2 = cyl(SC, T1-BH-GAP, RX, RY, BH).difference(d1.buffer(GAP))
    if variant in ('b', 'c'):
        parts.append((d1.difference(ellipse(SC, T1, RX, RY).buffer(0)), 'ink')); parts.append((ellipse(SC, T1, RX, RY), 'acc'))
    else:
        parts.append((d1, 'ink'))
    parts.append((d2, 'ink'))
    # bottom disk dissolving into bits: its silhouette cut into a grid; lower cells drop / go missing
    T3 = T1 - 2*(BH+GAP)
    d3 = cyl(SC, T3, RX, RY, BH).difference(d2.buffer(GAP))
    q = RX*2/5
    top_band = d3.intersection(box(-1e4, T3 - 4, 1e4, 1e4))
    lower = d3.difference(box(-1e4, T3 - 4, 1e4, 1e4))
    parts.append((top_band, 'ink'))
    drops = [0, 22, None, 34, 6]          # None = already gone
    for k in range(5):
        x0 = SC - RX + k*q
        piece = lower.intersection(box(x0 + g/2, -1e4, x0 + q - g/2, T3 - 4 - g))
        if piece.is_empty or drops[k] is None: continue
        parts.append((translate(piece, 0, -drops[k]), 'ink'))
    # falling bits, converging onto the stem
    fb = b*0.72
    for (dx, y) in [(-0.05, 700), (0.62, 648), (-0.55, 612)]:
        x = SC + dx*cell
        parts.append((box(x-fb/2, y-fb/2, x+fb/2, y+fb/2), 'acc'))
    return parts

def wordmark(c, theme, variant, x, ybase, k):
    """Draw at scale k (px per font unit), baseline ybase."""
    ink = INKS[theme]
    names = ['s', 'dotlessi', 'f', 't']; adv = 0
    bp = BoundsPen(GS)
    for n in names: GS[n].draw(TransformPen(bp, (1,0,0,1,adv,0))); adv += HM[n][0]
    x0 = bp.bounds[0]; adv = 0
    for n in names:
        c.save(); c.translate(x + (adv - x0)*k, ybase); c.scale(k, -k)
        if n == 'dotlessi':
            for g, role in i_parts(variant):
                fill_geom(c, g, ORANGE if role == 'acc' else ink)
        else:
            c.new_path(); GS[n].draw(CP(GS, c)); c.set_fill_rule(cairo.FILL_RULE_WINDING); c.set_source_rgba(*ink); c.fill()
        c.restore(); adv += HM[n][0]

if __name__ == "__main__":
    k = 0.3; Wd, Hd = 1300, 1260
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, Wd, Hd); c = cairo.Context(s)
    y = 0
    for variant in ('a', 'b', 'c'):
        for j, theme in enumerate(('light', 'dark')):
            c.set_source_rgba(*BGS[theme]); c.rectangle(j*650, y, 650, 420); c.fill()
            wordmark(c, theme, variant, j*650 + 90, y + 330, k)
        y += 420
    s.write_to_png("variants.png")
