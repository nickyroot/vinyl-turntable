// Loads turntable.glb and puts it on screen. The GLB keeps build123d's
// naming, so the top-level nodes are the assembly groups from
// src/turntable/assembly.py and everything below them is a named part.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const MM = 0.001;                 // the GLB is in metres
const DEG = Math.PI / 180;
const HIDDEN_BY_DEFAULT = ['cover'];

// How each finish should respond to light. The exporter names the glTF
// materials after the palette in src/turntable/params.py, so these line up
// one for one with the finishes the model was built from.
const SURFACE = {
  plinth:      { metalness: 0.0, roughness: 0.52, envMapIntensity: 0.6 },
  plinth_edge: { metalness: 0.0, roughness: 0.45, envMapIntensity: 0.7 },
  aluminium:   { metalness: 1.0, roughness: 0.26, envMapIntensity: 1.0 },
  steel:       { metalness: 1.0, roughness: 0.38, envMapIntensity: 1.0 },
  brass:       { metalness: 1.0, roughness: 0.28, envMapIntensity: 1.0 },
  copper:      { metalness: 1.0, roughness: 0.34, envMapIntensity: 1.0 },
  rubber:      { metalness: 0.0, roughness: 0.88, envMapIntensity: 0.4 },
  felt:        { metalness: 0.0, roughness: 0.96, envMapIntensity: 0.3 },
  // Vinyl is glossy, but a near-black dielectric mirrors the environment
  // and goes grey, so keep its share of the room down.
  vinyl:       { metalness: 0.0, roughness: 0.44, envMapIntensity: 0.35 },
  label:       { metalness: 0.0, roughness: 0.80, envMapIntensity: 0.5 },
  cartridge:   { metalness: 0.0, roughness: 0.42, envMapIntensity: 0.6 },
  acrylic:     { metalness: 0.0, roughness: 0.04, envMapIntensity: 1.0 },
};

const canvas = document.getElementById('view');
const stage = document.getElementById('stage');
const partName = document.getElementById('part-name');

// ----------------------------------------------------------------- renderer

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.92;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, 1, 0.02, 40);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.minDistance = 0.25;
controls.maxDistance = 4;
controls.maxPolarAngle = Math.PI * 0.495;   // stay above the floor
controls.autoRotateSpeed = 0.7;

// Studio-ish lighting: a soft room for reflections, one key light for shape.
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.9;

const key = new THREE.DirectionalLight(0xffffff, 1.25);
key.position.set(0.9, 1.5, 0.75);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.bias = -0.0006;
key.shadow.normalBias = 0.004;
const cam = key.shadow.camera;
cam.left = -0.6; cam.right = 0.6; cam.top = 0.6; cam.bottom = -0.6;
cam.near = 0.1; cam.far = 4;
scene.add(key);

scene.add(new THREE.DirectionalLight(0x9fb4d0, 0.3).translateX(-1.2).translateY(0.6));
scene.add(new THREE.HemisphereLight(0xdfe6f0, 0x15161a, 0.25));

// Floor, for the shadow to land on.
const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(6, 6),
  new THREE.ShadowMaterial({ opacity: 0.42 }),
);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);

// --------------------------------------------------------------- model load

const state = {
  groups: new Map(),            // name -> { node, home: Vector3 }
  platterSpin: null,            // pivot wrappers we rotate
  recordSpin: null,
  armSwing: null,
  sweep: [0, 0],
  rpm: 33.333,
  playing: false,
  armT: 0,                      // 0 = lead-in, 1 = run-out
  materials: [],
  bounds: new THREE.Box3(),
};

const LOCAL = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
const bust = LOCAL ? `?t=${Date.now()}` : '';

const manifest = await fetch(`models/manifest.json${bust}`).then((r) => r.json());
const gltf = await new GLTFLoader().loadAsync(`models/${manifest.model}${bust}`);
const root = gltf.scene;

root.traverse((o) => {
  if (!o.isMesh) return;
  o.castShadow = true;
  o.receiveShadow = true;
  const m = o.material;
  const surface = SURFACE[m.name];
  if (surface) Object.assign(m, surface);
  if (m.transparent || m.opacity < 1) {
    m.depthWrite = false;
    o.castShadow = false;
  }
  if (!state.materials.includes(m)) state.materials.push(m);
});

// The exporter's root carries a -90deg X rotation to get from build123d's
// Z-up to glTF's Y-up, so anything we add inside it stays in Z-up mm space.
const zUp = root.children.length === 1 && root.children[0].children.length
  ? root.children[0]
  : root;

scene.add(root);

// Sit the model on the floor and centre it on the origin.
const box = new THREE.Box3().setFromObject(root);
const centre = box.getCenter(new THREE.Vector3());
root.position.x -= centre.x;
root.position.z -= centre.z;
root.position.y -= box.min.y;
state.bounds = new THREE.Box3().setFromObject(root);

for (const { name } of manifest.groups) {
  const node = zUp.children.find((c) => c.name === name);
  if (!node) continue;
  state.groups.set(name, { node, home: node.position.clone() });
}

// ------------------------------------------------------- rotation wrappers

/** Re-parent a node under a pivot at (x, y) mm so we can spin it in place. */
function pivotAt(node, [x, y]) {
  const parent = node.parent;
  const pivot = new THREE.Object3D();
  pivot.position.set(x * MM, y * MM, 0);
  parent.add(pivot);
  node.position.sub(pivot.position);
  pivot.add(node);
  return pivot;
}

const platter = state.groups.get('platter');
const record = state.groups.get('record');
if (platter) state.platterSpin = pivotAt(platter.node, manifest.spindle_mm);
if (record) state.recordSpin = pivotAt(record.node, manifest.spindle_mm);

// Only the arm itself swings; the arm rest beside it stays put.
const armGroup = state.groups.get('arm');
const armNode = armGroup?.node.children.find((c) => c.name === 'tonearm');
if (armNode) {
  state.armSwing = pivotAt(armNode, manifest.arm_pivot_mm);
  state.sweep = manifest.arm_sweep_deg;
}

// ----------------------------------------------------------------- hit test

/** GLTFLoader suffixes repeated names (record_label_2), so trim back to the
 *  part the model actually names. */
function partLabel(raw) {
  if (!raw) return null;
  return raw.replace(/_\d+$/, '').replace(/_/g, ' ');
}

const ray = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let hovered = null;

canvas.addEventListener('pointermove', (e) => {
  const r = canvas.getBoundingClientRect();
  pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  ray.setFromCamera(pointer, camera);
  const hit = ray.intersectObject(root, true).find((h) => h.object.visible);
  const name = partLabel(hit?.object.name);
  if (name !== hovered) {
    hovered = name;
    partName.textContent = name ?? '—';
  }
});

canvas.addEventListener('pointerleave', () => {
  hovered = null;
  partName.textContent = '—';
});

// -------------------------------------------------------------------- camera

/** World position of a named part, for views that frame one. */
function partPosition(prefix, fallback) {
  let found = null;
  root.traverse((o) => {
    if (!found && o.isMesh && o.name.startsWith(prefix)) found = o;
  });
  if (!found) return new THREE.Vector3(...fallback);
  found.updateWorldMatrix(true, false);
  return new THREE.Vector3().setFromMatrixPosition(found.matrixWorld);
}

// Overview distances are multiples of the distance that just fits the model,
// so the framing holds if the deck's dimensions change; detail views give an
// absolute distance and frame a part by name.
const VIEWS = {
  iso: { theta: 48, phi: 62, zoom: 1.0, target: [0, 0.05, 0] },
  front: { theta: 90, phi: 80, zoom: 1.0, target: [0, 0.04, 0] },
  top: { theta: 90, phi: 2, zoom: 0.95, target: [0, 0.02, 0] },
  arm: {
    phi: 68,
    dist: 0.22,
    focus: () => partPosition('stylus', [0, 0.1, 0]),
    // Look across the record's radius rather than along it, so the label
    // does not sit directly behind the cartridge.
    heading: () => {
      const tip = partPosition('stylus', [0, 0.1, 0]);
      const hub = partPosition('record_label', [0, 0.1, 0]);
      return Math.atan2(tip.z - hub.z, tip.x - hub.x) / DEG + 55;
    },
  },
};

/** Camera distance that just fits the model's bounding sphere in frame. */
function fitDistance() {
  const sphere = state.bounds.getBoundingSphere(new THREE.Sphere());
  const vertical = sphere.radius / Math.sin((camera.fov * DEG) / 2);
  const horizontal = vertical / Math.min(1, camera.aspect);
  return Math.max(vertical, horizontal) * 1.08;
}

function applyView(name, instant = false) {
  const v = VIEWS[name];
  const p = v.phi * DEG;
  const t = (v.heading ? v.heading() : v.theta) * DEG;
  const dist = v.dist ?? fitDistance() * v.zoom;
  const target = v.focus ? v.focus() : new THREE.Vector3(...v.target);
  const pos = new THREE.Vector3(
    dist * Math.sin(p) * Math.cos(t),
    dist * Math.cos(p),
    dist * Math.sin(p) * Math.sin(t),
  ).add(target);
  if (instant) {
    camera.position.copy(pos);
    controls.target.copy(target);
  } else {
    tween = { from: camera.position.clone(), to: pos, fromT: controls.target.clone(), toT: target, t: 0 };
  }
  currentView = name;
  for (const b of document.querySelectorAll('#views button')) {
    b.classList.toggle('on', b.dataset.view === name);
  }
}

let tween = null;
let currentView = 'iso';

function stepTween(dt) {
  if (!tween) return;
  tween.t = Math.min(1, tween.t + dt * 1.6);
  const e = 1 - Math.pow(1 - tween.t, 3);
  camera.position.lerpVectors(tween.from, tween.to, e);
  controls.target.lerpVectors(tween.fromT, tween.toT, e);
  if (tween.t === 1) tween = null;
}

// ------------------------------------------------------------------ controls

const layers = document.getElementById('layers');
for (const { name, parts } of manifest.groups) {
  const entry = state.groups.get(name);
  if (!entry) continue;
  const on = !HIDDEN_BY_DEFAULT.includes(name);
  entry.node.visible = on;
  const label = document.createElement('label');
  label.className = 'switch';
  label.title = parts.join(', ').replace(/_/g, ' ');
  label.innerHTML = `<input type="checkbox"${on ? ' checked' : ''}><span>${name}</span>`;
  label.querySelector('input').addEventListener('change', (e) => {
    entry.node.visible = e.target.checked;
  });
  layers.append(label);
}

const specs = document.getElementById('specs');
for (const { label, value } of manifest.specs) {
  const row = document.createElement('div');
  row.innerHTML = `<dt>${label}</dt><dd>${value}</dd>`;
  specs.append(row);
}

for (const b of document.querySelectorAll('#views button')) {
  b.addEventListener('click', () => applyView(b.dataset.view));
}

const explode = document.getElementById('explode');
const explodeOut = document.getElementById('explode-out');
// Spread the stack vertically, in the order the thing is assembled.
const LIFT = { chassis: 0, drive: 0.35, platter: 1, arm: 0.75, record: 1.5, cover: 2.2 };

explode.addEventListener('input', () => {
  const mm = Number(explode.value);
  explodeOut.textContent = `${mm} mm`;
  for (const [name, { node, home }] of state.groups) {
    // Groups that were re-parented under a pivot move with the pivot.
    const target = node.parent?.isObject3D && node.parent !== zUp ? node.parent : node;
    const base = target === node ? home : new THREE.Vector3(0, 0, 0);
    const offset = mm * MM * (LIFT[name] ?? 0);
    if (target === node) target.position.set(base.x, base.y, base.z + offset);
    else target.position.z = offset;
  }
});

document.getElementById('wireframe').addEventListener('change', (e) => {
  for (const m of state.materials) m.wireframe = e.target.checked;
});

document.getElementById('orbit').addEventListener('change', (e) => {
  controls.autoRotate = e.target.checked;
});

const playBtn = document.getElementById('play');
const note = document.getElementById('playback-note');

playBtn.addEventListener('click', () => {
  state.playing = !state.playing;
  playBtn.textContent = state.playing ? 'Stop' : 'Play';
  playBtn.classList.toggle('primary', !state.playing);
  if (state.playing && state.armT >= 1) state.armT = 0;
});

for (const b of document.querySelectorAll('.rpm')) {
  b.addEventListener('click', () => {
    state.rpm = Number(b.dataset.rpm);
    for (const o of document.querySelectorAll('.rpm')) o.classList.toggle('on', o === b);
  });
}

// --------------------------------------------------------------------- loop

function resize() {
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

const observer = new ResizeObserver(() => {
  resize();
  applyView(currentView, true);   // keep the model framed as the pane changes
});
observer.observe(canvas);
resize();
applyView('iso', true);

// Arm crosses the record in about 20 minutes at 33; compress that to 40s.
const SWEEP_SECONDS = 40;
const clock = new THREE.Clock();

function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);

  if (state.playing) {
    const turns = (state.rpm / 60) * dt * Math.PI * 2;
    if (state.platterSpin) state.platterSpin.rotation.z -= turns;
    if (state.recordSpin) state.recordSpin.rotation.z -= turns;
    state.armT = Math.min(1, state.armT + dt / SWEEP_SECONDS);
    if (state.armT >= 1) {
      state.playing = false;
      playBtn.textContent = 'Play';
      playBtn.classList.add('primary');
      note.textContent = 'Run-out reached. Press play to drop the needle again.';
    }
  }

  if (state.armSwing) {
    const [leadIn, leadOut] = state.sweep;
    state.armSwing.rotation.z = (leadIn + (leadOut - leadIn) * state.armT) * DEG;
  }

  stepTween(dt);
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

document.getElementById('loading').classList.add('done');
frame();

// Handle for poking at the scene from the console.
window.turntable = { scene, root, camera, controls, state, manifest, applyView };

// ------------------------------------------------------------ live reload

// `uv run watch` rewrites the manifest on every rebuild, so watching its
// timestamp is enough to know when to pick up new geometry. Only while
// developing: on a deployed site there is nothing to poll for.
if (LOCAL) {
  const stamp = manifest.generated;
  setInterval(async () => {
    try {
      const fresh = await fetch(`models/manifest.json?t=${Date.now()}`, { cache: 'no-store' });
      if (!fresh.ok) return;
      const { generated } = await fresh.json();
      if (generated && generated !== stamp) location.reload();
    } catch {
      // watcher restarting, or the file is mid-write; try again next tick
    }
  }, 1000);
}
