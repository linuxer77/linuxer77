#!/usr/bin/env python3
"""
make_battle.py  ·  builds battle-light.svg and battle-dark.svg  (18 s loop)

Looks like a plain profile README. Then Charizard and Blastoise walk onto the page, and Gengar
comes up out of the heading's rule to mess with the copy.

Everything is SMIL. No JavaScript, no CSS animation, no external files: the sprite sheets
are baked in as data URIs, so GitHub's image proxy renders it as-is. Edit H1_TEXT / PARAS
to change the copy.

Sprites: PMD Sprite Collab (https://sprites.pmdcollab.org), see README.md for credits.
Each Pokémon's frames are packed into one strip; a single discrete <animate> on the strip's
x picks the frame, so the sprite animation stays in sync with everything else.

BEAT SHEET (seconds)
 0.3  Charizard walks in from the left, Blastoise from the right.
 2.3  Charizard: FLAMETHROWER. Blastoise withdraws into its shell, the fire splashes off.
 4.1  Blastoise pops out: HYDRO PUMP. Charizard is blasted back in a cloud of steam.
 5.9  Charizard powers up and rushes in. Impact. Blastoise is knocked back.
 7.1  Charizard hops back. Blastoise RAPID SPINs across the floor into him.
 9.3  Both charge up. The page rumbles.
10.5  Flamethrower vs Hydro Pump. The beams meet in the middle and push each other around.
12.4  BOOM. White flash. Both are thrown to the edges.
13.4  Smoke clears. Both are out cold. Zzz.
15.4  They get up, turn around and walk off. Clean page.
18.0  Loop.

GENGAR, meanwhile, up in the text
 0.5  Rises out of the rule. Grins. Floats down to "Software developer".
 3.5  Eats "developer", one letter at a time, last letter first. Licks its lips. Regrets it.
 7.5  Spits the letters back out, backwards ("repoleved"). They hop back into order. Gengar nods.
 9.8  Floats up to the heading, yanks the wave emoji off it and waves it at you.
12.5  The explosion below startles it. It drops the wave (which bounces home) and sinks into the rule.
"""
import base64
import html
import io
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageFont

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- constants
T = 18.0
EPS = 0.002
TICK = 1 / 60          # PMD durations are in 60 fps game frames
W, H, FLOOR = 830, 277, 258
S = 2                  # sprite scale
H1_Y, RULE_Y, P_Y = 32, 50, 84
FONT = ImageFont.truetype("/usr/share/fonts/liberation/LiberationSans-Regular.ttf", 16)
FONT_H1 = ImageFont.truetype("/usr/share/fonts/liberation/LiberationSans-Bold.ttf", 32)
FONT_STACK = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

H1_TEXT = "Hi, I'm Harshit Gupta"
H1_EMOJI = "\U0001F44B"            # Gengar steals this one
PARA = ("Software", "developer")   # Gengar eats the second word, letter by letter

PALETTES = {
    "light": dict(bg="#ffffff", fg="#1f2328", rule="#d1d9e0", shadow="#1f2328", flash="#ffffff",
                  smoke="#8c959f", steam="#c9d1d9", zz="#57606a"),
    "dark":  dict(bg="#0d1117", fg="#e6edf3", rule="#3d444d", shadow="#000000", flash="#f0f6fc",
                  smoke="#6e7681", steam="#8b949e", zz="#8b949e"),
}
FIRE = ["#d1242f", "#f0612e", "#ff9a3c", "#ffd34e"]
WATER = ["#1f6feb", "#4a9dff", "#9fd2ff", "#ffffff"]
SPLINES = {"lin": "0 0 1 1", "in": "0.55 0 1 1", "out": "0 0 0.45 1", "inout": "0.45 0 0.55 1",
           "snap": "0 0 0.15 1"}

# PMD sheet rows: Down, DownRight, Right, UpRight, Up, UpLeft, Left, DownLeft
ROW_RIGHT, ROW_LEFT = 2, 6


def n(v):
    s = f"{v:.1f}"
    s = s[:-2] if s.endswith(".0") else s
    return "0" if s == "-0" else s


def rnd(i):
    x = math.sin(i * 12.9898 + 78.233) * 43758.5453
    return x - math.floor(x)


# ---------------------------------------------------------------- tracks
class Track:
    def __init__(self, v0):
        self.keys = [[0.0, v0, "lin"]]

    @property
    def t(self):
        return self.keys[-1][0]

    @property
    def v(self):
        return self.keys[-1][1]

    def add(self, t, v, ease="lin"):
        if t <= self.t:
            t = self.t + EPS
        self.keys.append([round(t, 5), v, ease])

    def hold(self, t):
        if t > self.t + 1e-9:
            self.keys.append([round(t, 5), self.v, "lin"])

    def set(self, t, v):
        self.hold(t - EPS)
        self.add(t, v)

    def cut(self, t):
        """Drop every key at or after t (a newer instruction overrides what was planned)."""
        while len(self.keys) > 1 and self.keys[-1][0] >= t - 1e-9:
            self.keys.pop()

    def finished(self):
        ks = [list(k) for k in self.keys]
        assert ks[-1][0] <= T + 1e-9, f"key past loop end {ks[-1]}"
        if ks[-1][0] < T:
            ks.append([T, ks[-1][1], "lin"])
        ks[-1][0] = T
        return ks


def animate(track, attr, fmt=n, typ=None, discrete=False):
    ks = track.finished()
    vals = [fmt(v) for _, v, _ in ks]
    if len(set(vals)) == 1:
        return ""
    kt = ";".join(f"{t / T:.6f}".rstrip("0").rstrip(".") or "0" for t, _, _ in ks)
    if discrete:
        mode = 'calcMode="discrete"'
    else:
        mode = 'calcMode="spline" keySplines="' + ";".join(SPLINES[e] for _, _, e in ks[1:]) + '"'
    tag = f'animateTransform type="{typ}"' if typ else "animate"
    return (f'<{tag} attributeName="{attr}" dur="{n(T)}s" repeatCount="indefinite" '
            f'keyTimes="{kt}" values="{";".join(vals)}" {mode}/>')


def static(track, fmt=n):
    return fmt(track.keys[0][1])


def xy(v):
    return f"{n(v[0])} {n(v[1])}"


def g_translate(track, inner, extra=""):
    """<g> moved by a Track of (x, y) tuples."""
    a = animate(track, "transform", xy, "translate")
    return f'<g transform="translate({xy(track.keys[0][1])})"{extra}>{a}{inner}</g>'


# ---------------------------------------------------------------- sprites
class Mon:
    """One Pokémon: its packed frame strip plus the tracks that drive it."""

    def __init__(self, folder, row, anims, x0, floor=FLOOR):
        root = ET.parse(HERE / "sprites" / folder / "AnimData.xml").getroot()
        meta = {a.findtext("Name"): a for a in root.iter("Anim")}
        frames = []                       # (RGBA crop, anchor x, anchor y)
        self.cells, self.ticks = {}, {}
        for name in anims:
            a = meta[name]
            fw, fh = int(a.findtext("FrameWidth")), int(a.findtext("FrameHeight"))
            durs = [int(d.text) for d in a.iter("Duration")]
            sheet = Image.open(HERE / "sprites" / folder / f"{name}-Anim.png").convert("RGBA")
            shadow = Image.open(HERE / "sprites" / folder / f"{name}-Shadow.png").convert("RGBA")
            self.cells[name], self.ticks[name] = [], durs
            ax, ay = fw / 2, fh / 2
            r = row if sheet.height > fh else 0       # Sleep only has the one row
            for i in range(len(durs)):
                box = (i * fw, r * fh, (i + 1) * fw, (r + 1) * fh)
                im, sh = sheet.crop(box), shadow.crop(box)
                sb = sh.getchannel("A").getbbox()     # the shadow's centre is where the feet are
                if sb:                                # (no shadow drawn: keep the last frame's)
                    ax, ay = (sb[0] + sb[2]) / 2, (sb[1] + sb[3]) / 2
                self.cells[name].append(len(frames))
                frames.append((im, ax, ay))
        # one cell size for every frame, just big enough for all of them around the anchor
        l = u = r = d = 0
        for im, ax, ay in frames:
            b = im.getchannel("A").getbbox()
            l, u = max(l, ax - b[0]), max(u, ay - b[1])
            r, d = max(r, b[2] - ax), max(d, b[3] - ay)
        self.left, self.up = math.ceil(l), math.ceil(u)
        self.cw, self.ch = self.left + math.ceil(r), self.up + math.ceil(d)
        strip = Image.new("RGBA", (self.cw * len(frames), self.ch))
        for i, (im, ax, ay) in enumerate(frames):
            strip.paste(im, (int(i * self.cw + self.left - ax), int(self.up - ay)), im)
        buf = io.BytesIO()
        strip.save(buf, "PNG", optimize=True)
        self.png = base64.b64encode(buf.getvalue()).decode()

        self.frame = Track(self.cells[anims[0]][0])
        self.x = Track((x0, 0))
        self.y = Track((0, 0))
        self.face = Track(1)
        self.op = Track(1)
        self.floor = floor

    def dur(self, anim, i0=0, i1=None, speed=1.0):
        return sum(self.ticks[anim][i0:i1]) * TICK / speed

    def play(self, t, anim, i0=0, i1=None, speed=1.0, until=None, reverse=False):
        """Frames i0..i1 of anim from t. Once (then the last frame holds), or looped until `until`.
        Returns when the pass ends."""
        idx = list(range(len(self.ticks[anim])))[i0:i1]
        if reverse:
            idx.reverse()
        self.frame.cut(t)
        tt = t
        while True:
            for i in idx:
                if until is not None and tt >= until - 1e-6:
                    return tt
                self.frame.add(tt, self.cells[anim][i])
                tt += self.ticks[anim][i] * TICK / speed
            if until is None:
                return tt

    def go(self, t0, t1, x, ease="inout"):
        self.x.hold(t0)
        self.x.add(t1, (x, 0), ease)

    def hop(self, t0, t1, height, ease_up="out", ease_down="in"):
        mid = (t0 + t1) / 2
        self.y.hold(t0)
        self.y.add(mid, (0, -height), ease_up)
        self.y.add(t1, (0, 0), ease_down)

    def xat(self, t):
        ks = self.x.keys
        for (t0, v0, _), (t1, v1, e) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                s = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                return v0[0] + (v1[0] - v0[0]) * s
        return ks[-1][1][0]

    def svg(self, p, uid):
        img = (f'<svg x="{-self.left}" y="{-self.up}" width="{self.cw}" height="{self.ch}" overflow="hidden">'
               f'<image x="{-self.frame.keys[0][1] * self.cw}" y="0" width="{self.cw * self.strip_len}" '
               f'height="{self.ch}" style="image-rendering:crisp-edges;image-rendering:pixelated" '
               f'href="data:image/png;base64,{self.png}">'
               + animate(self.frame, "x", lambda v: str(-v * self.cw), discrete=True)
               + "</image></svg>")
        flip = animate(self.face, "transform", lambda v: f"{v * S} {S}", "scale", discrete=True)
        body = f'<g transform="scale({self.face.keys[0][1] * S} {S})">{flip}{img}</g>'
        body = f'<g transform="translate(0 {self.floor})">{g_translate(self.y, body)}</g>'
        op = animate(self.op, "opacity", n, discrete=True)
        return f'<g opacity="{static(self.op)}">{op}' + g_translate(self.x, body, f' id="{uid}"') + "</g>"

    @property
    def strip_len(self):
        return 1 + max(max(c) for c in self.cells.values())

    def shadow_svg(self, p):
        e = f'<ellipse cx="0" cy="{FLOOR}" rx="{9 * S}" ry="{2.5 * S}" fill="{p["shadow"]}" opacity="0.18"/>'
        return g_translate(self.x, e)


# ---------------------------------------------------------------- particles
class Particle:
    def __init__(self, draw):
        self.draw = draw              # callable(palette) -> svg, drawn around 0,0 at unit size
        self.pos = Track((0, 0))
        self.sc = Track(1)
        self.op = Track(0)
        self.free = 0.0

    def fly(self, t0, life, p0, p1, s0, s1, ease="out", op0=1.0, fade_at=0.6):
        self.pos.set(t0, p0)
        self.pos.add(t0 + life, p1, ease)
        self.sc.set(t0, s0)
        self.sc.add(t0 + life, s1, ease)
        self.op.set(t0, op0)
        self.op.add(t0 + life * fade_at, op0)
        self.op.add(t0 + life, 0, "in")
        self.free = t0 + life + 0.01

    def svg(self, p):
        sc = animate(self.sc, "transform", lambda v: f"{n(v)} {n(v)}" if v >= 0.05 else f"{v:.2f} {v:.2f}", "scale")
        op = animate(self.op, "opacity", lambda v: f"{v:.2f}".rstrip("0").rstrip(".") or "0")
        inner = f'<g transform="scale({static(self.sc)})">{sc}{self.draw(p)}</g>'
        return f'<g opacity="{static(self.op)}">{op}' + g_translate(self.pos, inner) + "</g>"


class Pool:
    def __init__(self, draw):
        self.draw, self.items = draw, []

    def get(self, t):
        for it in self.items:
            if it.free <= t:
                return it
        it = Particle(self.draw)
        self.items.append(it)
        return it

    def svg(self, p):
        return "".join(it.svg(p) for it in self.items)


def fire_draw(i):
    def d(p):
        return (f'<circle r="1" fill="{FIRE[1 + i % 2]}"/>'
                f'<circle r="0.6" cx="0.15" cy="-0.1" fill="{FIRE[3]}"/>')
    return d


def water_draw(p):
    return f'<ellipse rx="1.4" ry="0.8" fill="{WATER[1]}"/><ellipse rx="0.7" ry="0.35" cx="0.2" cy="-0.15" fill="{WATER[3]}"/>'


def steam_draw(p):
    return f'<circle r="1" fill="{p["steam"]}"/>'


def smoke_draw(p):
    return f'<circle r="1" fill="{p["smoke"]}"/>'


def star_draw(color):
    pts = " ".join(f"{n(math.cos(k * math.pi / 6) * (1 if k % 2 == 0 else 0.42) * 10)},"
                   f"{n(math.sin(k * math.pi / 6) * (1 if k % 2 == 0 else 0.42) * 10)}" for k in range(12))
    return lambda p: (f'<polygon points="{pts}" fill="{color}"/>'
                      f'<circle r="3.2" fill="#ffffff"/>')


def ring_draw(color):
    return lambda p: f'<circle r="10" fill="none" stroke="{color}" stroke-width="1.6"/>'


def line_draw(p):
    return f'<rect x="-12" y="-0.6" width="24" height="1.2" rx="0.6" fill="{p["smoke"]}"/>'


def zz_draw(p):
    return f'<text font-size="11" font-weight="700" fill="{p["zz"]}" text-anchor="middle">z</text>'


FX = {
    "fire": [Pool(fire_draw(0)), Pool(fire_draw(1))],
    "water": Pool(water_draw),
    "steam": Pool(steam_draw),
    "smoke": Pool(smoke_draw),
    "star": Pool(star_draw("#ffd34e")),
    "star_b": Pool(star_draw("#9fd2ff")),
    "ring": Pool(ring_draw("#ff9a3c")),
    "ring_b": Pool(ring_draw("#4a9dff")),
    "line": Pool(line_draw),
    "zz": Pool(zz_draw),
}
SEQ = [0]


def seq():
    SEQ[0] += 1
    return SEQ[0]


def flame_stream(t0, t1, src, target_x, spread=10, rate=0.03, life=0.42):
    """Flamethrower: blobs from src to wherever target_x(t) says the flames end."""
    t = t0
    while t < t1:
        k = seq()
        tx = target_x(t + life)
        dy = (rnd(k) - 0.5) * spread
        p = FX["fire"][k % 2].get(t)
        p.fly(t, life, src, (tx + 6 + rnd(k + 7) * 10, src[1] + dy + (rnd(k + 3) - 0.3) * 8),
              3.2, 6.5 + rnd(k + 1) * 3.5, "lin", fade_at=0.88)
        t += rate


def puff(t, at, n_=5, size=7, life=0.7, kind="steam", rise=22, spread=18):
    for i in range(n_):
        k = seq()
        p = FX[kind].get(t)
        dx = (rnd(k) - 0.5) * spread
        p.fly(t + i * 0.02, life * (0.8 + rnd(k + 2) * 0.4), (at[0] + dx * 0.3, at[1]),
              (at[0] + dx, at[1] - rise * (0.6 + rnd(k + 4) * 0.6)), size * 0.4, size * (0.8 + rnd(k + 5) * 0.5),
              "out", op0=0.75, fade_at=0.35)


def impact(t, at, big=False, blue=False):
    s = FX["star_b" if blue else "star"].get(t)
    s.fly(t, 0.22, at, at, 0.3, 1.6 if big else 1.1, "snap", fade_at=0.5)
    r = FX["ring_b" if blue else "ring"].get(t)
    r.fly(t, 0.35, at, at, 0.2, 2.6 if big else 1.8, "out", fade_at=0.3)


def speed_lines(t0, t1, mon, direction, y_mid):
    t = t0
    while t < t1:
        k = seq()
        x = mon.xat(t) - direction * 30
        y = y_mid + (rnd(k) - 0.5) * 50
        p = FX["line"].get(t)
        p.fly(t, 0.22, (x, y), (x - direction * 30, y), 1, 0.4, "out", op0=0.7, fade_at=0.2)
        t += 0.025


def snore(t0, t1, at, phase=0.0):
    t = t0 + phase
    while t < t1 - 0.6:
        p = FX["zz"].get(t)
        k = seq()
        p.fly(t, 1.1, at, (at[0] + 10 + rnd(k) * 6, at[1] - 28), 0.7, 1.5, "out", op0=0.9, fade_at=0.6)
        t += 0.55


# ---------------------------------------------------------------- page-level tracks
SHAKE = Track((0, 0))
FLASH = Track(0)


def shake(t, amp, dur=0.3, step=0.03):
    SHAKE.hold(t)
    k, tt = 0, t
    while tt < t + dur:
        a = amp * (1 - (tt - t) / dur)
        SHAKE.add(tt + step, ((rnd(k * 2 + t) - 0.5) * 2 * a, (rnd(k * 2 + 1 + t) - 0.5) * 2 * a * 0.6))
        tt += step
        k += 1
    SHAKE.add(tt + step, (0, 0))


# ---------------------------------------------------------------- the battle
CH = Mon("charizard", ROW_RIGHT, ["Idle", "Walk", "Shoot", "Hurt", "Charge", "Attack", "Hop", "Sleep"], -90)
BL = Mon("blastoise", ROW_LEFT, ["Idle", "Walk", "Shoot", "Hurt", "Charge", "Withdraw", "Ricochet", "Sleep"], 920)
CX, BX = 225, 605                     # where they square up
MOUTH = (20 * S, -14 * S)             # Charizard facing right, Shoot pose (sprite px from the feet)
CANNON = (-10 * S, -10 * S)           # Blastoise facing left, Shoot pose
MID_Y = FLOOR - 24 * S                # roughly chest height, for hits

# 0.3  walk in
CH.play(0, "Idle", until=0.3)
CH.play(0.3, "Walk", until=1.9)
CH.x.hold(0.3); CH.x.add(1.9, (CX, 0), "out")
CH.play(1.9, "Idle", until=T)
BL.play(0, "Idle", until=0.35)
BL.play(0.35, "Walk", until=2.0)
BL.x.hold(0.35); BL.x.add(2.0, (BX, 0), "out")
BL.play(2.0, "Idle", until=T)

# 2.3  Flamethrower into a withdrawn shell
t = 2.3
hit = t + CH.dur("Shoot", 0, 2, 0.8)
CH.play(t, "Shoot", 0, 2, speed=0.8)
CH.play(hit, "Shoot", 2, 5, speed=0.5, until=3.85)
CH.play(3.85, "Shoot", 5, speed=0.8)
CH.play(4.15, "Idle", until=T)
BL.play(2.42, "Withdraw", 1, speed=0.7)
shell = BL.cells["Withdraw"][-1]
BL.frame.add(2.42 + BL.dur("Withdraw", 1, None, 0.7), shell)
flame_src = (CX + MOUTH[0], FLOOR + MOUTH[1])
flame_stream(hit, 3.8, flame_src, lambda tt: BL.xat(tt) - 14, spread=8)
BL.x.hold(2.75); BL.x.add(3.8, (BX + 18, 0), "out")
for k, tt in enumerate([2.8, 3.05, 3.3, 3.55, 3.8]):
    puff(tt, (BX - 10 + k * 4, FLOOR - 16), 3, 6, 0.55, "smoke", rise=26)
    impact(tt, (BX - 6 + k * 4, FLOOR - 14 - (k % 2) * 8))

# 4.1  Hydro Pump
BL.play(4.0, "Withdraw", 1, speed=0.7, reverse=True)
BL.play(4.3, "Idle", until=T)
BL.x.hold(4.3); BL.x.add(4.6, (BX, 0), "inout")
t = 4.6
hit = t + BL.dur("Shoot", 0, 2, 0.7)
BL.play(t, "Shoot", 0, 2, speed=0.7)
BL.play(hit, "Shoot", 2, 4, speed=0.4, until=5.75)
BL.play(5.75, "Shoot", 4, speed=0.7)
BL.play(6.0, "Idle", until=T)
cannon = (BX + CANNON[0], FLOOR + CANNON[1])
water_end = Track(cannon[0])             # where the beam ends (its tip)
water_vis = Track(0)
water_end.hold(hit); water_vis.set(hit, 1)
water_end.add(hit + 0.16, CX + 16, "lin")
CH.x.hold(hit + 0.16); CH.x.add(5.7, (CX - 55, 0), "out")
water_end.add(5.7, CX - 55 + 16, "out")
water_end.add(5.85, CX - 30, "in"); water_vis.add(5.85, 0, "in")
CH.play(hit + 0.16, "Hurt", until=5.7)
CH.play(5.7, "Idle", until=T)
shake(hit + 0.16, 3, 0.4)
impact(hit + 0.16, (CX + 14, cannon[1] + 2), blue=True)
for k in range(9):
    tt = hit + 0.2 + k * 0.12
    puff(tt, (CH.xat(tt) + 10, cannon[1] + 4), 2, 6, 0.6, "steam", rise=30)
    puff(tt + 0.05, (CH.xat(tt) + 12, cannon[1] - 2), 2, 4, 0.4, "water", rise=-14, spread=26)

# 5.9  Charge, rush, impact
CX2 = CX - 55
t = 6.0
CH.play(t, "Charge", speed=0.9)
c_end = t + CH.dur("Charge", speed=0.9)
CH.play(c_end, "Charge", speed=0.9)
c_end += CH.dur("Charge", speed=0.9)
rush = c_end + CH.dur("Attack", 0, 2)
hit = rush + CH.dur("Attack", 2, 5)
CH.play(c_end, "Attack", 0, 5)
CH.frame.add(hit, CH.cells["Attack"][5])
CH.x.hold(rush); CH.x.add(hit, (BX - 70, 0), "in")
speed_lines(rush, hit, CH, 1, FLOOR - 40)
impact(hit, (BX - 30, MID_Y), big=True)
shake(hit, 5, 0.4)
STOP = 0.09                               # hit-stop
CH.play(hit + STOP, "Attack", 5, speed=0.8)
BL.play(hit + STOP, "Hurt", until=hit + 0.75)
BL.play(hit + 0.75, "Idle", until=T)
BL.x.hold(hit + STOP); BL.x.add(hit + 0.55, (BX + 75, 0), "out")
BL.hop(hit + STOP, hit + 0.45, 16)
puff(hit + 0.45, (BX + 70, FLOOR - 4), 4, 6, 0.6, "smoke", rise=14, spread=30)
for k in range(5):
    puff(c_end - 0.5 + k * 0.1, (CX2 + (k - 2) * 6, FLOOR - 6), 1, 5, 0.45, "smoke", rise=18, spread=10)

# 7.1  hop back, Rapid Spin
t = hit + 0.55
CH.play(t, "Hop", speed=0.9)
CH.x.hold(t); CH.x.add(t + CH.dur("Hop", speed=0.9), (CX, 0), "inout")
CH.play(t + CH.dur("Hop", speed=0.9), "Idle", until=T)
BL.x.hold(7.6); BL.x.add(7.9, (BX, 0), "inout")
t = 8.0
spin_hit = t + 0.42
BL.play(t, "Ricochet", 3, speed=1.3, until=spin_hit + 0.5)
BL.x.hold(t + 0.05); BL.x.add(spin_hit, (CX + 62, 0), "in")
speed_lines(t + 0.1, spin_hit, BL, -1, FLOOR - 26)
impact(spin_hit, (CX + 26, FLOOR - 36), big=True, blue=True)
shake(spin_hit, 5, 0.35)
CH.play(spin_hit + STOP, "Hurt", until=spin_hit + 0.85)
CH.play(spin_hit + 0.85, "Idle", until=T)
CH.x.hold(spin_hit + STOP); CH.x.add(spin_hit + 0.6, (CX - 70, 0), "out")
CH.hop(spin_hit + STOP, spin_hit + 0.5, 22)
puff(spin_hit + 0.5, (CX - 70, FLOOR - 4), 4, 6, 0.6, "smoke", rise=14, spread=30)
BL.x.hold(spin_hit + STOP); BL.x.add(spin_hit + 0.5, (BX, 0), "out")
BL.hop(spin_hit + STOP, spin_hit + 0.5, 12)
BL.play(spin_hit + 0.5, "Idle", until=T)
CH.x.hold(9.25); CH.x.add(9.6, (CX, 0), "inout")
CH.play(9.25, "Walk", until=9.6)
CH.play(9.6, "Idle", until=T)

# 9.7  both charge, page rumbles
t = 9.7
CH.play(t, "Charge", until=10.7)
BL.play(t, "Charge", until=10.7)
for k in range(5):
    tt = t + k * 0.2
    for mon, ring, x0 in ((CH, "ring", CX), (BL, "ring_b", BX)):
        r = FX[ring].get(tt)
        r.fly(tt, 0.45, (x0, FLOOR - 26), (x0, FLOOR - 26), 3.2, 0.8, "in", op0=0.8, fade_at=0.4)
SHAKE.hold(t)
for k in range(30):
    SHAKE.add(t + 0.033 * (k + 1), ((rnd(k + 99) - 0.5) * 1.6, (rnd(k + 199) - 0.5) * 1.0))
SHAKE.add(t + 1.05, (0, 0))

# 10.8  beam clash
t = 10.8
c_hit = t + CH.dur("Shoot", 0, 2, 0.8)
b_hit = t + BL.dur("Shoot", 0, 2, 0.7)
CH.play(t, "Shoot", 0, 2, speed=0.8)
CH.play(c_hit, "Shoot", 2, 5, speed=0.5, until=12.45)
BL.play(t, "Shoot", 0, 2, speed=0.7)
BL.play(b_hit, "Shoot", 2, 4, speed=0.4, until=12.45)
flame_src = (CX + MOUTH[0], FLOOR + MOUTH[1])
cannon = (BX + CANNON[0], FLOOR + CANNON[1])
CLASH = Track(415)
CLASH.hold(b_hit + 0.15)
for tt, x, e in [(11.3, 455, "inout"), (11.6, 380, "inout"), (11.95, 440, "inout"), (12.25, 400, "inout"),
                 (12.45, 415, "inout")]:
    CLASH.add(tt, x, e)


def clash_x(tt):
    ks = CLASH.keys
    for (t0, v0, _), (t1, v1, _) in zip(ks, ks[1:]):
        if t0 <= tt <= t1:
            return v0 + (v1 - v0) * (tt - t0) / (t1 - t0)
    return ks[-1][1]


flame_stream(c_hit, 12.4, flame_src, lambda tt: clash_x(tt) if tt > b_hit + 0.15 else BX - 30, spread=8)
water_end.hold(b_hit); water_vis.set(b_hit, 1)
water_end.add(b_hit + 0.15, 415, "lin")
for tt, v, e in CLASH.keys[1:]:
    if tt > b_hit + 0.15:
        water_end.add(tt, v + 6, e)
water_vis.hold(12.45)
water_vis.set(12.47, 0)
tt = b_hit + 0.2
while tt < 12.4:
    puff(tt, (clash_x(tt), (flame_src[1] + cannon[1]) / 2), 2, 9, 0.7, "steam", rise=36, spread=24)
    tt += 0.09

# 12.45  BOOM
boom = 12.47
FLASH.hold(boom - 0.02)
FLASH.add(boom, 1)
FLASH.add(boom + 0.08, 1)
FLASH.add(boom + 0.7, 0, "out")
shake(boom, 7, 0.6)
bx = (415, FLOOR - 50)
impact(boom, bx, big=True)
impact(boom + 0.05, bx, big=True, blue=True)
for k in range(18):
    a = k / 18 * 2 * math.pi + rnd(k + 70)
    d = 0.25 + rnd(k + 80) * 0.75                 # spread over the whole cloud, not just its rim
    p = FX["smoke"].get(boom)
    p.fly(boom + 0.05 + rnd(k + 90) * 0.08, 1.2 + rnd(k + 60) * 0.5, bx,
          (bx[0] + math.cos(a) * 95 * d, bx[1] + math.sin(a) * 38 * d - 18), 6, 14 + rnd(k + 40) * 14, "out",
          op0=0.85, fade_at=0.4)
for k in range(8):
    puff(boom + 0.3 + k * 0.08, (bx[0] + (rnd(k + 50) - 0.5) * 140, FLOOR - 10), 2, 10, 1.0, "smoke", rise=30, spread=30)
CH.play(boom, "Hurt", until=13.4)
BL.play(boom, "Hurt", until=13.4)
CH.x.hold(boom); CH.x.add(13.2, (85, 0), "out"); CH.hop(boom, 13.2, 30)
BL.x.hold(boom); BL.x.add(13.2, (745, 0), "out"); BL.hop(boom, 13.2, 30)
puff(13.2, (85, FLOOR - 4), 4, 6, 0.6, "smoke", rise=14, spread=30)
puff(13.2, (745, FLOOR - 4), 4, 6, 0.6, "smoke", rise=14, spread=30)

# 13.4  out cold
CH.play(13.4, "Sleep", until=15.4)
BL.play(13.4, "Sleep", until=15.4)
snore(13.6, 15.4, (85 + 6, FLOOR - 50))
snore(13.6, 15.4, (745 + 6, FLOOR - 44), 0.25)

# 15.4  get up, turn around, walk off
CH.play(15.4, "Idle", until=15.75)
BL.play(15.4, "Idle", until=15.75)
CH.face.set(15.75, -1)
BL.face.set(15.75, -1)
CH.play(15.75, "Walk", until=T)
BL.play(15.75, "Walk", until=T)
CH.x.hold(15.75); CH.x.add(17.5, (-90, 0), "in")
BL.x.hold(15.75); BL.x.add(17.5, (920, 0), "in")
CH.face.set(T - 0.05, 1)
BL.face.set(T - 0.05, 1)
CH.frame.add(T - 0.05, CH.cells["Idle"][0])
BL.frame.add(T - 0.05, BL.cells["Idle"][0])


# ---------------------------------------------------------------- Gengar, up in the text
class Glyph:
    """A piece of the copy that can be picked up. Drawn centred on 0,0 so it spins and shrinks in place."""

    def __init__(self, ch, cx, cy, size, dy, bold=False):
        self.ch, self.size, self.dy, self.bold = ch, size, dy, bold
        self.home = (cx, cy)
        self.pos = Track((cx, cy))
        self.sc = Track(1.0)
        self.rot = Track(0.0)
        self.op = Track(1)

    def arc(self, t0, t1, to, lift=14):
        x0, y0 = self.pos.v
        self.pos.hold(t0)
        self.pos.add((t0 + t1) / 2, ((x0 + to[0]) / 2, min(y0, to[1]) - lift), "out")
        self.pos.add(t1, to, "in")

    def bounce(self, t, h=4):
        x, y = self.pos.v
        self.pos.hold(t)
        self.pos.add(t + 0.08, (x, y - h), "out")
        self.pos.add(t + 0.16, (x, y), "in")

    def svg(self, p):
        rot = animate(self.rot, "transform", n, "rotate")
        sc = animate(self.sc, "transform", lambda v: f"{v:.2f} {v:.2f}", "scale")
        op = animate(self.op, "opacity", n, discrete=True)
        fw = ' font-weight="600"' if self.bold else ""
        txt = (f'<text x="0" y="{n(self.dy)}" font-size="{self.size}"{fw} text-anchor="middle" '
               f'fill="{p["fg"]}">{html.escape(self.ch)}</text>')
        inner = f'<g>{rot}<g>{sc}{txt}</g></g>'
        return f'<g opacity="{static(self.op)}">{op}' + g_translate(self.pos, inner) + "</g>"


H1_W = FONT_H1.getlength(H1_TEXT)
WORD1_W = FONT.getlength(PARA[0])
LETTERS, _x = [], WORD1_W + FONT.getlength(" ")
for _c in PARA[1]:
    _w = FONT.getlength(_c)
    LETTERS.append(Glyph(_c, _x + _w / 2, P_Y - 5.5, 16, 5.5))
    _x += _w
WORD2_END = _x
EMOJI = Glyph(H1_EMOJI, H1_W + FONT_H1.getlength(" ") + 18, H1_Y - 11, 32, 11)

GG = Mon("gengar", 0, ["Idle", "Walk", "Sink", "Pose", "Eat", "Charge", "Cringe", "Shoot", "Nod", "Pull"],
         650, floor=RULE_Y + 2)
GG.op = Track(0)
G_MOUTH = (0, -11 * S)                # front-facing, from the feet
PARA_DY = P_Y + 5 - GG.floor          # standing on the paragraph line instead of the rule
PUDDLE = Track((650, 0.0))            # (x, size) of the shadow pool Gengar comes out of


def g_mouth(t):
    return (GG.xat(t) + G_MOUTH[0], GG.floor + PARA_DY + G_MOUTH[1])


# 0.5  rises out of the rule, grins
PUDDLE.hold(0.3); PUDDLE.add(0.5, (650, 1.0), "out")
GG.op.set(0.5, 1)
t = GG.play(0.5, "Sink", reverse=True)
PUDDLE.hold(t); PUDDLE.add(t + 0.3, (650, 0.0), "in")
t = GG.play(t, "Pose")
GG.play(t + 0.25, "Idle", until=T)

# 2.3  floats down to "developer"
GX_P = WORD2_END + 36
GG.play(2.3, "Walk", until=3.25)
GG.x.hold(2.3); GG.x.add(3.25, (GX_P, 0), "inout")
GG.y.hold(2.3); GG.y.add(2.75, (0, -10), "out"); GG.y.add(3.25, (0, PARA_DY), "inout")
GG.play(3.25, "Idle", until=T)

# 3.5  eats it, last letter first
GG.play(3.45, "Eat", until=6.15)
for k, g in enumerate(reversed(LETTERS)):
    te = 3.5 + k * 0.28
    g.arc(te, te + 0.25, g_mouth(te), lift=12)
    g.sc.hold(te); g.sc.add(te + 0.25, 0.3, "in")
    g.rot.hold(te); g.rot.add(te + 0.25, -180, "in")
    g.op.set(te + 0.25, 0)

# 6.15  licks its lips. Then the aftertaste kicks in
GG.play(6.15, "Charge", until=6.75)
GG.play(6.75, "Cringe", until=7.35)
GG.x.hold(6.75)
for k in range(10):
    GG.x.add(6.8 + k * 0.05, (GX_P + (2 if k % 2 else -2), 0))
GG.x.add(7.35, (GX_P, 0))

# 7.35  spits it back out. Backwards.
t = 7.35
spit = t + GG.dur("Shoot", 0, 4)
GG.play(t, "Shoot", 0, 5)
GG.play(spit + 0.25, "Shoot", 5, speed=1.4)
GG.play(spit + 0.6, "Idle", until=T)
n_l = len(LETTERS)
for i, g in enumerate(LETTERS):
    ts = spit + 0.03 * (n_l - 1 - i)
    g.pos.set(ts, g_mouth(ts))
    g.op.set(ts, 1)
    g.sc.set(ts, 0.3); g.sc.add(ts + 0.38, 1.0, "out")
    g.rot.set(ts, 200); g.rot.add(ts + 0.38, 0, "out")
    g.arc(ts, ts + 0.38, LETTERS[n_l - 1 - i].home, lift=26)
    g.bounce(ts + 0.38)

# 8.6  the letters sort themselves out
for i, g in enumerate(LETTERS):
    tu = 8.6 + 0.05 * i
    g.arc(tu, tu + 0.4, g.home, lift=12 if i % 2 else -10)
    g.bounce(tu + 0.4, 3)
GG.play(9.3, "Nod", speed=0.8)
GG.play(9.3 + GG.dur("Nod", speed=0.8), "Idle", until=T)

# 9.8  floats up to the heading and yanks the wave off it
GX_E = EMOJI.home[0] + 54
GG.play(9.8, "Walk", until=10.55)
GG.x.hold(9.8); GG.x.add(10.55, (GX_E, 0), "inout")
GG.y.hold(9.8); GG.y.add(10.55, (0, 0), "inout")
GG.play(10.6, "Pull", until=11.3)
EMOJI.rot.hold(10.65)
for k in range(8):
    EMOJI.rot.add(10.7 + k * 0.075, 10 if k % 2 else -10)
pop = 11.3
puff(pop, EMOJI.home, 4, 5, 0.45, "smoke", rise=12, spread=20)
HAND = (GX_E - 32, GG.floor - 24)
EMOJI.rot.add(pop + 0.3, -20, "out")
EMOJI.sc.hold(pop); EMOJI.sc.add(pop + 0.3, 0.75, "out")
EMOJI.arc(pop, pop + 0.3, HAND, lift=6)
GG.play(pop, "Pose")
GG.play(pop + GG.dur("Pose") + 0.1, "Idle", until=T)

# 11.7  waves it at you. Hi!
k = 0
while EMOJI.rot.t < 12.4:
    EMOJI.rot.add(EMOJI.rot.t + 0.2, 25 if k % 2 else -25, "inout")
    k += 1

# 12.47  the explosion below startles it: drops the wave and sinks into the rule
GG.play(boom, "Cringe", until=13.15)
GG.y.hold(boom); GG.y.add(boom + 0.1, (0, -8), "out"); GG.y.add(boom + 0.3, (0, 0), "in")
EMOJI.rot.hold(boom); EMOJI.rot.add(boom + 0.35, 0, "out")
EMOJI.sc.hold(boom); EMOJI.sc.add(boom + 0.35, 1.0, "out")
EMOJI.arc(boom + 0.02, boom + 0.4, EMOJI.home, lift=18)
EMOJI.bounce(boom + 0.4, 5)
PUDDLE.set(13.0, (GX_E, 0.0)); PUDDLE.add(13.2, (GX_E, 1.0), "out")
t = GG.play(13.2, "Sink")
GG.op.set(t + 0.05, 0)
PUDDLE.hold(t); PUDDLE.add(t + 0.3, (GX_E, 0.0), "in")


def puddle(p):
    pos = Track((650, RULE_Y + 1))
    pos.keys = [[t, (v[0], RULE_Y + 1), e] for t, v, e in PUDDLE.keys]
    size = Track(0.0)
    size.keys = [[t, v[1], e] for t, v, e in PUDDLE.keys]
    sc = animate(size, "transform", lambda v: f"{v:.2f} {v:.2f}", "scale")
    pool = (f'<g transform="scale(0 0)">{sc}<ellipse rx="22" ry="4" fill="#4b2a7b" opacity="0.75"/>'
            f'<ellipse rx="13" ry="2.2" fill="#2a1450" opacity="0.8"/></g>')
    return g_translate(pos, pool)


# ---------------------------------------------------------------- output
def water_beam(p):
    """Hydro Pump: a beam from the cannon to water_end, drawn as a scaled bar plus a foamy tip."""
    length = Track(0.0)
    length.keys = [[t, max(0.01, cannon[0] - v), e] for t, v, e in water_end.keys]
    sx = animate(length, "transform", lambda v: f"{-v:.1f} 1", "scale")
    vis = animate(water_vis, "opacity", n, discrete=True)
    bar = (f'<g transform="translate({n(cannon[0])} {n(cannon[1])})">'
           f'<g transform="scale(-0.01 1)">{sx}'
           f'<rect x="0" y="-7" width="1" height="14" fill="{WATER[0]}" opacity="0.85"/>'
           f'<rect x="0" y="-4.5" width="1" height="9" fill="{WATER[1]}"/>'
           f'<rect x="0" y="-1.6" width="1" height="3.2" fill="{WATER[3]}" opacity="0.9"/></g></g>')
    tip_track = Track((cannon[0], cannon[1]))
    tip_track.keys = [[t, (v, cannon[1]), e] for t, v, e in water_end.keys]
    tip = g_translate(tip_track, f'<circle r="9" fill="{WATER[1]}"/><circle r="5" cx="2" fill="{WATER[3]}"/>')
    wob = Track(0)
    k = 0
    while wob.t < T - 0.05:
        wob.add(wob.t + 0.05, (rnd(k + 300) - 0.5) * 2.5)
        k += 1
    wobble = animate(wob, "transform", lambda v: f"0 {n(v)}", "translate")
    return f'<g opacity="0">{vis}<g>{wobble}{bar}{tip}</g></g>'


def build(mode):
    p = PALETTES[mode]
    defs = ""
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="{html.escape(FONT_STACK, quote=True)}">{defs}',
           f'<rect width="{W}" height="{H}" fill="{p["bg"]}"/>']
    page = [f'<text x="0" y="{H1_Y}" font-size="32" font-weight="600" fill="{p["fg"]}" '
            f'textLength="{n(H1_W)}">{html.escape(H1_TEXT)}</text>',
            f'<path d="M0,{RULE_Y} H{W}" stroke="{p["rule"]}" stroke-width="1"/>',
            f'<text x="0" y="{P_Y}" font-size="16" fill="{p["fg"]}" textLength="{n(WORD1_W)}">{PARA[0]}</text>',
            puddle(p), GG.svg(p, "gengar")]
    page += [g.svg(p) for g in LETTERS + [EMOJI]]
    page += [CH.shadow_svg(p), BL.shadow_svg(p), BL.svg(p, "blastoise"), CH.svg(p, "charizard"),
             water_beam(p)]
    for pool in FX.values():
        for pl in (pool if isinstance(pool, list) else [pool]):
            page.append(pl.svg(p))
    out.append(g_translate(SHAKE, "".join(page)))
    out.append(f'<rect width="{W}" height="{H}" fill="{p["flash"]}" opacity="0">'
               + animate(FLASH, "opacity", lambda v: f"{v:.2f}") + "</rect>")
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    for mode in PALETTES:
        svg = build(mode)
        (HERE / f"battle-{mode}.svg").write_text(svg)
        print(f"battle-{mode}.svg  {len(svg) / 1024:.0f} KB")
