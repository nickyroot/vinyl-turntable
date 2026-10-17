"""Where the arm has to sit to put the stylus on a given groove.

A pivoted arm traces an arc, so the rotation that lands the stylus on a
groove of radius r is pure trigonometry: the pivot, the spindle and the
stylus form a triangle with two known sides.
"""

from __future__ import annotations

from math import acos, cos, degrees, radians, sin

from .params import TurntableParams


def arm_angle(p: TurntableParams, groove_radius: float) -> float:
    """Signed rotation, in degrees, from the modelled arm position.

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
    _px, py = p.pivot
    heading = radians(p.arm_bearing + 180.0)
    probe = radians(10.0)
    y = py + p.tonearm.effective_length * sin(heading + probe)
    return y < p.spindle_y


def playable_sweep(p: TurntableParams) -> tuple[float, float]:
    """Sweep limits as rotations away from the arm's modelled position.

    The model is built with the arm already on a groove, so the viewer only
    needs the delta from there to the lead-in and the run-out.
    """
    parked = arm_angle(p, p.parked_groove)
    return (
        arm_angle(p, p.lead_in_radius) - parked,
        arm_angle(p, p.record.lead_out_radius) - parked,
    )


def stylus_xy(p: TurntableParams, angle_deg: float) -> tuple[float, float]:
    """Stylus position for a given arm rotation, for checking the arc."""
    px, py = p.pivot
    base = radians(p.arm_bearing + 180.0)
    a = base + radians(angle_deg)
    return (
        px + p.tonearm.effective_length * cos(a),
        py + p.tonearm.effective_length * sin(a),
    )
