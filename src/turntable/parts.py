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

from math import cos, radians, sin

from build123d import (
    Align,
    Axis,
    Box,
    Circle,
    Color,
    Compound,
    Cone,
    Cylinder,
    Plane,
    Pos,
    Rot,
    Shape,
    Spline,
    chamfer,
    fillet,
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


def plinth(p: TurntableParams) -> Shape:
    """Die-cast alloy top plate on a heavy moulded rubber base.

    Two separate parts in reality and here: the alloy carries the motor and
    the arm, the rubber kills what the alloy passes on.
    """
    s, f = p.plinth, p.foot
    out = []

    base = Box(s.length - 2 * s.base_inset, s.depth - 2 * s.base_inset, s.base, align=BOTTOM)
    base = fillet(base.edges().filter_by(Axis.Z), s.corner_radius - s.base_inset)
    out.append(finish(Pos(Z=f.height) * base, "rubber_base", "base"))

    plate = Box(s.length, s.depth, s.top_plate, align=BOTTOM)
    plate = fillet(plate.edges().filter_by(Axis.Z), s.corner_radius)
    plate = chamfer(plate.faces().sort_by(Axis.Z)[-1].edges(), s.top_chamfer)

    # Bores for the bearing and the arm pillar, and the two sunken wells.
    plate -= Pos(*p.spindle, -1) * Cylinder(p.drive.hub_radius, s.top_plate + 2, align=BOTTOM)
    plate -= Pos(*p.controls.adapter_at, s.top_plate - 4) * Cylinder(
        p.controls.adapter_radius + 2, 6, align=BOTTOM
    )
    slot_w, slot_l = p.controls.pitch_slot
    plate -= Pos(*p.controls.pitch_at, s.top_plate - 5) * Box(slot_w, slot_l, 7, align=BOTTOM)

    out.append(finish(Pos(Z=f.height + s.base) * plate, "top_plate", "top_plate"))
    return Compound(children=out, label="cabinet")


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
    """Captive phono leads and the earthing post, out of the back."""
    y = p.plinth.depth / 2 - p.plinth.base_inset
    z = p.foot.height + p.plinth.base / 2
    out = []

    boss = Box(78, 6, 24, align=(Align.CENTER, Align.MIN, Align.CENTER))
    boss = fillet(boss.edges().filter_by(Axis.Y), 3)
    out.append(finish(Pos(96, y, z) * boss, "outlet_boss", "base"))

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
    return finish(Pos(*p.spindle, z) * body, "platter", "aluminium")


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
    out.append(finish(Pos(*c.start_stop_at, z) * pad, "start_stop", "aluminium"))

    for name, dx in ((33, -c.speed_pitch / 2), (45, c.speed_pitch / 2)):
        bw, bd = c.speed_button
        btn = Box(bw, bd, 4.5, align=BOTTOM)
        btn = fillet(btn.edges().filter_by(Axis.Z), 2)
        out.append(
            finish(
                Pos(c.speed_at[0] + dx, c.speed_at[1], z) * btn,
                f"speed_{name}",
                "aluminium",
            )
        )
        led = Pos(c.speed_at[0] + dx, c.speed_at[1] + bd / 2 + 3, z) * Cylinder(
            1.8, 1.2, align=BOTTOM
        )
        out.append(finish(led, f"speed_led_{name}", "lamp"))

    # Power switch, with the strobe lamp ganged to it.
    knob = Cylinder(c.power_radius, c.power_height, align=BOTTOM)
    knob = chamfer(knob.edges().group_by(Axis.Z)[-1], 1.5)
    out.append(finish(Pos(*c.power_at, z) * knob, "power_switch", "aluminium"))

    ww, wd = c.strobe_window
    window = Box(ww, wd, 2.5, align=BOTTOM)
    window = fillet(window.edges().filter_by(Axis.Z), 1.5)
    out.append(finish(Pos(*c.strobe_at, z) * window, "strobe_lamp", "lamp"))

    # Pitch fader: the MK2's headline change, rotary knob to a 100 mm slide.
    slot_w, slot_l = c.pitch_slot
    rail = Box(3.5, slot_l - 10, 1.5, align=BOTTOM)
    out.append(finish(Pos(*c.pitch_at, z - 4) * rail, "pitch_rail", "steel"))

    kw, kd, kh = c.pitch_knob
    knob = Box(kw, kd, kh, align=BOTTOM)
    knob = fillet(knob.edges().filter_by(Axis.Z), 2.5)
    knob -= Pos(0, 0, z * 0 + kh - 1) * Box(kw + 2, 2.2, 2, align=BOTTOM)
    out.append(finish(Pos(*c.pitch_at, z - 5) * knob, "pitch_fader", "aluminium"))

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
    (effective_length, 0) by definition and the headshell kinks off it at
    the offset angle. Everything else follows from that.
    """
    t = p.tonearm
    axis = radians(OFFSET_SIGN * t.offset_angle)
    reach = t.collar_length + t.headshell_length

    stylus = (t.effective_length, 0.0)
    collar = (stylus[0] - reach * cos(axis), stylus[1] - reach * sin(axis))

    # Vertical stack under the tube centreline, set so the stylus just
    # touches the record.
    head_top = -t.tube_radius
    head_bottom = head_top - t.headshell_thickness
    cart_bottom = head_bottom - t.cartridge_height
    cantilever_z = cart_bottom + 2.0
    tip_z = cantilever_z - t.stylus_length

    return {
        "axis": axis,
        "stylus": stylus,
        "collar": collar,
        "head_top": head_top,
        "head_bottom": head_bottom,
        "cantilever_z": cantilever_z,
        "tip_z": tip_z,
        "tube_z": p.record_surface - tip_z,
    }


def _s_path(p: TurntableParams) -> Spline:
    """The S, as a spline from the pivot to the headshell collar.

    Control points are given along the pivot-to-collar chord and across it,
    so reshaping the bend cannot move either end.
    """
    t = p.tonearm
    g = _arm_frame(p)
    cx, cy = g["collar"]
    chord = (cx**2 + cy**2) ** 0.5
    ux, uy = cx / chord, cy / chord
    px, py = -uy, ux  # perpendicular

    pts = [(0.0, 0.0, 0.0)]
    for along, across in t.s_curve:
        d = along * chord
        o = across * t.effective_length
        pts.append((ux * d + px * o, uy * d + py * o, 0.0))
    pts.append((cx, cy, 0.0))
    return Spline(*pts)


def tonearm(p: TurntableParams) -> Shape:
    """Universal S-shaped arm, built at the pivot and swung into place."""
    t = p.tonearm
    g = _arm_frame(p)
    px, py = p.pivot
    out = []

    # The black arm board let into the top plate.
    board = Cylinder(t.base_radius, t.base_height, align=BOTTOM)
    board = chamfer(board.edges().group_by(Axis.Z)[-1], 1.5)
    out.append(finish(Pos(px, py, p.plinth_top) * board, "arm_board", "base"))

    tube_z = g["tube_z"]
    post_top = tube_z - t.yoke_thickness / 2 - 3
    post_base = p.plinth_top + t.base_height
    post = Cylinder(t.post_radius, post_top - post_base, align=BOTTOM)
    out.append(finish(Pos(px, py, post_base) * post, "arm_pillar", "steel"))

    # VTA helicoid and its lock ring: 6 mm of height adjustment.
    helicoid = Cylinder(t.collar_radius, t.vta_range + 8, align=BOTTOM)
    helicoid = chamfer(helicoid.edges(), 1.0)
    out.append(
        finish(Pos(px, py, post_top - t.vta_range - 8) * helicoid, "vta_collar", "arm_alloy")
    )
    lock = Cylinder(t.collar_radius + 2.5, 4, align=BOTTOM)
    lock = chamfer(lock.edges(), 0.8)
    out.append(finish(Pos(px, py, post_base + 2) * lock, "vta_lock", "arm_alloy"))

    # From here everything is laid out in the local frame and swung round.
    place = Pos(px, py, tube_z) * Rot(Z=heading(p))

    yoke = Box(t.yoke_width, t.yoke_width, t.yoke_thickness)
    yoke = fillet(yoke.edges().filter_by(Axis.Z), 5)
    out.append(finish(place * yoke, "gimbal_yoke", "arm_alloy"))

    for i, side in enumerate((-1, 1)):
        pin = Rot(X=90) * Cylinder(3.0, 5, align=BOTTOM)
        out.append(
            finish(
                place * Pos(0, side * (t.yoke_width / 2 + 2), 0) * pin,
                f"gimbal_pin_{i + 1}",
                "steel",
            )
        )

    # The S itself.
    path = _s_path(p)
    section = Plane(origin=path @ 0, z_dir=path % 0) * Circle(t.tube_radius)
    tube = sweep(section, path)
    out.append(finish(place * tube, "arm_tube", "arm_alloy"))

    # Straight stub behind the pivot carrying the counterweight.
    stub = Rot(Y=-90) * Cylinder(t.tube_radius, t.tube_rear, align=BOTTOM)
    out.append(finish(place * stub, "arm_stub", "arm_alloy"))

    cw = Rot(Y=90) * Cylinder(t.counterweight_radius, t.counterweight_length, align=BOTTOM)
    cw = chamfer(cw.edges(), 2.5)
    cw_x = -t.tube_rear + 6
    out.append(finish(place * Pos(cw_x) * cw, "counterweight", "rubber"))

    dial = Rot(Y=90) * Cylinder(t.counterweight_radius * 0.6, 6, align=BOTTOM)
    out.append(
        finish(place * Pos(cw_x + t.counterweight_length) * dial, "stylus_force_dial", "arm_alloy")
    )

    # Anti-skate: a calibrated dial beside the pillar on the 1200.
    reach, bearing = t.antiskate_at
    ax = px + reach * cos(radians(bearing))
    ay = py + reach * sin(radians(bearing))
    anti = Cylinder(t.antiskate_radius, 10, align=BOTTOM)
    anti = chamfer(anti.edges().group_by(Axis.Z)[-1], 1.0)
    out.append(finish(Pos(ax, ay, p.plinth_top) * anti, "antiskate_dial", "arm_alloy"))

    # Headshell: bayonet collar, then the shell at the offset angle.
    head = place * Pos(*g["collar"]) * Rot(Z=OFFSET_SIGN * t.offset_angle)

    collar = Rot(Y=90) * Cylinder(t.collar_dia / 2, t.collar_length, align=BOTTOM)
    collar = chamfer(collar.edges(), 1.0)
    out.append(finish(head * collar, "headshell_collar", "arm_alloy"))

    shell = Box(
        t.headshell_length,
        t.headshell_width,
        t.headshell_thickness,
        align=(Align.MIN, Align.CENTER, Align.MAX),
    )
    shell = fillet(shell.edges().filter_by(Axis.Z), 3)
    out.append(
        finish(head * Pos(t.collar_length, 0, g["head_top"]) * shell, "headshell", "arm_alloy")
    )

    finger = Box(12, 4, 16, align=(Align.MIN, Align.CENTER, Align.MIN))
    finger = fillet(finger.edges().filter_by(Axis.Y), 2)
    out.append(
        finish(
            head * Pos(t.collar_length + t.headshell_length - 12, 0, g["head_top"]) * finger,
            "finger_lift",
            "arm_alloy",
        )
    )

    reach = t.collar_length + t.headshell_length
    cart = Box(
        t.cartridge_length,
        t.cartridge_width,
        t.cartridge_height,
        align=(Align.MAX, Align.CENTER, Align.MAX),
    )
    cart = fillet(cart.edges().filter_by(Axis.X), 1.5)
    out.append(finish(head * Pos(reach - 5, 0, g["head_bottom"]) * cart, "cartridge", "cartridge"))

    cantilever = Rot(Y=90) * Cylinder(0.7, 7, align=BOTTOM)
    out.append(
        finish(
            head * Pos(reach - 7, 0, g["cantilever_z"]) * cantilever, "cantilever", "arm_alloy"
        )
    )

    tip = Rot(Y=180) * Cone(0.9, 0.05, t.stylus_length, align=BOTTOM)
    out.append(finish(head * Pos(reach, 0, g["cantilever_z"]) * tip, "stylus", "steel"))

    return Compound(children=out, label="tonearm")


def arm_rest(p: TurntableParams) -> Shape:
    """Rest and clamp, on the arm board outboard of the pivot."""
    t = p.tonearm
    g = _arm_frame(p)
    px, py = p.pivot
    reach, bearing = t.rest_at
    a = radians(bearing)
    x, y = px + reach * cos(a), py + reach * sin(a)

    height = g["tube_z"] - p.plinth_top - 10
    out = []
    post = Cylinder(5.5, height, align=BOTTOM)
    out.append(finish(Pos(x, y, p.plinth_top) * post, "rest_post", "arm_alloy"))
    cradle = Cylinder(9.5, 8, align=BOTTOM)
    cradle -= Pos(Z=4.5) * Box(5.0, 32, 9, align=BOTTOM)
    out.append(finish(Pos(x, y, p.plinth_top + height) * cradle, "rest_cradle", "rubber"))
    clip = Box(4, 13, 3, align=BOTTOM)
    clip = fillet(clip.edges().filter_by(Axis.Z), 1.2)
    out.append(
        finish(Pos(x + 9, y, p.plinth_top + height + 4) * clip, "rest_clamp", "arm_alloy")
    )
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
    outer = fillet(outer.edges().filter_by(Axis.Z), s.corner_radius + c.margin)
    outer = fillet(outer.faces().sort_by(Axis.Z)[-1].edges(), 7)

    inner = Box(ol - 2 * c.wall, od - 2 * c.wall, c.height, align=BOTTOM)
    inner = fillet(inner.edges().filter_by(Axis.Z), s.corner_radius + c.margin - c.wall)
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
