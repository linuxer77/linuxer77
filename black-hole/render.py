"""Build the script-free README animation with NumPy and Pillow.

Run python3 black-hole/render.py after editing the artwork or timing.
"""

from base64 import b64encode
from io import BytesIO
from math import atan2, cos, hypot, pi, sin, sqrt
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

WIDTH, HEIGHT = 880, 300
CENTER_X, CENTER_Y = 440, 145
FIRST_PICKUP = 2.8
CAPTURE_INTERVAL = 0.43
FALL_TIME = .68
TRACK_Y = HEIGHT * .74
SHADOW = sqrt(27)
DISK_SPAN = 44
DISK_WIDTH = 352
DISK_HEIGHT = 160
SENTENCE = "Buidling random shit that pops up in my head"
FONT_SIZE = 30
TEXT_LEFT = 54
TEXT_BASELINE = 64
TRACKING = 0.12

# Arial-compatible advances in thousandths of an em.
ADVANCES = {
    " ": 278, "B": 667, "a": 556, "d": 556, "e": 556, "g": 556, "h": 556,
    "i": 222, "l": 222, "m": 833, "n": 556, "o": 556, "p": 556, "r": 333,
    "s": 500, "t": 278, "u": 556, "y": 500,
}

STYLE = """
  svg { color-scheme: light dark; --title:#202830; }
  @media (prefers-color-scheme: dark) {
    svg { --title:#f0f4fa; }
  }
  text {
    font-family:Arial, "Liberation Sans", sans-serif;
    font-weight:400;
    text-anchor:middle;
    fill:var(--title);
  }
  .motion { opacity:0; transform-origin:0 0; }
"""


def photon_paths():
    """Trace Schwarzschild null rays backward from a distant camera, in units G=M=c=1."""
    impact = np.linspace(0.2, DISK_SPAN / 2 + 3, 5201)
    angles = np.linspace(0, 4 * np.pi, 1259)
    step = angles[1]
    inverse_radius = np.zeros_like(impact)
    velocity = 1 / impact
    alive = np.ones_like(impact, dtype=bool)
    path = np.zeros((angles.size, impact.size), dtype=np.float32)

    # The orbit equation for inverse radius u is u'' = 3u² - u.
    # Velocity Verlet keeps the two turning branches continuous at closest approach.
    for row in path[1:]:
        half_velocity = velocity + step * 0.5 * (3 * inverse_radius**2 - inverse_radius)
        next_radius = inverse_radius + step * half_velocity
        alive &= (next_radius > 0) & (next_radius < 0.5)
        inverse_radius = np.where(alive, next_radius, 0)
        velocity = np.where(
            alive, half_velocity + step * 0.5 * (3 * inverse_radius**2 - inverse_radius), 0
        )
        row[:] = inverse_radius
    return impact, angles, path


def sample_paths(path, impact_index, angle_index):
    x, y = impact_index.astype(int), angle_index.astype(int)
    fx, fy = impact_index - x, angle_index - y
    upper = path[y, x] * (1 - fx) + path[y, x + 1] * fx
    lower = path[y + 1, x] * (1 - fx) + path[y + 1, x + 1] * fx
    return upper * (1 - fy) + lower * fy


def disk_frame(impact, angles, path, phase):
    """Color the first optically thick disk intersection along each light ray."""
    spacing = DISK_SPAN / DISK_WIDTH
    x = (np.arange(DISK_WIDTH) + 0.5 - DISK_WIDTH / 2) * spacing
    y = (DISK_HEIGHT / 2 - np.arange(DISK_HEIGHT) - 0.5) * spacing
    x, y = np.meshgrid(x, y)
    b = np.hypot(x, y)
    inclination = np.deg2rad(9)
    # A ray lies in a plane through the center. Solve z(phi)=0 for its disk crossings.
    crossing = np.arctan2(np.sin(inclination), -y / b * np.cos(inclination))
    impact_index = (np.clip(b, impact[0], impact[-1] - 0.01) - impact[0]) / (impact[1] - impact[0])
    rgb = np.zeros((*b.shape, 3))
    shadow = np.clip((SHADOW - b) / spacing + 0.5, 0, 1)
    alpha = shadow.copy()
    opaque = np.zeros_like(b, dtype=bool)

    for order in range(4):
        angle = crossing + order * np.pi
        u = sample_paths(path, impact_index, angle / angles[1])
        radius = np.divide(1, u, out=np.full_like(u, 1000), where=u > 0)
        hit = (radius >= 6) & (radius < 21.2) & ~opaque
        if not hit.any():
            continue
        opaque |= hit
        r, a = radius[hit], angle[hit]
        azimuth = np.arctan2(
            np.cos(inclination) * np.cos(a) - y[hit] / b[hit] * np.sin(inclination) * np.sin(a),
            x[hit] / b[hit] * np.sin(a),
        )

        # Frequency shift for photons from circular Keplerian emitters.
        angular_momentum = -x[hit] * np.cos(inclination)
        shift = np.sqrt(1 - 3 / r) / (1 - angular_momentum / r**1.5)
        # Advect emission around the same lensed disk. The inner wisps lap the
        # cooler outer gas twice per texture loop, following the Portfolio disk.
        log_r = np.log(r)
        inner = np.clip((15 - r) / 7, 0, 1)
        ripple = 48 * log_r + 2 * azimuth + 1.3 * np.sin(5 * azimuth - phase)
        bands = (0.55 + 0.15 * np.sin(23 * log_r + 3 * azimuth - phase)
                 + 0.14 * np.sin(ripple - phase)
                 + inner * 0.14 * np.sin(82 * log_r - 4 * azimuth + 2 * phase))
        edge = np.minimum(np.clip((r - 6) / 0.35, 0, 1), np.clip((21.2 - r) / 5.1, 0, 1))
        intensity = 4.7 * bands * (6 / r)**1.9 * shift**3.5 * edge
        brightness = 1 - np.exp(-intensity)
        heat = np.clip(1.12 * brightness + 0.21 * (shift - 0.65), 0, 1)
        cool = np.array([224, 66, 22])
        hot = np.array([255, 248, 224])
        emission = 1 - np.exp(-2.6 * intensity)
        alpha[hit] = emission + (1 - emission) * shadow[hit]
        weight = np.divide(emission, alpha[hit], out=np.zeros_like(emission), where=alpha[hit] > 0)
        rgb[hit] = (cool + (hot - cool) * heat[:, None]) * weight[:, None]

    plasma = np.asarray(np.dstack((rgb, alpha * 255)).round(), dtype=np.uint8)
    image = Image.fromarray(plasma)
    glow_alpha = Image.fromarray(
        np.asarray(np.where(opaque, (alpha - shadow).clip(0) * 120, 0), dtype=np.uint8)
    ).filter(ImageFilter.GaussianBlur(6))
    glow = Image.new("RGBA", image.size, (233, 105, 43))
    glow.putalpha(glow_alpha)
    return Image.alpha_composite(glow, image)


def render_disk():
    rays = photon_paths()
    frames = [disk_frame(*rays, 2 * pi * i / 24) for i in range(24)]
    data = BytesIO()
    frames[0].save(data, format="WEBP", save_all=True, append_images=frames[1:],
                   duration=100, loop=0, quality=72, alpha_quality=80, method=4)
    return b64encode(data.getvalue()).decode()


def smooth(start, end, time):
    p = min(1, max(0, (time - start) / (end - start)))
    return p * p * (3 - 2 * p)


def matrix(x, y, angle, radial, tangent, roll):
    """Apply the local radial and tangential magnification, then the letter's rotation."""
    c, s = cos(angle), sin(angle)
    xx = radial * c * c + tangent * s * s
    yy = radial * s * s + tangent * c * c
    xy = (radial - tangent) * c * s
    cr, sr = cos(roll), sin(roll)
    values = (xx * cr + xy * sr, xy * cr + yy * sr, xy * cr - xx * sr, yy * cr - xy * sr)
    return f"matrix({','.join(f'{n:.3f}' for n in values)},{x:.2f},{y:.2f})"


def layout():
    glyphs = []
    left = TEXT_LEFT - CENTER_X
    y = TEXT_BASELINE - CENTER_Y - FONT_SIZE * .345
    for char in SENTENCE:
        width = ADVANCES[char] * FONT_SIZE / 1000
        if char != " ":
            glyphs.append((left + width / 2, y, char, width))
        left += width + TRACKING
    return glyphs


GLYPHS = layout()
LAST_CAPTURE = FIRST_PICKUP + (len(GLYPHS) - 1) * CAPTURE_INTERVAL + FALL_TIME
COLLAPSE = LAST_CAPTURE + 0.68
DOT = COLLAPSE + 1.15
BANG = DOT + 0.28
DURATION = BANG + 4.2
# Like Portfolio's swallow(), add the area of each captured glyph to the mass.
MASS = np.r_[0, np.cumsum([w * FONT_SIZE for _, _, _, w in GLYPHS])]
RADII = 3.0 + 0.18 * np.sqrt(MASS)
# Leave room ahead of the shadow for the next letter to peel off the page.
first_x = GLYPHS[0][0]
TRACK = np.maximum.accumulate([
    x - r - 9 - 20 * smooth(first_x, first_x + 100, x)
    for (x, _, _, _), r in zip(GLYPHS, RADII)
])


def hole(time):
    progress = min(len(GLYPHS), max(0, (time - FIRST_PICKUP) / CAPTURE_INTERVAL))
    arrivals = np.clip((time - FIRST_PICKUP - FALL_TIME) / CAPTURE_INTERVAL + 1, 0, len(GLYPHS))
    eaten = int(arrivals)
    prev = max(0, eaten - 1)
    radius = RADII[prev] + (RADII[eaten] - RADII[prev]) * smooth(0, .36, arrivals - eaten)
    if time >= LAST_CAPTURE:
        radius = RADII[-2] + (RADII[-1] - RADII[-2]) * smooth(LAST_CAPTURE, LAST_CAPTURE + .16, time)
    x = np.interp(progress, range(len(TRACK)), TRACK)
    if time < FIRST_PICKUP:
        x = -WIDTH / 2 - 18 + (TRACK[0] + WIDTH / 2 + 18) * smooth(.85, FIRST_PICKUP, time)
    drift = smooth(LAST_CAPTURE - CAPTURE_INTERVAL, COLLAPSE, time)
    y = TRACK_Y - CENTER_Y + .18 * radius + 3 * sin(progress * .2)
    return x + 13 * drift, y, radius


def lensed(x, y, time):
    cx, cy, radius = hole(time)
    dx, dy = x - cx, y - cy
    d = hypot(dx, dy)
    reach = 3 * radius + 175
    einstein = radius * 1.25 * (1 - smooth(reach * .45, reach, d))
    gap = hypot(d, 2 * einstein)
    magnification = (1 + gap / d) / 2
    return (cx + dx * magnification, cy + dy * magnification, atan2(dy, dx),
            (1 + d / gap) / 2, magnification)


def spiral(dx, dy, radius):
    """Integrate Portfolio's tangential launch, inward acceleration, and orbital drag."""
    distance = hypot(dx, dy)
    gravity = 26000 + radius * 900
    speed = sqrt(gravity) * .62
    vx = (-dy * speed - dx * 30) / distance
    vy = (dx * speed - dy * 30) / distance
    points = [(dx, dy)]
    while distance > radius * .9:
        dt = max(.12, sqrt(max(0, 1 - radius / distance))) / 120
        acceleration = gravity / max(distance, radius)
        vx = (vx - dx / distance * acceleration * dt) * (1 - .85 * dt)
        vy = (vy - dy / distance * acceleration * dt) * (1 - .85 * dt)
        dx, dy = dx + vx * dt, dy + vy * dt
        distance = hypot(dx, dy)
        points.append((dx, dy))
    return np.asarray(points)


def keyframes(name, samples):
    rules = [f"    {time / DURATION:.5%} {{ {properties} }}" for time, properties in samples]
    return (f"  @keyframes {name} {{\n" + "\n".join(rules) + "\n  }\n"
            + f"  .{name} {{ animation:{name} {DURATION:.3f}s linear infinite; }}")


def pose(transform, opacity=1):
    return f"transform:{transform}; opacity:{opacity:.3f};"


def build_letters():
    styles, elements = [], []
    bx, by, _ = hole(BANG)
    for i, (x, y, char, _) in enumerate(GLYPHS):
        start = FIRST_PICKUP + i * CAPTURE_INTERVAL
        home = f"translate({x:.2f}px,{y:.2f}px)"
        frames = [(0, pose(home))]
        # Keep distant type anchored and sample the lens as it travels past.
        for t in np.linspace(max(.85, start - 4), start, 23):
            lx, ly, angle, radial, tangent = lensed(x, y, t)
            frames.append((t, pose(matrix(lx, ly, angle, radial, tangent, 0))))
        cx, cy, radius = hole(start)
        # A long accelerating fall delivers the glyph to the local capture orbit.
        # Keeping that orbit close to the horizon lets it fit beneath the text.
        dx0, dy0 = lx - cx, ly - cy
        orbit_fraction = (radius + 29) / hypot(dx0, dy0)
        orbit = spiral(dx0 * orbit_fraction, dy0 * orbit_fraction, radius)
        for p in np.linspace(0, 1, 32)[1:]:
            t = start + p * FALL_TIME
            cx, cy, _ = hole(t)
            if p < .57:
                q = p / .57
                approach = 1 - (1 - orbit_fraction) * q**1.85
                dx = dx0 * approach + 14 * sin(pi * q)**2
                dy = dy0 * approach
            else:
                dx, dy = orbit[round((p - .57) / .43 * (len(orbit) - 1))]
            size = 1 - .92 * smooth(.05, 1, p)
            stretch = 1 + 1.8 * smooth(.2, .87, p)
            transform = matrix(cx + dx, cy + dy, atan2(dy, dx),
                               radial * size * stretch, tangent * size / stretch, -2.5 * p)
            frames.append((t, pose(transform, 1 - smooth(.87, 1, p))))
        # Eject each glyph with its own momentum, then bend the trajectory home.
        rng = np.random.default_rng(810 + i)
        azimuth = rng.uniform(0, 2 * pi)
        speed = rng.uniform(70, 155)
        release = BANG + .06 + hypot(x - bx, y - by) / 2100 + rng.uniform(0, .09)
        duration = rng.uniform(1.16, 1.66)
        for p in np.linspace(0, 1, 33):
            t = release + p * duration
            kick = 8 * p * (1 - p)**3
            travel = smooth(.02, 1, p)
            size = .08 + .92 * smooth(0, .67, p)
            transform = matrix(bx + (x - bx) * travel + kick * speed * cos(azimuth),
                               by + (y - by) * travel + kick * speed * sin(azimuth) * .40,
                               0, size, size, 2.6 * sin(azimuth) * (1 - travel))
            frames.append((t, pose(transform, smooth(.025, .2, p))))
        frames.append((DURATION, pose(home)))
        name = f"glyph-{i}"
        styles.append(keyframes(name, frames))
        elements.append(f'<g class="{name}" transform="translate({x:.2f} {y})">'
                        f'<text y="{FONT_SIZE * .345:.2f}">{escape(char)}</text></g>')
    return "\n".join(styles), "\n".join(elements)


def effect_styles():
    samples = []
    times = np.unique(np.r_[np.arange(0, DOT, .065), COLLAPSE, DOT, BANG, DURATION])
    for t in times:
        cx, cy, r = hole(t)
        shrink = 1 - smooth(COLLAPSE, DOT, t)
        scale = r / (SHADOW * 7.25) * shrink
        transform = f"translate({cx:.2f}px,{cy:.2f}px) scale({scale:.4f})"
        samples.append((t, pose(transform, 1 if t < DOT else 0)))
    styles = [keyframes("hole", samples)]
    point = [(0, 0, 0), (COLLAPSE, 0, .1), (DOT, 1, .63),
             (BANG, 1, .8), (BANG + .06, 0, .1), (DURATION, 0, 0)]
    styles.append(keyframes("point", [(t, pose(f"scale({scale})", opacity))
                                     for t, opacity, scale in point]))
    # The strip advances only after the dot bursts. Both ends of the strip are blank.
    styles.append(keyframes("ejecta", [
        (0, "transform:translateY(0);"),
        (BANG, f"transform:translateY(0); animation-timing-function:steps({BLAST_FRAMES},end);"),
        (BANG + BLAST_SECONDS, f"transform:translateY(-{BLAST_HEIGHT * BLAST_FRAMES}px);"),
        (DURATION, f"transform:translateY(-{BLAST_HEIGHT * BLAST_FRAMES}px);"),
    ]))
    return "\n".join(styles)


# Paint the burst across the entire banner so fast material can leave the frame.
BLAST_WIDTH, BLAST_HEIGHT = WIDTH, HEIGHT
BLAST_FRAMES, BLAST_SECONDS = 48, 1.8


def blast_strip():
    rng = np.random.default_rng(448)
    bx, by, _ = hole(BANG)
    ox, oy = bx + CENTER_X, by + CENTER_Y
    yy, xx = np.mgrid[:HEIGHT, :WIDTH]
    dx, dy = xx - ox, yy - oy
    # Shred the disk into ballistic filaments. Within each stream, nearby gas
    # shares a launch angle and speed, producing folds with distinct bright tips.
    streams, fibers = 38, 17
    side = rng.choice([-1, 1], (streams, 1))
    speed = side * rng.uniform(370, 1150, (streams, 1)) * rng.normal(1, .093, (streams, fibers))
    pitch = rng.normal(-.14, .21, (streams, 1)) + rng.normal(0, .014, speed.shape)
    curl = rng.uniform(-52, 52, (streams, 1)) + rng.normal(0, 3, speed.shape)
    launch = rng.uniform(0, .17, (streams, 1)) + rng.uniform(0, .035, speed.shape)
    length = rng.uniform(.07, .29, (streams, 1)) * rng.uniform(.6, 1.4, speed.shape)
    phase = rng.uniform(-.6, .6, (streams, 1))
    cool = rng.random((streams, 1)) < .31
    tint = np.where(cool, .12, rng.uniform(.66, 1, (streams, 1)))
    brightness = rng.uniform(.25, .95, speed.shape)
    strip = Image.new("RGBA", (WIDTH, HEIGHT * BLAST_FRAMES))

    for i in range(1, BLAST_FRAMES):
        t = i * BLAST_SECONDS / BLAST_FRAMES
        lines = Image.new("RGB", (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(lines)
        # Sample along each filament from its trailing, cooler end to its leading tip.
        age = np.maximum(0, t - launch)
        sample_age = age[..., None] * np.linspace(0, 1, 9)
        sample_age += np.maximum(age - length, 0)[..., None] * np.linspace(1, 0, 9)
        d = speed[..., None] * (1 - np.exp(-1.2 * sample_age)) / 1.2
        x = ox + d
        ripple = np.sin(5 * sample_age + phase[..., None]) - np.sin(phase[..., None])
        y = oy + pitch[..., None] * d + curl[..., None] * ripple
        power = brightness * (1 - np.exp(-age*26)) * np.exp(-1.6 * age)
        for index in np.ndindex(speed.shape):
            row, _ = index
            if power[index] < .035:
                continue
            warm = tint[row, 0]
            color = np.array([.38+.62*warm, .74-.10*warm, 1-.59*warm])
            for j in range(0, 8, 2):
                points = list(zip(x[index][j:j+3], y[index][j:j+3]))
                hot = .12 + .88 * ((j+2)/8)**2
                rgb = np.minimum(255, (color + hot*.2) * 315 * power[index] * hot)
                draw.line(points, fill=tuple(rgb.astype(int)), width=1)
        radiance = np.asarray(lines, dtype=float) / 255
        for blur, gain in [(2, 1.4), (9, 1.7)]:
            radiance += gain * np.asarray(lines.filter(ImageFilter.GaussianBlur(blur))) / 255
        # A short white diffraction spike and its blue halo extinguish before the
        # fastest streamers cross the page. All the later light comes from the debris.
        flash = np.exp(-8*t)
        spike = np.exp(-np.abs(dx)/(22+165*(1-np.exp(-9*t))) - (dy/(.9+1.8*flash))**2)
        core = np.exp(-np.hypot(dx, dy)/(3+15*flash))
        radiance += flash * (spike[..., None] * np.array([2.4, 3.1, 4.3])
                              + core[..., None] * np.array([6.5, 7.6, 9]))
        light = (1 - np.exp(-radiance)) * (1 - smooth(1.05, BLAST_SECONDS, t))
        alpha = light.max(axis=2)
        color = light / np.maximum(alpha[..., None], 1e-6)
        rgba = np.dstack((color, alpha))
        strip.paste(Image.fromarray(np.uint8(np.round(rgba * 255))), (0, i * HEIGHT))
    data = BytesIO()
    strip.save(data, format="WEBP", quality=81, alpha_quality=80, method=4)
    return b64encode(data.getvalue()).decode()


def build_svg():
    disk = render_disk()
    letters_style, letters = build_letters()
    bx, by, _ = hole(BANG)
    return f"""<!-- Generated by black-hole/render.py. -->
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="heading">
  <title id="heading">{escape(SENTENCE)}</title>
  <style>
{STYLE}
{letters_style}
{effect_styles()}
  @media (prefers-reduced-motion: reduce) {{
    * {{ animation:none !important; }}
  }}
  </style>
  <defs>
    <radialGradient id="point">
      <stop stop-color="#fff"/>
      <stop offset=".25" stop-color="#fff4d4"/>
      <stop offset="1" stop-color="#ef923c" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <g transform="translate({CENTER_X} {CENTER_Y})" font-size="{FONT_SIZE}" aria-hidden="true">
    <g>
      <svg x="{-CENTER_X}" y="{-CENTER_Y}" width="{BLAST_WIDTH}" height="{BLAST_HEIGHT}" overflow="hidden">
        <image class="ejecta" width="{BLAST_WIDTH}" height="{BLAST_HEIGHT * BLAST_FRAMES}" xlink:href="data:image/webp;base64,{blast_strip()}"/>
      </svg>
    </g>
{letters}
    <g class="motion hole">
      <g transform="rotate(-10)">
        <image x="-159.5" y="-72.2734375" width="319" height="144.546875" xlink:href="data:image/webp;base64,{disk}"/>
      </g>
    </g>
    <g transform="translate({bx:.2f} {by:.2f})">
    <g class="motion point">
      <circle r="12" fill="url(#point)"/>
      <circle r="1.5" fill="#fff7e7"/>
    </g>
    </g>
  </g>
</svg>
"""


if __name__ == "__main__":
    Path(__file__).with_name("tidal-sweep.svg").write_text(build_svg(), encoding="utf-8")
