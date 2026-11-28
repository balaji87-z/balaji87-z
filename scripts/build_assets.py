#!/usr/bin/env python3
"""Generate the animated SVG artwork that README.md embeds.

Run `python3 scripts/build_assets.py` from the repository root; it rewrites
every file in assets/. GitHub shows these through <img>, so they cannot use
scripts, external fonts or external images: everything is plain SVG with SMIL
and CSS animation.
"""
import itertools
import json
import math
import pathlib
import random
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
ICONS = json.loads((ROOT / "scripts" / "icons.json").read_text())

G = "#00FF41"      # matrix green
HI = "#B6FFC8"     # highlight
MID = "#00B32C"
DIM = "#0A5C22"
BG = "#030806"
RED = "#FF2D55"
BLUE = "#2D8CFF"

BASE_CSS = (
    ".m{font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,"
    "'Liberation Mono','DejaVu Sans Mono',monospace}"
    ".s{font-family:'Arial Black','Segoe UI Black','Helvetica Neue',Helvetica,Arial,sans-serif}"
    ".b{font-weight:700}.x{font-weight:900}"
    "@keyframes bl{50%{opacity:0}}.bl{animation:bl 1.1s steps(1) infinite}"
    "@keyframes pu{50%{opacity:.35}}.pu{animation:pu 3s ease-in-out infinite}"
)

BASE_DEFS = (
    '<filter id="gl" x="-20%" y="-60%" width="140%" height="220%">'
    '<feGaussianBlur stdDeviation="3.2"/></filter>'
    '<filter id="gl2" x="-30%" y="-80%" width="160%" height="260%">'
    '<feGaussianBlur stdDeviation="10"/></filter>'
    '<linearGradient id="top" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#F2FFF5"/><stop offset=".45" stop-color="#00FF41"/>'
    '<stop offset="1" stop-color="#00B32C"/></linearGradient>'
    '<linearGradient id="panel" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#06200F"/><stop offset=".55" stop-color="#030B06"/>'
    '<stop offset="1" stop-color="#020503"/></linearGradient>'
)

_ids = itertools.count(1)


def uid(prefix="i"):
    return f"{prefix}{next(_ids)}"


def n(v):
    """Compact number formatting."""
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def doc(w, h, body, label, css="", defs=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{escape(label)}"><title>{escape(label)}</title>'
        f"<style>{BASE_CSS}{css}</style><defs>{BASE_DEFS}{defs}</defs>{body}</svg>\n"
    )


def write(name, content):
    (OUT / name).write_text(content)


# ---------------------------------------------------------------- 3D maths

def rot_x(v, a):
    x, y, z = v
    c, s = math.cos(a), math.sin(a)
    return (x, y * c - z * s, y * s + z * c)


def rot_y(v, a):
    x, y, z = v
    c, s = math.cos(a), math.sin(a)
    return (x * c + z * s, y, -x * s + z * c)


def rot_z(v, a):
    x, y, z = v
    c, s = math.cos(a), math.sin(a)
    return (x * c - y * s, x * s + y * c, z)


def unit(vs):
    r = max(math.sqrt(sum(c * c for c in v)) for v in vs)
    return [tuple(c / r for c in v) for v in vs]


def axis_to_y(vs, axis):
    """Rotate the vertices so that `axis` points straight up."""
    l = math.sqrt(sum(c * c for c in axis))
    u = tuple(c / l for c in axis)
    k = (u[2], 0.0, -u[0])                      # u x (0,1,0)
    s = math.sqrt(sum(c * c for c in k))
    c = u[1]
    if s < 1e-9:
        return list(vs)
    k = tuple(a / s for a in k)
    out = []
    for v in vs:
        kv = (k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0])
        kd = sum(a * b for a, b in zip(k, v))
        out.append(tuple(v[i] * c + kv[i] * s + k[i] * kd * (1 - c) for i in range(3)))
    return out


def edges_of(vs):
    pairs = list(itertools.combinations(range(len(vs)), 2))
    d = {p: math.dist(vs[p[0]], vs[p[1]]) for p in pairs}
    m = min(d.values())
    return [p for p in pairs if d[p] < m * 1.01]


def _shapes():
    phi = (1 + 5 ** 0.5) / 2
    cube = unit([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)])
    octa = unit([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)])
    tetra = unit([(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)])
    icosa = unit([p for a in (-1, 1) for b in (-phi, phi)
                  for p in ((0, a, b), (a, b, 0), (b, 0, a))])
    # Each entry: vertices with a symmetry axis pointing up, edges, and the
    # angle after which a spin about that axis looks identical again.
    return {
        "cube": (axis_to_y(cube, (1, 1, 1)), edges_of(cube), 120),
        "octa": (octa, edges_of(octa), 90),
        "tetra": (axis_to_y(tetra, (1, 1, 1)), edges_of(tetra), 120),
        "icosa": (axis_to_y(icosa, icosa[0]), edges_of(icosa), 72),
    }


SHAPES = _shapes()


def proj(v, cx, cy, r, persp=3.6):
    k = persp / (persp - v[2])
    return cx + v[0] * r * k, cy - v[1] * r * k


def glow_uses(pid, color, sw):
    """Cheap glow: the same animated path drawn three times, wide to narrow."""
    return (
        f'<use href="#{pid}" stroke="{color}" stroke-width="{n(sw * 5)}" opacity=".12"/>'
        f'<use href="#{pid}" stroke="{color}" stroke-width="{n(sw * 2.4)}" opacity=".3"/>'
        f'<use href="#{pid}" stroke="{HI if color == G else color}" stroke-width="{n(sw)}"/>'
    )


def wire(shape, cx, cy, r, color=G, sw=1.5, tilt_x=0.5, tilt_z=0.3, speed=26, step=8):
    """A spinning wireframe solid, projected to 2D and animated with SMIL."""
    verts, edges, period = SHAPES[shape]
    frames = max(6, round(period / step))
    values = []
    for i in range(frames + 1):
        a = math.radians(period * i / frames)
        pts = [proj(rot_z(rot_x(rot_y(v, a), tilt_x), tilt_z), cx, cy, r) for v in verts]
        values.append("".join(
            f"M{n(pts[a_][0])} {n(pts[a_][1])}L{n(pts[b_][0])} {n(pts[b_][1])}" for a_, b_ in edges))
    pid = uid("w")
    return (
        f'<defs><path id="{pid}" fill="none" stroke-linecap="round" d="{values[0]}">'
        f'<animate attributeName="d" dur="{n(period / speed)}s" repeatCount="indefinite" '
        f'values="{";".join(values)}"/></path></defs>' + glow_uses(pid, color, sw)
    )


def globe(cx, cy, r, color=G, sw=1.2, tilt_x=0.38, tilt_z=0.3, meridians=6, seg=24):
    """Wireframe globe: fixed parallels, meridians spinning about the axis."""
    def place(v, a):
        return proj(rot_z(rot_x(rot_y(v, a), tilt_x), tilt_z), cx, cy, r, persp=6)

    def poly(points):
        return "M" + "L".join(f"{n(x)} {n(y)}" for x, y in points)

    par = ""
    for lat in (-60, -30, 0, 30, 60):
        la = math.radians(lat)
        ring = [(math.cos(la) * math.cos(t), math.sin(la), math.cos(la) * math.sin(t))
                for t in (2 * math.pi * i / 36 for i in range(37))]
        par += poly([place(v, 0) for v in ring])
    period = 180 / meridians
    frames = 6
    values = []
    for i in range(frames + 1):
        a = math.radians(period * i / frames)
        d = ""
        for m in range(meridians):
            lon = math.pi * m / meridians
            ring = [(math.cos(t) * math.cos(lon), math.sin(t), math.cos(t) * math.sin(lon))
                    for t in (2 * math.pi * j / seg for j in range(seg + 1))]
            d += poly([place(v, a) for v in ring])
        values.append(d)
    pid, sid = uid("w"), uid("w")
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{n(r * 1.02)}" fill="#04170B" opacity=".85"/>'
        f'<defs><path id="{sid}" fill="none" d="{par}"/>'
        f'<path id="{pid}" fill="none" d="{values[0]}">'
        f'<animate attributeName="d" dur="3.2s" repeatCount="indefinite" values="{";".join(values)}"/>'
        f'</path></defs>'
        f'<use href="#{sid}" stroke="{color}" stroke-width="{n(sw)}" opacity=".45"/>'
        + glow_uses(pid, color, sw)
        + f'<circle cx="{cx}" cy="{cy}" r="{n(r * 1.02)}" fill="none" stroke="{color}" stroke-width="6" opacity=".14"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{n(r * 1.02)}" fill="none" stroke="{HI}" stroke-width="1.6"/>'
    )


# ---------------------------------------------------------------- building blocks

def ext_text(txt, x, y, size, depth=6, cls="m b", anchor="start", ls=0, top="url(#top)",
             side_far="#012A0D", side_near="#02611C", glow=G, extra="", dx=1.0, dy=1.0,
             glow_filter="gl", glow_cls=""):
    """Text with a stacked extrusion behind it and a blurred glow."""
    tid = uid("t")
    out = (f'<defs><text id="{tid}" x="{n(x)}" y="{n(y)}" class="{cls}" font-size="{size}" '
           f'text-anchor="{anchor}" letter-spacing="{ls}" {extra}>{escape(txt)}</text></defs>')
    if glow:
        out += (f'<use href="#{tid}" fill="{glow}" filter="url(#{glow_filter})" opacity=".9" '
                f'class="{glow_cls}" transform="translate({n(depth * dx / 2)} {n(depth * dy / 2)})"/>')
    for i in range(depth, 0, -1):
        out += (f'<use href="#{tid}" fill="{mix(side_near, side_far, i / depth)}" '
                f'transform="translate({n(i * dx)} {n(i * dy)})"/>')
    return out + f'<use href="#{tid}" fill="{top}"/>'


def slab(x, y, w, h, r=12, depth=8, fill="url(#panel)", stroke=G, side_far="#011A08",
         side_near="#03461A", pulse=False):
    """A raised panel: stacked offset copies give it thickness."""
    out = ""
    for i in range(depth, 0, -1):
        out += (f'<rect x="{n(x + i)}" y="{n(y + i)}" width="{w}" height="{h}" rx="{r}" '
                f'fill="{mix(side_near, side_far, i / depth)}"/>')
    cls = ' class="pu"' if pulse else ""
    return (out + f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="none" stroke="{stroke}" '
            f'stroke-width="7" opacity=".13"{cls}/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="none" stroke="{stroke}" '
            f'stroke-width="1.6" opacity=".85"/>')


def brackets(x, y, w, h, s=18, color=G, sw=2.5):
    """HUD corner brackets."""
    d = (f"M{x} {y + s}V{y}H{x + s}M{x + w - s} {y}H{x + w}V{y + s}"
         f"M{x + w} {y + h - s}V{y + h}H{x + w - s}M{x + s} {y + h}H{x}V{y + h - s}")
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>'


def grid_floor(cx, y0, y1, color=G, rows=9, cols=16, far=46, near=250, dur=1.5, xmin=0, xmax=1200):
    """A perspective floor whose rows roll toward the viewer."""
    mid, gid = uid("m"), uid("g")
    out = (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
           f'<stop offset=".35" stop-color="#fff" stop-opacity=".55"/>'
           f'<stop offset="1" stop-color="#fff"/></linearGradient>'
           f'<mask id="{mid}"><rect x="{xmin}" y="{y0}" width="{xmax - xmin}" height="{y1 - y0}" '
           f'fill="url(#{gid})"/></mask></defs>'
           f'<g mask="url(#{mid})" stroke="{color}" stroke-width="1.4" fill="none">')
    for k in range(-cols, cols + 1):
        out += f'<path d="M{n(cx + k * far)} {y0}L{n(cx + k * near)} {y1}" opacity=".7"/>'
    for k in range(1, rows + 1):
        ys = [y0 + (y1 - y0) / (k + 1 - t / 6) for t in range(7)]
        vals = ";".join(f"0 {n(v)}" for v in ys)
        out += (f'<path d="M{xmin} 0H{xmax}"><animateTransform attributeName="transform" type="translate" '
                f'dur="{dur}s" repeatCount="indefinite" values="{vals}"/></path>')
    out += "</g>"
    out += (f'<path d="M{xmin} {y0}H{xmax}" stroke="{color}" stroke-width="8" opacity=".18"/>'
            f'<path d="M{xmin} {y0}H{xmax}" stroke="{HI}" stroke-width="1.8"/>')
    return out


RAIN_CHARS = "01" * 6 + "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾜ" + "<>{}[]$#*+=/:"


def rain(w, h, seed, step=30, size=16, opacity=0.5):
    """Matrix digital rain: columns of glyphs falling at different speeds."""
    rnd = random.Random(seed)
    gid = uid("g")
    out = (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0" stop-color="{G}" stop-opacity="0"/>'
           f'<stop offset=".8" stop-color="{G}" stop-opacity=".85"/>'
           f'<stop offset="1" stop-color="#E6FFEC"/></linearGradient></defs>'
           f'<g class="m" font-size="{size}" text-anchor="middle" fill="url(#{gid})" opacity="{opacity}">')
    lead = size + 3
    for x in range(step // 2, w, step):
        count = rnd.randint(7, 16)
        dur = rnd.uniform(4.5, 9.5)
        delay = rnd.uniform(0, dur)
        spans = "".join(f'<tspan x="{x}" dy="{lead}">{escape(rnd.choice(RAIN_CHARS))}</tspan>' for _ in range(count))
        length = count * lead
        out += (f'<text y="0"><animateTransform attributeName="transform" type="translate" '
                f'dur="{n(dur)}s" begin="-{n(delay)}s" repeatCount="indefinite" '
                f'values="0 {-length - 20};0 {h + 20}"/>{spans}</text>')
    return out + "</g>"


def eq_bars(x, base, count=7, w=7, gap=5, color=G, seed=0, hmax=34):
    rnd = random.Random(seed)
    out = f'<g fill="{color}">'
    for i in range(count):
        hs = [rnd.randint(5, hmax) for _ in range(4)]
        hs.append(hs[0])
        dur = n(rnd.uniform(0.9, 1.7))
        out += (f'<rect x="{x + i * (w + gap)}" width="{w}" y="{base - hs[0]}" height="{hs[0]}" rx="1.5">'
                f'<animate attributeName="height" dur="{dur}s" repeatCount="indefinite" values="{";".join(map(str, hs))}"/>'
                f'<animate attributeName="y" dur="{dur}s" repeatCount="indefinite" '
                f'values="{";".join(str(base - v) for v in hs)}"/></rect>')
    return out + "</g>"


def icon(name, x, y, size, color=G, glow=True):
    """A 24-unit icon path scaled to `size`, with a soft outline as glow."""
    s = size / 24
    g = (f'<path d="{ICONS[name]}" fill="none" stroke="{color}" stroke-width="{n(4 / s)}" '
         f'stroke-linejoin="round" opacity=".16"/>') if glow else ""
    return (f'<g transform="translate({n(x)} {n(y)}) scale({s:.3f})">{g}'
            f'<path d="{ICONS[name]}" fill="{color}"/></g>')


def sheen(w, h, dur=7, begin=0):
    """A band of light sweeping across a panel."""
    gid = uid("g")
    return (f'<defs><linearGradient id="{gid}" x1="0" x2="1" y1="0" y2="0">'
            f'<stop offset="0" stop-color="{HI}" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="{HI}" stop-opacity=".13"/>'
            f'<stop offset="1" stop-color="{HI}" stop-opacity="0"/></linearGradient></defs>'
            f'<rect x="-260" y="0" width="240" height="{h}" fill="url(#{gid})" transform="skewX(-20)">'
            f'<animate attributeName="x" dur="{dur}s" begin="{begin}s" repeatCount="indefinite" '
            f'values="-260;{w + 120};{w + 120}" keyTimes="0;.45;1"/></rect>')


def clip(w, h, r, body):
    cid = uid("c")
    return (f'<defs><clipPath id="{cid}"><rect width="{w}" height="{h}" rx="{r}"/></clipPath></defs>'
            f'<g clip-path="url(#{cid})">{body}</g>')


def frame(w, h, r):
    return (f'<rect x="1.5" y="1.5" width="{w - 3}" height="{h - 3}" rx="{r}" fill="none" stroke="{G}" '
            f'stroke-width="7" opacity=".12"/>'
            f'<rect x="1.5" y="1.5" width="{w - 3}" height="{h - 3}" rx="{r}" fill="none" stroke="{G}" '
            f'stroke-width="1.5" opacity=".6"/>')


# ---------------------------------------------------------------- assets

NAME = "Kavin Harish"


def hero():
    w, h = 1200, 440
    horizon = 328
    defs = ('<radialGradient id="bg" cx=".5" cy=".45" r=".7">'
            '<stop offset="0" stop-color="#072A12"/><stop offset=".6" stop-color="#030C06"/>'
            '<stop offset="1" stop-color="#010302"/></radialGradient>'
            '<radialGradient id="veil" cx=".5" cy=".5" r=".5">'
            '<stop offset="0" stop-color="#010302" stop-opacity=".92"/>'
            '<stop offset=".7" stop-color="#010302" stop-opacity=".6"/>'
            '<stop offset="1" stop-color="#010302" stop-opacity="0"/></radialGradient>'
            '<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{G}" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="{G}" stop-opacity=".1"/>'
            f'<stop offset="1" stop-color="{G}" stop-opacity="0"/></linearGradient>')
    body = f'<rect width="{w}" height="{h}" fill="url(#bg)"/>'
    body += rain(w, horizon, seed=7)
    body += f'<rect y="{horizon}" width="{w}" height="{h - horizon}" fill="#010402"/>'
    body += grid_floor(600, horizon, h)
    body += '<ellipse cx="600" cy="196" rx="470" ry="150" fill="url(#veil)"/>'
    for cx, shape in ((132, "icosa"), (1068, "cube")):
        body += f'<ellipse cx="{cx}" cy="176" rx="112" ry="112" fill="#010302" opacity=".55"/>'
        ring = uid("p")
        body += (f'<path id="{ring}" d="M{cx - 112} 176a112 34 0 1 0 224 0a112 34 0 1 0 -224 0" fill="none" '
                 f'stroke="{G}" stroke-width="1.2" opacity=".4" transform="rotate(-18 {cx} 176)"/>')
        body += wire(shape, cx, 176, 78, sw=1.8)
        body += (f'<g transform="rotate(-18 {cx} 176)"><circle r="4.5" fill="{HI}">'
                 f'<animateMotion dur="6s" repeatCount="indefinite" '
                 f'path="M{cx - 112} 176a112 34 0 1 0 224 0a112 34 0 1 0 -224 0"/></circle></g>')
    body += ext_text(NAME.upper(), 600, 212, 104, depth=13, cls="s x", anchor="middle", dx=1.1, dy=1.1,
                     extra='transform="translate(600 0) scale(.83 1) translate(-600 0)"', glow_filter="gl2",
                     glow_cls="pu", side_far="#011F09", side_near="#037020")
    body += ext_text("BREAK. BUILD. SECURE.", 600, 278, 27, depth=3, anchor="middle", ls=9, top=HI)
    body += (f'<text x="600" y="308" class="m b" font-size="15" text-anchor="middle" letter-spacing="6" '
             f'fill="{G}" opacity=".9">AI × SECURITY  //  AUTOMATION  //  LINUX</text>')
    body += (f'<rect y="-120" width="{w}" height="120" fill="url(#scan)">'
             f'<animate attributeName="y" dur="7s" repeatCount="indefinite" values="-120;{h}"/></rect>')
    body += brackets(22, 22, w - 44, h - 44, s=26)
    body += (f'<text x="60" y="58" class="m b" font-size="15" fill="{G}" letter-spacing="2">'
             f'root@matrix:~$ ./whoami<tspan class="bl" fill="{HI}"> █</tspan></text>')
    body += (f'<circle cx="1052" cy="53" r="6" fill="{G}" class="bl"/>'
             f'<circle cx="1052" cy="53" r="11" fill="{G}" opacity=".25" class="pu"/>'
             f'<text x="1070" y="58" class="m b" font-size="15" fill="{G}" letter-spacing="3">ONLINE</text>')
    write("hero.svg", doc(w, h, clip(w, h, 20, body) + frame(w, h, 20),
                          f"{NAME} — Break. Build. Secure. AI × Security, automation, Linux.", defs=defs))


SECTIONS = [
    ("01", "SYSTEM INITIALIZATION", "boot sequence  /  whoami", "icosa"),
    ("02", "TECH STACK", "loaded modules", "cube"),
    ("03", "ZAP-LABS", "web security cyber range", "icosa"),
    ("04", "CURRENT PROJECTS", "active operations", "octa"),
    ("05", "CHOOSE YOUR PILL", "red or blue", "tetra"),
    ("06", "GITHUB TELEMETRY", "live signal", "icosa"),
    ("07", "CONTRIBUTION SNAKE", "grid crawler", "cube"),
    ("08", "INCOMING TRANSMISSION", "intercepted signal", "octa"),
    ("09", "NETWORK", "open channels", "tetra"),
]


def section(num, title, sub, shape):
    w, h = 1200, 100
    body = f'<rect width="{w}" height="{h}" fill="url(#panel)"/>'
    body += sheen(w, h, dur=8, begin=int(num) * 0.6)
    # keycap with the section number
    for i in range(7, 0, -1):
        body += f'<rect x="{26 + i}" y="{20 + i}" width="70" height="54" rx="9" fill="{mix("#02611C", "#012A0D", i / 7)}"/>'
    body += '<rect x="26" y="20" width="70" height="54" rx="9" fill="url(#top)"/>'
    body += (f'<rect x="26" y="20" width="70" height="54" rx="9" fill="none" stroke="{G}" stroke-width="8" '
             f'opacity=".2" class="pu"/>')
    body += (f'<text x="61" y="59" class="m x" font-size="34" text-anchor="middle" fill="#012A0D">{num}</text>')
    body += ext_text(title, 128, 54, 33, depth=5, ls=4)
    body += (f'<text x="130" y="80" class="m" font-size="14" fill="{G}" opacity=".75" letter-spacing="3">'
             f'// {escape(sub)}</text>')
    body += eq_bars(960, 70, seed=int(num), hmax=40)
    body += wire(shape, 1126, 50, 31, sw=1.4, speed=30)
    body += (f'<path d="M24 93H1176" stroke="{G}" stroke-width="2" opacity=".35"/>'
             f'<rect y="91.5" width="130" height="3" rx="1.5" fill="{HI}">'
             f'<animate attributeName="x" dur="4s" repeatCount="indefinite" values="24;1046;24"/></rect>'
             f'<rect y="88" width="130" height="10" rx="5" fill="{G}" opacity=".25">'
             f'<animate attributeName="x" dur="4s" repeatCount="indefinite" values="24;1046;24"/></rect>')
    write(f"sec-{num}.svg", doc(w, h, clip(w, h, 14, body) + frame(w, h, 14), f"{num} — {title.title()}"))


TERMINAL = [
    ("p", "$ ./boot.sh --user balaji87-z"),
    ("o", "> loading modules ............ [ OK ]"),
    ("o", "> initializing environment ... [ OK ]"),
    ("o", "> mounting /dev/curiosity .... [ OK ]"),
    ("p", "$ whoami"),
    ("o", "user    : Kavin Harish"),
    ("o", "role    : cybersecurity learner"),
    ("o", "motto   : Break. Build. Secure."),
    ("o", "focus   : AI × Security, automation, Linux"),
    ("p", "$ cat now.txt"),
    ("o", "building  -> ZAP-LABS cyber range, kortex-shield WAF"),
    ("o", "learning  -> ethical hacking"),
    ("o", "exploring -> LLMs for vulnerability discovery"),
]


def terminal():
    w, h = 1200, 470
    cycle = 24.0
    css = ""
    body = f'<rect width="{w}" height="{h}" rx="16" fill="{BG}"/>'
    body += slab(26, 24, 770, 410, r=14, depth=12, fill="#040C07")
    body += (f'<path d="M26 62H796" stroke="{G}" stroke-width="1.2" opacity=".5"/>'
             '<circle cx="52" cy="43" r="7" fill="#FF5F57"/><circle cx="76" cy="43" r="7" fill="#FEBC2E"/>'
             '<circle cx="100" cy="43" r="7" fill="#28C840"/>'
             f'<text x="411" y="48" class="m" font-size="14" text-anchor="middle" fill="{G}" opacity=".8" '
             f'letter-spacing="2">balaji87-z@matrix: ~</text>')
    lines_glow, lines = "", ""
    y = 92
    for i, (kind, text) in enumerate(TERMINAL):
        start = (0.4 + i * 0.45) / cycle * 100
        css += (f"@keyframes l{i}{{0%,{start:.2f}%{{opacity:0}}{start + 0.1:.2f}%,96%{{opacity:1}}"
                f"100%{{opacity:0}}}}.l{i}{{animation:l{i} {cycle}s infinite}}")
        fill = HI if kind == "p" else G
        t = escape(text).replace("[ OK ]", f'<tspan fill="{HI}" class="b">[ OK ]</tspan>')
        row = f'<text x="52" y="{y}" class="l{i}" fill="{fill}" xml:space="preserve">{t}</text>'
        lines += row
        lines_glow += f'<text x="52" y="{y}" class="l{i}" xml:space="preserve">{escape(text)}</text>'
        y += 25
    start = (0.4 + len(TERMINAL) * 0.45) / cycle * 100
    css += (f"@keyframes lc{{0%,{start:.2f}%{{opacity:0}}{start + 0.1:.2f}%,96%{{opacity:1}}100%{{opacity:0}}}}"
            f".lc{{animation:lc {cycle}s infinite}}")
    lines += (f'<g class="lc"><text x="52" y="{y}" fill="{HI}">$ <tspan class="bl">█</tspan></text></g>')
    body += f'<g class="m" font-size="17" fill="{G}" filter="url(#gl)" opacity=".55">{lines_glow}</g>'
    body += f'<g class="m" font-size="17">{lines}</g>'

    # side panel: spinning core and status read-outs
    body += slab(836, 24, 330, 410, r=14, depth=12, fill="#040C07")
    body += (f'<text x="1001" y="56" class="m b" font-size="15" text-anchor="middle" fill="{G}" '
             f'letter-spacing="6">CORE</text>')
    body += (f'<circle cx="1001" cy="172" r="98" fill="none" stroke="{G}" stroke-width="1" opacity=".3" '
             f'stroke-dasharray="3 9"><animateTransform attributeName="transform" type="rotate" dur="40s" '
             f'repeatCount="indefinite" values="0 1001 172;360 1001 172"/></circle>')
    body += wire("icosa", 1001, 172, 78, sw=1.8)
    wave = "M0 0" + "".join(f"q15 {-16 if i % 2 == 0 else 16} 30 0" for i in range(14))
    cid = uid("c")
    body += (f'<defs><clipPath id="{cid}"><rect x="862" y="282" width="278" height="44"/></clipPath></defs>'
             f'<g clip-path="url(#{cid})"><path d="{wave}" fill="none" stroke="{G}" stroke-width="2">'
             f'<animateTransform attributeName="transform" type="translate" dur="1.6s" repeatCount="indefinite" '
             f'values="802 304;862 304"/></path></g>')
    for i, (k, v) in enumerate((("STATUS", "ACTIVE"), ("MODE", "LEARNING"), ("UPLINK", "STABLE"))):
        yy = 352 + i * 26
        body += (f'<circle cx="870" cy="{yy - 5}" r="4.5" fill="{G}" class="bl" style="animation-delay:{i * 0.35}s"/>'
                 f'<text x="886" y="{yy}" class="m" font-size="15" fill="{G}" opacity=".8" letter-spacing="2">{k}</text>'
                 f'<text x="1140" y="{yy}" class="m b" font-size="15" fill="{HI}" text-anchor="end" '
                 f'letter-spacing="2">{v}</text>')
    alt = "Terminal boot sequence: " + " | ".join(t for _, t in TERMINAL)
    write("terminal.svg", doc(w, h, body, alt, css=css))


STACK = [
    ("PYTHON", "python"), ("BASH", "gnubash"), ("LINUX", "linux"), ("KALI", "kalilinux"),
    ("DOCKER", "docker"), ("AWS", "aws"), ("GIT", "git"), ("ACTIONS", "githubactions"),
]


def tile(cx, cy, label, icon_name, idx):
    a, b, d = 96, 48, 44
    L, R, T, B = (cx - a, cy), (cx + a, cy), (cx, cy - b), (cx, cy + b)
    delay = idx * 0.45
    bob = (f'<animateTransform attributeName="transform" type="translate" dur="4.2s" begin="-{n(delay)}s" '
           f'repeatCount="indefinite" values="0 0;0 -9;0 0" calcMode="spline" '
           f'keySplines=".45 0 .55 1;.45 0 .55 1"/>')
    out = (f'<ellipse cx="{cx}" cy="{cy + d + 58}" rx="84" ry="15" fill="#000" opacity=".55">'
           f'<animate attributeName="rx" dur="4.2s" begin="-{n(delay)}s" repeatCount="indefinite" '
           f'values="84;70;84"/></ellipse>')
    out += f"<g>{bob}"
    # sides
    out += (f'<path d="M{L[0]} {L[1]}L{B[0]} {B[1]}V{B[1] + d}L{L[0]} {L[1] + d}Z" fill="#083A17"/>'
            f'<path d="M{B[0]} {B[1]}L{R[0]} {R[1]}V{R[1] + d}L{B[0]} {B[1] + d}Z" fill="#031C0B"/>')
    # top face and glowing rim
    top = f"M{T[0]} {T[1]}L{R[0]} {R[1]}L{B[0]} {B[1]}L{L[0]} {L[1]}Z"
    out += (f'<path d="{top}" fill="#0C4A1E"/>'
            f'<path d="{top}" fill="none" stroke="{G}" stroke-width="9" opacity=".16" stroke-linejoin="round"/>'
            f'<path d="{top}" fill="none" stroke="{HI}" stroke-width="1.8" stroke-linejoin="round"/>'
            f'<path d="M{L[0]} {L[1]}V{L[1] + d}L{B[0]} {B[1] + d}L{R[0]} {R[1] + d}V{R[1]}M{B[0]} {B[1]}V{B[1] + d}" '
            f'fill="none" stroke="{G}" stroke-width="1.3" opacity=".7"/>')
    # emitter ring on the top face and the light cone above it
    out += (f'<ellipse cx="{cx}" cy="{cy}" rx="50" ry="25" fill="#03140A" stroke="{G}" stroke-width="1.5"/>'
            f'<ellipse cx="{cx}" cy="{cy}" rx="34" ry="17" fill="{G}" opacity=".35" class="pu" '
            f'style="animation-delay:-{n(delay)}s"/>'
            f'<path d="M{cx - 50} {cy}L{cx - 38} {cy - 104}H{cx + 38}L{cx + 50} {cy}Z" fill="url(#cone)"/>')
    # label on the left face, sheared to sit on it
    out += (f'<text transform="matrix(1 .5 0 1 {L[0]} {L[1]})" x="{a / 2}" y="{d / 2 + 7}" class="m b" '
            f'font-size="17" text-anchor="middle" fill="{HI}" letter-spacing="1.5">{label}</text>')
    for i in range(3):
        out += (f'<circle transform="matrix(1 -.5 0 1 {B[0]} {B[1]})" cx="{24 + i * 22}" cy="{d / 2}" r="4" '
                f'fill="{G}" class="bl" style="animation-delay:-{n(i * 0.37 + idx * 0.2)}s"/>')
    out += "</g>"
    # hologram: the logo floats above the tile, out of phase with it
    out += (f'<g><animateTransform attributeName="transform" type="translate" dur="4.2s" '
            f'begin="-{n(delay + 0.7)}s" repeatCount="indefinite" values="0 0;0 -15;0 0" calcMode="spline" '
            f'keySplines=".45 0 .55 1;.45 0 .55 1"/>'
            f'<circle cx="{cx}" cy="{cy - 84}" r="40" fill="{G}" opacity=".1"/>'
            + icon(icon_name, cx - 29, cy - 113, 58, color=HI) + "</g>")
    return out


def stack():
    w, h = 1200, 470
    defs = (f'<linearGradient id="cone" x1="0" y1="1" x2="0" y2="0">'
            f'<stop offset="0" stop-color="{G}" stop-opacity=".38"/>'
            f'<stop offset="1" stop-color="{G}" stop-opacity="0"/></linearGradient>')
    body = f'<rect width="{w}" height="{h}" fill="url(#panel)"/>'
    # faint isometric floor
    floor = ""
    for k in range(-14, 30):
        floor += f"M{k * 96 - 480} 0l960 480M{k * 96 + 480} 0l-960 480"
    body += f'<path d="{floor}" stroke="{G}" stroke-width="1" opacity=".09" fill="none"/>'
    pos = [(168, 164), (420, 164), (672, 164), (924, 164), (294, 336), (546, 336), (798, 336), (1050, 336)]
    order = [0, 1, 2, 3, 4, 5, 6, 7]
    for i in order:
        body += tile(pos[i][0], pos[i][1], STACK[i][0], STACK[i][1], i)
    label = "Tech stack: Python, Bash, Linux, Kali, Docker, AWS, Git, GitHub Actions"
    write("stack.svg", doc(w, h, clip(w, h, 16, body) + frame(w, h, 16), label, defs=defs))


PROJECTS = [
    ("kortex", "01", "KORTEX-SHIELD", "A web application firewall built to a checkable standard",
     ["evaluation harness with frozen attack and benign corpora",
      "baselines measured against OWASP CRS",
      "proxy engine built on Coraza"], "icosa", "PUBLIC REPO"),
]


def project(slug, num, title, tagline, bullets, shape, status):
    w, h = 1200, 262
    body = slab(8, 8, 1172, 234, r=16, depth=12)
    cid = uid("c")
    body += (f'<defs><clipPath id="{cid}"><rect x="8" y="8" width="1172" height="234" rx="16"/></clipPath></defs>'
             f'<g clip-path="url(#{cid})">{sheen(w, 250, dur=9, begin=int(num) * 1.3)}</g>')
    # left: spinning solid inside a hexagon
    hx = "M124 34L203 79.5V170.5L124 216L45 170.5V79.5Z"
    body += (f'<path d="{hx}" fill="#03140A" stroke="{G}" stroke-width="8" opacity=".16" class="pu"/>'
             f'<path d="{hx}" fill="none" stroke="{G}" stroke-width="1.6"/>')
    body += wire(shape, 124, 125, 58, sw=1.7)
    body += (f'<text x="124" y="235" class="m b" font-size="13" text-anchor="middle" fill="{G}" opacity=".7" '
             f'letter-spacing="4">OP-{num}</text>')
    body += f'<path d="M238 40V212" stroke="{G}" stroke-width="1.2" opacity=".35"/>'
    body += ext_text(title, 268, 78, 34, depth=5, ls=3)
    body += (f'<text x="270" y="112" class="m" font-size="18" fill="{HI}">{escape(tagline)}</text>')
    for i, b in enumerate(bullets):
        y = 150 + i * 29
        body += (f'<path d="M272 {y - 12}l10 6.5-10 6.5z" fill="{G}"/>'
                 f'<text x="294" y="{y}" class="m" font-size="17" fill="{G}">{escape(b)}</text>')
    # right: status
    body += (f'<rect x="968" y="34" width="184" height="34" rx="17" fill="#03140A" stroke="{G}" stroke-width="1.4"/>'
             f'<circle cx="988" cy="51" r="5.5" fill="{G}" class="bl"/>'
             f'<circle cx="988" cy="51" r="10" fill="{G}" opacity=".25" class="pu"/>'
             f'<text x="1070" y="56" class="m b" font-size="14" text-anchor="middle" fill="{HI}" '
             f'letter-spacing="2">{status}</text>')
    body += eq_bars(1046, 200, count=9, seed=int(num) + 20, hmax=46)
    if slug == "kortex":
        body += (f'<text x="1152" y="110" class="m b pu" font-size="15" text-anchor="end" fill="{G}" '
                 f'letter-spacing="2">CLICK TO OPEN</text>'
                 f'<path d="M1136 120l14 9-14 9z" fill="{HI}" class="bl"/>')
    label = f"{title.title()} — {tagline}: " + "; ".join(bullets) + f". Status: {status.lower()}."
    write(f"project-{slug}.svg", doc(w, h, body, label))


def pill(slug, color, dark, light, title, sub):
    w, h = 1200, 150
    gid, hid = uid("g"), uid("g")
    defs = (f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{light}"/><stop offset=".45" stop-color="{color}"/>'
            f'<stop offset=".85" stop-color="{dark}"/><stop offset="1" stop-color="{color}"/></linearGradient>'
            f'<linearGradient id="{hid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#fff" stop-opacity=".85"/>'
            f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    body = f'<rect width="{w}" height="{h}" fill="url(#panel)"/>'
    body += sheen(w, h, dur=8)
    body += f'<ellipse cx="140" cy="128" rx="78" ry="9" fill="#000" opacity=".6"/>'
    body += (f'<ellipse cx="140" cy="72" rx="105" ry="46" fill="{color}" filter="url(#gl2)" opacity=".55" '
             f'class="pu"/>')
    body += ('<g><animateTransform attributeName="transform" type="translate" dur="3.6s" repeatCount="indefinite" '
             'values="0 0;0 -7;0 0" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"/>'
             '<g transform="rotate(-16 140 74)">'
             f'<rect x="56" y="42" width="168" height="64" rx="32" fill="url(#{gid})"/>'
             f'<rect x="56" y="42" width="168" height="64" rx="32" fill="none" stroke="{light}" stroke-width="1.5" '
             f'opacity=".7"/>'
             f'<path d="M140 43V105" stroke="{dark}" stroke-width="2" opacity=".55"/>'
             f'<rect x="74" y="48" width="132" height="20" rx="10" fill="url(#{hid})"/>'
             '<ellipse cx="84" cy="60" rx="7" ry="4" fill="#fff" opacity=".9"/>'
             '</g></g>')
    body += ext_text(title, 280, 76, 38, depth=6, ls=4, top=light, side_far=mix(dark, "#000000", .6),
                     side_near=dark, glow=color)
    body += f'<text x="282" y="112" class="m" font-size="18" fill="{light}" opacity=".9">{escape(sub)}</text>'
    body += (f'<g class="pu"><text x="1118" y="82" class="m b" font-size="15" text-anchor="end" fill="{light}" '
             f'letter-spacing="3">CLICK TO TOGGLE</text>'
             f'<path d="M1134 68h26l-13 17z" fill="{light}"/></g>')
    out = clip(w, h, 16, body) + (
        f'<rect x="1.5" y="1.5" width="{w - 3}" height="{h - 3}" rx="16" fill="none" stroke="{color}" '
        f'stroke-width="7" opacity=".14"/>'
        f'<rect x="1.5" y="1.5" width="{w - 3}" height="{h - 3}" rx="16" fill="none" stroke="{color}" '
        f'stroke-width="1.5" opacity=".7"/>')
    write(f"pill-{slug}.svg", doc(w, h, out, f"{title.title()} — {sub}", defs=defs))


EMAIL = "kavinharish07@gmail.com"


def uplink():
    w, h = 1200, 320
    body = f'<rect width="{w}" height="{h}" fill="url(#panel)"/>'
    body += rain(w, h, seed=21, step=40, size=14, opacity=0.16)
    gx, gy, gr = 200, 160, 112
    orbit = f"M{gx - 160} {gy}a160 44 0 1 0 320 0a160 44 0 1 0 -320 0"
    body += (f'<path d="{orbit}" fill="none" stroke="{G}" stroke-width="1.2" opacity=".4" '
             f'transform="rotate(-22 {gx} {gy})"/>')
    body += globe(gx, gy, gr)
    body += (f'<g transform="rotate(-22 {gx} {gy})"><circle r="5.5" fill="{HI}">'
             f'<animateMotion dur="7s" repeatCount="indefinite" path="{orbit}"/></circle>'
             f'<circle r="11" fill="{G}" opacity=".3"><animateMotion dur="7s" repeatCount="indefinite" '
             f'path="{orbit}"/></circle></g>')
    # signal arcs leaving the globe
    for i in range(3):
        r = 150 + i * 34
        body += (f'<path d="M{n(gx + r * math.cos(-0.5))} {n(gy + r * math.sin(-0.5))}'
                 f'A{r} {r} 0 0 1 {n(gx + r * math.cos(0.5))} {n(gy + r * math.sin(0.5))}" fill="none" '
                 f'stroke="{G}" stroke-width="3" stroke-linecap="round" opacity="0">'
                 f'<animate attributeName="opacity" dur="2.4s" begin="{i * 0.35}s" repeatCount="indefinite" '
                 f'values="0;.9;0;0" keyTimes="0;.2;.55;1"/></path>')
    # packets travelling to the read-out
    body += f'<path d="M452 160H548" stroke="{G}" stroke-width="1.5" stroke-dasharray="2 8" opacity=".6"/>'
    for i in range(3):
        body += (f'<circle cy="160" r="4.5" fill="{HI}"><animate attributeName="cx" dur="1.8s" '
                 f'begin="{i * 0.6}s" repeatCount="indefinite" values="452;548"/></circle>')
    body += slab(566, 44, 590, 222, r=14, depth=10, fill="#040C07")
    body += (f'<text x="592" y="78" class="m" font-size="14" fill="{G}" opacity=".75" letter-spacing="4">'
             f'UPLINK // CHANNEL 01</text>')
    body += ext_text("CONNECTION ESTABLISHED", 592, 124, 33, depth=5, ls=2)
    body += (f'<text x="592" y="168" class="m b" font-size="23" fill="{HI}">&gt; github.com/balaji87-z</text>'
             f'<text x="592" y="202" class="m b" font-size="23" fill="{HI}">&gt; {EMAIL}'
             f'<tspan class="bl" fill="{G}"> █</tspan></text>')
    for i, (k, v) in enumerate((("STATUS", "OPEN"), ("SIGNAL", "STRONG"))):
        x = 592 + i * 220
        body += (f'<circle cx="{x + 5}" cy="237" r="5" fill="{G}" class="bl" style="animation-delay:{i * 0.4}s"/>'
                 f'<text x="{x + 20}" y="242" class="m" font-size="15" fill="{G}" letter-spacing="2">{k} '
                 f'<tspan fill="{HI}" class="b">{v}</tspan></text>')
    body += eq_bars(1046, 240, count=8, seed=99, hmax=42)
    write("uplink.svg", doc(w, h, clip(w, h, 16, body) + frame(w, h, 16),
                            f"Connection established: github.com/balaji87-z, {EMAIL}"))


ZAP_STATS = [("20", "LIVE TARGETS"), ("10", "VULN CLASSES"), ("04", "SEC TIERS PER LAB")]
ZAP_CHAIN = ["RECON", "ENUMERATION", "DISCOVERY", "EXPLOITATION", "PRIVILEGE", "CAPTURE"]
ZAP_CLASSES = ["AUTH", "SQL INJECTION", "XSS", "ACCESS CONTROL", "FILE UPLOAD",
               "PATH TRAVERSAL", "COMMAND INJECTION", "SSRF", "JWT", "BUSINESS LOGIC"]
BOLT = "M18 -98L-56 12H-6L-26 98L56 -22H8L32 -98Z"


def zaplabs():
    w, h = 1200, 430
    body = f'<rect width="{w}" height="{h}" fill="url(#panel)"/>'
    body += rain(w, h, seed=42, step=40, size=14, opacity=0.13)
    body += sheen(w, h, dur=9)
    # emblem: an extruded lightning bolt inside spinning rings
    cx, cy = 178, 212
    body += f'<circle cx="{cx}" cy="{cy}" r="150" fill="#010302" opacity=".6"/>'
    for r, dash, dur, sign in ((138, "4 12", 36, 1), (120, "40 14", 24, -1)):
        body += (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{G}" stroke-width="1.6" opacity=".55" '
                 f'stroke-dasharray="{dash}"><animateTransform attributeName="transform" type="rotate" '
                 f'dur="{dur}s" repeatCount="indefinite" values="0 {cx} {cy};{sign * 360} {cx} {cy}"/></circle>')
    body += wire("icosa", cx, cy, 104, sw=1.1, speed=14)
    flick = ('<animate attributeName="opacity" dur="2.6s" repeatCount="indefinite" '
             'values="1;1;.35;1;.6;1;1" keyTimes="0;.62;.66;.7;.74;.8;1"/>')
    body += (f'<g transform="translate({cx} {cy})">'
             '<animateTransform attributeName="transform" type="translate" dur="4s" repeatCount="indefinite" '
             f'values="{cx} {cy};{cx} {cy - 8};{cx} {cy}" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"/>'
             f'<path d="{BOLT}" fill="{G}" filter="url(#gl2)" opacity=".9" transform="translate(7 7)">{flick}</path>')
    for i in range(14, 0, -1):
        body += f'<path d="{BOLT}" fill="{mix("#037020", "#011F09", i / 14)}" transform="translate({i} {i})"/>'
    body += (f'<path d="{BOLT}" fill="url(#top)" stroke="{HI}" stroke-width="1.5" stroke-linejoin="round"/></g>')
    # sparks jumping off the bolt
    for i, (x1, y1, x2, y2) in enumerate(((258, 150, 292, 132), (86, 262, 54, 282), (268, 268, 300, 292),
                                           (92, 150, 62, 128))):
        body += (f'<path d="M{x1} {y1}L{(x1 + x2) / 2 + 6} {(y1 + y2) / 2 - 7}L{x2} {y2}" fill="none" stroke="{HI}" '
                 f'stroke-width="2.4" stroke-linecap="round" opacity="0">'
                 f'<animate attributeName="opacity" dur="2.6s" begin="{i * 0.45}s" repeatCount="indefinite" '
                 f'values="0;0;1;0;.8;0;0" keyTimes="0;.6;.64;.68;.72;.78;1"/></path>')
    # title block
    body += (f'<text x="372" y="56" class="m" font-size="15" fill="{G}" opacity=".8" letter-spacing="5">'
             f'// BREAK. LEARN. EXPLOIT. DEFEND.</text>')
    body += ext_text("ZAP-LABS", 368, 138, 84, depth=11, cls="s x", glow_filter="gl2", glow_cls="pu",
                     extra='textLength="470" lengthAdjust="spacingAndGlyphs"', side_far="#011F09",
                     side_near="#037020")
    body += ext_text("WEB SECURITY CYBER RANGE", 372, 190, 26, depth=3, ls=6, top=HI)
    body += (f'<text class="m" font-size="18" fill="{HI}">'
             f'<tspan x="372" y="232">Break into 20 live targets across 10 vulnerability classes.</tspan>'
             f'<tspan x="372" y="258" fill="{G}">Every target launches as your own ephemeral container</tspan>'
             f'<tspan x="372" y="282" fill="{G}">with a fresh random flag, scored server-side.</tspan></text>')
    body += eq_bars(1050, 62, count=9, seed=77, hmax=38)
    for i, (num, label) in enumerate(ZAP_STATS):
        x = 372 + i * 268
        body += slab(x, 310, 244, 84, r=12, depth=9, fill="#040C07", pulse=True)
        body += ext_text(num, x + 20, 372, 54, depth=5, cls="s x", glow=None)
        body += (f'<text x="{x + 104}" y="358" class="m b" font-size="15" fill="{HI}" letter-spacing="2">')
        words = label.split(" ")
        first = " ".join(words[:2]) if len(words) > 2 else words[0]
        rest = " ".join(words[2:]) if len(words) > 2 else " ".join(words[1:])
        body += (f'<tspan x="{x + 104}" dy="-10">{first}</tspan>'
                 f'<tspan x="{x + 104}" dy="21">{rest}</tspan></text>')
    label = ("ZAP-LABS, a web security cyber range. Break. Learn. Exploit. Defend. Break into 20 live targets "
             "across 10 vulnerability classes. Every target launches as your own ephemeral container with a "
             "fresh random flag, scored server-side. 4 security tiers per lab.")
    write("zaplabs.svg", doc(w, h, clip(w, h, 16, body) + frame(w, h, 16), label))


def zapchain():
    w, h = 1200, 372
    cycle = 6.0
    css = (f"@keyframes nd{{0%{{opacity:0}}4%{{opacity:1}}22%{{opacity:0}}100%{{opacity:0}}}}"
           f".nd{{opacity:0;animation:nd {cycle}s infinite}}")
    body = f'<rect width="{w}" height="{h}" fill="url(#panel)"/>'
    body += (f'<text x="34" y="42" class="m" font-size="15" fill="{G}" opacity=".8" letter-spacing="5">'
             f'// ATTACK CHAIN</text>')
    xs = [112 + i * 195.2 for i in range(len(ZAP_CHAIN))]
    y = 108
    body += (f'<path d="M{xs[0]} {y}H{xs[-1]}" stroke="{G}" stroke-width="2" stroke-dasharray="3 9" opacity=".7"/>')
    body += (f'<circle cy="{y}" r="7" fill="{HI}"><animate attributeName="cx" dur="{cycle}s" '
             f'repeatCount="indefinite" values="{xs[0]};{n(xs[-1] + 195.2)}"/>'
             f'<animate attributeName="opacity" dur="{cycle}s" repeatCount="indefinite" values="1;1;0;0" '
             f'keyTimes="0;.83;.86;1"/></circle>')
    for i, (x, name) in enumerate(zip(xs, ZAP_CHAIN)):
        delay = f'style="animation-delay:{n(i * cycle / len(ZAP_CHAIN))}s"'
        hexagon = (f"M{n(x)} {y - 40}L{n(x + 35)} {y - 20}V{y + 20}L{n(x)} {y + 40}"
                   f"L{n(x - 35)} {y + 20}V{y - 20}Z")
        for d in range(7, 0, -1):
            body += (f'<path d="{hexagon}" fill="{mix("#03461A", "#011A08", d / 7)}" '
                     f'transform="translate({d} {d})"/>')
        body += (f'<path d="{hexagon}" fill="#06200F" stroke="{G}" stroke-width="1.6"/>'
                 f'<path d="{hexagon}" fill="#0E8F33" stroke="{G}" stroke-width="10" stroke-linejoin="round" '
                 f'class="nd" {delay}/>'
                 f'<text x="{n(x)}" y="{y + 10}" class="m x" font-size="27" text-anchor="middle" '
                 f'fill="{HI}">{i + 1:02d}</text>'
                 f'<text x="{n(x)}" y="{y + 76}" class="m b" font-size="16" text-anchor="middle" fill="{HI}" '
                 f'letter-spacing="1.5">{name}</text>')
    body += f'<path d="M34 212H1166" stroke="{G}" stroke-width="1.2" opacity=".3"/>'
    body += (f'<text x="34" y="244" class="m" font-size="15" fill="{G}" opacity=".8" letter-spacing="5">'
             f'// 10 VULNERABILITY CLASSES</text>')
    for i, name in enumerate(ZAP_CLASSES):
        x = 34 + (i % 5) * 229
        yy = 262 + (i // 5) * 52
        body += slab(x, yy, 212, 36, r=9, depth=5, fill="#040C07")
        body += (f'<circle cx="{x + 18}" cy="{yy + 18}" r="4.5" fill="{G}" class="bl" '
                 f'style="animation-delay:-{n(i * 0.23)}s"/>'
                 f'<text x="{x + 34}" y="{yy + 23}" class="m b" font-size="14" fill="{HI}" '
                 f'letter-spacing=".5">{name}</text>')
    label = ("ZAP-LABS attack chain: " + ", ".join(c.lower() for c in ZAP_CHAIN) + ". Vulnerability classes: "
             + ", ".join(c.lower() for c in ZAP_CLASSES) + ".")
    write("zaplabs-chain.svg", doc(w, h, clip(w, h, 16, body) + frame(w, h, 16), label, css=css))


SIGNALS = [
    "Break. Build. Secure.",
    "Trust nothing. Verify everything.",
    "Measure first. Claim later.",
    "Automate the boring. Investigate the strange.",
    "Wake up, Neo...",
]


def transmission():
    w, h = 1200, 250
    per = 4.0
    cycle = per * len(SIGNALS)
    share = 100 / len(SIGNALS)
    css = (f"@keyframes sg{{0%{{opacity:0}}{share * .12:.2f}%,{share * .88:.2f}%{{opacity:1}}"
           f"{share:.2f}%,100%{{opacity:0}}}}.sg{{opacity:0;animation:sg {cycle}s infinite}}")
    body = f'<rect width="{w}" height="{h}" fill="url(#panel)"/>'
    body += rain(w, h, seed=11, step=40, size=14, opacity=0.14)
    # left: receiver dish drawn as a spinning solid inside pulsing rings
    for i in range(3):
        body += (f'<circle cx="140" cy="125" r="50" fill="none" stroke="{G}" stroke-width="2" opacity="0">'
                 f'<animate attributeName="r" dur="3s" begin="{i}s" repeatCount="indefinite" values="50;112"/>'
                 f'<animate attributeName="opacity" dur="3s" begin="{i}s" repeatCount="indefinite" '
                 f'values=".7;0"/></circle>')
    body += f'<circle cx="140" cy="125" r="64" fill="#03140A" stroke="{G}" stroke-width="1.5"/>'
    body += wire("octa", 140, 125, 46, sw=1.7)
    body += slab(280, 34, 876, 172, r=14, depth=10, fill="#040C07")
    body += (f'<text x="308" y="70" class="m" font-size="14" fill="{G}" opacity=".75" letter-spacing="4">'
             f'SIGNAL DECODED // ROTATING</text>')
    body += eq_bars(1040, 76, count=8, seed=5, hmax=30)
    for i, line in enumerate(SIGNALS):
        delay = f'style="animation-delay:{n(i * per)}s"'
        body += (f'<g class="sg" {delay}>'
                 + ext_text(f"\u201c{line}\u201d", 308, 134, 27, depth=4, ls=1)
                 + f'<text x="308" y="178" class="m" font-size="15" fill="{HI}" opacity=".85" '
                   f'letter-spacing="3">TRANSMISSION {i + 1:02d} / {len(SIGNALS):02d}</text></g>')
    # progress bar that refills for every line
    body += (f'<rect x="700" y="166" width="428" height="6" rx="3" fill="{DIM}" opacity=".6"/>'
             f'<rect x="700" y="166" height="6" rx="3" fill="{HI}"><animate attributeName="width" '
             f'dur="{per}s" repeatCount="indefinite" values="0;428"/></rect>')
    label = "Incoming transmission: " + " / ".join(SIGNALS)
    write("transmission.svg", doc(w, h, clip(w, h, 16, body) + frame(w, h, 16), label, css=css))


def button(name, label, icon_name=None, w=400, h=104, size=24, depth=9, aria=None):
    body = slab(6, 6, w - 6 - depth - 6, h - 6 - depth - 6, r=14, depth=depth, pulse=True)
    iw = w - 6 - depth - 6
    ih = h - 6 - depth - 6
    cid = uid("c")
    body += (f'<defs><clipPath id="{cid}"><rect x="6" y="6" width="{iw}" height="{ih}" rx="14"/></clipPath></defs>'
             f'<g clip-path="url(#{cid})">{sheen(w, h, dur=6)}</g>')
    cy = 6 + ih / 2
    if icon_name:
        isz = ih * 0.52
        body += icon(icon_name, 30, cy - isz / 2, isz)
        body += ext_text(label, 30 + isz + 18, cy + size * 0.35, size, depth=3, ls=2)
        body += f'<path d="M{iw - 30} {n(cy - 10)}l14 10-14 10z" fill="{HI}" class="pu"/>'
    else:
        body += ext_text(label, 6 + iw / 2, cy + size * 0.35, size, depth=3, ls=2, anchor="middle")
    write(f"{name}.svg", doc(w, h, body, aria or label.title()))


def footer():
    w, h = 1200, 250
    horizon = 150
    sid = uid("c")
    defs = ('<radialGradient id="bg" cx=".5" cy=".6" r=".7">'
            '<stop offset="0" stop-color="#062410"/><stop offset=".6" stop-color="#030C06"/>'
            '<stop offset="1" stop-color="#010302"/></radialGradient>'
            f'<clipPath id="{sid}"><rect x="0" y="0" width="{w}" height="{horizon}"/></clipPath>')
    body = f'<rect width="{w}" height="{h}" fill="url(#bg)"/>'
    body += rain(w, horizon, seed=3, step=40, size=14, opacity=0.22)
    # a striped sun sinking behind the horizon
    body += (f'<g clip-path="url(#{sid})">'
             f'<circle cx="600" cy="{horizon}" r="104" fill="{G}" filter="url(#gl2)" opacity=".4" class="pu"/>'
             f'<circle cx="600" cy="{horizon}" r="92" fill="url(#top)"/>')
    for i, y in enumerate((horizon - 14, horizon - 32, horizon - 48, horizon - 62)):
        body += f'<rect x="490" y="{y}" width="220" height="{7 - i * 1.4:.1f}" fill="#030C06"/>'
    body += "</g>"
    body += f'<rect y="{horizon}" width="{w}" height="{h - horizon}" fill="#010402"/>'
    body += grid_floor(600, horizon, h, rows=8)
    body += ext_text("END OF TRANSMISSION", 600, 48, 30, depth=5, ls=8, anchor="middle")
    body += (f'<text x="600" y="228" class="m b" font-size="15" text-anchor="middle" fill="{HI}" '
             f'letter-spacing="5">{NAME.lower()}  //  break. build. secure.<tspan class="bl" fill="{G}"> █</tspan></text>')
    write("footer.svg", doc(w, h, clip(w, h, 20, body) + frame(w, h, 20), "End of transmission", defs=defs))


NAV = ["whoami", "stack", "zaplabs", "projects", "pill", "telemetry", "snake", "network"]


def main():
    OUT.mkdir(exist_ok=True)
    hero()
    for s in SECTIONS:
        section(*s)
    terminal()
    stack()
    zaplabs()
    zapchain()
    for p in PROJECTS:
        project(*p)
    pill("red", RED, "#7A0018", "#FFC2CC", "TAKE THE RED PILL", "Stay in Wonderland and see how deep the rabbit hole goes.")
    pill("blue", BLUE, "#062E73", "#C4DEFF", "TAKE THE BLUE PILL", "The story ends. Believe whatever you want to believe.")
    transmission()
    uplink()
    button("btn-github", "GITHUB PROFILE", "github")
    button("btn-repos", "REPOSITORIES", "git")
    button("btn-kortex", "KORTEX-SHIELD", "shield")
    button("btn-email", EMAIL, "mail", w=620, aria=f"Email {EMAIL}")
    for name in NAV:
        button(f"nav-{name}", name.upper(), w=214, h=70, size=21, depth=6)
    button("btn-top", "BACK TO TOP", w=300, h=70, size=21, depth=6)
    footer()
    total = sum(f.stat().st_size for f in OUT.glob("*.svg"))
    print(f"wrote {len(list(OUT.glob('*.svg')))} files, {total / 1024:.0f} KB")


if __name__ == "__main__":
    main()
