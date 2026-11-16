"""Makes the printable Galaxy Cube case (spec §13).

    pip install manifold3d trimesh numpy pillow
    python3 case/make_case.py

Writes case/shell.stl, case/base.stl, case/light_strip.stl and case/preview.png.
All sizes are in millimetres. Change a number below and run it again.

Layout (looking at the front):
  front  OLED window (with a 1 mm bezel), knob below it, small mic holes bottom right
  top    TALK (big) and MUTE (small) buttons, slot for the glowing light strip
  back   holes for the Pi's USB port (headset adapter) and power port
  base   Pi Zero standoffs, speaker holder with grille, 4 feet, 4 screws into the shell
"""
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import Manifold

HERE = Path(__file__).resolve().parent
SEG = 48                       # roundness of circles

SIZE = 70.0                    # outside of the cube
RADIUS = 8.0                   # rounded corners
WALL = 2.4
BASE = 3.0                     # base plate thickness
FIT = 0.3                      # gap so the base slides into the shell

# Screen: 1.3" SH1106 module (board 35.5 x 33.5). Visible window 30 x 15.5.
OLED_WINDOW = (30.0, 15.5)
OLED_BOARD = (36.2, 34.2)
OLED_Z = 47.0                  # height of the window's centre
# Knob: EC11 encoder, 7 mm threaded bush
KNOB_HOLE = 7.4
KNOB_Z = 21.0
# Buttons on top: 12 mm tactile switches with round caps
TALK_HOLE = 12.6
MUTE_HOLE = 12.6                # same button and cap as TALK (common 12 mm caps are ~12 mm wide)
# Pi Zero 2 W: 65 x 30 board, M2.5 holes 3.5 mm from each edge
PI = (65.0, 30.0)
PI_HOLES = [(3.5, 3.5), (61.5, 3.5), (3.5, 26.5), (61.5, 26.5)]
STANDOFF = 5.0
PI_BACK_GAP = 1.0              # board edge to the inside of the back wall
USB_X, PWR_X = 41.4, 54.0      # port centres, measured from the board's left edge
# Speaker: 28 mm
SPEAKER = 28.0


def rounded_box(x, y, z, r):
    """A box with every edge rounded, from (0,0,0) to (x,y,z)."""
    corners = [Manifold.sphere(r, SEG).translate((cx, cy, cz))
               for cx in (r, x - r) for cy in (r, y - r) for cz in (r, z - r)]
    return Manifold.batch_hull(corners)


def flat_bottom_box(x, y, z, r):
    """Rounded on top and on the vertical edges, flat on the bottom (so it sits on the table)."""
    parts = [Manifold.sphere(r, SEG).translate((cx, cy, z - r)) for cx in (r, x - r) for cy in (r, y - r)]
    parts += [Manifold.cylinder(0.01, r, circular_segments=SEG).translate((cx, cy, 0)) for cx in (r, x - r) for cy in (r, y - r)]
    return Manifold.batch_hull(parts)


def rounded_prism(x, y, h, r):
    """A box with rounded vertical edges only, from (0,0,0) to (x,y,h)."""
    posts = [Manifold.cylinder(h, r, circular_segments=SEG).translate((cx, cy, 0))
             for cx in (r, x - r) for cy in (r, y - r)]
    return Manifold.batch_hull(posts)


def box(x, y, z, at=(0, 0, 0)):
    return Manifold.cube((x, y, z)).translate(at)


def hole(d, length, at, axis="z"):
    c = Manifold.cylinder(length, d / 2, circular_segments=SEG)
    if axis == "y":
        c = c.rotate((-90, 0, 0))
    elif axis == "x":
        c = c.rotate((0, 90, 0))
    return c.translate(at)


def centred(m):
    """Move so x/y are centred on 0 (z stays)."""
    return m.translate((-SIZE / 2, -SIZE / 2, 0))


# The front is the -Y face, the back is the +Y face, z = 0 is the table.
INNER = SIZE - 2 * WALL
inner_r = RADIUS - WALL
SCREW_AT = INNER / 2 - 4.5      # corner screw bosses


def make_shell():
    shell = centred(flat_bottom_box(SIZE, SIZE, SIZE, RADIUS))
    cavity = centred(flat_bottom_box(INNER, INNER, SIZE - WALL + 1, inner_r).translate((WALL, WALL, -1)))
    shell = shell - cavity

    front = -SIZE / 2
    # screen: window through the wall, and a pocket inside for the module's board (leaves a 1 mm bezel)
    shell -= box(OLED_WINDOW[0], WALL + 2, OLED_WINDOW[1], (-OLED_WINDOW[0] / 2, front - 1, OLED_Z - OLED_WINDOW[1] / 2))
    shell -= box(OLED_BOARD[0], WALL, OLED_BOARD[1], (-OLED_BOARD[0] / 2, front + 1.0, OLED_Z - 17.0))
    # knob
    shell -= hole(KNOB_HOLE, WALL + 2, (0, front - 1, KNOB_Z), "y")
    # microphone holes (3 x 3)
    for i in range(3):
        for j in range(3):
            shell -= hole(1.3, WALL + 2, (20 + i * 2.6, front - 1, 9 + j * 2.6), "y")

    top = SIZE
    # TALK (big, front-right) and MUTE (small, back-left) on top
    shell -= hole(TALK_HOLE, WALL + 2, (10, 4, top - WALL - 1))
    shell -= hole(MUTE_HOLE, WALL + 2, (-14, 12, top - WALL - 1))
    # slot for the light strip near the front edge of the top
    shell -= box(46, 5, WALL + 2, (-23, -SIZE / 2 + 9, top - WALL - 1))

    back = SIZE / 2
    board_left = -PI[0] / 2
    port_z = BASE + STANDOFF + 1.4 + 1.6
    # one opening for both ports: USB (headset adapter) and power
    left, right = board_left + USB_X - 7, board_left + PWR_X + 6
    shell -= box(right - left, WALL + 2, 9, (left, back - WALL - 1, port_z - 4.5))

    # 4 screw bosses in the bottom corners (M2.5 screws come up through the base)
    for sx in (-1, 1):
        for sy in (-1, 1):
            boss = Manifold.cylinder(12, 4.0, circular_segments=SEG).translate((sx * SCREW_AT, sy * SCREW_AT, BASE))
            corner = Manifold.cylinder(12, 2.0, circular_segments=SEG).translate((sx * 30.0, sy * 30.0, BASE))
            boss = Manifold.batch_hull([boss, corner])   # joins the post to the corner, staying inside the wall
            shell += boss - hole(2.2, 13, (sx * SCREW_AT, sy * SCREW_AT, BASE - 0.5))
    return shell


def make_base():
    base = centred(rounded_prism(INNER - 2 * FIT, INNER - 2 * FIT, BASE, inner_r).translate((WALL + FIT, WALL + FIT, 0)))
    # screw holes with countersink from below
    for sx in (-1, 1):
        for sy in (-1, 1):
            base -= hole(2.8, BASE + 2, (sx * SCREW_AT, sy * SCREW_AT, -1))
            base -= Manifold.cylinder(1.6, 2.9, 1.4, SEG).translate((sx * SCREW_AT, sy * SCREW_AT, -0.01))
    # Pi standoffs, board's back edge PI_BACK_GAP from the back wall
    board_y0 = INNER / 2 - PI_BACK_GAP - PI[1]
    for hx, hy in PI_HOLES:
        x, y = -PI[0] / 2 + hx, board_y0 + hy
        base += Manifold.cylinder(STANDOFF, 2.6, circular_segments=SEG).translate((x, y, BASE)) - hole(2.1, STANDOFF + 1, (x, y, BASE))
    # speaker in the front half: a ring to hold it, and grille holes under it
    sy = -INNER / 2 + SPEAKER / 2 + 4
    ring = Manifold.cylinder(2.5, SPEAKER / 2 + 1.6, circular_segments=SEG) - Manifold.cylinder(3, SPEAKER / 2 + 0.2, circular_segments=SEG).translate((0, 0, -0.2))
    base += ring.translate((0, sy, BASE))
    for r, n in ((0, 1), (4.5, 6), (9, 12)):
        for k in range(n):
            a = 2 * np.pi * k / n
            base -= hole(2.2, BASE + 2, (r * np.cos(a), sy + r * np.sin(a), -1))
    # feet (lift the base so the speaker can be heard)
    for fx in (-1, 1):
        for fy in (-1, 1):
            base += Manifold.cylinder(2.0, 4.0, circular_segments=SEG).translate((fx * 24, fy * 24, -2.0))
    return base


def make_strip():
    """Print in clear / translucent PLA or PETG. Slides up into the slot from inside; the lip holds it."""
    strip = box(45.6, 4.6, WALL, (-22.8, -2.3, 0))
    lip = box(50, 9, 1.2, (-25, -4.5, -1.2))
    return strip + lip


def save(m, name):
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts))
    tm.export(HERE / name)
    return tm


def render(tm, elev, azim, size=360):
    """A small depth-buffer renderer (numpy + Pillow), so the preview needs no 3D software."""
    e, a = np.radians(elev), np.radians(azim)
    rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
    v = (tm.vertices - tm.bounds.mean(axis=0)) @ (rx @ rz).T
    n = tm.face_normals @ (rx @ rz).T
    scale = size * 0.78 / (np.ptp(v[:, [0, 2]], axis=0).max())
    px = v[:, 0] * scale + size / 2
    py = size / 2 - v[:, 2] * scale
    depth = np.full((size, size), np.inf)
    img = np.zeros((size, size, 3))
    light = np.array([-0.45, -0.7, 0.55]) / np.linalg.norm([-0.45, -0.7, 0.55])
    for f, normal in zip(tm.faces, n):
        if normal[1] > 0:          # facing away from us
            continue
        x, y, z = px[f], py[f], v[f, 1]
        x0, x1 = max(int(x.min()), 0), min(int(x.max()) + 1, size)
        y0, y1 = max(int(y.min()), 0), min(int(y.max()) + 1, size)
        if x0 >= x1 or y0 >= y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-9:
            continue
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
        region = depth[y0:y1, x0:x1]
        closer = inside & (zz < region)
        region[closer] = zz[closer]
        shade = 0.30 + 0.70 * max(0.0, float(normal @ light))
        img[y0:y1, x0:x1][closer] = np.array([0.36, 0.42, 0.78]) * shade
    img[np.isinf(depth)] = [0.96, 0.96, 0.98]
    return (img * 255).astype(np.uint8)


def preview(meshes, path):
    from PIL import Image, ImageDraw
    views = [(meshes[0], 20, 30, "Front"), (meshes[0], 20, 210, "Back"), (meshes[0], 70, 30, "Top"),
             (meshes[1], 55, 30, "Base")]
    sheet = Image.new("RGB", (360 * len(views), 390), (245, 245, 250))
    d = ImageDraw.Draw(sheet)
    for i, (tm, elev, azim, title) in enumerate(views):
        sheet.paste(Image.fromarray(render(tm, elev, azim)), (i * 360, 30))
        d.text((i * 360 + 14, 10), title, fill=(30, 30, 50))
    sheet.save(path)


if __name__ == "__main__":
    shell, base, strip = make_shell(), make_base(), make_strip()
    meshes = [save(shell, "shell.stl"), save(base, "base.stl"), save(strip, "light_strip.stl")]
    for name, tm in zip(("shell", "base", "light_strip"), meshes):
        print(f"{name}.stl  {tm.extents.round(1)} mm  {tm.volume / 1000 * 1.24:.0f} g PLA  watertight={tm.is_watertight}")
    try:
        preview(meshes, HERE / "preview.png")
        print("preview.png")
    except ImportError:
        print("(install Pillow for preview.png)")
