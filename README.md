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

## Designing

One command gives you the whole loop:

```bash
uv run watch
```

Open <http://localhost:4173>, edit anything under `src/turntable`, and save.
The model rebuilds in about a second and the page reloads itself with the new
geometry. The watcher also runs the geometry checks on every rebuild, so a
change that breaks something says so immediately:

```
[14:22:08] change detected
  FAIL  platter clashes with rest_post (82 mm3)
  rebuilt in  1.1s    1507 kB   1 CHECK(S) FAILED
```

That is a real example: a 336 mm platter reaches the tonearm rest. A syntax
error prints the offending line and the watcher keeps going, so a typo does
not cost you a restart.

The rebuild is quick because the watcher keeps one process alive and reloads
only the turntable modules. Importing build123d takes about five seconds;
paying that on every save would make the loop useless.

### Where the dials are

Everything is in [`src/turntable/params.py`](src/turntable/params.py), grouped
by assembly:

```python
@dataclass(frozen=True)
class Platter:
    radius: float = 150.0
    thickness: float = 20.0
    clearance: float = 16.0         # platter underside above plinth top
```

Some things worth trying:

| Change | Where |
| --- | --- |
| Bigger platter | `Platter.radius` |
| Taller or slimmer plinth | `Plinth.height`, `Plinth.corner_radius` |
| Different arm geometry | `Tonearm.effective_length`, `pivot_to_spindle`, `offset_angle` |
| Move the arm round the deck | `TurntableParams.arm_bearing` |
| Open the dust cover | `DustCover.open_angle` — try `62` |
| Colours and materials | `PALETTE` at the top of the file |

Derived values are properties rather than constants, so the stack stays
consistent: `platter_top` follows the plinth height and the platter clearance,
the tonearm pillar is sized so the stylus meets the record, and the belt plane
is taken from the sub-platter groove and reused for the motor pulley. Change
the plinth height and everything above it moves with it.

### Driving it from Python

```python
from turntable import TurntableParams, build
from turntable.params import Platter, Tonearm

deck = TurntableParams(
    platter=Platter(radius=180.0, thickness=30.0),
    tonearm=Tonearm(effective_length=254.0, pivot_to_spindle=236.0),
)
model = build(deck)
print(deck.describe())
```

`build()` takes a `groups=` list if you only want part of the assembly, and
`turntable.assembly.part_registry()` gives you a name-to-builder map for
looking at one part on its own.

### Other commands

```bash
uv run export                 # GLB for the web, plus STEP and STL in dist/
uv run export --quality high  # finer tessellation
uv run verify                 # geometry checks on their own
```

Open `dist/turntable.step` in FreeCAD, Fusion or Onshape if you want the solid
model rather than the mesh.

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
  watch.py          rebuild on save and serve the viewer
  export_model.py   GLB for the web, STEP and STL for CAD
  verify.py         geometry checks
web/               the viewer
```

## Licence

MIT.
