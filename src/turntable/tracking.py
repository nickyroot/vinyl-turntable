"""Where the arm sits, and how square the cartridge is to the groove.

A pivoted arm traces an arc, so the rotation that lands the stylus on a
given groove is pure trigonometry: the pivot, the spindle and the stylus
form a triangle with two known sides.

The offset angle is the other half of the story. Technics quote a tracking
error of +0 deg 32 min at the inner groove and +2 deg 32 min at the outer,
and `tracking_error` here reproduces that, which is what tells us the
headshell is kinked the right way round rather than the wrong one.
"""

from __future__ import annotations

from math import acos, atan2, cos, degrees, radians, sin

from .params import TurntableParams

# Which way the headshell is kinked relative to the pivot-to-stylus line.
# Negative swings the cartridge towards the spindle side, which is what
# brings it near the groove tangent; flipping this roughly doubles the
# tracking error, and scripts/verify.py would catch it.
OFFSET_SIGN = -1.0


def arm_angle(p: TurntableParams, groove_radius: float) -> float:
    """Signed rotation, in degrees, from the arm's natural zero.

    At zero the stylus sits `overhang` past the spindle. Positive numbers
    swing the stylus towards the front of the deck, which is the side a
    conventional back-right arm plays from.
    """
    length = p.tonearm.effective_length
    dist = p.tonearm.pivot_to_spindle
    cosine = (length**2 + dist**2 - groove_radius**2) / (2 * length * dist)
    cosine = max(-1.0, min(1.0, cosine))
    swing = degrees(acos(cosine))
    return swing if _front_is_positive(p) else -swing


def _front_is_positive(p: TurntableParams) -> bool:
    """Which way round the pivot moves the stylus towards the front edge."""
    _, py = p.pivot
    heading = radians(p.arm_bearing + 180.0)
    y = py + p.tonearm.effective_length * sin(heading + radians(10.0))
    return y < p.spindle_y


def base_heading(p: TurntableParams) -> float:
    """Degrees from the pivot towards the spindle: the arm's zero."""
    px, py = p.pivot
    return degrees(atan2(p.spindle_y - py, p.spindle_x - px))


def heading(p: TurntableParams, groove_radius: float | None = None) -> float:
    """Where the arm points, in degrees, for a given groove."""
    groove = p.parked_groove if groove_radius is None else groove_radius
    return base_heading(p) + arm_angle(p, groove)


def playable_sweep(p: TurntableParams) -> tuple[float, float]:
    """Sweep limits as rotations away from the arm's modelled position."""
    parked = arm_angle(p, p.parked_groove)
    return (
        arm_angle(p, p.lead_in_radius) - parked,
        arm_angle(p, p.record.lead_out_radius) - parked,
    )


def stylus_xy(p: TurntableParams, groove_radius: float | None = None) -> tuple[float, float]:
    """Stylus position in cabinet coordinates for a given groove."""
    px, py = p.pivot
    a = radians(heading(p, groove_radius))
    return (
        px + p.tonearm.effective_length * cos(a),
        py + p.tonearm.effective_length * sin(a),
    )


def tracking_error(p: TurntableParams, groove_radius: float) -> float:
    """Angle, in degrees, between the cartridge axis and the groove tangent.

    Zero would mean the cartridge is perfectly tangential, which a pivoted
    arm only manages at two null radii.
    """
    head = radians(heading(p, groove_radius))
    axis = head + radians(OFFSET_SIGN * p.tonearm.offset_angle)

    sx, sy = stylus_xy(p, groove_radius)
    radial = atan2(sy - p.spindle_y, sx - p.spindle_x)
    tangent = radial + radians(90.0)

    error = degrees(axis - tangent)
    # Fold onto (-90, 90]: the cartridge axis is a line, not an arrow.
    while error > 90.0:
        error -= 180.0
    while error <= -90.0:
        error += 180.0
    return error


def as_minutes(degrees_value: float) -> str:
    """Format an angle the way a tonearm spec sheet would."""
    sign = "-" if degrees_value < 0 else "+"
    total = abs(degrees_value)
    whole = int(total)
    minutes = round((total - whole) * 60)
    if minutes == 60:
        whole, minutes = whole + 1, 0
    return f"{sign}{whole}d{minutes:02d}m"
