"""Put the parts together."""

from __future__ import annotations

from collections.abc import Callable

from build123d import Compound, Shape

from . import parts
from .params import DEFAULT, TurntableParams

# Group name -> builder. The groups become the top level of the GLB scene,
# and the viewer's layer toggles. Everything that turns with the spindle is
# in "platter", including the rotor magnet, because on a direct drive deck
# the platter really is half the motor.
GROUPS: dict[str, list[Callable[[TurntableParams], Shape]]] = {
    "cabinet": [parts.plinth, parts.feet, parts.rear_panel],
    "controls": [parts.controls, parts.target_light, parts.adapter],
    "drive": [parts.direct_drive, parts.spindle],
    "platter": [parts.rotor, parts.platter, parts.platter_damping, parts.strobe_dots, parts.mat],
    "arm": [parts.tonearm, parts.arm_rest],
    "record": [parts.record],
    "cover": [parts.dust_cover],
}


def part_registry() -> dict[str, Callable[[TurntableParams], Shape]]:
    """Flat name -> builder map, handy for rendering one part on its own."""
    return {fn.__name__: fn for fns in GROUPS.values() for fn in fns}


def build(
    p: TurntableParams | None = None,
    groups: list[str] | None = None,
) -> Compound:
    p = p or DEFAULT
    wanted = groups or list(GROUPS)
    children = []
    for name in wanted:
        if name not in GROUPS:
            raise KeyError(f"unknown group {name!r}, expected one of {list(GROUPS)}")
        members = [fn(p) for fn in GROUPS[name]]
        children.append(Compound(children=members, label=name))
    return Compound(children=children, label="turntable")
