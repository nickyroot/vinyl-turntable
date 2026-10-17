"""Dimensions and finishes for the turntable.

Everything is millimetres and degrees. The tonearm geometry follows the
classic 239 mm effective length / 222 mm pivot-to-spindle alignment, which
puts the stylus 17 mm past the spindle at a 23.1 deg headshell offset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, hypot, radians, sin


@dataclass(frozen=True)
class Finish:
    """A named colour, as linear-ish sRGB plus alpha."""

    rgba: tuple[float, float, float, float]


PALETTE = {
    "plinth": Finish((0.10, 0.10, 0.11, 1.0)),
    "plinth_edge": Finish((0.16, 0.16, 0.17, 1.0)),
    "aluminium": Finish((0.72, 0.73, 0.75, 1.0)),
    "steel": Finish((0.55, 0.57, 0.60, 1.0)),
    "brass": Finish((0.72, 0.58, 0.28, 1.0)),
    "rubber": Finish((0.14, 0.14, 0.15, 1.0)),
    "felt": Finish((0.11, 0.10, 0.12, 1.0)),
    "vinyl": Finish((0.04, 0.04, 0.05, 1.0)),
    "label": Finish((0.80, 0.26, 0.18, 1.0)),
    "acrylic": Finish((0.70, 0.78, 0.82, 0.22)),
    "cartridge": Finish((0.62, 0.14, 0.12, 1.0)),
    "copper": Finish((0.78, 0.45, 0.25, 1.0)),
}


@dataclass(frozen=True)
class Plinth:
    length: float = 450.0   # left to right
    depth: float = 350.0    # front to back
    height: float = 42.0
    corner_radius: float = 10.0
    top_chamfer: float = 1.5


@dataclass(frozen=True)
class Foot:
    radius: float = 20.0
    height: float = 18.0
    inset: float = 38.0     # from plinth corner, in both axes


@dataclass(frozen=True)
class Platter:
    radius: float = 150.0
    thickness: float = 20.0
    rim_chamfer: float = 1.5
    clearance: float = 16.0         # platter underside above plinth top
    relief_radius: float = 140.0    # machined relief on the underside
    relief_depth: float = 4.0
    boss_radius: float = 58.0       # central land that seats on the sub-platter
    mat_radius: float = 147.0
    mat_thickness: float = 3.0
    strobe_ring_radius: float = 143.0


@dataclass(frozen=True)
class Bearing:
    housing_radius: float = 22.0
    housing_height: float = 4.0     # flange above the plinth top
    sub_radius: float = 55.0        # sub-platter / belt pulley
    sub_thickness: float = 12.0
    spindle_radius: float = 3.55    # 7.1 mm dia, vinyl hole is 7.24
    spindle_above_mat: float = 32.0


@dataclass(frozen=True)
class Motor:
    body_radius: float = 20.0
    body_height: float = 34.0
    pulley_radius: float = 8.0
    pulley_height: float = 10.0
    belt_thickness: float = 1.2
    belt_height: float = 5.0


@dataclass(frozen=True)
class Tonearm:
    effective_length: float = 239.0
    pivot_to_spindle: float = 222.0
    offset_angle: float = 23.1
    base_radius: float = 21.0
    base_height: float = 12.0
    post_radius: float = 9.0
    post_height: float = 56.0
    yoke_width: float = 26.0
    yoke_thickness: float = 7.0
    tube_radius: float = 5.0
    tube_rear: float = 82.0         # pivot to counterweight stub end
    headshell_length: float = 46.0
    headshell_width: float = 15.0
    headshell_thickness: float = 5.0
    counterweight_radius: float = 22.0
    counterweight_length: float = 26.0
    cartridge_length: float = 28.0
    cartridge_width: float = 13.0
    cartridge_height: float = 15.0
    stylus_length: float = 7.0
    rest_height: float = 62.0


@dataclass(frozen=True)
class DustCover:
    wall: float = 3.0
    height: float = 110.0
    margin: float = 4.0             # overhang past the plinth edge
    hinge_radius: float = 7.0
    hinge_length: float = 34.0
    open_angle: float = 0.0         # degrees; 0 = closed, try 62


@dataclass(frozen=True)
class Record:
    radius: float = 151.0           # 12 inch
    thickness: float = 1.8
    label_radius: float = 50.0
    hole_radius: float = 3.62
    lead_out_radius: float = 58.0


@dataclass(frozen=True)
class TurntableParams:
    plinth: Plinth = field(default_factory=Plinth)
    foot: Foot = field(default_factory=Foot)
    platter: Platter = field(default_factory=Platter)
    bearing: Bearing = field(default_factory=Bearing)
    motor: Motor = field(default_factory=Motor)
    tonearm: Tonearm = field(default_factory=Tonearm)
    cover: DustCover = field(default_factory=DustCover)
    record: Record = field(default_factory=Record)

    # Spindle position on the plinth, measured from the plinth centre.
    spindle_x: float = -58.0
    spindle_y: float = 0.0

    # Groove radius the arm is modelled at. The natural zero puts the
    # stylus past the spindle, which is where it would sit if you lifted the
    # record away, so park it on the lead-in groove instead.
    modelled_groove: float | None = None

    # Where the arm sits relative to the spindle, as a bearing in the XY
    # plane. 26 deg puts the pillar in the back right corner with the
    # counterweight still clear of the plinth edge and the dust cover.
    arm_bearing: float = 26.0

    @property
    def plinth_top(self) -> float:
        """Z of the plinth top face, with the feet standing on z = 0."""
        return self.foot.height + self.plinth.height

    @property
    def spindle(self) -> tuple[float, float]:
        return (self.spindle_x, self.spindle_y)

    @property
    def pivot(self) -> tuple[float, float]:
        """Tonearm pivot, placed pivot_to_spindle away from the spindle."""
        a = radians(self.arm_bearing)
        return (
            self.spindle_x + self.tonearm.pivot_to_spindle * cos(a),
            self.spindle_y + self.tonearm.pivot_to_spindle * sin(a),
        )

    @property
    def motor_centre(self) -> tuple[float, float]:
        """Motor pulley, tucked into the back left of the sub-platter."""
        return (self.spindle_x - 86.0, self.spindle_y + 84.0)

    @property
    def platter_top(self) -> float:
        p, pl = self.platter, self.plinth_top
        return pl + p.clearance + p.thickness

    @property
    def record_surface(self) -> float:
        return self.platter_top + self.platter.mat_thickness

    @property
    def lead_in_radius(self) -> float:
        return self.record.radius - 4.0

    @property
    def parked_groove(self) -> float:
        return self.lead_in_radius if self.modelled_groove is None else self.modelled_groove

    @property
    def overhang(self) -> float:
        return self.tonearm.effective_length - self.tonearm.pivot_to_spindle


    def describe(self) -> str:
        span = hypot(self.pivot[0] - self.spindle_x, self.pivot[1] - self.spindle_y)
        lines = [
            f"plinth        {self.plinth.length} x {self.plinth.depth} x {self.plinth.height} mm",
            f"platter       dia {self.platter.radius * 2:.0f} x {self.platter.thickness} mm",
            f"height        {self.platter_top:.1f} mm to platter top",
            f"spindle       ({self.spindle_x}, {self.spindle_y})",
            f"arm pivot     ({self.pivot[0]:.1f}, {self.pivot[1]:.1f})",
            f"pivot-spindle {span:.1f} mm",
            f"overhang      {self.overhang:.1f} mm at {self.tonearm.offset_angle} deg offset",
        ]
        return "\n".join(lines)


DEFAULT = TurntableParams()
