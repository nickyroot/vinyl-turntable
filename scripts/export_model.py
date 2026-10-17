#!/usr/bin/env python
"""Build the turntable and write it out for the web viewer and for CAD.

    uv run export                      # everything
    uv run export --formats glb        # just the web model
    uv run export --quality high       # finer tessellation for the GLB
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from build123d import Unit, export_gltf, export_step, export_stl
from pygltflib import GLTF2

from turntable import DEFAULT, build
from turntable.assembly import GROUPS
from turntable.params import PALETTE
from turntable.tracking import as_minutes, playable_sweep, tracking_error

ROOT = Path(__file__).resolve().parents[1]
WEB_MODELS = ROOT / "web" / "models"
DIST = ROOT / "dist"

# linear / angular deflection passed to the tessellator
QUALITY = {
    "draft": (0.05, 0.4),
    "normal": (0.012, 0.18),
    "high": (0.004, 0.08),
}


def _to_linear(c: float) -> float:
    """sRGB transfer function, matching what the exporter writes out."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def retouch_materials(path: Path) -> None:
    """Name each material after its finish, and set the blend mode.

    build123d writes mat_0, mat_1... and records the alpha without setting
    alphaMode, so neither the finish nor the transparency survives into the
    viewer. Match each material back to the palette entry it came from and
    write the name through, so the viewer can give brass, felt and acrylic
    the surface response they deserve instead of guessing from brightness.
    """
    swatches = {
        key: tuple(_to_linear(c) for c in finish.rgba[:3])
        for key, finish in PALETTE.items()
    }
    gltf = GLTF2().load(str(path))
    named = blended = 0
    for mat in gltf.materials:
        pbr = mat.pbrMetallicRoughness
        if pbr is None or pbr.baseColorFactor is None:
            continue
        rgb = pbr.baseColorFactor[:3]

        def gap(swatch: tuple[float, ...], rgb: list[float] = rgb) -> float:
            return sum((a - b) ** 2 for a, b in zip(rgb, swatch, strict=True))

        key, dist = min(
            ((k, gap(v)) for k, v in swatches.items()), key=lambda kv: kv[1]
        )
        if dist < 1e-4:
            mat.name = key
            named += 1
        if pbr.baseColorFactor[3] < 0.999:
            mat.alphaMode = "BLEND"
            mat.doubleSided = True
            blended += 1
    gltf.save(str(path))
    print(f"  named {named}/{len(gltf.materials)} materials, {blended} transparent")


def write_manifest(path: Path, model: Path) -> None:
    p = DEFAULT
    lead_in, lead_out = playable_sweep(p)
    inner = tracking_error(p, p.record.lead_out_radius)
    outer = tracking_error(p, p.lead_in_radius)
    manifest = {
        "model": model.name,
        "generated": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "units": "mm",
        # The GLB is in metres with a Z-up root, so the viewer divides these
        # by 1000 and rotates about local Z.
        "spindle_mm": [p.spindle_x, p.spindle_y],
        "arm_pivot_mm": list(p.pivot),
        "arm_sweep_deg": [round(lead_in, 2), round(lead_out, 2)],
        "rpm": [33.333, 45.0],
        "groups": [
            {"name": name, "parts": [fn.__name__ for fn in fns]}
            for name, fns in GROUPS.items()
        ],
        "specs": [
            {
                "label": "Cabinet",
                "value": f"{p.plinth.length:.0f} x {p.plinth.depth:.0f} mm",
            },
            {
                "label": "Platter",
                "value": f"{p.platter.radius * 2:.0f} mm die-cast alloy",
            },
            {"label": "Drive", "value": "Quartz-locked direct drive"},
            {
                "label": "Starting torque",
                "value": f"{p.drive.starting_torque} kg-cm",
            },
            {
                "label": "Run-up",
                "value": f"{p.drive.run_up_seconds} s to 33 rpm",
            },
            {"label": "Speeds", "value": "33 1/3 and 45 rpm"},
            {
                "label": "Pitch",
                "value": f"+/- {p.controls.pitch_range:.0f} % slide fader",
            },
            {"label": "Arm", "value": "Universal S-shape, gimbal"},
            {
                "label": "Effective length",
                "value": f"{p.tonearm.effective_length:.0f} mm",
            },
            {
                "label": "Overhang",
                "value": f"{p.overhang:.0f} mm at {p.tonearm.offset_angle:.0f} deg offset",
            },
            {
                "label": "Tracking error",
                "value": f"{as_minutes(inner)} to {as_minutes(outer)}",
            },
            {
                "label": "Height to platter",
                "value": f"{p.platter_top:.0f} mm",
            },
        ],
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def write_web_assets(quality: str = "normal", groups: list[str] | None = None) -> Path:
    """Build the model and write the GLB and manifest the viewer reads.

    Separate from main() so the watcher can call it repeatedly inside one
    process; importing build123d costs several seconds, and paying that on
    every keystroke would make the loop useless.
    """
    WEB_MODELS.mkdir(parents=True, exist_ok=True)
    model = build(DEFAULT, groups=groups)
    out = WEB_MODELS / "turntable.glb"
    lin, ang = QUALITY[quality]
    export_gltf(
        model,
        out,
        unit=Unit.MM,
        binary=True,
        linear_deflection=lin,
        angular_deflection=ang,
    )
    retouch_materials(out)
    write_manifest(WEB_MODELS / "manifest.json", out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--formats",
        nargs="+",
        default=["glb", "step", "stl"],
        choices=["glb", "step", "stl"],
    )
    ap.add_argument("--quality", default="normal", choices=list(QUALITY))
    ap.add_argument("--groups", nargs="+", default=None, help="subset of groups to build")
    args = ap.parse_args()

    WEB_MODELS.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)

    print(DEFAULT.describe())
    t0 = time.perf_counter()
    model = build(DEFAULT, groups=args.groups)
    solids = len(model.solids())
    print(f"\nbuilt {solids} solids in {time.perf_counter() - t0:.1f}s")

    if "glb" in args.formats:
        t = time.perf_counter()
        out = write_web_assets(args.quality, args.groups)
        size = out.stat().st_size / 1024
        print(f"glb   {out.relative_to(ROOT)}  {size:.0f} kB  ({time.perf_counter() - t:.1f}s)")

    if "step" in args.formats:
        out = DIST / "turntable.step"
        export_step(model, out)
        print(f"step  {out.relative_to(ROOT)}  {out.stat().st_size / 1024:.0f} kB")

    if "stl" in args.formats:
        for group in model.children:
            out = DIST / f"{group.label}.stl"
            export_stl(group, out, tolerance=0.02)
            print(f"stl   {out.relative_to(ROOT)}  {out.stat().st_size / 1024:.0f} kB")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
