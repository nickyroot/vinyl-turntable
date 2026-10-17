# Vinyl turntable

A belt-drive turntable modelled parametrically in
[build123d](https://build123d.readthedocs.io), exported to glTF, and viewed in
the browser.

Every dimension lives in one dataclass, so changing the platter diameter or the
tonearm's effective length reshapes the model and the viewer follows.

**[View it →](https://nickyroot.github.io/vinyl-turntable/)**

## What's modelled

46 solids across six groups, which are also the viewer's layers:

| Group | Parts |
| --- | --- |
| `chassis` | plinth, feet, phono outputs, DC inlet, speed switch, 45 adapter |
| `drive` | motor, pulley, belt, bearing housing |
| `platter` | sub-platter, platter, mat, spindle |
| `arm` | tonearm, headshell, cartridge, counterweight, anti-skate, rest |
| `record` | 12-inch record and label |
| `cover` | acrylic dust cover and hinges |

The tonearm follows real alignment geometry: 239 mm effective length, 222 mm
pivot to spindle, 17 mm overhang at a 23.1 degree headshell offset. The arm is
modelled sitting on the lead-in groove, and `turntable.tracking` solves the
rotation that puts the stylus on any groove radius — which is what drives the
viewer's playback animation.

## Getting started

Needs [uv](https://docs.astral.sh/uv/). It fetches its own Python, so the
system one being old does not matter.

```bash
git clone https://github.com/nickyroot/vinyl-turntable.git
cd vinyl-turntable
uv sync
```

Build the model and write the web assets plus STEP and STL:

```bash
uv run export
```

Check the geometry is still sane:

```bash
uv run python scripts/verify.py
```

Serve the viewer:

```bash
python3 -m http.server 4173 --directory web
```

## Changing the design

All the numbers are in [`src/turntable/params.py`](src/turntable/params.py).
Edit a value, re-run `uv run export`, reload the page.

```python
from turntable import TurntableParams, build
from turntable.params import Platter

big = TurntableParams(platter=Platter(radius=180.0, thickness=30.0))
model = build(big)
```

Derived values are properties rather than constants, so the stack stays
consistent: `platter_top` follows the plinth height and the platter clearance,
the tonearm pillar is sized so the stylus meets the record, and the belt plane
is taken from the sub-platter groove and reused for the motor pulley.

## Checks

`scripts/verify.py` asserts the things that a render will not reveal:

- the stylus touches the record surface, rather than floating above it
- pivot-to-stylus equals the effective length, and the stylus sits on the
  lead-in groove
- the belt, the sub-platter groove and the motor pulley groove share a plane
- no two solids occupy the same space, apart from an allowlist of press fits

That last one is the useful one. It caught the motor pulley passing up through
the record, and the sub-platter sitting on top of the platter instead of under
it — both invisible in a quick render.

## Viewer

Plain ES modules and [three.js](https://threejs.org) from a CDN, no build step.

- layer toggles, driven by the groups in the GLB
- exploded view
- playback: the platter turns at 33⅓ or 45, and the arm tracks from the
  lead-in groove to the run-out
- iso / front / top / tonearm views, framed from the model's own bounds
- hover a part to read its name

The exporter names each glTF material after the finish it came from, so the
viewer gives aluminium, brass, felt, vinyl and acrylic their own surface
response instead of guessing from brightness.

## Layout

```
src/turntable/
  params.py      every dimension, and the derived stack
  parts.py       one function per part, positioned in the assembly frame
  assembly.py    the groups
  tracking.py    where the arm sits for a given groove radius
scripts/
  export_model.py   GLB for the web, STEP and STL for CAD
  verify.py         geometry checks
web/               the viewer
```

## Licence

MIT.
