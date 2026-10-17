"""Put the parts together."""

from __future__ import annotations

from collections.abc import Callable

from build123d import Compound, Shape

from . import parts
from .params import DEFAULT, TurntableParams

# Group name -> builder. The groups become the top level of the GLB scene,
# which is what the web viewer's layer toggles switch on and off.
# The grouping is chosen so the viewer can animate whole groups: everything
# in "platter" turns with the spindle, everything in "record" turns with it,
# and the parts that stay put (the 45 adapter, the arm rest) live elsewhere.
GROUPS: dict[str, list[Callable[[TurntableParams], Shape]]] = {
    "chassis": [parts.plinth, parts.feet, parts.rear_panel, parts.speed_switch, parts.puck],
    "drive": [parts.motor, parts.belt, parts.bearing_housing],
    "platter": [parts.sub_platter, parts.platter, parts.mat, parts.spindle],
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
