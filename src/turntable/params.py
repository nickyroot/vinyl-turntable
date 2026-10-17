"""Dimensions and finishes for an SL-1210 MK2 style direct-drive deck.

Everything is millimetres and degrees. The headline numbers come from the
Technics service data: 453 x 360 mm cabinet, 332 mm die-cast platter, and a
universal S-shaped arm of 230 mm effective length with 15 mm overhang at a
22 degree headshell offset. Pivot to spindle is therefore 215 mm.

The 1210 is the black version of the 1200, so the top plate is black rather
than brushed silver.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, hypot, radians, sin


@dataclass(frozen=True)
class Finish:
    """A named colour, as sRGB plus alpha."""

    rgba: tuple[float, float, float, float]


PALETTE = {
    # The 1210's cabinet: satin black die-cast top on a heavy rubber base.
    "top_plate": Finish((0.13, 0.13, 0.14, 1.0)),
    "base": Finish((0.07, 0.07, 0.075, 1.0)),
    "aluminium": Finish((0.70, 0.71, 0.73, 1.0)),
    "arm_alloy": Finish((0.78, 0.79, 0.80, 1.0)),
    "steel": Finish((0.55, 0.57, 0.60, 1.0)),
    "brass": Finish((0.72, 0.58, 0.28, 1.0)),
    "rubber": Finish((0.10, 0.10, 0.11, 1.0)),
    "mat": Finish((0.09, 0.09, 0.10, 1.0)),
    "vinyl": Finish((0.04, 0.04, 0.05, 1.0)),
    "label": Finish((0.80, 0.26, 0.18, 1.0)),
    "acrylic": Finish((0.70, 0.78, 0.82, 0.20)),
    "cartridge": Finish((0.62, 0.14, 0.12, 1.0)),
    "strobe": Finish((0.62, 0.63, 0.64, 1.0)),
    "lamp": Finish((0.95, 0.35, 0.20, 1.0)),
    "led": Finish((0.30, 0.85, 0.40, 1.0)),
    "copper": Finish((0.78, 0.45, 0.25, 1.0)),
}


@dataclass(frozen=True)
class Plinth:
    """One solid slab, faceted the way a LaCie Mobile Drive is.

    The profile is symmetrical about its mid-height: the top and bottom
    edges take identical 45 degree bevels with a vertical wall band
    between them. Each corner is a vertical diamond facet that starts as a
    point at the top-face corner, widens across the wall band and closes
    to a point at the bottom-face corner, so the corner is set entirely by
    the bevel and has no dial of its own.

    `length` and `depth` are the top face, the 1210's working surface; the
    bevels add to the outline, so the widest point is length + 2 * bevel.
    """

    length: float = 453.0
    depth: float = 360.0
    height: float = 56.0
    bevel: float = 14.0             # 45 deg, top and bottom alike


@dataclass(frozen=True)
class Foot:
    """Spring-and-rubber insulator, height adjustable."""

    radius: float = 22.0
    height: float = 26.0
    inset: float = 36.0
    collar: float = 5.0             # the gold band around the base


@dataclass(frozen=True)
class Platter:
    """332 mm aluminium die-cast, 2 kg with the mat.

    The underside carries a rubber coating to stop it ringing; the top takes
    a 2 mm rubber mat. The strobe dots are machined into the outer rim.
    """

    radius: float = 166.0
    thickness: float = 16.0
    rim_chamfer: float = 1.0
    clearance: float = 5.0          # underside above the top plate
    relief_radius: float = 150.0
    relief_depth: float = 7.0
    boss_radius: float = 48.0
    mat_radius: float = 163.0
    mat_thickness: float = 2.0
    damping_thickness: float = 1.2  # rubber coating on the underside
    strobe_rows: int = 4
    strobe_per_row: int = 60        # stylised; the real rim carries far more
    strobe_dot: float = 1.5
    strobe_row_gap: float = 2.6


@dataclass(frozen=True)
class DirectDrive:
    """The platter is the rotor: no belt, no idler, nothing to stretch.

    A magnet ring on the platter underside runs over the stator coils, so
    the motor and the platter are one rotating mass. 1.5 kg-cm of starting
    torque brings it to 33 rpm in 0.7 s, a quarter of a turn.
    """

    rotor_radius: float = 78.0      # magnet ring, outside the coils
    rotor_wall: float = 11.0
    rotor_height: float = 9.0
    stator_radius: float = 66.0
    stator_height: float = 7.0
    coil_count: int = 12
    hub_radius: float = 26.0
    hub_height: float = 9.0
    spindle_radius: float = 3.55
    spindle_above_mat: float = 34.0
    starting_torque: float = 1.5    # kg-cm, for the spec sheet
    run_up_seconds: float = 0.7


@dataclass(frozen=True)
class Tonearm:
    """Universal S-shaped static-balance arm on a gimbal.

    The S is not styling: it lets the headshell sit at the offset angle
    while the counterweight stays on the pivot axis.
    """

    effective_length: float = 230.0
    pivot_to_spindle: float = 215.0
    offset_angle: float = 22.0
    tube_radius: float = 4.2
    tube_rear: float = 76.0

    # Interior control points of the S, as (fraction along the pivot-to-
    # collar chord, sideways offset as a fraction of the effective length).
    # Tune these to reshape the bend; the ends are fixed by the pivot and
    # the headshell collar, so the curve stays geometrically honest.
    s_curve: tuple[tuple[float, float], ...] = (
        (0.28, -0.030),
        (0.60, 0.010),
        (0.86, 0.038),
    )

    base_radius: float = 48.0       # the black arm board let into the plate
    base_height: float = 4.0
    post_radius: float = 11.0
    collar_radius: float = 14.0     # VTA helicoid with its lock ring
    vta_range: float = 6.0
    yoke_width: float = 30.0
    yoke_thickness: float = 8.0

    collar_length: float = 16.0     # headshell bayonet collar
    collar_dia: float = 14.0
    headshell_length: float = 52.0
    headshell_width: float = 17.0
    headshell_thickness: float = 5.0
    counterweight_radius: float = 22.0
    counterweight_length: float = 30.0
    cartridge_length: float = 28.0
    cartridge_width: float = 14.0
    cartridge_height: float = 15.0
    stylus_length: float = 7.0
    antiskate_radius: float = 11.0
    antiskate_at: tuple[float, float] = (30.0, 26.0)   # from the pivot, bearing deg
    rest_at: tuple[float, float] = (44.0, -62.0)       # from the pivot, bearing deg


@dataclass(frozen=True)
class Controls:
    """The front-panel furniture, all of it on the top plate."""

    start_stop_size: tuple[float, float] = (46.0, 30.0)
    speed_button: tuple[float, float] = (26.0, 15.0)
    power_radius: float = 15.0
    power_height: float = 11.0
    strobe_window: tuple[float, float] = (16.0, 10.0)
    pitch_slot: tuple[float, float] = (28.0, 112.0)
    pitch_knob: tuple[float, float, float] = (26.0, 17.0, 9.0)
    pitch_range: float = 8.0        # per cent
    target_radius: float = 7.0
    target_height: float = 34.0
    adapter_radius: float = 19.0

    # Where each control sits, from the cabinet centre. The platter is a
    # circle in a rectangle, so the furniture lives in the corners where
    # the rim curves away.
    start_stop_at: tuple[float, float] = (-176.0, -150.0)
    speed_at: tuple[float, float] = (-112.0, -168.0)
    speed_pitch: float = 32.0       # between the 33 and 45 buttons
    power_at: tuple[float, float] = (-202.0, -106.0)
    strobe_at: tuple[float, float] = (-188.0, -85.0)
    pitch_at: tuple[float, float] = (168.0, -78.0)
    target_at: tuple[float, float] = (124.0, -58.0)
    adapter_at: tuple[float, float] = (-190.0, 140.0)


@dataclass(frozen=True)
class DustCover:
    wall: float = 3.0
    height: float = 80.0
    margin: float = 5.0
    corner_radius: float = 21.0
    hinge_radius: float = 8.0
    hinge_length: float = 36.0
    open_angle: float = 0.0         # degrees; 0 = closed


@dataclass(frozen=True)
class Record:
    radius: float = 151.0
    thickness: float = 1.8
    label_radius: float = 50.0
    hole_radius: float = 3.62
    lead_out_radius: float = 58.0


@dataclass(frozen=True)
class TurntableParams:
    plinth: Plinth = field(default_factory=Plinth)
    foot: Foot = field(default_factory=Foot)
    platter: Platter = field(default_factory=Platter)
    drive: DirectDrive = field(default_factory=DirectDrive)
    tonearm: Tonearm = field(default_factory=Tonearm)
    controls: Controls = field(default_factory=Controls)
    cover: DustCover = field(default_factory=DustCover)
    record: Record = field(default_factory=Record)

    # Spindle position, from the cabinet centre. The platter sits left and
    # slightly back, which is what leaves room for the arm and the fader.
    spindle_x: float = -45.0
    spindle_y: float = 4.0

    # Bearing from the spindle to the arm pivot, putting the arm board in
    # the back right corner the way Technics do.
    arm_bearing: float = 28.0

    # Groove radius the arm is modelled at. The natural zero puts the
    # stylus past the spindle, so park it on the lead-in groove instead.
    modelled_groove: float | None = None

    @property
    def plinth_top(self) -> float:
        """Z of the chassis top face, with the feet on z = 0."""
        return self.foot.height + self.plinth.height

    @property
    def spindle(self) -> tuple[float, float]:
        return (self.spindle_x, self.spindle_y)

    @property
    def pivot(self) -> tuple[float, float]:
        a = radians(self.arm_bearing)
        return (
            self.spindle_x + self.tonearm.pivot_to_spindle * cos(a),
            self.spindle_y + self.tonearm.pivot_to_spindle * sin(a),
        )

    @property
    def platter_top(self) -> float:
        return self.plinth_top + self.platter.clearance + self.platter.thickness

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
            f"cabinet       {self.plinth.length} x {self.plinth.depth} mm",
            f"platter       dia {self.platter.radius * 2:.0f} mm die-cast",
            f"height        {self.platter_top:.1f} mm to platter top",
            f"drive         direct, {self.drive.starting_torque} kg-cm,"
            f" {self.drive.run_up_seconds}s run-up",
            f"spindle       ({self.spindle_x}, {self.spindle_y})",
            f"arm pivot     ({self.pivot[0]:.1f}, {self.pivot[1]:.1f})",
            f"pivot-spindle {span:.1f} mm",
            f"overhang      {self.overhang:.1f} mm at {self.tonearm.offset_angle} deg offset",
        ]
        return "\n".join(lines)


DEFAULT = TurntableParams()
