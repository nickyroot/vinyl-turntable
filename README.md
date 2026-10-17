# Direct-drive turntable

A quartz-locked direct-drive turntable, modelled parametrically in
[build123d](https://build123d.readthedocs.io), exported to glTF, and viewed
in the browser. The starting point is the Technics SL-1210 MK2.

Every dimension lives in one dataclass, so changing the platter diameter or
the tonearm's effective length reshapes the model and the viewer follows.

**[View it &rarr;](https://nickyroot.github.io/vinyl-turntable/)**

## The deck it is based on

The SL-1200/1210 MK2 is the turntable that accidentally became a musical
instrument. Technics designed it for speed accuracy; DJs found that what
makes a deck accurate also makes it playable. The numbers below come from
the Technics service data, and the model is built to them.

| | |
| --- | --- |
| Cabinet | 453 x 360 mm, 162 mm high with the cover |
| Platter | 332 mm die-cast aluminium, 2 kg with the mat |
| Drive | Quartz phase-locked, brushless DC, direct |
| Torque | 1.5 kg-cm starting, 0.7 s to 33 rpm |
| Pitch | +/- 8 % slide fader |
| Arm | Universal S-shape, gimbal, 230 mm effective |
| Alignment | 15 mm overhang, 22 deg offset, 215 mm pivot to spindle |
| Tracking error | +0 deg 32 min inner to +2 deg 32 min outer |

What is worth copying, and what this model tries to capture:

- **The platter is the motor.** The rotor magnet rides on the platter
  underside and runs outside the stator coils on the chassis. No belt to
  stretch, no idler to go hard, and nothing between the motor and the
  record but the spindle bearing. `drive` and `platter` in the model are
  two halves of one machine, which is why the rotor lives in the platter
  group and turns with it.
- **Torque, and symmetrical braking.** 1.5 kg-cm gets it to speed in a
  quarter of a turn, and the electronic brake stops it just as briskly.
  Designed so stylus drag could not slow it; it turned out to be what lets
  a DJ hold a record by hand and have it return to pitch.
- **Quartz phase lock.** Speed referenced to a crystal rather than to the
  mains, sensing the whole circumference of the shaft rather than one
  point on it. This made the strobe redundant in 1979 and Technics kept
  the dots anyway, because people wanted to see the speed as well as
  trust it.
- **Isolation in layers.** A die-cast alloy top plate carries the motor
  and the arm; a heavy moulded rubber base carries the alloy; spring-and-
  rubber feet carry the lot. Motor, arm and cover are each isolated
  separately up to their own mounting points, which is why the deck works
  standing next to a PA stack.
- **The pitch fader.** The MK2 swapped a rotary knob for a 100 mm linear
  fader. A small change that turned a speed trim into a performance
  control.
- **A removable headshell**, so a cartridge swap takes seconds.

The S-bend of the arm is not styling either: it lets the headshell sit at
the offset angle while the counterweight stays on the pivot axis.

## The chassis

The cabinet is one solid slab, faceted after the LaCie Mobile Drive, and its
profile is symmetrical about its mid-height. It starts as a box and loses
sixteen flat slices: identical 45 degree bevels on the top and bottom
edges, with a vertical wall band between them, and a vertical corner facet
at each corner. Each corner facet is a six-sided diamond that starts as a
point at the top-face corner, widens across the wall band and closes to a
point at the bottom-face corner, so it is set entirely by the bevel and has
no dial of its own.

The top and bottom faces are matching perfect rectangles at the 1210's
453 x 360, so the bevels add to the outline: the widest point is 481 x 388.

## What is modelled

317 solids across seven groups, which are also the viewer's layers:

| Group | Parts |
| --- | --- |
| `cabinet` | faceted chassis slab, insulator feet, phono leads |
| `controls` | start/stop, 33 and 45, power, strobe lamp, pitch fader, target light, 45 adapter |
| `drive` | bearing hub, stator plate and coils, spindle |
| `platter` | rotor magnet, platter, damping ring, strobe dots, mat |
| `arm` | arm board, pillar, VTA collar, gimbal, S-tube, headshell, cartridge, counterweight, anti-skate, rest |
| `record` | 12-inch record and label |
| `cover` | dust cover and hinges |

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
| Chassis facets | `Plinth.bevel` (45 deg, top and bottom alike) |
| Reshape the S-bend | `Tonearm.s_curve` |
| Different arm geometry | `Tonearm.effective_length`, `pivot_to_spindle`, `offset_angle` |
| Move a control | `Controls.*_at` |
| Strobe dot density | `Platter.strobe_per_row`, `strobe_rows` |
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
- the cartridge stays within about 3 degrees of the groove tangent across
  the side, which is what catches a headshell kinked the wrong way
- the rotor magnet keeps its air gap from the stator coils
- the chassis top and bottom faces are both four-sided 453 x 360
  rectangles, and the slab mirrored about its mid-height leaves nothing
  over, so the profile really is symmetrical
- no two solids occupy the same space, apart from an allowlist of press
  fits

The last two are the useful ones. The clash check caught the rotor and the
stator occupying the same millimetres, which is the sort of thing a render
hides completely. The tracking error check is the reason the headshell
offset is handed correctly: flip it and the error goes from 2.7 degrees to
46, which no amount of looking at the model would have told you.

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
  tracking.py    arm position and tracking error for a given groove
scripts/
  watch.py          rebuild on save and serve the viewer
  export_model.py   GLB for the web, STEP and STL for CAD
  verify.py         geometry checks
web/               the viewer
```

## Licence

MIT.
