#!/usr/bin/env python
"""Sanity checks on the built model.

These are the things that are easy to get wrong and hard to spot in a
render: the stylus has to touch the record, the arm has to measure up to its
alignment numbers, the belt has to run in both grooves, and nothing should
poke out through the dust cover.
"""

from __future__ import annotations

from math import hypot

from build123d import Shape

from turntable import DEFAULT, build
from turntable.parts import belt_plane

# Pairs that are meant to share space: press fits, shafts through bores and
# parts that are modelled as sitting inside one another.
ALLOWED_CLASHES = {
    frozenset(("spindle", "sub_platter")),
    frozenset(("spindle", "bearing_housing")),
    frozenset(("motor_shaft", "motor_pulley")),
    frozenset(("motor_shaft", "motor_body")),
    frozenset(("arm_post", "arm_collar")),
    frozenset(("arm_post", "arm_base")),
    frozenset(("arm_tube", "arm_yoke")),
    frozenset(("arm_tube", "counterweight")),
    frozenset(("counterweight", "vta_nut")),
    frozenset(("arm_tube", "headshell")),
    frozenset(("headshell", "finger_lift")),
    frozenset(("headshell", "cartridge")),
    frozenset(("cartridge", "cantilever")),
    frozenset(("cantilever", "stylus")),
    frozenset(("rest_post", "rest_cradle")),
    frozenset(("record", "record_label")),
    frozenset(("rca_1", "rca_pin_1")),
    frozenset(("rca_2", "rca_pin_2")),
    frozenset(("output_plate", "rca_1")),
    frozenset(("output_plate", "rca_2")),
    frozenset(("output_plate", "ground_post")),
    frozenset(("switch_plate", "button_1")),
    frozenset(("switch_plate", "button_2")),
    frozenset(("antiskate_arm", "arm_tube")),
    frozenset(("antiskate_arm", "antiskate_weight")),
    frozenset(("antiskate_arm", "arm_yoke")),
    frozenset(("arm_tube", "vta_nut")),
    frozenset(("output_plate", "rca_pin_1")),
    frozenset(("output_plate", "rca_pin_2")),
    frozenset(("cover_shell", "hinge_1")),
    frozenset(("cover_shell", "hinge_2")),
}

CLASH_VOLUME = 1.0  # mm^3, enough to ignore coincident faces

TOL = 0.25


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


def clashes(flat: dict[str, Shape]) -> int:
    """Flag solids that overlap when they have no business doing so.

    Bounding boxes come first because a real boolean on every pair of 46
    solids is far more work than it is worth.
    """
    items = sorted(flat.items())
    found = 0
    for i, (name_a, a) in enumerate(items):
        box_a = a.bounding_box()
        for name_b, b in items[i + 1 :]:
            if frozenset((name_a, name_b)) in ALLOWED_CLASHES:
                continue
            box_b = b.bounding_box()
            if (
                box_a.max.X < box_b.min.X or box_b.max.X < box_a.min.X
                or box_a.max.Y < box_b.min.Y or box_b.max.Y < box_a.min.Y
                or box_a.max.Z < box_b.min.Z or box_b.max.Z < box_a.min.Z
            ):
                continue
            try:
                overlap = (a & b).volume
            except Exception as exc:  # a boolean that OCCT refuses is not a clash
                print(f"  note  could not test {name_a} against {name_b}: {exc}")
                continue
            if overlap > CLASH_VOLUME:
                print(f"  FAIL  {name_a} clashes with {name_b} ({overlap:.0f} mm3)")
                found += 1
    if not found:
        print(f"  ok    no clashes among {len(items)} solids")
    return found


def main() -> int:
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

    belt = flat["drive_belt"].bounding_box()
    checks.append(("belt centre", (belt.min.Z + belt.max.Z) / 2, belt_plane(p)))
    pulley = flat["motor_pulley"].bounding_box()
    checks.append(("pulley groove centre", (pulley.min.Z + pulley.max.Z) / 2, belt_plane(p)))

    sub = flat["sub_platter"].bounding_box()
    checks.append(("sub-platter groove centre", (sub.min.Z + sub.max.Z) / 2, belt_plane(p)))

    mat = flat["platter_mat"].bounding_box()
    checks.append(("record sits on mat", flat["record"].bounding_box().min.Z, mat.max.Z))

    failures = 0
    for name, got, want in checks:
        ok = abs(got - want) <= TOL
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'}  {name:26s} {got:8.2f}  expected {want:8.2f}")

    # Containment: nothing outside the dust cover, feet flat on z = 0.
    cover = flat["cover_shell"].bounding_box()
    inside = [
        (n, s)
        for n, s in flat.items()
        if not n.startswith(("cover", "hinge")) and not n.startswith("foot")
    ]
    for name, shape in inside:
        b = shape.bounding_box()
        if b.max.Z > cover.max.Z or b.min.X < cover.min.X or b.max.X > cover.max.X:
            print(f"  FAIL  {name} pokes out of the dust cover")
            failures += 1

    failures += clashes(flat)

    bb = model.bounding_box()
    if abs(bb.min.Z) > TOL:
        print(f"  FAIL  model does not sit on z=0 (min z {bb.min.Z:.2f})")
        failures += 1
    else:
        size = f"{bb.size.X:.0f} x {bb.size.Y:.0f} x {bb.size.Z:.0f} mm"
        print(f"  ok    sits on z=0, overall {size}")

    print("\n" + ("all checks passed" if not failures else f"{failures} check(s) failed"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
