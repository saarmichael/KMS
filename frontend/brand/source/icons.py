import math, random
import numpy as np, cairo
from scipy.spatial import Voronoi
from shapely.geometry import Polygon
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen

def hexc(h, a=1.0):
    h = h.lstrip('#'); return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255, a)
def mix(a, b, t): return tuple(a[i]*(1-t)+b[i]*t for i in range(4))
def sstep(a, b, v):
    t = min(1, max(0, (v-a)/(b-a))); return t*t*(3-2*t)

PAL = {
 "dark":  dict(INK=hexc('#ECE5D6'), INK_D=hexc('#A9A294'), INK_L=hexc('#F8F4EB'), TOPF=hexc('#F6F1E7'), MESH=hexc('#0E161D'), MESHL=hexc('#ECE5D6',0.35)),
 "light": dict(INK=hexc('#1B2631'), INK_D=hexc('#0E151C'), INK_L=hexc('#33414F'), TOPF=hexc('#2B3845'), MESH=hexc('#F3EEE4'), MESHL=hexc('#1B2631',0.35)),
}
ORANGE = hexc('#F0763A'); ORANGE_L = hexc('#FF9C5E')
TILE_IN, TILE_OUT = hexc('#1D2935'), hexc('#0E151C')

def ell(c, x, y, rx, ry):
    c.save(); c.translate(x, y); c.scale(rx, ry); c.arc(0, 0, 1, 0, 2*math.pi); c.restore()
def arc_half(c, x, y, rx, ry, neg=False):
    c.save(); c.translate(x, y); c.scale(rx, ry)
    (c.arc_negative(0, 0, 1, math.pi, 0) if neg else c.arc(0, 0, 1, 0, math.pi)); c.restore()
def body(c, x, yt, rx, ry, h):
    c.new_path(); c.move_to(x-rx, yt); c.line_to(x-rx, yt+h)
    arc_half(c, x, yt+h, rx, ry, neg=True); c.line_to(x+rx, yt); arc_half(c, x, yt, rx, ry); c.close_path()
def cylg(P, x0, x1):
    g = cairo.LinearGradient(x0, 0, x1, 0)
    for s, k in [(0, 'INK_D'), (0.14, 'INK'), (0.4, 'INK_L'), (0.78, 'INK'), (1, 'INK_D')]: g.add_color_stop_rgba(s, *P[k])
    return g
def disk(c, P, x, yt, rx, ry, h, top):
    body(c, x, yt, rx, ry, h); c.set_source(cylg(P, x-rx, x+rx)); c.fill()
    ell(c, x, yt, rx, ry); c.set_source_rgba(*top); c.fill()
def poly(c, pts):
    c.new_path(); c.move_to(*pts[0]); [c.line_to(*p) for p in pts[1:]]; c.close_path()
def sq(c, x, y, s, rot, col):
    c.save(); c.translate(x, y); c.rotate(rot); c.rectangle(-s/2, -s/2, s, s); c.set_source_rgba(*col); c.fill(); c.restore()

def tile(c, radius=22):
    r = radius; c.new_path()
    c.arc(100-r, r, r, -math.pi/2, 0); c.arc(100-r, 100-r, r, 0, math.pi/2)
    c.arc(r, 100-r, r, math.pi/2, math.pi); c.arc(r, r, r, math.pi, 1.5*math.pi); c.close_path()
    g = cairo.RadialGradient(50, 42, 4, 50, 50, 80)
    g.add_color_stop_rgba(0, *TILE_IN); g.add_color_stop_rgba(1, *TILE_OUT)
    c.set_source(g); c.fill()

def mark(c, theme="dark", glow=True, seed=4):
    """Detailed square mark in a 100x100 box: crumbling DB -> hourglass -> sifter -> fan of bits."""
    P = PAL[theme]; random.seed(seed); np.random.seed(seed)
    X, RX, RY, DH = 50, 19, 4.6, 7.5
    if glow:
        g = cairo.RadialGradient(50, 64, 0, 50, 64, 30)
        g.add_color_stop_rgba(0, *ORANGE[:3], 0.28); g.add_color_stop_rgba(1, *ORANGE[:3], 0)
        c.set_source(g); c.rectangle(0, 0, 100, 100); c.fill()
    D1, D2, D3 = 13, 22.5, 32
    # fractured disk 3
    pts = [(X+RX*math.cos(math.pi+math.pi*i/40), D3+RY*math.sin(math.pi+math.pi*i/40)) for i in range(41)]
    pts += [(X+RX*math.cos(math.pi*i/40), D3+DH+RY*math.sin(math.pi*i/40)) for i in range(41)]
    d3 = Polygon(pts)
    seeds = [(31.5, 35), (40, 38), (50, 37), (60, 38), (68.5, 35), (36, 42.5), (46, 43), (55, 43.5), (64, 42), (50, 31)]
    vor = Voronoi(np.array(seeds + [(-500,-500),(600,-500),(-500,600),(600,600)]))
    for i, ri in enumerate(vor.point_region[:len(seeds)]):
        reg = vor.regions[ri]
        if -1 in reg or not reg: continue
        cp = Polygon([vor.vertices[k] for k in reg]).intersection(d3)
        if cp.is_empty: continue
        if cp.geom_type != 'Polygon': cp = max(cp.geoms, key=lambda q: q.area)
        ccx, ccy = cp.centroid.x, cp.centroid.y
        f = sstep(D3+1, D3+DH+RY, ccy)
        shp = cp.buffer(-0.35) if f > 0 else cp
        dy = 7.5*f**1.6; dx = (X-ccx)*0.22*f; rot = math.radians(random.uniform(-30, 30)*f)
        c.save(); c.translate(ccx+dx, ccy+dy); c.rotate(rot); c.scale(1-0.2*f, 1-0.2*f); c.translate(-ccx, -ccy)
        poly(c, list(shp.exterior.coords)); c.save(); c.clip(); disk(c, P, X, D3, RX, RY, DH, P['TOPF']); c.restore()
        c.restore()
    disk(c, P, X, D2, RX, RY, DH, P['TOPF'])
    disk(c, P, X, D1, RX, RY, DH, ORANGE)
    for yy in (D2, D3):
        arc_half(c, X, yy, RX, RY); c.set_source_rgba(*P['INK_D'][:3], 0.9); c.set_line_width(0.45); c.stroke()
    # sifter back
    SX, SY, SRX, SRY, SH = 50, 63, 15.5, 3.6, 3.4
    ell(c, SX, SY, SRX, SRY); c.set_source_rgba(*P['TOPF']); c.fill()
    ell(c, SX, SY, SRX-1.4, SRY-0.8); c.set_source_rgba(*P['MESH']); c.fill()
    c.save(); ell(c, SX, SY, SRX-1.4, SRY-0.8); c.clip(); c.set_source_rgba(*P['MESHL']); c.set_line_width(0.22)
    for k in range(-12, 13):
        x = SX + k*1.3; c.move_to(x-6, SY-6); c.line_to(x+6, SY+6); c.stroke(); c.move_to(x+6, SY-6); c.line_to(x-6, SY+6); c.stroke()
    for j in range(3):
        for i in range(-6, 7):
            x = SX + i*1.25 + (j % 2)*0.6; y = SY + 1.8 - j*1.0
            if abs(x-SX) < 7.5 - j*2.4: sq(c, x, y, 1.05, 0, ORANGE)
    c.restore()
    # funnel bits: from shards to neck
    for k in range(16):
        t = (k % 4 + 0.5)/4 + random.uniform(-0.08, 0.08)
        x0 = 32 + (k*37 % 36)
        x = x0 + (SX + (x0-SX)*0.15 - x0)*sstep(0, 1, t); y = 47 + (SY-2 - 47)*t
        s = 2.4 - 1.2*t
        sq(c, x, y, s, random.uniform(-0.6, 0.6)*(1-t), mix(P['INK'], ORANGE, sstep(0.2, 0.8, t)))
    # sifter front
    c.new_path(); arc_half(c, SX, SY, SRX, SRY); c.save(); c.translate(SX, SY); c.scale(SRX-1.4, SRY-0.8); c.arc_negative(0, 0, 1, math.pi, 0); c.restore(); c.close_path()
    c.set_source_rgba(*P['TOPF']); c.fill()
    c.new_path(); c.move_to(SX-SRX, SY); c.line_to(SX-SRX, SY+SH); arc_half(c, SX, SY+SH, SRX, SRY, neg=True); c.line_to(SX+SRX, SY); arc_half(c, SX, SY, SRX, SRY); c.close_path()
    c.set_source(cylg(P, SX-SRX, SX+SRX)); c.fill()
    c.save(); c.translate(SX-SRX+0.4, SY+1.5); c.rotate(math.radians(-8))
    c.new_path(); c.move_to(0.5, -0.9); c.line_to(-10, -0.9); c.arc(-10, 0, 0.9, -math.pi/2, math.pi/2); c.line_to(0.5, 0.9); c.close_path()
    c.set_source_rgba(*P['INK']); c.fill(); c.restore()
    # fan below: spreading and settling into an ordered row
    BOT = SY + SH + SRY
    fan = [(-2, .15), (2, .2), (0, .35), (-5, .45), (5, .5), (-1.5, .55), (-9, .68), (9, .7), (3, .72), (-4, .8), (-13, .86), (13, .88), (7, .9)]
    for xt, t in fan:
        x = SX + xt*1.35*sstep(0, 1, t) + xt*0.08; y = BOT + 1.2 + (84 - BOT)*t
        sq(c, x, y, 1.6 + 0.8*t, (1-t)*0.5*(1 if xt > 0 else -1), mix(ORANGE, ORANGE_L, random.random()*0.4))
    for i in range(-7, 8):
        for j in range(2):
            if j == 1 and abs(i) > 4: continue
            if random.random() < 0.12: continue
            sq(c, SX + i*2.7, 88.5 - j*2.7, 2.3, 0, P['INK'] if (j == 0 and random.random() < 0.7) else ORANGE)

def simple_mark(c, theme="dark"):
    """Bold version for 16-48 px: DB with an orange top, bottom crumbling into bits."""
    P = PAL[theme]
    X, RX, RY, DH = 50, 27, 7, 13
    body(c, X, 36, RX, RY, DH); c.set_source(cylg(P, X-RX, X+RX)); c.fill()
    ell(c, X, 36, RX, RY); c.set_source_rgba(*P['TOPF']); c.fill()
    disk(c, P, X, 20, RX, RY, DH, ORANGE)
    arc_half(c, X, 36, RX, RY); c.set_source_rgba(*P['INK_D'][:3], 0.9); c.set_line_width(1.2); c.stroke()
    # crumbled bits: 3 then 2 then 1 converging (hourglass)
    for (x, y, s, col) in [(34, 64, 9, P['INK']), (50, 65, 9, P['INK']), (66, 64, 9, P['INK']),
                           (42, 76, 8, ORANGE), (58, 76, 8, ORANGE), (50, 87, 8, ORANGE)]:
        sq(c, x, y, s, 0, col)

# ---------- wordmark ----------
FONT = TTFont("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf")
GS = FONT.getGlyphSet(); CM = FONT.getBestCmap(); HM = FONT['hmtx']
class CairoPen(BasePen):
    def __init__(s, gs, c): super().__init__(gs); s.c = c
    def _moveTo(s, p): s.c.move_to(*p)
    def _lineTo(s, p): s.c.line_to(*p)
    def _curveToOne(s, a, b, p): s.c.curve_to(*a, *b, *p)
    def _closePath(s): s.c.close_path()
WORD = ['s', 'dotlessi', 'f', 't']
def word_metrics():
    bp = BoundsPen(GS); adv = 0; xs = []
    for n in WORD:
        xs.append(adv); GS[n].draw(TransformPen(bp, (1, 0, 0, 1, adv, 0))); adv += HM[n][0]
    return bp.bounds, xs
def wordmark(c, x, ybase, height, theme="dark"):
    """Draw 'sift' with an orange square i-dot; height = ascender height (f top) in user units."""
    P = PAL[theme]; (x0, y0, x1, y1), xs = word_metrics()
    k = height / y1
    c.new_path()
    for n, a in zip(WORD, xs):
        GS[n].draw(TransformPen(CairoPen(GS, c), (k, 0, 0, -k, x + (a - x0)*k, ybase)))
    c.set_source_rgba(*P['INK']); c.fill()
    ia = xs[1]; s = 165*k; cxs = x + (ia + 160.5 - x0)*k
    c.rectangle(cxs - s/2, ybase - 628*k - s, s, s); c.set_source_rgba(*ORANGE); c.fill()
    return (x1 - x0)*k
