"""Every part of the turntable, one function each.

Each function takes the parameter set and returns a shape that is already
positioned in the assembly's world frame: feet on z = 0, plinth centred on
the origin, X running left to right and Y running front to back. That keeps
the assembly module a plain list of calls and makes any single part easy to
look at on its own.
"""

from __future__ import annotations

from math import atan2, cos, degrees, radians, sin

from build123d import (
    Align,
    Axis,
    Box,
    Circle,
    Color,
    Compound,
    Cone,
    Cylinder,
    Kind,
    Pos,
    Rot,
    Shape,
    Torus,
    chamfer,
    extrude,
    fillet,
    make_hull,
    offset,
)

from .params import PALETTE, TurntableParams
from .tracking import arm_angle

BOTTOM = (Align.CENTER, Align.CENTER, Align.MIN)
TOP = (Align.CENTER, Align.CENTER, Align.MAX)


def finish(shape: Shape, label: str, key: str) -> Shape:
    """Tag a shape with a name and a colour so the GLB carries both."""
    r, g, b, a = PALETTE[key].rgba
    shape.color = Color(r, g, b, a)
    shape.label = label
    return shape


# --------------------------------------------------------------------- plinth


def plinth(p: TurntableParams) -> Shape:
    s = p.plinth
    body = Box(s.length, s.depth, s.height, align=BOTTOM)
    body = fillet(body.edges().filter_by(Axis.Z), s.corner_radius)
    top = body.faces().sort_by(Axis.Z)[-1]
    body = chamfer(top.edges(), s.top_chamfer)

    # Through holes for the main bearing and the motor can.
    body -= Pos(*p.spindle, -1) * Cylinder(
        p.bearing.housing_radius - 6, s.height + 2, align=BOTTOM
    )
    body -= Pos(*p.motor_centre, -1) * Cylinder(
        p.motor.body_radius + 0.4, s.height + 2, align=BOTTOM
    )
    return finish(Pos(Z=p.foot.height) * body, "plinth", "plinth")


def feet(p: TurntableParams) -> Shape:
    f, s = p.foot, p.plinth
    dx = s.length / 2 - f.inset
    dy = s.depth / 2 - f.inset
    out = []
    for i, (x, y) in enumerate(((-dx, -dy), (dx, -dy), (-dx, dy), (dx, dy))):
        one = Cylinder(f.radius, f.height, align=BOTTOM)
        one = fillet(one.edges().group_by(Axis.Z)[0], f.radius * 0.35)
        one = chamfer(one.edges().group_by(Axis.Z)[-1], 1.2)
        out.append(finish(Pos(x, y, 0) * one, f"foot_{i + 1}", "rubber"))
    return Compound(children=out, label="feet")


def rear_panel(p: TurntableParams) -> Shape:
    """Phono outputs and the DC inlet, let into the back face."""
    y = p.plinth.depth / 2
    z = p.foot.height + p.plinth.height / 2
    out = []

    plate = Box(72, 3, 22, align=(Align.CENTER, Align.MIN, Align.CENTER))
    out.append(finish(Pos(120, y, z) * plate, "output_plate", "steel"))

    for i, dx in enumerate((100, 124)):
        jack = Rot(X=-90) * Cylinder(5.0, 11, align=BOTTOM)
        out.append(finish(Pos(dx, y, z) * jack, f"rca_{i + 1}", "brass"))
        pin = Rot(X=-90) * Cylinder(1.1, 13, align=BOTTOM)
        out.append(finish(Pos(dx, y, z) * pin, f"rca_pin_{i + 1}", "copper"))

    ground = Rot(X=-90) * Cylinder(3.2, 9, align=BOTTOM)
    out.append(finish(Pos(146, y, z) * ground, "ground_post", "brass"))

    inlet = Rot(X=-90) * Cylinder(4.2, 10, align=BOTTOM)
    out.append(finish(Pos(-150, y, z) * inlet, "dc_inlet", "steel"))

    return Compound(children=out, label="rear_panel")


def speed_switch(p: TurntableParams) -> Shape:
    z = p.plinth_top
    body = Box(34, 16, 5, align=BOTTOM)
    body = fillet(body.edges().filter_by(Axis.Z), 3)
    out = [finish(Pos(-168, -132, z) * body, "switch_plate", "steel")]
    for i, dx in enumerate((-10, 10)):
        knob = Cylinder(4.6, 4, align=BOTTOM)
        knob = chamfer(knob.edges().group_by(Axis.Z)[-1], 0.8)
        out.append(finish(Pos(-168 + dx, -132, z + 5) * knob, f"button_{i + 1}", "aluminium"))
    return Compound(children=out, label="speed_switch")


# ------------------------------------------------------------ bearing, platter


def bearing_housing(p: TurntableParams) -> Shape:
    b = p.bearing
    body = Cylinder(b.housing_radius, b.housing_height, align=BOTTOM)
    body = chamfer(body.edges().group_by(Axis.Z)[-1], 2.0)
    body -= Pos(Z=-1) * Cylinder(b.spindle_radius + 1.2, b.housing_height + 2, align=BOTTOM)
    return finish(Pos(*p.spindle, p.plinth_top) * body, "bearing_housing", "steel")


def sub_platter(p: TurntableParams) -> Shape:
    """Belt pulley that the platter drops onto, with a groove for the belt."""
    b, m = p.bearing, p.motor
    z = p.plinth_top + p.bearing.housing_height
    body = Cylinder(b.sub_radius, b.sub_thickness, align=BOTTOM)
    groove = Pos(Z=b.sub_thickness / 2) * Torus(b.sub_radius, m.belt_height / 2)
    body -= groove
    body -= Pos(Z=-1) * Cylinder(b.spindle_radius + 0.1, b.sub_thickness + 2, align=BOTTOM)
    body = chamfer(body.edges().group_by(Axis.Z)[-1], 1.0)
    return finish(Pos(*p.spindle, z) * body, "sub_platter", "aluminium")


def spindle(p: TurntableParams) -> Shape:
    b = p.bearing
    bottom = p.plinth_top - 6
    top = p.record_surface + b.spindle_above_mat
    shaft = Cylinder(b.spindle_radius, top - bottom, align=BOTTOM)
    shaft = chamfer(shaft.edges().group_by(Axis.Z)[-1], b.spindle_radius * 0.45)
    return finish(Pos(*p.spindle, bottom) * shaft, "spindle", "steel")


def platter(p: TurntableParams) -> Shape:
    pl, b = p.platter, p.bearing
    z = p.plinth_top + pl.clearance
    body = Cylinder(pl.radius, pl.thickness, align=BOTTOM)
    # Relieve the underside into an annulus, leaving a central land that
    # seats on the sub-platter and a rim that comes back down. The relief is
    # what gives the motor pulley and the belt somewhere to live.
    relief = Cylinder(pl.relief_radius, pl.relief_depth, align=BOTTOM) - Cylinder(
        pl.boss_radius, pl.relief_depth, align=BOTTOM
    )
    body -= Pos(Z=-0.01) * relief
    body -= Pos(Z=-1) * Cylinder(b.spindle_radius + 0.15, pl.thickness + 2, align=BOTTOM)
    body = chamfer(
        body.faces().sort_by(Axis.Z)[-1].edges().sort_by(Axis.X)[-1], pl.rim_chamfer
    )
    return finish(Pos(*p.spindle, z) * body, "platter", "aluminium")


def mat(p: TurntableParams) -> Shape:
    pl = p.platter
    body = Cylinder(pl.mat_radius, pl.mat_thickness, align=BOTTOM)
    body -= Pos(Z=-1) * Cylinder(
        p.bearing.spindle_radius + 0.2, pl.mat_thickness + 2, align=BOTTOM
    )
    # Shallow relief ring, the usual trick to keep the label area clear.
    body -= Pos(Z=pl.mat_thickness - 0.4) * (
        Cylinder(pl.strobe_ring_radius, 1, align=BOTTOM)
        - Cylinder(pl.strobe_ring_radius - 3, 1, align=BOTTOM)
    )
    return finish(Pos(*p.spindle, p.platter_top) * body, "platter_mat", "felt")


def puck(p: TurntableParams) -> Shape:
    """45 rpm adapter, parked on the plinth where there is room for it."""
    body = Cylinder(19, 6, align=BOTTOM)
    body = chamfer(body.edges().group_by(Axis.Z)[-1], 1.2)
    body -= Pos(Z=-1) * Cylinder(3.6, 8, align=BOTTOM)
    return finish(Pos(150, -120, p.plinth_top) * body, "adapter_45", "aluminium")


# ----------------------------------------------------------------- drive train


def belt_plane(p: TurntableParams) -> float:
    """Z of the belt centreline: the sub-platter groove sets it, and the
    motor pulley groove is then placed to match."""
    return p.plinth_top + p.bearing.housing_height + p.bearing.sub_thickness / 2


def motor(p: TurntableParams) -> Shape:
    m = p.motor
    mx, my = p.motor_centre
    z = p.plinth_top
    out = []

    can = Cylinder(m.body_radius, m.body_height, align=TOP)
    can = chamfer(can.edges().group_by(Axis.Z)[0], 1.5)
    out.append(finish(Pos(mx, my, z + 2) * can, "motor_body", "steel"))

    pulley_z = belt_plane(p) - m.pulley_height / 2
    pulley = Cylinder(m.pulley_radius, m.pulley_height, align=BOTTOM)
    pulley -= Pos(Z=m.pulley_height / 2) * Torus(m.pulley_radius, m.belt_height / 2)
    pulley = chamfer(pulley.edges().group_by(Axis.Z)[-1], 0.8)
    out.append(finish(Pos(mx, my, pulley_z) * pulley, "motor_pulley", "aluminium"))

    shaft = Cylinder(2.0, pulley_z + m.pulley_height - (z - 2), align=BOTTOM)
    out.append(finish(Pos(mx, my, z - 2) * shaft, "motor_shaft", "steel"))

    return Compound(children=out, label="motor")


def belt(p: TurntableParams) -> Shape:
    """Flat belt wrapped round the pulley and the sub-platter.

    The path a belt takes over two pulleys is the convex hull of the two
    circles, so build that hull as a face and give it a wall thickness.
    """
    m, b = p.motor, p.bearing
    sx, sy = p.spindle
    mx, my = p.motor_centre
    z = belt_plane(p) - m.belt_height / 2

    big = Pos(sx, sy) * Circle(b.sub_radius)
    small = Pos(mx, my) * Circle(m.pulley_radius)
    hull = make_hull(big.edges() + small.edges())
    ring = offset(hull, m.belt_thickness, kind=Kind.ARC) - hull
    body = extrude(ring, m.belt_height)
    return finish(Pos(Z=z) * body, "drive_belt", "rubber")


# -------------------------------------------------------------------- tonearm


def _arm_geometry(p: TurntableParams) -> dict[str, float]:
    """Resolve the armtube heading from the alignment numbers.

    The tube runs `tube_front` from the pivot, then the headshell carries on
    at `offset_angle`. Picking tube_front so the two legs resolve to the
    effective length puts the stylus exactly `overhang` past the spindle.
    """
    t = p.tonearm
    off = radians(t.offset_angle)
    l2 = t.headshell_length
    tube_front = -l2 * cos(off) + (t.effective_length**2 - (l2 * sin(off)) ** 2) ** 0.5
    # Angle between the tube and the pivot-to-stylus line.
    kink = degrees(atan2(l2 * sin(off), tube_front + l2 * cos(off)))

    px, py = p.pivot
    to_stylus = degrees(atan2(p.spindle_y - py, p.spindle_x - px))

    # Vertical stack under the armtube centreline, which fixes how high the
    # pillar has to hold the tube for the stylus to just touch the record.
    head_top = -t.tube_radius
    head_bottom = head_top - t.headshell_thickness
    cart_bottom = head_bottom - t.cartridge_height
    cantilever_z = cart_bottom + 2.0
    tip_z = cantilever_z - t.stylus_length

    return {
        "tube_front": tube_front,
        "heading": to_stylus - kink + arm_angle(p, p.parked_groove),
        "stylus_heading": to_stylus,
        "tube_z": p.record_surface - tip_z,
        "head_top": head_top,
        "head_bottom": head_bottom,
        "cantilever_z": cantilever_z,
        "tip_z": tip_z,
    }


def tonearm(p: TurntableParams) -> Shape:
    t = p.tonearm
    g = _arm_geometry(p)
    px, py = p.pivot
    tube_z = g["tube_z"]
    out = []

    # Pillar, in world coordinates: it does not care about the heading.
    base = Cylinder(t.base_radius, t.base_height, align=BOTTOM)
    base = chamfer(base.edges().group_by(Axis.Z)[-1], 1.5)
    out.append(finish(Pos(px, py, p.plinth_top) * base, "arm_base", "aluminium"))

    post_top = tube_z - t.yoke_thickness / 2 - 2
    post_h = post_top - (p.plinth_top + t.base_height)
    post = Cylinder(t.post_radius, post_h, align=BOTTOM)
    out.append(
        finish(Pos(px, py, p.plinth_top + t.base_height) * post, "arm_post", "steel")
    )

    collar = Cylinder(t.post_radius + 3, 8, align=BOTTOM)
    collar = chamfer(collar.edges(), 0.8)
    out.append(finish(Pos(px, py, post_top - 8) * collar, "arm_collar", "aluminium"))

    # Everything from here is built along +X and then swung to the heading.
    place = Pos(px, py, tube_z) * Rot(Z=g["heading"])

    yoke = Box(t.yoke_width, t.yoke_width, t.yoke_thickness)
    yoke = fillet(yoke.edges().filter_by(Axis.Z), 4)
    out.append(finish(place * yoke, "arm_yoke", "aluminium"))

    tube_len = g["tube_front"] + t.tube_rear
    tube = Rot(Y=90) * Cylinder(t.tube_radius, tube_len, align=BOTTOM)
    out.append(finish(place * Pos(-t.tube_rear) * tube, "arm_tube", "aluminium"))

    # Counterweight on a stub behind the pivot.
    cw = Rot(Y=90) * Cylinder(t.counterweight_radius, t.counterweight_length, align=BOTTOM)
    cw = chamfer(cw.edges(), 2.0)
    cw_x = -t.tube_rear + 4
    out.append(finish(place * Pos(cw_x) * cw, "counterweight", "rubber"))

    cw_ring = Rot(Y=90) * Cylinder(t.counterweight_radius * 0.55, 5, align=BOTTOM)
    out.append(
        finish(place * Pos(cw_x + t.counterweight_length) * cw_ring, "vta_nut", "brass")
    )

    # Anti-skate weight hanging off a short outrigger.
    arm_out = Rot(X=90) * Cylinder(1.4, 26, align=BOTTOM)
    out.append(finish(place * Pos(-14, 0, 2) * arm_out, "antiskate_arm", "steel"))
    bob = Cylinder(5.5, 9, align=BOTTOM)
    bob = chamfer(bob.edges(), 1.0)
    out.append(finish(place * Pos(-14, -26, -12) * bob, "antiskate_weight", "brass"))

    # Headshell, carrying on at the offset angle. Its own origin is the
    # front of the armtube, so the stylus sits at x = headshell_length and
    # the whole kinked path resolves to the effective length.
    head = place * Pos(g["tube_front"]) * Rot(Z=t.offset_angle)
    shell = Box(
        t.headshell_length,
        t.headshell_width,
        t.headshell_thickness,
        align=(Align.MIN, Align.CENTER, Align.MAX),
    )
    shell = fillet(shell.edges().filter_by(Axis.Z), 2.5)
    out.append(finish(head * Pos(Z=g["head_top"]) * shell, "headshell", "aluminium"))

    finger = Box(11, 4, 15, align=(Align.MIN, Align.CENTER, Align.MIN))
    finger = fillet(finger.edges().filter_by(Axis.Y), 2)
    out.append(
        finish(
            head * Pos(t.headshell_length - 11, 0, g["head_top"]) * finger,
            "finger_lift",
            "aluminium",
        )
    )

    # Cartridge body sits behind the stylus, hung under the headshell.
    cart = Box(
        t.cartridge_length,
        t.cartridge_width,
        t.cartridge_height,
        align=(Align.MAX, Align.CENTER, Align.MAX),
    )
    cart = fillet(cart.edges().filter_by(Axis.X), 1.5)
    out.append(
        finish(
            head * Pos(t.headshell_length - 5, 0, g["head_bottom"]) * cart,
            "cartridge",
            "cartridge",
        )
    )

    cantilever = Rot(Y=90) * Cylinder(0.7, 7, align=BOTTOM)
    out.append(
        finish(
            head * Pos(t.headshell_length - 7, 0, g["cantilever_z"]) * cantilever,
            "cantilever",
            "aluminium",
        )
    )

    # Stylus tip, pointing down and landing exactly on the record surface.
    tip = Rot(Y=180) * Cone(0.9, 0.05, t.stylus_length, align=BOTTOM)
    out.append(
        finish(
            head * Pos(t.headshell_length, 0, g["cantilever_z"]) * tip,
            "stylus",
            "steel",
        )
    )

    return Compound(children=out, label="tonearm")


def arm_rest(p: TurntableParams) -> Shape:
    """Rest and clip for the arm, just outboard of the pivot."""
    g = _arm_geometry(p)
    px, py = p.pivot
    a = radians(g["heading"] - 52)
    x, y = px + 54 * cos(a), py + 54 * sin(a)

    # Stand the cradle so its notch sits just under the armtube.
    height = g["tube_z"] - p.plinth_top - 9
    out = []
    post = Cylinder(5, height, align=BOTTOM)
    out.append(finish(Pos(x, y, p.plinth_top) * post, "rest_post", "aluminium"))
    cradle = Cylinder(9, 7, align=BOTTOM)
    cradle -= Pos(Z=4) * Box(4.5, 30, 8, align=BOTTOM)
    out.append(
        finish(Pos(x, y, p.plinth_top + height) * cradle, "rest_cradle", "rubber")
    )
    return Compound(children=out, label="arm_rest")


# ---------------------------------------------------------- record, dust cover


def record(p: TurntableParams) -> Shape:
    r = p.record
    z = p.record_surface
    out = []

    disc = Cylinder(r.radius, r.thickness, align=BOTTOM)
    disc -= Pos(Z=-1) * Cylinder(r.hole_radius, r.thickness + 2, align=BOTTOM)
    # Drop the grooved band a hair below the rims so the band reads as a band.
    band = Cylinder(r.radius - 4, 0.3, align=BOTTOM) - Cylinder(
        r.lead_out_radius, 0.3, align=BOTTOM
    )
    disc -= Pos(Z=r.thickness - 0.3) * band
    disc -= Pos(Z=-0.3) * band
    out.append(finish(Pos(*p.spindle, z) * disc, "record", "vinyl"))

    label = Cylinder(r.label_radius, 0.25, align=BOTTOM)
    label -= Pos(Z=-1) * Cylinder(r.hole_radius, 3, align=BOTTOM)
    out.append(
        finish(Pos(*p.spindle, z + r.thickness) * label, "record_label", "label")
    )
    return Compound(children=out, label="record_assembly")


def dust_cover(p: TurntableParams) -> Shape:
    c, s = p.cover, p.plinth
    ol, od = s.length + 2 * c.margin, s.depth + 2 * c.margin
    z0 = p.plinth_top

    outer = Box(ol, od, c.height, align=BOTTOM)
    outer = fillet(outer.edges().filter_by(Axis.Z), s.corner_radius + c.margin)
    outer = fillet(outer.faces().sort_by(Axis.Z)[-1].edges(), 8)

    inner = Box(ol - 2 * c.wall, od - 2 * c.wall, c.height, align=BOTTOM)
    inner = fillet(inner.edges().filter_by(Axis.Z), s.corner_radius + c.margin - c.wall)
    shell = outer - Pos(Z=-c.wall) * inner

    # Open the back so the cover can hinge and the cables can leave.
    shell -= Pos(0, od / 2, c.height / 2) * Box(
        ol - 60, 40, c.height, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )
    shell = finish(shell, "cover_shell", "acrylic")

    hinge_y = od / 2 - c.wall
    parts = [shell]
    for i, dx in enumerate((-120, 120)):
        pin = Rot(Y=90) * Cylinder(c.hinge_radius, c.hinge_length, align=BOTTOM)
        parts.append(
            finish(
                Pos(dx - c.hinge_length / 2, hinge_y, c.hinge_radius + 2) * pin,
                f"hinge_{i + 1}",
                "steel",
            )
        )

    group = Compound(children=parts, label="dust_cover")
    swing = Pos(0, hinge_y, z0) * Rot(X=-c.open_angle) * Pos(0, -hinge_y, 0)
    return swing * group
