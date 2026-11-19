"""Build the script-free README animation with NumPy and Pillow.

Run python3 black-hole/render.py after editing the artwork or timing.
"""

from base64 import b64encode
from io import BytesIO
from math import atan2, cos, hypot, pi, sin, sqrt
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image, ImageFilter

WIDTH, HEIGHT = 880, 300
CENTER_X, CENTER_Y = 440, 145
DURATION = 12
SHADOW = sqrt(27)
DISK_SPAN = 44
DISK_WIDTH = 512
DISK_HEIGHT = 232
EINSTEIN_RADIUS = 45
LINES = ("Buidling random shit", "that pops up in my head")
FONT_SIZE = 47
TRACKING = 0.4

# Arial-compatible advances in thousandths of an em.
ADVANCES = {
    " ": 278, "B": 722, "a": 556, "d": 611, "e": 556, "g": 611, "h": 611,
    "i": 278, "l": 278, "m": 889, "n": 611, "o": 611, "p": 611, "r": 389,
    "s": 556, "t": 333, "u": 611, "y": 556,
}

STYLE = """
  svg { color-scheme: light dark; --title:#202830; }
  @media (prefers-color-scheme: dark) {
    svg { --title:#f0f4fa; }
  }
  text {
    font-family:Arial, "Liberation Sans", sans-serif;
    font-weight:700;
    text-anchor:middle;
    fill:var(--title);
  }
  .motion { opacity:0; transform-origin:0 0; }
  .hole { animation:hole 12s linear infinite; }
  .point { animation:point 12s linear infinite; }
  .flash { animation:flash 12s linear infinite; }
  .wave { animation:wave 12s linear infinite; }
  .embers { animation:embers 12s linear infinite; }
  @keyframes hole {
    0%, 21% { opacity:0; transform:scale(.04); }
    27% { opacity:.55; transform:scale(.36); }
    37% { opacity:1; transform:scale(.90); }
    50% { opacity:1; transform:scale(1); }
    56% { opacity:1; transform:scale(1.04); animation-timing-function:cubic-bezier(.55,0,.75,.40); }
    65% { opacity:1; transform:scale(.025); }
    66%, 100% { opacity:0; transform:scale(0); }
  }
  @keyframes point {
    0%, 61% { opacity:0; transform:scale(.1); }
    64% { opacity:1; transform:scale(.65); }
    66% { opacity:1; transform:scale(1); }
    67%, 100% { opacity:0; transform:scale(.25); }
  }
  @keyframes flash {
    0%, 66% { opacity:0; transform:scale(.03); }
    67.25% { opacity:.88; transform:scale(.66); }
    70% { opacity:.32; transform:scale(1.18); }
    76%, 100% { opacity:0; transform:scale(1.48); }
  }
  @keyframes wave {
    0%, 66% { opacity:0; transform:scale(.02); }
    67.4% { opacity:.58; transform:scale(.28); animation-timing-function:cubic-bezier(.22,.65,.45,1); }
    75% { opacity:.18; transform:scale(1.43); }
    80%, 100% { opacity:0; transform:scale(1.68); }
  }
  @keyframes embers {
    0%, 66% { opacity:0; transform:scale(.01); }
    67.5% { opacity:.9; transform:scale(.4); animation-timing-function:cubic-bezier(.22,.65,.40,1); }
    75% { opacity:.54; transform:scale(.92); }
    82%, 100% { opacity:0; transform:scale(1.25); }
  }
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


def render_disk():
    """Color the first optically thick disk intersection along each light ray."""
    impact, angles, path = photon_paths()
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
        bands = (
            0.63 + 0.18 * np.sin(12.0 * np.log(r) + 4 * azimuth)
            + 0.11 * np.sin(27.0 * np.log(r) - 7 * azimuth)
            + 0.08 * np.sin(45.0 * np.log(r) + 13 * azimuth)
        )
        edge = np.minimum(np.clip((r - 6) / 0.35, 0, 1), np.clip((21.2 - r) / 5.1, 0, 1))
        intensity = 5.6 * bands * (6 / r)**1.9 * shift**3.5 * edge
        brightness = 1 - np.exp(-intensity)
        heat = np.clip(1.18 * brightness + 0.21 * (shift - 0.65), 0, 1)
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
    result = Image.alpha_composite(glow, image)
    data = BytesIO()
    result.save(data, format="PNG", optimize=True)
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


def letter_frame(x, y, start, time, secondary):
    radius, initial_angle = hypot(x, y), atan2(y, x)
    finish = 6.0
    if time >= 7.92:
        # The shock sends glyphs outward, with a small overshoot before they settle.
        p = min(1, (time - 7.92) / 1.36)
        travel = 1 - (1 - p)**3 + 0.20 * sin(pi * p)**2 * p
        scale = 0.09 + 0.91 * travel
        return matrix(x * travel, y * travel, 0, scale, scale, (1 - travel) * 0.9), (
            0 if secondary else smooth(0, 0.23, p)
        )
    p = min(1, max(0, (time - start) / (finish - start)))
    if p == 1:
        return "matrix(.01,0,0,.01,0,0)", 0

    orbit = initial_angle - 4.1 * p**1.55
    distance = radius * (1 - p**1.9)
    # The outer part of each orbit is foreshortened in the vertical direction.
    # It opens up close to the shadow, where the lens can arc letters around it.
    flattening = 1 - 0.61 * smooth(0, 0.22, p) * smooth(68, 146, distance)
    orbit_x, orbit_y = distance * cos(orbit), distance * sin(orbit) * flattening
    distance, angle = hypot(orbit_x, orbit_y), atan2(orbit_y, orbit_x)
    # The point-mass lens equation gives outer and flipped inner images on one axis.
    # Like the Portfolio effect, fade the lens away from the center of the artwork.
    lens = EINSTEIN_RADIUS * smooth(2.55, 4.45, time) * (1 - smooth(90, 198, distance))
    gap = hypot(distance, 2 * lens)
    apparent = (distance + (-gap if secondary else gap)) / 2
    radial = (1 + (-distance / gap if secondary else distance / gap)) / 2
    tangent = min(2.2, abs(apparent) / distance)
    stretch = 1 + 1.1 * smooth(0.38, 0.89, p)
    size = 1 - 0.88 * smooth(0.5, 1, p)
    roll = (orbit - initial_angle) * 0.78
    shadow = SHADOW * 7.25 * (0.3 + 0.7 * smooth(3.2, 4.7, time))
    visible = 1 - smooth(0.79, 1.0, p)
    if secondary:
        visible *= 0.42 * smooth(shadow, shadow + 9, abs(apparent))

    return matrix(
        apparent * cos(angle), apparent * sin(angle), angle,
        size * radial * stretch, size * tangent / sqrt(stretch) * (-1 if secondary else 1), roll,
    ), visible


def build_letters():
    style, primary, secondary = [], [], []
    for line, y in zip(LINES, (-39, 34)):
        widths = [ADVANCES[char] / 1000 * FONT_SIZE for char in line]
        left = -(sum(widths) + TRACKING * (len(line) - 1)) / 2
        for char, width in zip(line, widths):
            x = left + width / 2
            left += width + TRACKING
            if char == " ":
                continue
            start = 3.12 + 0.76 * smooth(37, 270, hypot(x, y))
            start += (sin(x * 0.11) + 1) * 0.10
            times = (
                [0, 2.55, 2.82, 3.08, start]
                + list(np.linspace(start, 6.0, 26)[1:])
                + [7.92, 8.00, 8.10, 8.22, 8.38, 8.58, 8.85, 9.12, 9.28, DURATION]
            )
            for image, elements, is_secondary in [("outer", primary, False), ("inner", secondary, True)]:
                name = f"{image}-{len(elements)}"
                samples = [letter_frame(x, y, start, time, is_secondary) for time in times]
                if is_secondary and max(opacity for _, opacity in samples) < 0.02:
                    continue
                frames = [
                    f"    {time / DURATION:.5%} {{ transform:{transform}; opacity:{opacity:.3f}; }}"
                    for time, (transform, opacity) in zip(times, samples)
                ]
                style.extend([
                    f"  @keyframes {name} {{", *frames, "  }",
                    f"  .{name} {{ animation:{name} {DURATION}s linear infinite; }}",
                ])
                # These base coordinates also show the undistorted text under reduced motion.
                visibility = ' opacity="0"' if is_secondary else ""
                elements.append(
                    f'    <g class="{name}" transform="translate({x:.2f} {y})"{visibility}>'
                    f'<text y="{FONT_SIZE * .345:.2f}">{escape(char)}</text></g>'
                )
    return "\n".join(style), "\n".join(primary), "\n".join(secondary)


def burst_embers():
    rng = np.random.default_rng(77)
    streaks = []
    for i in range(46):
        angle = rng.uniform(0, 2 * pi)
        distance = rng.uniform(45, 283)
        x, y = cos(angle) * distance, sin(angle) * distance * 0.54
        length = rng.uniform(.015, .12)
        shade = ["#ffcf98", "#ec8c62", "#ffd9b1", "#9ebbed"][i % 4]
        streaks.append(
            f'<path d="M{x * (1 - length):.1f} {y * (1 - length):.1f} L{x:.1f} {y:.1f}"'
            f' stroke="{shade}" stroke-width="{rng.uniform(.75, 2.0):.2f}"/>'
        )
    return "\n        ".join(streaks)


def build_svg():
    disk = render_disk()
    letters_style, primary, secondary = build_letters()
    return f"""<!-- Generated by black-hole/render.py. -->
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="heading">
  <title id="heading">{escape(" ".join(LINES))}</title>
  <style>
{STYLE}
{letters_style}
  @media (prefers-reduced-motion: reduce) {{
    * {{ animation:none !important; }}
  }}
  </style>
  <defs>
    <radialGradient id="plasma">
      <stop stop-color="#fff7e7"/>
      <stop offset=".15" stop-color="#ffd4a1" stop-opacity=".95"/>
      <stop offset=".43" stop-color="#ec8e55" stop-opacity=".46"/>
      <stop offset="1" stop-color="#d35a38" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="point">
      <stop stop-color="#fff"/>
      <stop offset=".25" stop-color="#fff4d4"/>
      <stop offset="1" stop-color="#ef923c" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <g transform="translate({CENTER_X} {CENTER_Y})" font-size="{FONT_SIZE}" aria-hidden="true">
    <g class="motion wave" fill="none">
      <ellipse rx="167" ry="84" stroke="#ffa75f" stroke-width="2.7"/>
      <ellipse rx="147" ry="73" stroke="#ffe0ae" stroke-opacity=".65" stroke-width=".9"/>
    </g>
    <g class="motion flash"><ellipse rx="153" ry="103" fill="url(#plasma)"/></g>
    <g class="motion embers" stroke-linecap="round">
        {burst_embers()}
    </g>
{primary}
{secondary}
    <g class="motion hole">
      <g transform="rotate(-10)">
        <image x="-159.5" y="-72.2734375" width="319" height="144.546875" xlink:href="data:image/png;base64,{disk}"/>
      </g>
    </g>
    <g class="motion point">
      <circle r="12" fill="url(#point)"/>
      <circle r="1.5" fill="#fff7e7"/>
    </g>
  </g>
</svg>
"""


if __name__ == "__main__":
    Path(__file__).with_name("black-hole.svg").write_text(build_svg(), encoding="utf-8")
