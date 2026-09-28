import math, random, sys
import numpy as np, cairo
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, Point
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen

W, H = 1000, 1360
def hexc(h, a=1.0):
    h = h.lstrip('#'); return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255, a)
def mix(c1, c2, t):
    return tuple(c1[i]*(1-t)+c2[i]*t for i in range(4))
def sstep(a, b, v):
    t = min(1, max(0, (v-a)/(b-a))); return t*t*(3-2*t)


def draw_logo(cx, THEME='dark', TRANSPARENT=False, SEED=5):
    random.seed(SEED); np.random.seed(SEED)
    if THEME == "dark":
        BG_IN, BG_OUT = hexc('#1B2733'), hexc('#0A1016')
        INK = hexc('#ECE5D6'); INK_D = hexc('#A9A294'); INK_L = hexc('#F8F4EB'); TOPF = hexc('#F6F1E7')
        CRACK = hexc('#0E151C')
        MESH_BG = hexc('#0E161D'); MESH_LN = hexc('#ECE5D6', 0.30)
    else:
        BG_IN, BG_OUT = hexc('#FBF8F2'), hexc('#EEE8DC')
        INK = hexc('#1B2631'); INK_D = hexc('#0E151C'); INK_L = hexc('#33414F'); TOPF = hexc('#2B3845')
        CRACK = hexc('#F5F1E9')
        MESH_BG = hexc('#F3EEE4'); MESH_LN = hexc('#1B2631', 0.35)
    ORANGE = hexc('#F0763A'); ORANGE_L = hexc('#FF9C5E')

    cx.set_line_join(cairo.LINE_JOIN_ROUND); cx.set_line_cap(cairo.LINE_CAP_ROUND)

    # ---------- background ----------
    if not TRANSPARENT:
        g = cairo.RadialGradient(500, 620, 50, 500, 620, 900)
        g.add_color_stop_rgba(0, *BG_IN); g.add_color_stop_rgba(1, *BG_OUT)
        cx.set_source(g); cx.paint()
        # warm glow at the neck
        gl = cairo.RadialGradient(500, 700, 0, 500, 700, 330)
        ga = 0.22 if THEME == "dark" else 0.10
        gl.add_color_stop_rgba(0, *ORANGE[:3], ga); gl.add_color_stop_rgba(0.5, *ORANGE[:3], ga*0.35); gl.add_color_stop_rgba(1, *ORANGE[:3], 0)
        cx.set_source(gl); cx.paint()


    # ---------- helpers ----------
    def cyl_gradient(x0, x1):
        lg = cairo.LinearGradient(x0, 0, x1, 0)
        lg.add_color_stop_rgba(0.0, *INK_D); lg.add_color_stop_rgba(0.12, *INK)
        lg.add_color_stop_rgba(0.38, *INK_L); lg.add_color_stop_rgba(0.75, *INK)
        lg.add_color_stop_rgba(1.0, *INK_D)
        return lg
    def ellipse_path(c, x, y, rx, ry):
        c.save(); c.translate(x, y); c.scale(rx, ry); c.arc(0, 0, 1, 0, 2*math.pi); c.restore()
    def body_path(c, x, ytop, rx, ry, h):
        c.new_path()
        c.move_to(x-rx, ytop)
        c.line_to(x-rx, ytop+h)
        c.save(); c.translate(x, ytop+h); c.scale(rx, ry); c.arc_negative(0, 0, 1, math.pi, 0); c.restore()
        c.line_to(x+rx, ytop)
        c.save(); c.translate(x, ytop); c.scale(rx, ry); c.arc(0, 0, 1, 0, math.pi); c.restore()
        c.close_path()
    def draw_disk(c, x, ytop, rx, ry, h, topcol):
        body_path(c, x, ytop, rx, ry, h); c.set_source(cyl_gradient(x-rx, x+rx)); c.fill()
        ellipse_path(c, x, ytop, rx, ry); c.set_source_rgba(*topcol); c.fill()
    def poly(c, pts):
        c.new_path(); c.move_to(*pts[0])
        for p in pts[1:]: c.line_to(*p)
        c.close_path()

    DBX, RX, RY, DH = 500, 200, 48, 76
    D1, D2, D3 = 128, 226, 324

    # ---------- disk 3: fractured ----------
    def disk_poly(ytop, rx, ry, h, n=90):
        pts = []
        for i in range(n+1):
            a = math.pi + math.pi*i/n; pts.append((DBX+rx*math.cos(a), ytop+ry*math.sin(a)))
        for i in range(n+1):
            a = math.pi*i/n; pts.append((DBX+rx*math.cos(a), ytop+h+ry*math.sin(a)))
        return Polygon(pts)
    d3 = disk_poly(D3, RX, RY, DH)
    seeds = []
    while len(seeds) < 70:
        x = random.uniform(DBX-RX, DBX+RX); y = random.uniform(D3-RY, D3+DH+RY)
        p = Point(x, y)
        if not d3.contains(p): continue
        keep = sstep(D3+10, D3+DH+RY-5, y)**0.9
        if random.random() < 0.08 + 0.92*keep: seeds.append((x, y))
    far = [(-3000,-3000),(4000,-3000),(-3000,4000),(4000,4000)]
    vor = Voronoi(np.array(seeds + far))
    cells = []
    for i, reg_i in enumerate(vor.point_region[:len(seeds)]):
        reg = vor.regions[reg_i]
        if -1 in reg or not reg: continue
        cp = Polygon([vor.vertices[k] for k in reg]).intersection(d3)
        if cp.is_empty or cp.area < 4: continue
        if cp.geom_type != 'Polygon': cp = max(cp.geoms, key=lambda q: q.area)
        cells.append(cp)

    def render_disk3(c):
        draw_disk(c, DBX, D3, RX, RY, DH, TOPF)
    fall_chunks = []
    for cp in sorted(cells, key=lambda q: q.centroid.y):
        ccx, ccy = cp.centroid.x, cp.centroid.y
        f = sstep(D3+34, D3+DH+RY, ccy + random.uniform(-10, 10))
        dy = 95*f**1.9 + f*random.uniform(0, 25)
        dx = (DBX-ccx)*0.30*f**1.6
        rot = math.radians(random.uniform(-38, 38)*f**1.4)
        sc = 1 - 0.28*f**1.5
        shp = cp.buffer(-1.0) if f > 0.01 else cp
        if shp.is_empty: continue
        if shp.geom_type != 'Polygon': shp = max(shp.geoms, key=lambda q: q.area)
        pts = list(shp.exterior.coords)
        cx.save()
        cx.translate(ccx+dx, ccy+dy); cx.rotate(rot); cx.scale(sc, sc); cx.translate(-ccx, -ccy)
        poly(cx, pts); cx.save(); cx.clip(); render_disk3(cx); cx.restore()
        cx.restore()
    # disks 2 and 1 above
    draw_disk(cx, DBX, D2, RX, RY, DH, TOPF)
    draw_disk(cx, DBX, D1, RX, RY, DH, ORANGE)
    # thin separators so the disks read as a stack
    for yy in (D2, D3):
        cx.save(); cx.translate(DBX, yy); cx.scale(RX, RY); cx.arc(0, 0, 1, 0, math.pi); cx.restore()
        cx.set_source_rgba(*(INK_D[:3] if TRANSPARENT else CRACK[:3]), 0.55 if not TRANSPARENT else 0.9); cx.set_line_width(2.2); cx.stroke()

    # ---------- sifter geometry ----------
    SX, SY, SRX, SRY, SH = 500, 668, 150, 34, 34
    IRX, IRY = 136, 28
    NECK_Y = SY - 6

    # back of sifter: rim top face + mesh
    ellipse_path(cx, SX, SY, SRX, SRY); cx.set_source_rgba(*TOPF); cx.fill()
    ellipse_path(cx, SX, SY, IRX, IRY); cx.set_source_rgba(*MESH_BG); cx.fill()
    cx.save(); ellipse_path(cx, SX, SY, IRX, IRY); cx.clip()
    cx.set_source_rgba(*MESH_LN); cx.set_line_width(0.9)
    for k in range(-40, 41):
        x = SX + k*7.5
        cx.move_to(x-40, SY-40); cx.line_to(x+40, SY+40); cx.stroke()
        cx.move_to(x+40, SY-40); cx.line_to(x-40, SY+40); cx.stroke()
    cx.restore()
    # heap in the mesh
    cx.save(); ellipse_path(cx, SX, SY, IRX-4, IRY-3); cx.clip()
    for j in range(12):
        for i in range(-30, 31):
            x = SX + i*6.2 + (j % 2)*3.1; y = SY + 20 - j*4.2
            dx = (x-SX)/110.0
            hgt = 26*math.exp(-dx*dx*2.2)
            if (SY+20-y) > hgt: continue
            if random.random() < 0.88:
                s = random.uniform(4.2, 5.4)
                col = mix(ORANGE, ORANGE_L, random.random()*0.5)
                cx.save(); cx.translate(x, y); cx.rotate(random.uniform(-0.4, 0.4))
                cx.rectangle(-s/2, -s/2, s, s); cx.set_source_rgba(*col); cx.fill(); cx.restore()
    cx.restore()

    # ---------- particles ----------
    placed = []
    def free(x, y, r):
        for (px, py, pr) in placed:
            if (x-px)**2 + (y-py)**2 < ((r+pr)*0.62)**2: return False
        return True
    def chunk(c, x, y, s, rot, col, jag=True):
        c.save(); c.translate(x, y); c.rotate(rot)
        if jag and s > 8:
            n = random.randint(5, 7); pts = []
            for k in range(n):
                a = 2*math.pi*k/n + random.uniform(-0.3, 0.3)
                r = s*0.55*random.uniform(0.72, 1.1); pts.append((r*math.cos(a), r*math.sin(a)))
            poly(c, pts)
        else:
            c.rectangle(-s/2, -s/2, s, s)
        c.set_source_rgba(*col); c.fill(); c.restore()
    def trail(c, pts, w, col, a):
        c.new_path(); c.move_to(*pts[0])
        for p in pts[1:]: c.line_to(*p)
        c.set_source_rgba(*col[:3], a); c.set_line_width(w); c.stroke()

    # upper funnel: disk bottom -> neck
    up = []
    tries = 0
    while len(up) < 290 and tries < 60000:
        tries += 1
        x0 = random.uniform(DBX-RX+14, DBX+RX-14)
        y0 = random.uniform(D3+DH+18, D3+DH+RY+30)
        xn = SX + (x0-SX)*0.16 + random.gauss(0, 5)
        t = random.random()**0.85
        def P(t, x0=x0, y0=y0, xn=xn):
            e = sstep(0, 1, t)
            return (x0 + (xn-x0)*e, y0 + (NECK_Y-y0)*t**1.22)
        x, y = P(t)
        s = (16.5 - 11*t**0.75) * random.uniform(0.75, 1.2)
        if not free(x, y, s*0.55): continue
        placed.append((x, y, s*0.55)); up.append((t, P, s))
    for t, P, s in sorted(up, key=lambda q: q[0]):
        m = sstep(0.28, 0.9, t + random.uniform(-0.12, 0.12))
        col = mix(INK, ORANGE, m)
        if t > 0.08:
            pts = [P(max(0, t - 0.075*k/5)) for k in range(6)][::-1]
            trail(cx, pts, max(1.0, s*0.34), col, 0.16 if THEME == "dark" else 0.13)
        x, y = P(t)
        chunk(cx, x, y, s, random.uniform(-1, 1)*math.pi*(1 - 0.6*t), col, jag=True)

    # front of sifter: front rim, band, handle
    cx.new_path()
    cx.save(); cx.translate(SX, SY); cx.scale(SRX, SRY); cx.arc(0, 0, 1, 0, math.pi); cx.restore()
    cx.save(); cx.translate(SX, SY); cx.scale(IRX, IRY); cx.arc_negative(0, 0, 1, math.pi, 0); cx.restore()
    cx.close_path(); cx.set_source_rgba(*TOPF); cx.fill()
    body_path(cx, SX, SY, SRX, SRY, SH)
    # (body_path includes the top front arc; fill band area only below the rim)
    cx.new_path()
    cx.move_to(SX-SRX, SY); cx.line_to(SX-SRX, SY+SH)
    cx.save(); cx.translate(SX, SY+SH); cx.scale(SRX, SRY); cx.arc_negative(0, 0, 1, math.pi, 0); cx.restore()
    cx.line_to(SX+SRX, SY)
    cx.save(); cx.translate(SX, SY); cx.scale(SRX, SRY); cx.arc(0, 0, 1, 0, math.pi); cx.restore()
    cx.close_path(); cx.set_source(cyl_gradient(SX-SRX, SX+SRX)); cx.fill()
    # rim lip line
    cx.save(); cx.translate(SX, SY); cx.scale(SRX, SRY); cx.arc(0, 0, 1, 0, math.pi); cx.restore()
    cx.set_source_rgba(*(INK_D[:3] if TRANSPARENT else CRACK[:3]), 0.45 if not TRANSPARENT else 0.9); cx.set_line_width(1.6); cx.stroke()
    # handle to the left
    cx.save(); cx.translate(SX-SRX+4, SY+14); cx.rotate(math.radians(-8))
    cx.new_path(); cx.move_to(0, -8); cx.line_to(-118, -8)
    cx.arc_negative(-118, 0, 8, -math.pi/2, math.pi/2) if False else None
    cx.new_path()
    cx.move_to(4, -7.5); cx.line_to(-112, -7.5); cx.arc(-112, 0, 7.5, -math.pi/2, math.pi/2)
    cx.line_to(4, 7.5); cx.close_path()
    hg = cairo.LinearGradient(0, -8, 0, 8); hg.add_color_stop_rgba(0, *INK_L); hg.add_color_stop_rgba(1, *INK_D)
    cx.set_source(hg); cx.fill()
    cx.arc(-104, 0, 3.2, 0, 2*math.pi); cx.set_source_rgba(*(INK_D if TRANSPARENT else CRACK)); cx.fill()
    cx.restore()
    # small tab on the right
    cx.save(); cx.translate(SX+SRX-4, SY+14); cx.rotate(math.radians(8))
    cx.new_path(); cx.move_to(-4, -6); cx.line_to(22, -6); cx.arc(22, 0, 6, -math.pi/2, math.pi/2); cx.line_to(-4, 6); cx.close_path()
    cx.set_source(hg); cx.fill(); cx.restore()

    # ---------- word ----------
    font = TTFont("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf")
    gs = font.getGlyphSet(); cmap = font.getBestCmap(); hm = font['hmtx']
    names = [cmap[ord(ch)] for ch in "sift"]
    bp = BoundsPen(gs); adv = 0
    for n in names:
        gs[n].draw(TransformPen(bp, (1, 0, 0, 1, adv, 0))); adv += hm[n][0]
    xmin, ymin, xmax, ymax = bp.bounds
    WX0, WX1, WY0 = 175, 825, 930
    k = (WX1-WX0)/(xmax-xmin); WH = (ymax-ymin)*k
    class CairoPen(BasePen):
        def __init__(s, gs, c): super().__init__(gs); s.c = c
        def _moveTo(s, p): s.c.move_to(*p)
        def _lineTo(s, p): s.c.line_to(*p)
        def _curveToOne(s, a, b, p): s.c.curve_to(*a, *b, *p)
        def _closePath(s): s.c.close_path()
    def word_path(c):
        c.new_path(); adv = 0
        for n in names:
            t = (k, 0, 0, -k, WX0 + (adv - xmin)*k, WY0 + ymax*k)
            gs[n].draw(TransformPen(CairoPen(gs, c), t)); adv += hm[n][0]
    # mask for sampling
    ms = cairo.ImageSurface(cairo.FORMAT_A8, W, H); mc = cairo.Context(ms)
    word_path(mc); mc.set_source_rgba(0, 0, 0, 1); mc.fill(); ms.flush()
    mstride = ms.get_stride(); mdata = ms.get_data()
    def inglyph(x, y):
        xi, yi = int(x), int(y)
        if 0 <= xi < W and 0 <= yi < H: return mdata[yi*mstride + xi] > 128
        return False
    SOLID = WY0 + WH*0.50
    # solid lower half
    cx.save(); cx.rectangle(0, SOLID, W, H); cx.clip(); word_path(cx)
    wg = cairo.LinearGradient(0, SOLID, 0, WY0+WH); wg.add_color_stop_rgba(0, *INK_L); wg.add_color_stop_rgba(1, *INK)
    cx.set_source(wg); cx.fill(); cx.restore()
    # accumulated bits (dithered, ordered grid)
    C, B = 8.0, 6.8
    nx = int((WX1-WX0)/C)+2; ny = int((SOLID-WY0)/C)+3
    err = np.zeros((ny+2, nx+2)); tops = {}
    bits = []
    for j in range(ny):
        y = SOLID - (j+1)*C
        rng = range(nx) if j % 2 == 0 else range(nx-1, -1, -1); dr = 1 if j % 2 == 0 else -1
        for i in rng:
            x = WX0 + i*C
            if not inglyph(x+C/2, y+C/2): continue
            t = (y - WY0)/(SOLID - WY0)
            w = math.exp(-((x+C/2-500)/230)**2)
            v = (0.14 + 0.86*max(0, t)**(0.55 + 0.9*(1-w))) + err[j][i]
            on = v > 0.5; e = v - (1 if on else 0)
            if on:
                tt = max(0, t)
                col = INK if random.random() < 0.18 + 0.82*tt**1.4 else mix(ORANGE, ORANGE_L, random.random()*0.4)
                bits.append((x+(C-B)/2, y+(C-B)/2, col))
                tops[i] = min(tops.get(i, 1e9), y)
            for di, dj, wt in [(dr, 0, 7/16), (-dr, 1, 3/16), (0, 1, 5/16), (dr, 1, 1/16)]:
                ii = i + di
                if 0 <= ii < nx: err[j+dj][ii] += e*wt
    for (x, y, col) in bits:
        cx.rectangle(x, y, B, B); cx.set_source_rgba(*col); cx.fill()

    # lower fan: neck -> letters (hourglass bottom bulb)
    cols = sorted(tops.keys())
    def land(xt):
        i = int((xt - WX0)/C)
        near = [tops[j] for j in range(i-1, i+2) if j in tops]
        return (min(near) if near else SOLID) - 6
    low = []; tries = 0
    placed = []
    BOT = SY + SH + SRY - 2
    while len(low) < 300 and tries < 80000:
        tries += 1
        # landing x: across the word, a bit denser toward the middle
        xt = 500 + random.gauss(0, 150)
        if not (WX0+6 < xt < WX1-6): continue
        ci = int((xt - WX0)/C)
        if ci not in tops and random.random() < 0.85: continue
        yl = land(xt)
        xs = SX + (xt-SX)*0.13 + random.gauss(0, 4)
        t = random.random()**1.05
        def P(t, xs=xs, xt=xt, yl=yl):
            e = sstep(0, 1, t)
            return (xs + (xt-xs)*e, BOT + (yl-BOT)*t**1.25)
        x, y = P(t)
        if y > yl - 4: continue
        s = (4.6 + 2.6*t) * random.uniform(0.9, 1.1)
        if not free(x, y, s*0.7): continue
        placed.append((x, y, s*0.7)); low.append((t, P, s))
    for t, P, s in sorted(low, key=lambda q: q[0]):
        col = mix(ORANGE, ORANGE_L, random.random()*0.45)
        if t > 0.06:
            pts = [P(max(0, t - 0.08*kk/5)) for kk in range(6)][::-1]
            trail(cx, pts, max(0.9, s*0.3), col, 0.15 if THEME == "dark" else 0.12)
        x, y = P(t)
        rot = random.uniform(-1, 1)*0.9*(1-t)**1.6
        chunk(cx, x, y, s, rot, col, jag=False)


