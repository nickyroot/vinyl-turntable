"""Every part of the deck, one function each.

Each function takes the parameter set and returns a shape already placed in
the assembly's world frame: feet on z = 0, cabinet centred on the origin,
X running left to right and Y front to back.

The tonearm is the exception worth knowing about. It is built in a local
frame with the pivot at the origin and the stylus at (effective_length, 0),
then rotated into place as one piece. That keeps the S-bend, the headshell
offset and the counterweight in one coordinate system where the alignment
numbers mean what they say.
"""

from __future__ import annotations

from math import atan2, cos, degrees, hypot, radians, sin

from build123d import (
    Align,
    Axis,
    Box,
    Color,
    Compound,
    Cone,
    Cylinder,
    Keep,
    Plane,
    Polygon,
    Pos,
    Rectangle,
    Rot,
    Shape,
    SlotCenterToCenter,
    Sphere,
    Spline,
    Vector,
    chamfer,
    extrude,
    fillet,
    split,
    sweep,
)

from .params import PALETTE, TurntableParams
from .tracking import OFFSET_SIGN, heading

BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
TOP = (Align.CENTER, Align.CENTER, Align.MAX)


def finish(shape: Shape, label: str, key: str) -> Shape:
    """Tag a shape with a name and a colour so the GLB carries both."""
    r, g, b, a = PALETTE[key].rgba
    shape.color = Color(r, g, b, a)
    shape.label = label
    return shape


# ------------------------------------------------------------------ cabinet


def _trim(body: Shape, a, b, c, keep) -> Shape:
    """Slice `body` with the plane through a, b and c, keeping `keep`'s side."""
    a, b, c = Vector(*a), Vector(*b), Vector(*c)
    normal = (b - a).cross(c - a).normalized()
    if normal.dot(Vector(*keep) - a) > 0:
        normal = -normal  # point the normal at the material coming off
    return split(body, bisect_by=Plane(origin=a, z_dir=normal), keep=Keep.BOTTOM)


def plinth_blank(p: TurntableParams) -> Shape:
    """The faceted slab on its own: a box with sixteen flat slices taken off.

    Eight bevels, the top and bottom edges as mirror images, then four
    vertical corner planes, each through a top-face corner at 45 degrees.
    Every cut is a plane, so the facets meet in straight creases, the top
    and bottom faces are matching perfect rectangles, and each corner facet
    closes to a point at both ends.
    """
    s = p.plinth
    z0, z1 = p.foot.height, p.plinth_top
    x, y, b = s.length / 2, s.depth / 2, s.bevel
    centre = (0.0, 0.0, (z0 + z1) / 2)

    body = Pos(Z=z0) * Box(s.length + 2 * b, s.depth + 2 * b, s.height, align=BOTTOM)
    for fz, wz in ((z1, z1 - b), (z0, z0 + b)):  # face height, wall height
        for side in (-1, 1):
            front_back = ((-x, side * y, fz), (x, side * y, fz), (0, side * (y + b), wz))
            left_right = ((side * x, -y, fz), (side * x, y, fz), (side * (x + b), 0, wz))
            body = _trim(body, *front_back, centre)
            body = _trim(body, *left_right, centre)
    for sx in (-1, 1):
        for sy in (-1, 1):
            corner = ((sx * x, sy * y, z0), (sx * x, sy * y, z1), (sx * (x - b), sy * (y + b), z0))
            body = _trim(body, *corner, centre)
    return body


def plinth(p: TurntableParams) -> Shape:
    """The chassis: the faceted blank, with its bores and wells."""
    z1 = p.plinth_top
    body = plinth_blank(p)

    # Bores and wells for the parts that sit in the top face.
    body -= Pos(*p.spindle, z1 - 15) * Cylinder(p.drive.hub_radius, 16, align=BOTTOM)
    body -= Pos(*p.controls.adapter_at, z1 - 4) * Cylinder(
        p.controls.adapter_radius + 2, 6, align=BOTTOM
    )
    slot_w, slot_l = p.controls.pitch_slot
    body -= Pos(*p.controls.pitch_at, z1 - 5) * Box(slot_w, slot_l, 7, align=BOTTOM)

    return finish(body, "chassis", "top_plate")


def feet(p: TurntableParams) -> Shape:
    """Spring-and-rubber insulators, adjustable for height."""
    f, s = p.foot, p.plinth
    dx = s.length / 2 - f.inset
    dy = s.depth / 2 - f.inset
    out = []
    for i, (x, y) in enumerate(((-dx, -dy), (dx, -dy), (-dx, dy), (dx, dy))):
        band_z = f.height - f.collar - 2
        band = Cylinder(f.radius + 0.3, f.collar, align=BOTTOM)
        body = Cylinder(f.radius, f.height, align=BOTTOM)
        body = fillet(body.edges().group_by(Axis.Z)[0], f.radius * 0.3)
        body -= Pos(Z=band_z) * band        # let the band into the rubber
        out.append(finish(Pos(x, y, 0) * body, f"foot_{i + 1}", "rubber"))
        out.append(finish(Pos(x, y, band_z) * band, f"foot_band_{i + 1}", "brass"))
    return Compound(children=out, label="feet")


def rear_panel(p: TurntableParams) -> Shape:
    """Captive phono leads and the earthing post, out of the back wall.

    They leave from the middle of the vertical wall band, between the two
    bevels, so the facets stay clean.
    """
    s = p.plinth
    y = s.depth / 2 + s.bevel
    z = p.foot.height + s.height / 2
    out = []

    for i, dx in enumerate((74, 118)):
        lead = Rot(X=-90) * Cylinder(4.0, 26, align=BOTTOM)
        out.append(finish(Pos(dx, y, z) * lead, f"phono_lead_{i + 1}", "rubber"))
        tip = Rot(X=-90) * Cylinder(4.6, 9, align=BOTTOM)
        out.append(finish(Pos(dx, y + 24, z) * tip, f"phono_plug_{i + 1}", "brass"))

    post = Rot(X=-90) * Cylinder(3.4, 10, align=BOTTOM)
    out.append(finish(Pos(146, y, z) * post, "earth_post", "brass"))

    inlet = Rot(X=-90) * Cylinder(4.2, 22, align=BOTTOM)
    out.append(finish(Pos(-150, y, z) * inlet, "mains_lead", "rubber"))

    return Compound(children=out, label="rear_panel")


# -------------------------------------------------------------- direct drive


def direct_drive(p: TurntableParams) -> Shape:
    """The motor that is also the bearing that is also the platter mount.

    Technics put the rotor magnet on the platter itself and the coils on
    the chassis, so there is no belt, no idler and nothing between the
    motor and the record but the spindle bearing.
    """
    d = p.drive
    z = p.plinth_top
    out = []

    hub = Cylinder(d.hub_radius, d.hub_height, align=BOTTOM)
    hub = chamfer(hub.edges().group_by(Axis.Z)[-1], 1.5)
    hub -= Pos(Z=-1) * Cylinder(d.spindle_radius + 1.0, d.hub_height + 2, align=BOTTOM)
    out.append(finish(Pos(*p.spindle, z - 4) * hub, "bearing_hub", "steel"))

    # Stator: a ring of coils on the chassis, facing up at the rotor.
    plate = Cylinder(d.stator_radius, 2.0, align=BOTTOM)
    plate -= Pos(Z=-1) * Cylinder(d.hub_radius + 0.5, 4, align=BOTTOM)
    out.append(finish(Pos(*p.spindle, z) * plate, "stator_plate", "base"))

    coils = []
    ring = d.stator_radius - 9
    for index in range(d.coil_count):
        a = radians(360 * index / d.coil_count)
        coils.append(
            Pos(ring * cos(a), ring * sin(a), 0)
            * Cylinder(6.5, d.stator_height, align=BOTTOM)
        )
    stator = Pos(*p.spindle, z + 2) * Compound(coils)
    out.append(finish(stator, "stator_coils", "copper"))

    return Compound(children=out, label="direct_drive")


def rotor(p: TurntableParams) -> Shape:
    """Magnet ring on the platter underside: the other half of the motor.

    It turns with the platter, which is why this lives in the platter group
    and not with the stator.
    """
    d, pl = p.drive, p.platter
    ceiling = p.plinth_top + pl.clearance + pl.relief_depth
    body = Cylinder(d.rotor_radius, d.rotor_height, align=TOP)
    body -= Pos(Z=1) * Cylinder(d.rotor_radius - d.rotor_wall, d.rotor_height + 2, align=TOP)
    body = chamfer(body.edges().group_by(Axis.Z)[0], 0.8)
    return finish(Pos(*p.spindle, ceiling) * body, "rotor_magnet", "steel")


def spindle(p: TurntableParams) -> Shape:
    d = p.drive
    bottom = p.plinth_top - 10
    top = p.record_surface + d.spindle_above_mat
    shaft = Cylinder(d.spindle_radius, top - bottom, align=BOTTOM)
    shaft = chamfer(shaft.edges().group_by(Axis.Z)[-1], d.spindle_radius * 0.45)
    return finish(Pos(*p.spindle, bottom) * shaft, "spindle", "steel")


# ------------------------------------------------------------------- platter


def platter(p: TurntableParams) -> Shape:
    """332 mm of die-cast aluminium, relieved underneath for the rotor."""
    pl, d = p.platter, p.drive
    z = p.plinth_top + pl.clearance
    body = Cylinder(pl.radius, pl.thickness, align=BOTTOM)
    # Cut a hair deeper than the relief, so the rotor's top face lands
    # flush in the void instead of a sliver inside the casting.
    deep = pl.relief_depth + 0.02
    relief = Cylinder(pl.relief_radius, deep, align=BOTTOM) - Cylinder(
        pl.boss_radius, deep, align=BOTTOM
    )
    body -= Pos(Z=-0.01) * relief
    body -= Pos(Z=-1) * Cylinder(d.spindle_radius + 0.15, pl.thickness + 2, align=BOTTOM)
    body = chamfer(
        body.faces().sort_by(Axis.Z)[-1].edges().sort_by(Axis.X)[-1], pl.rim_chamfer
    )
    return finish(Pos(*p.spindle, z) * body, "platter", "matt_black")


def platter_damping(p: TurntableParams) -> Shape:
    """The rubber coating on the underside that stops the casting ringing."""
    pl, d = p.platter, p.drive
    ceiling = p.plinth_top + pl.clearance + pl.relief_depth
    ring = Cylinder(pl.relief_radius - 1, pl.damping_thickness, align=TOP) - Cylinder(
        d.rotor_radius + 2, pl.damping_thickness, align=TOP
    )
    return finish(Pos(*p.spindle, ceiling) * ring, "platter_damping", "rubber")


def strobe_dots(p: TurntableParams) -> Shape:
    """Four rows of marks machined into the platter rim.

    Quartz lock made these redundant in 1979 and Technics kept them anyway,
    because DJs wanted to see the speed as well as trust it. The count here
    is stylised: the real rim carries several times as many.
    """
    pl = p.platter
    z0 = p.plinth_top + pl.clearance
    span = (pl.strobe_rows - 1) * pl.strobe_row_gap
    first = z0 + pl.thickness / 2 - span / 2
    dot = pl.strobe_dot

    marks = []
    for row in range(pl.strobe_rows):
        z = first + row * pl.strobe_row_gap
        for i in range(pl.strobe_per_row):
            a = 360 * i / pl.strobe_per_row
            mark = Pos(pl.radius + 0.2, 0, z) * Box(0.6, dot, dot)
            marks.append(Rot(Z=a) * mark)
    return finish(Pos(*p.spindle) * Compound(marks), "strobe_dots", "strobe")


def mat(p: TurntableParams) -> Shape:
    """The 2 mm rubber mat, ribbed to damp the record."""
    pl = p.platter
    body = Cylinder(pl.mat_radius, pl.mat_thickness, align=BOTTOM)
    body -= Pos(Z=-1) * Cylinder(p.drive.spindle_radius + 0.2, pl.mat_thickness + 2, align=BOTTOM)
    body -= Pos(Z=pl.mat_thickness - 0.35) * (
        Cylinder(pl.mat_radius - 12, 1, align=BOTTOM)
        - Cylinder(pl.mat_radius - 15, 1, align=BOTTOM)
    )
    return finish(Pos(*p.spindle, p.platter_top) * body, "platter_mat", "mat")


# ------------------------------------------------------------------ controls


def controls(p: TurntableParams) -> Shape:
    """Start/stop, speed, power, strobe window and the pitch fader."""
    c = p.controls
    z = p.plinth_top
    out = []

    # Start/stop: the big one, front left, where a hand falls on it.
    w, dep = c.start_stop_size
    pad = Box(w, dep, 6, align=BOTTOM)
    pad = fillet(pad.edges().filter_by(Axis.Z), 4)
    out.append(finish(Pos(*c.start_stop_at, z) * pad, "start_stop", "matt_black"))

    for name, dx in ((33, -c.speed_pitch / 2), (45, c.speed_pitch / 2)):
        bw, bd = c.speed_button
        btn = Box(bw, bd, 4.5, align=BOTTOM)
        btn = fillet(btn.edges().filter_by(Axis.Z), 2)
        out.append(
            finish(
                Pos(c.speed_at[0] + dx, c.speed_at[1], z) * btn,
                f"speed_{name}",
                "matt_black",
            )
        )
        led = Pos(c.speed_at[0] + dx, c.speed_at[1] + bd / 2 + 3, z) * Cylinder(
            1.8, 1.2, align=BOTTOM
        )
        out.append(finish(led, f"speed_led_{name}", "lamp"))

    # Power switch, with the strobe lamp ganged to it.
    knob = Cylinder(c.power_radius, c.power_height, align=BOTTOM)
    knob = chamfer(knob.edges().group_by(Axis.Z)[-1], 1.5)
    out.append(finish(Pos(*c.power_at, z) * knob, "power_switch", "matt_black"))

    ww, wd = c.strobe_window
    window = Box(ww, wd, 2.5, align=BOTTOM)
    window = fillet(window.edges().filter_by(Axis.Z), 1.5)
    out.append(finish(Pos(*c.strobe_at, z) * window, "strobe_lamp", "lamp"))

    # Pitch fader: the MK2's headline change, rotary knob to a 100 mm slide.
    slot_w, slot_l = c.pitch_slot
    rail = Box(3.5, slot_l - 10, 1.5, align=BOTTOM)
    out.append(finish(Pos(*c.pitch_at, z - 4) * rail, "pitch_rail", "matt_black"))

    kw, kd, kh = c.pitch_knob
    knob = Box(kw, kd, kh, align=BOTTOM)
    knob = fillet(knob.edges().filter_by(Axis.Z), 2.5)
    knob -= Pos(0, 0, z * 0 + kh - 1) * Box(kw + 2, 2.2, 2, align=BOTTOM)
    out.append(finish(Pos(*c.pitch_at, z - 5) * knob, "pitch_fader", "matt_black"))

    # Green LED that lights when the quartz lock holds the speed.
    lock = Cylinder(2.0, 1.2, align=BOTTOM)
    out.append(
        finish(Pos(c.pitch_at[0] - 21, c.pitch_at[1], z) * lock, "quartz_lock_led", "led")
    )

    return Compound(children=out, label="controls")


def target_light(p: TurntableParams) -> Shape:
    """The pop-up stylus illuminator, stowed in the cabinet when not needed."""
    c = p.controls
    z = p.plinth_top
    out = []
    barrel = Cylinder(c.target_radius, c.target_height, align=BOTTOM)
    barrel = chamfer(barrel.edges().group_by(Axis.Z)[-1], 1.2)
    out.append(finish(Pos(*c.target_at, z) * barrel, "target_light", "aluminium"))
    lens = Cylinder(c.target_radius - 2, 2.5, align=BOTTOM)
    out.append(
        finish(Pos(*c.target_at, z + c.target_height - 1) * lens, "target_lens", "lamp")
    )
    return Compound(children=out, label="target_light")


def adapter(p: TurntableParams) -> Shape:
    """45 rpm adaptor, parked in its well at the back left."""
    c = p.controls
    z = p.plinth_top - 3
    body = Cylinder(c.adapter_radius, 5, align=BOTTOM)
    body = chamfer(body.edges().group_by(Axis.Z)[-1], 1.2)
    body -= Pos(Z=-1) * Cylinder(3.6, 7, align=BOTTOM)
    return finish(Pos(*c.adapter_at, z) * body, "adapter_45", "aluminium")


# ------------------------------------------------------------------- tonearm


def _arm_frame(p: TurntableParams) -> dict:
    """Resolve the arm's local geometry.

    Local X runs from the pivot to the stylus, so the stylus is at
    (effective_length, 0) by definition. The headshell runs back from it at
    the offset angle to its neck, and the straight tube joins the pivot to
    that neck, which is why the tube sits a few degrees off the X axis.
    """
    t = p.tonearm
    axis = radians(OFFSET_SIGN * t.offset_angle)
    stylus = (t.effective_length, 0.0)
    neck = (stylus[0] - t.head_reach * cos(axis), stylus[1] - t.head_reach * sin(axis))

    # Vertical stack under the tube centreline, set so the stylus just
    # touches the record. The tube runs down into the cast plate.
    head_top = -t.tube_radius_tip + 1.0
    head_bottom = head_top - t.head_thickness
    cart_bottom = head_bottom - t.cartridge_height
    cantilever_z = cart_bottom + 2.0
    tip_z = cantilever_z - t.stylus_length

    return {
        "axis": axis,
        "stylus": stylus,
        "neck": neck,
        "tube_angle": degrees(atan2(neck[1], neck[0])),
        "tube_length": hypot(*neck),
        "head_top": head_top,
        "head_bottom": head_bottom,
        "cantilever_z": cantilever_z,
        "tip_z": tip_z,
        "tube_z": p.record_surface - tip_z,
    }


def _headshell(t) -> Shape:
    """The cast headshell plate, with Rega's lightening holes and slots.

    Built in its own frame: neck at the origin, axis along +X, top face at
    z = 0.
    """
    th = t.head_thickness
    outline = Polygon(
        (0, -t.head_neck_width / 2),
        (t.head_length, -t.head_width / 2),
        (t.head_length, t.head_width / 2),
        (0, t.head_neck_width / 2),
        align=None,
    )
    plate = extrude(outline, -th)
    plate = fillet(plate.edges().filter_by(Axis.Z), 2.0)
    through = th + 2
    for x, y, r in ((9, 0, 3.2), (17, 4.8, 2.4), (17, -4.8, 2.4), (35, 0, 2.2)):
        plate -= Pos(x, y, -th - 1) * Cylinder(r, through, align=BOTTOM)
    # Half-inch mounting slots, so the cartridge can slide for alignment.
    slot_x = t.head_reach - 13
    for y in (6.35, -6.35):
        plate -= Pos(Z=-th - 1) * extrude(Pos(slot_x, y) * SlotCenterToCenter(5.0, 3.0), through)
    return plate


def _finger_lift(t) -> Shape:
    """Thin strip swept out and down from the plate's outer front corner."""
    x0, y0, z0 = t.head_length - 7, t.head_width / 2 - 1, -t.head_thickness / 2
    n = t.finger_lift_length
    path = Spline(
        (x0, y0, z0),
        (x0 + 1.5, y0 + n * 0.36, z0 - 2.5),
        (x0 + 2.5, y0 + n * 0.54, z0 - n * 0.8),
    )
    section = Plane(origin=path @ 0, z_dir=path % 0) * Rectangle(5.0, 1.6)
    return sweep(section, path)


def tonearm(p: TurntableParams) -> Shape:
    """Rega RB220, built at the pivot and swung into place as one piece."""
    t = p.tonearm
    g = _arm_frame(p)
    px, py = p.pivot
    tube_z = g["tube_z"]
    out = []

    # Three-point base on the chassis, and the short pillar above it.
    base = Cylinder(t.base_radius, t.base_height, align=BOTTOM)
    base = chamfer(base.edges().group_by(Axis.Z)[-1], 1.2)
    out.append(finish(Pos(px, py, p.plinth_top) * base, "arm_base", "matt_black"))

    hl, hw, hh = t.housing
    pillar_base = p.plinth_top + t.base_height
    pillar = Cylinder(t.pillar_radius, tube_z - hh / 2 - pillar_base + 1, align=BOTTOM)
    out.append(finish(Pos(px, py, pillar_base) * pillar, "arm_pillar", "matt_black"))

    # Everything from here is laid out along the tube and swung round.
    place = Pos(px, py, tube_z) * Rot(Z=heading(p))
    along = place * Rot(Z=g["tube_angle"])

    # Bearing housing: the block the tube runs through, its top sloping
    # away front and back the way Rega's casting does.
    housing = Box(hl, hw, hh)
    housing = chamfer(housing.edges().group_by(Axis.Z)[-1].filter_by(Axis.Y), hh * 0.4)
    housing = fillet(housing.edges().filter_by(Axis.Z), 3)
    out.append(finish(along * housing, "bearing_housing", "matt_black"))

    # One piece, tapering from the bearing out to the headshell.
    tube = Rot(Y=90) * Cone(
        t.tube_radius_root, t.tube_radius_tip, g["tube_length"], align=BOTTOM
    )
    out.append(finish(along * tube, "arm_tube", "matt_black"))

    stub = Rot(Y=-90) * Cylinder(t.stub_radius, t.tube_rear, align=BOTTOM)
    out.append(finish(along * stub, "arm_stub", "matt_black"))

    cw = Rot(Y=90) * Cylinder(t.counterweight_radius, t.counterweight_length, align=BOTTOM)
    cw = chamfer(cw.edges(), 1.5)
    out.append(finish(along * Pos(-t.tube_rear + 1) * cw, "counterweight", "matt_black"))

    # The headshell is cast with the tube, angled at the offset.
    head = place * Pos(*g["neck"]) * Rot(Z=OFFSET_SIGN * t.offset_angle)
    shell = head * Pos(Z=g["head_top"])
    out.append(finish(shell * _headshell(t), "headshell", "matt_black"))
    out.append(finish(shell * _finger_lift(t), "finger_lift", "matt_black"))

    cart = Box(
        t.cartridge_length,
        t.cartridge_width,
        t.cartridge_height,
        align=(Align.MAX, Align.CENTER, Align.MAX),
    )
    cart = fillet(cart.edges().filter_by(Axis.X), 1.5)
    out.append(
        finish(head * Pos(t.head_reach - 5, 0, g["head_bottom"]) * cart, "cartridge", "cartridge")
    )

    cantilever = Rot(Y=90) * Cylinder(0.7, 7, align=BOTTOM)
    out.append(
        finish(
            head * Pos(t.head_reach - 7, 0, g["cantilever_z"]) * cantilever,
            "cantilever",
            "steel",
        )
    )

    tip = Rot(Y=180) * Cone(0.9, 0.05, t.stylus_length, align=BOTTOM)
    out.append(finish(head * Pos(t.head_reach, 0, g["cantilever_z"]) * tip, "stylus", "steel"))

    return Compound(children=out, label="tonearm")


def _parked_direction(p: TurntableParams) -> float:
    """World angle, in radians, of the tube when the arm is on its rest."""
    return radians(heading(p, p.tonearm.rest_groove) + _arm_frame(p)["tube_angle"])


def arm_rest(p: TurntableParams) -> Shape:
    """Rest, bias slider and cue lever, around the base.

    The rest sits on a bracket off the base, under the tube where the
    parked arm lies, and the bracket carries the bias slider as Rega's
    base does. The cue lever sticks out on the side away from the platter.
    """
    t = p.tonearm
    g = _arm_frame(p)
    px, py = p.pivot
    z0 = p.plinth_top
    a = _parked_direction(p)
    out = []

    # Bracket from the base out to the rest, with the bias slot in it.
    span = t.rest_reach - t.base_radius + 8
    bracket = Box(span, 10, 3, align=(Align.MIN, Align.CENTER, Align.MIN))
    bracket = fillet(bracket.edges().filter_by(Axis.Z), 2)
    bracket -= Pos(6, 0, -1) * Box(9, 3, 5, align=(Align.MIN, Align.CENTER, Align.MIN))
    out_along = Pos(px, py, z0) * Rot(Z=degrees(a)) * Pos(t.base_radius - 6)
    out.append(finish(out_along * bracket, "rest_bracket", "matt_black"))
    knob = Cylinder(2.2, 4.5, align=BOTTOM)
    out.append(finish(out_along * Pos(9.5, 0, 1) * knob, "bias_slider", "steel"))

    # Rest: a post and a U cradle, the groove in line with the parked tube.
    x, y = px + t.rest_reach * cos(a), py + t.rest_reach * sin(a)
    taper = (t.tube_radius_tip - t.tube_radius_root) / g["tube_length"]
    tube_r = t.tube_radius_root + taper * t.rest_reach
    seat = g["tube_z"] - tube_r - 1.0
    post = Cylinder(4.0, seat - 6 - (z0 + 3), align=BOTTOM)
    out.append(finish(Pos(x, y, z0 + 3) * post, "rest_post", "matt_black"))
    cradle = Box(9, 15, 11, align=BOTTOM)
    cradle -= Pos(Z=6 + tube_r + 1) * Rot(Y=90) * Cylinder(tube_r + 0.5, 20)
    cradle = Rot(Z=degrees(a)) * cradle
    out.append(finish(Pos(x, y, seat - 6) * cradle, "rest_cradle", "matt_black"))

    # Cue lever, on whichever side of the pillar faces away from the platter.
    sx, sy = p.spindle_x - px, p.spindle_y - py
    side = a + radians(90)
    if cos(side) * sx + sin(side) * sy > 0:
        side = a - radians(90)
    cx, cy = px + t.cue_reach * cos(side), py + t.cue_reach * sin(side)
    lift_top = g["tube_z"] - t.tube_radius_root - 8
    post = Cylinder(4.0, lift_top - z0, align=BOTTOM)
    out.append(finish(Pos(cx, cy, z0) * post, "cue_post", "matt_black"))
    lever_z = z0 + (lift_top - z0) * 0.6
    lever = Rot(Z=degrees(side)) * Rot(Y=90) * Cylinder(1.3, 22, align=BOTTOM)
    out.append(finish(Pos(cx, cy, lever_z) * lever, "cue_lever", "steel"))
    ball = Pos(cx + 22 * cos(side), cy + 22 * sin(side), lever_z) * Sphere(2.6)
    out.append(finish(ball, "cue_knob", "matt_black"))

    return Compound(children=out, label="arm_rest")


# ---------------------------------------------------------- record and cover


def record(p: TurntableParams) -> Shape:
    r = p.record
    z = p.record_surface
    out = []

    disc = Cylinder(r.radius, r.thickness, align=BOTTOM)
    disc -= Pos(Z=-1) * Cylinder(r.hole_radius, r.thickness + 2, align=BOTTOM)
    band = Cylinder(r.radius - 4, 0.3, align=BOTTOM) - Cylinder(
        r.lead_out_radius, 0.3, align=BOTTOM
    )
    disc -= Pos(Z=r.thickness - 0.3) * band
    disc -= Pos(Z=-0.3) * band
    out.append(finish(Pos(*p.spindle, z) * disc, "record", "vinyl"))

    label = Cylinder(r.label_radius, 0.25, align=BOTTOM)
    label -= Pos(Z=-1) * Cylinder(r.hole_radius, 3, align=BOTTOM)
    out.append(finish(Pos(*p.spindle, z + r.thickness) * label, "record_label", "label"))
    return Compound(children=out, label="record_assembly")


def dust_cover(p: TurntableParams) -> Shape:
    c, s = p.cover, p.plinth
    ol, od = s.length + 2 * c.margin, s.depth + 2 * c.margin
    z0 = p.plinth_top

    outer = Box(ol, od, c.height, align=BOTTOM)
    outer = fillet(outer.edges().filter_by(Axis.Z), c.corner_radius)
    outer = fillet(outer.faces().sort_by(Axis.Z)[-1].edges(), 7)

    inner = Box(ol - 2 * c.wall, od - 2 * c.wall, c.height, align=BOTTOM)
    inner = fillet(inner.edges().filter_by(Axis.Z), c.corner_radius - c.wall)
    shell = outer - Pos(Z=-c.wall) * inner

    shell -= Pos(0, od / 2, c.height / 2) * Box(ol - 80, 40, c.height)
    shell = finish(shell, "cover_shell", "acrylic")

    hinge_y = od / 2 - c.wall
    parts = [shell]
    for i, dx in enumerate((-130, 130)):
        pin = Rot(Y=90) * Cylinder(c.hinge_radius, c.hinge_length, align=BOTTOM)
        parts.append(
            finish(
                Pos(dx - c.hinge_length / 2, hinge_y, c.hinge_radius + 2) * pin,
                f"hinge_{i + 1}",
                "base",
            )
        )

    group = Compound(children=parts, label="dust_cover")
    swing = Pos(0, hinge_y, z0) * Rot(X=-c.open_angle) * Pos(0, -hinge_y, 0)
    return swing * group


# Re-exported so other modules can ask where the belt plane is... there is
# no belt on a direct drive deck, which is rather the point.
__all__ = [
    "adapter",
    "arm_rest",
    "controls",
    "direct_drive",
    "dust_cover",
    "feet",
    "finish",
    "mat",
    "platter",
    "platter_damping",
    "plinth",
    "rear_panel",
    "record",
    "rotor",
    "spindle",
    "strobe_dots",
    "target_light",
    "tonearm",
]
