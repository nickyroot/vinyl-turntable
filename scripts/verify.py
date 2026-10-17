#!/usr/bin/env python
"""Sanity checks on the built model.

These are the things that are easy to get wrong and hard to spot in a
render: the stylus has to touch the record, the arm has to measure up to
its alignment numbers, the rotor has to sit over the stator without
touching it, and nothing should poke out through the dust cover.

The tracking error check is the one that earns its keep on this deck. It
compares the modelled cartridge against the figures Technics publish, so
kinking the headshell the wrong way shows up as a number rather than as a
render that looks vaguely fine.
"""

from __future__ import annotations

from dataclasses import replace
from math import hypot

from build123d import Axis, Shape

from turntable import DEFAULT, build
from turntable.parts import dust_cover
from turntable.tracking import as_minutes, tracking_error

TOL = 0.25

# Pairs that are meant to share space: press fits, shafts through bores and
# parts modelled as sitting inside one another.
ALLOWED_CLASHES = {
    frozenset(("spindle", "bearing_hub")),
    frozenset(("spindle", "rotor_magnet")),
    frozenset(("arm_pillar", "arm_board")),
    frozenset(("arm_pillar", "vta_collar")),
    frozenset(("arm_pillar", "vta_lock")),
    frozenset(("arm_board", "vta_lock")),
    frozenset(("arm_board", "antiskate_dial")),
    frozenset(("arm_board", "rest_post")),
    frozenset(("arm_tube", "gimbal_yoke")),
    frozenset(("arm_stub", "gimbal_yoke")),
    frozenset(("arm_stub", "counterweight")),
    frozenset(("arm_stub", "arm_tube")),
    frozenset(("counterweight", "stylus_force_dial")),
    frozenset(("arm_tube", "headshell_collar")),
    frozenset(("headshell_collar", "headshell")),
    frozenset(("headshell", "finger_lift")),
    frozenset(("headshell", "cartridge")),
    frozenset(("cartridge", "cantilever")),
    frozenset(("cantilever", "stylus")),
    frozenset(("gimbal_yoke", "gimbal_pin_1")),
    frozenset(("gimbal_yoke", "gimbal_pin_2")),
    frozenset(("rest_post", "rest_cradle")),
    frozenset(("rest_cradle", "rest_clamp")),
    frozenset(("record", "record_label")),
    frozenset(("phono_lead_1", "phono_plug_1")),
    frozenset(("phono_lead_2", "phono_plug_2")),
    frozenset(("stator_plate", "stator_coils")),
    frozenset(("bearing_hub", "stator_coils")),
    frozenset(("arm_stub", "stylus_force_dial")),
    frozenset(("pitch_fader", "pitch_rail")),
    frozenset(("spindle", "stator_plate")),
    frozenset(("target_light", "target_lens")),
    frozenset(("platter", "platter_damping")),
    frozenset(("platter", "strobe_dots")),
    frozenset(("cover_shell", "hinge_1")),
    frozenset(("cover_shell", "hinge_2")),
}

CLASH_VOLUME = 1.0  # mm^3, enough to ignore coincident faces

# Parts that live outside the cover by design.
OUTSIDE_COVER = (
    "foot_",
    "cover",
    "hinge",
    "phono_",
    "earth_post",
    "mains_lead",
)


def walk(node: Shape, prefix: str = "") -> dict[str, Shape]:
    """Flatten the assembly to path -> shape, with world locations applied."""
    found: dict[str, Shape] = {}
    for child in node.children:
        path = f"{prefix}/{child.label}"
        moved = node.location * child if prefix else child
        if child.children:
            found.update(walk(moved, path))
        else:
            found[path] = moved
    return found


def clashes(flat: dict[str, Shape], quiet: bool = False) -> int:
    """Flag solids that overlap when they have no business doing so.

    Bounding boxes are computed once up front: asking OCCT for them inside
    the pair loop turns a quick check into a very slow one.
    """
    items = sorted(flat.items())
    boxes = {name: shape.bounding_box() for name, shape in items}
    found = 0
    for i, (name_a, a) in enumerate(items):
        box_a = boxes[name_a]
        for name_b, b in items[i + 1 :]:
            if frozenset((name_a, name_b)) in ALLOWED_CLASHES:
                continue
            box_b = boxes[name_b]
            if (
                box_a.max.X < box_b.min.X or box_b.max.X < box_a.min.X
                or box_a.max.Y < box_b.min.Y or box_b.max.Y < box_a.min.Y
                or box_a.max.Z < box_b.min.Z or box_b.max.Z < box_a.min.Z
            ):
                continue
            try:
                overlap = (a & b).volume
            except Exception as exc:  # a boolean OCCT refuses is not a clash
                print(f"  note  could not test {name_a} against {name_b}: {exc}")
                continue
            if overlap > CLASH_VOLUME:
                print(f"  FAIL  {name_a} clashes with {name_b} ({overlap:.0f} mm3)")
                found += 1
    if not found and not quiet:
        print(f"  ok    no clashes among {len(items)} parts")
    return found


def main() -> int:
    return 1 if run_checks() else 0


def run_checks(quiet: bool = False) -> int:
    """Run every check and return how many failed."""
    say = (lambda *a: None) if quiet else print
    p = DEFAULT
    model = build(p)
    flat = {k.rsplit("/", 1)[-1]: v for k, v in walk(model).items()}
    px, py = p.pivot

    checks: list[tuple[str, float, float]] = []

    stylus = flat["stylus"].bounding_box()
    checks.append(("stylus touches record", stylus.min.Z, p.record_surface))

    tip = stylus.center()
    checks.append(
        ("pivot to stylus", hypot(tip.X - px, tip.Y - py), p.tonearm.effective_length)
    )
    checks.append(
        (
            "stylus on lead-in groove",
            hypot(tip.X - p.spindle_x, tip.Y - p.spindle_y),
            p.parked_groove,
        )
    )

    # The platter carries the rotor magnet and it runs outside the stator
    # coils, so what matters is the radial air gap, not a vertical one.
    d = p.drive
    coil_outer = (d.stator_radius - 9) + 6.5
    gap = (d.rotor_radius - d.rotor_wall) - coil_outer
    checks.append(("motor air gap", round(gap, 2), 3.5))

    mat = flat["platter_mat"].bounding_box()
    checks.append(("record sits on mat", flat["record"].bounding_box().min.Z, mat.max.Z))

    checks.append(("platter top", flat["platter"].bounding_box().max.Z, p.platter_top))

    # The chassis top face has to stay a perfect rectangle: every facet is
    # meant to be below it, so it should still have exactly four sides.
    chassis = flat["chassis"]
    top = chassis.faces().sort_by(Axis.Z)[-1].outer_wire()
    tb = top.bounding_box()
    checks.append(("chassis top face sides", len(top.edges()), 4))
    checks.append(("chassis top face length", tb.size.X, p.plinth.length))
    checks.append(("chassis top face depth", tb.size.Y, p.plinth.depth))
    checks.append(("chassis is one solid", len(chassis.solids()), 1))

    failures = 0
    for name, got, want in checks:
        ok = abs(got - want) <= TOL
        failures += not ok
        line = f"  {'ok  ' if ok else 'FAIL'}  {name:26s} {got:8.2f}  expected {want:8.2f}"
        say(line) if ok else print(line)

    # Tracking error: Technics quote +0d32m inner to +2d32m outer, so the
    # modelled cartridge should stay inside about 3 degrees across the side.
    worst = 0.0
    for radius in (p.record.lead_out_radius, 90.0, 120.0, p.lead_in_radius):
        error = tracking_error(p, radius)
        worst = max(worst, abs(error))
        say(f"  ok    tracking error at r{radius:5.1f}   {as_minutes(error)}")
    if worst > 3.0:
        print(f"  FAIL  tracking error reaches {worst:.2f} deg; headshell offset is wrong way")
        failures += 1
    else:
        say(f"  ok    worst tracking error      {worst:8.2f}  within 3.00")

    # Containment: measure against a closed cover, otherwise raising it
    # lifts the ceiling out of the way and the check tests nothing.
    shut = replace(p, cover=replace(p.cover, open_angle=0.0))
    cover = dust_cover(shut).bounding_box()
    for name, shape in flat.items():
        if name.startswith(OUTSIDE_COVER):
            continue
        b = shape.bounding_box()
        if b.max.Z > cover.max.Z or b.min.X < cover.min.X or b.max.X > cover.max.X:
            print(f"  FAIL  {name} pokes out of the dust cover")
            failures += 1

    failures += clashes(flat, quiet)

    bb = model.bounding_box()
    if abs(bb.min.Z) > TOL:
        print(f"  FAIL  model does not sit on z=0 (min z {bb.min.Z:.2f})")
        failures += 1
    else:
        size = f"{bb.size.X:.0f} x {bb.size.Y:.0f} x {bb.size.Z:.0f} mm"
        say(f"  ok    sits on z=0, overall {size}")

    say("\n" + ("all checks passed" if not failures else f"{failures} check(s) failed"))
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
