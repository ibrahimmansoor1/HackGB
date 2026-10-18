// A small floating home rendered with three.js, then redrawn every frame as
// warm ASCII glyphs. Framework-free: createAsciiHome(host) appends a canvas to
// `host` and returns { launch, destroy }.
//
// How the ASCII pass works: the 3D scene renders into a tiny texture (2x2
// pixels per character cell). A full-screen shader then reads each cell's
// brightness, picks a glyph from RAMP, and tints it with the scene's color.
// Where brightness jumps between neighboring cells (a silhouette or a fold),
// it draws a directional stroke from EDGES instead, which outlines shapes.
import * as THREE from 'three';

const RAMP = ' .·:-~=+*o#%@';
const EDGES = '-/|\\'; // tangent bins: horizontal, rising, vertical, falling
const ATLAS = RAMP + EDGES;
const DOT = RAMP.indexOf('.');
const STAR = RAMP.indexOf('*');
const SAMPLES = 2; // scene pixels per cell, per axis; averaging them cuts shimmer

const C = {
  night: '#1d1522',
  star: '#f6d9a8',
  plaster: '#d9bd96',
  roof: '#9a4630',
  chimney: '#9c4a35',
  trim: '#5b3b2c',
  door: '#7a4630',
  window: '#ffb04a',
  porch: '#ffd27a',
  grass: '#55744a',
  soil: '#4e3528',
  leaf: '#4f7046',
  trunk: '#6b4a33',
  stone: '#cdbba3',
  kraft: '#c69c62',
  tape: '#efe0c2',
  smoke: '#d9cfd9'
};

const vertexShader = /* glsl */ `
  void main() { gl_Position = vec4(position.xy, 0.0, 1.0); }
`;

const fragmentShader = /* glsl */ `
  precision highp float;
  uniform sampler2D tScene;
  uniform sampler2D tGlyphs;
  uniform vec2 uCellPx;   // device pixels per cell
  uniform vec2 uGrid;     // cols, rows
  uniform float uRamp;    // glyphs in the brightness ramp
  uniform float uAtlas;   // ramp + edge glyphs
  uniform float uDot;
  uniform float uStar;
  uniform vec3 uBg;       // sRGB
  uniform vec3 uStarInk;  // sRGB
  uniform float uTime;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

  vec3 sampleCell(vec2 cell) {
    return pow(texture2D(tScene, (cell + 0.5) / uGrid).rgb, vec3(1.0 / 2.2));
  }
  float levelOf(vec3 c) { return clamp(dot(c, vec3(0.299, 0.587, 0.114)) * 1.2, 0.0, 1.0); }
  float levelAt(vec2 cell) { return levelOf(sampleCell(cell)); }

  void main() {
    vec2 cellPos = gl_FragCoord.xy / uCellPx;
    vec2 cell = floor(cellPos);
    vec2 local = fract(cellPos);

    vec3 src = sampleCell(cell);
    float level = levelOf(src);
    float index = floor(level * (uRamp - 1.0) + 0.5);
    float peak = max(max(src.r, src.g), src.b);
    vec3 ink = src / max(peak, 0.001) * (0.45 + 0.55 * level);

    // Sobel over neighboring cells. Strokes go on the brighter side of an
    // edge only, so outlines stay one cell thick; lit windows keep their '@'.
    float tl = levelAt(cell + vec2(-1.0, 1.0)), tc = levelAt(cell + vec2(0.0, 1.0)), tr = levelAt(cell + vec2(1.0, 1.0));
    float ml = levelAt(cell + vec2(-1.0, 0.0)), mr = levelAt(cell + vec2(1.0, 0.0));
    float bl = levelAt(cell + vec2(-1.0, -1.0)), bc = levelAt(cell + vec2(0.0, -1.0)), br = levelAt(cell + vec2(1.0, -1.0));
    vec2 g = vec2((tr + 2.0 * mr + br) - (tl + 2.0 * ml + bl), (tl + 2.0 * tc + tr) - (bl + 2.0 * bc + br)) / 4.0;
    float mean = (tl + tc + tr + ml + mr + bl + bc + br + level) / 9.0;
    if (length(g) > 0.2 && level > 0.04 && level >= mean && level < 0.85) {
      float angle = mod(atan(g.x, -g.y), 3.14159265);
      index = uRamp + mod(floor((angle + 0.3927) / 0.7854), 4.0);
      ink *= 1.15;
    }

    // Sparse twinkling stars in empty cells.
    if (index < 0.5) {
      float h = hash(cell);
      if (h > 0.986) {
        float twinkle = 0.5 + 0.5 * sin(uTime * (0.5 + h) + h * 97.0);
        index = h > 0.997 ? uStar : uDot;
        ink = uStarInk * (0.3 + 0.7 * twinkle);
      }
    }

    float glyph = texture2D(tGlyphs, vec2((index + local.x) / uAtlas, local.y)).r;
    gl_FragColor = vec4(mix(uBg, ink, glyph), 1.0);
  }
`;

function srgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return new THREE.Vector3(((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255);
}

const mat = (color, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.9, metalness: 0, flatShading: true, ...extra });

function mesh(geometry, material, [x, y, z] = [0, 0, 0]) {
  const m = new THREE.Mesh(geometry, material);
  m.position.set(x, y, z);
  return m;
}

function glyphAtlas(cellW, cellH, font) {
  const canvas = document.createElement('canvas');
  canvas.width = cellW * ATLAS.length;
  canvas.height = cellH;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#fff';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = `500 ${Math.round(cellH * 0.86)}px ${font}`;
  [...ATLAS].forEach((ch, i) => ctx.fillText(ch, i * cellW + cellW / 2, cellH * 0.54));
  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;
  return texture;
}

function buildHome() {
  const home = new THREE.Group();
  const glow = mat('#2a1a10', { emissive: C.window, emissiveIntensity: 1.6 });
  const porchGlow = mat('#3a2a10', { emissive: C.porch, emissiveIntensity: 2.2 });
  const trim = mat(C.trim);
  const leaf = mat(C.leaf);

  // Floating island
  home.add(mesh(new THREE.CylinderGeometry(2.7, 2.55, 0.45, 40), mat(C.grass), [0, -0.225, 0]));
  const soil = mesh(new THREE.ConeGeometry(2.55, 1.9, 40), mat(C.soil), [0, -1.4, 0]);
  soil.rotation.x = Math.PI;
  home.add(soil);

  // Walls and gables
  home.add(mesh(new THREE.BoxGeometry(2.2, 1.5, 1.7), mat(C.plaster), [0, 0.75, 0]));
  const gable = new THREE.ExtrudeGeometry(
    new THREE.Shape([new THREE.Vector2(-1.1, 0), new THREE.Vector2(1.1, 0), new THREE.Vector2(0, 1)]),
    { depth: 1.7, bevelEnabled: false }
  );
  gable.translate(0, 0, -0.85);
  home.add(mesh(gable, mat(C.plaster), [0, 1.5, 0]));

  // Roof slabs with an overhang
  const pitch = Math.atan2(1, 1.1);
  for (const side of [-1, 1]) {
    const slab = mesh(new THREE.BoxGeometry(1.8, 0.12, 2.1), mat(C.roof), [side * 0.7, 1.95, 0]);
    slab.rotation.z = -side * pitch;
    home.add(slab);
  }

  // Chimney, with a marker where the smoke starts
  home.add(mesh(new THREE.BoxGeometry(0.3, 0.8, 0.3), mat(C.chimney), [0.6, 2.25, -0.35]));
  const chimneyTop = new THREE.Object3D();
  chimneyTop.position.set(0.6, 2.75, -0.35);
  home.add(chimneyTop);

  // Door, porch light, and a donation box waiting on the step
  home.add(mesh(new THREE.BoxGeometry(0.46, 0.82, 0.06), mat(C.door), [0, 0.41, 0.86]));
  home.add(mesh(new THREE.IcosahedronGeometry(0.08, 1), porchGlow, [0.38, 1.02, 0.9]));
  const door = new THREE.Object3D();
  door.position.set(0, 0.5, 1.0);
  home.add(door);
  const box = new THREE.Group();
  box.add(mesh(new THREE.BoxGeometry(0.42, 0.34, 0.42), mat(C.kraft), [0, 0.17, 0]));
  box.add(mesh(new THREE.BoxGeometry(0.43, 0.015, 0.09), mat(C.tape), [0, 0.345, 0]));
  box.position.set(0.68, 0, 1.3);
  box.rotation.y = 0.35;
  home.add(box);

  // Lit windows: front pair, sides, back, and a round one in the gable
  for (const x of [-0.66, 0.66]) {
    home.add(mesh(new THREE.BoxGeometry(0.54, 0.54, 0.04), trim, [x, 0.9, 0.855]));
    home.add(mesh(new THREE.BoxGeometry(0.44, 0.44, 0.05), glow, [x, 0.9, 0.86]));
    home.add(mesh(new THREE.BoxGeometry(0.035, 0.44, 0.07), trim, [x, 0.9, 0.87]));
    home.add(mesh(new THREE.BoxGeometry(0.44, 0.035, 0.07), trim, [x, 0.9, 0.87]));
  }
  for (const s of [-1, 1]) {
    home.add(mesh(new THREE.BoxGeometry(0.04, 0.54, 0.64), trim, [s * 1.105, 0.9, 0]));
    home.add(mesh(new THREE.BoxGeometry(0.05, 0.44, 0.54), glow, [s * 1.11, 0.9, 0]));
  }
  home.add(mesh(new THREE.BoxGeometry(0.44, 0.44, 0.05), glow, [0.5, 0.9, -0.86]));
  home.add(mesh(new THREE.CircleGeometry(0.17, 20), glow, [0, 1.85, 0.861]));

  // Garden
  for (const [x, z] of [[0.05, 1.25], [-0.08, 1.65], [0.06, 2.05], [-0.04, 2.45]]) {
    home.add(mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.05, 10), mat(C.stone), [x, 0.02, z]));
  }
  home.add(mesh(new THREE.CylinderGeometry(0.08, 0.11, 0.55, 6), mat(C.trunk), [-1.8, 0.27, -0.6]));
  home.add(mesh(new THREE.ConeGeometry(0.6, 0.95, 7), leaf, [-1.8, 0.95, -0.6]));
  home.add(mesh(new THREE.ConeGeometry(0.45, 0.75, 7), leaf, [-1.8, 1.45, -0.6]));
  home.add(mesh(new THREE.IcosahedronGeometry(0.32, 0), leaf, [1.55, 0.2, 0.75]));
  home.add(mesh(new THREE.IcosahedronGeometry(0.26, 0), leaf, [-1.45, 0.16, 0.95]));
  home.add(mesh(new THREE.IcosahedronGeometry(0.22, 0), leaf, [1.9, 0.14, -0.2]));

  return { home, glow, porchGlow, chimneyTop, door };
}

// Everyday things that drift around the house, about half a unit across.
const ITEMS = [
  function mug() {
    const g = new THREE.Group();
    const glaze = mat('#6f93b0');
    g.add(mesh(new THREE.CylinderGeometry(0.2, 0.18, 0.36, 14), glaze));
    g.add(mesh(new THREE.TorusGeometry(0.11, 0.035, 6, 14), glaze, [0.21, 0, 0]));
    return g;
  },
  function lamp() {
    const g = new THREE.Group();
    const metal = mat('#3f3a44');
    g.add(mesh(new THREE.CylinderGeometry(0.16, 0.18, 0.05, 14), metal, [0, -0.3, 0]));
    g.add(mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.5, 6), metal, [0, -0.03, 0]));
    g.add(mesh(new THREE.CylinderGeometry(0.12, 0.25, 0.26, 14),
      mat('#f3d9a4', { emissive: '#ffb85c', emissiveIntensity: 0.8 }), [0, 0.3, 0]));
    return g;
  },
  function books() {
    const g = new THREE.Group();
    const stack = [['#b5523b', 0.5, 0.1, 0.36, -0.1, 0.1], ['#d9a441', 0.46, 0.09, 0.33, -0.005, -0.15],
      ['#5f7d5b', 0.42, 0.11, 0.31, 0.095, 0.25]];
    for (const [color, w, h, d, y, turn] of stack) {
      const book = mesh(new THREE.BoxGeometry(w, h, d), mat(color), [0, y, 0]);
      book.rotation.y = turn;
      g.add(book);
    }
    return g;
  },
  function boot() {
    const g = new THREE.Group();
    const leather = mat('#7a4b2d');
    g.add(mesh(new THREE.BoxGeometry(0.22, 0.42, 0.24), leather, [-0.08, 0.09, 0]));
    g.add(mesh(new THREE.BoxGeometry(0.44, 0.16, 0.26), leather, [0.03, -0.2, 0]));
    g.add(mesh(new THREE.BoxGeometry(0.46, 0.05, 0.27), mat('#3a2a22'), [0.03, -0.3, 0]));
    return g;
  },
  function teddy() {
    const g = new THREE.Group();
    const fur = mat('#b07a4f');
    g.add(mesh(new THREE.IcosahedronGeometry(0.22, 1), fur, [0, -0.1, 0]));
    g.add(mesh(new THREE.IcosahedronGeometry(0.16, 1), fur, [0, 0.2, 0]));
    g.add(mesh(new THREE.IcosahedronGeometry(0.06, 0), fur, [-0.12, 0.33, 0]));
    g.add(mesh(new THREE.IcosahedronGeometry(0.06, 0), fur, [0.12, 0.33, 0]));
    g.add(mesh(new THREE.IcosahedronGeometry(0.065, 0), mat('#e2c6a3'), [0, 0.17, 0.14]));
    return g;
  },
  function beanie() {
    const g = new THREE.Group();
    g.add(mesh(new THREE.SphereGeometry(0.22, 14, 7, 0, Math.PI * 2, 0, Math.PI / 2), mat('#c2453a'), [0, -0.05, 0]));
    g.add(mesh(new THREE.CylinderGeometry(0.228, 0.228, 0.09, 14), mat('#a63a31'), [0, -0.08, 0]));
    g.add(mesh(new THREE.IcosahedronGeometry(0.08, 1), mat('#f0e2d0'), [0, 0.22, 0]));
    return g;
  }
];

function parcel() {
  const g = new THREE.Group();
  g.add(mesh(new THREE.BoxGeometry(0.4, 0.32, 0.4), mat(C.kraft)));
  g.add(mesh(new THREE.BoxGeometry(0.41, 0.33, 0.08), mat(C.tape)));
  return g;
}

function dispose(object) {
  object.traverse((o) => {
    o.geometry?.dispose();
    for (const m of [o.material].flat()) {
      m?.map?.dispose();
      m?.dispose();
    }
  });
}

function bezier([a, b, c], t, out) {
  const u = 1 - t;
  return out.set(0, 0, 0).addScaledVector(a, u * u).addScaledVector(b, 2 * u * t).addScaledVector(c, t * t);
}

const easeInOut = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

/**
 * @param {HTMLElement} host  element to fill; its size drives the grid
 * @param {{ cellWidth?: number, cellHeight?: number, font?: string, background?: string }} [options]
 */
export async function createAsciiHome(host, options = {}) {
  const {
    cellWidth = 8,
    cellHeight = 14,
    font = '"DM Mono", ui-monospace, monospace',
    background = C.night
  } = options;
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Glyphs are drawn once into an atlas, so the font has to be ready first.
  await document.fonts?.load(`500 16px ${font}`).catch(() => {});

  const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'low-power' });
  renderer.setClearColor(0x000000, 1);
  const canvas = renderer.domElement;
  canvas.style.cssText = 'display:block;width:100%;height:100%';
  host.appendChild(canvas);

  // --- 3D scene ---------------------------------------------------------
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
  let distance = 11;

  scene.add(new THREE.HemisphereLight('#b9a3d6', '#3a2a20', 0.7));
  const sun = new THREE.DirectionalLight('#ffe0b8', 2.0);
  sun.position.set(4, 6, 5);
  scene.add(sun);
  const rim = new THREE.DirectionalLight('#8f86ff', 0.7);
  rim.position.set(-5, 3, -4);
  scene.add(rim);

  const world = new THREE.Group();
  scene.add(world);
  const { home, glow, porchGlow, chimneyTop, door } = buildHome();
  world.add(home);
  const porchLight = new THREE.PointLight('#ffb054', 5, 5, 2);
  porchLight.position.set(0.3, 1.1, 1.6);
  home.add(porchLight);

  const orbit = new THREE.Group();
  scene.add(orbit);
  const orbiters = ITEMS.map((make, i) => {
    const obj = make();
    obj.userData = { angle: (i / ITEMS.length) * Math.PI * 2, lift: 0.5 + (i % 3) * 0.45, phase: i * 1.7, spin: 0.4 + (i % 2) * 0.3 };
    orbit.add(obj);
    return obj;
  });

  const puffs = Array.from({ length: 7 }, (_, i) => {
    const puff = mesh(new THREE.IcosahedronGeometry(0.17, 1), mat(C.smoke, { transparent: true, depthWrite: false }));
    puff.userData.offset = i / 7;
    scene.add(puff);
    return puff;
  });

  // --- ASCII pass -------------------------------------------------------
  const target = new THREE.WebGLRenderTarget(1, 1, {
    minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter
  });
  const post = new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    depthTest: false,
    depthWrite: false,
    uniforms: {
      tScene: { value: target.texture },
      tGlyphs: { value: null },
      uCellPx: { value: new THREE.Vector2() },
      uGrid: { value: new THREE.Vector2() },
      uRamp: { value: RAMP.length },
      uAtlas: { value: ATLAS.length },
      uDot: { value: DOT },
      uStar: { value: STAR },
      uBg: { value: srgb(background) },
      uStarInk: { value: srgb(C.star) },
      uTime: { value: 0 }
    }
  });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), post);
  quad.frustumCulled = false;
  const postScene = new THREE.Scene();
  postScene.add(quad);
  const postCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

  let atlasDpr = 0;
  let focusX = 0.5; // where the house sits across the panel, 0..1
  function resize() {
    const width = Math.max(1, host.clientWidth);
    const height = Math.max(1, host.clientHeight);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr);
    renderer.setSize(width, height, false);

    const cols = Math.ceil(width / cellWidth);
    const rows = Math.ceil(height / cellHeight);
    target.setSize(cols * SAMPLES, rows * SAMPLES);
    post.uniforms.uCellPx.value.set(cellWidth * dpr, cellHeight * dpr);
    post.uniforms.uGrid.value.set(cols, rows);
    if (dpr !== atlasDpr) {
      post.uniforms.tGlyphs.value?.dispose();
      post.uniforms.tGlyphs.value = glyphAtlas(Math.round(cellWidth * dpr), Math.round(cellHeight * dpr), font);
      atlasDpr = dpr;
    }

    // Fit the whole island and orbit, and on wide screens slide the house
    // right so the headline has room on the left.
    const aspect = (cols * cellWidth) / (rows * cellHeight);
    camera.aspect = aspect;
    distance = Math.max(9.2, 12 / aspect);
    const shift = aspect > 1.3 ? Math.min(0.36, (aspect - 1.3) * 0.6) : 0;
    camera.filmOffset = -shift * camera.getFilmWidth() * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * aspect;
    camera.updateProjectionMatrix();
    focusX = (1 + shift) / 2;
  }

  // --- Animation --------------------------------------------------------
  // Where the cursor is relative to the house, -1..1 on each axis. The home
  // turns to face it on a slow spring (see step), so it follows without snapping.
  const pointer = new THREE.Vector2();
  const onPointer = (e) => {
    const r = host.getBoundingClientRect();
    pointer.set(
      THREE.MathUtils.clamp((e.clientX - (r.left + r.width * focusX)) / (r.width * 0.5), -1, 1),
      THREE.MathUtils.clamp((e.clientY - (r.top + r.height * 0.45)) / (r.height * 0.6), -1, 1)
    );
  };
  const onLeave = () => pointer.set(0, 0);
  addEventListener('pointermove', onPointer, { passive: true });
  document.documentElement.addEventListener('mouseleave', onLeave);

  // Critically damped spring: eases toward its target and never overshoots.
  // FOLLOW is its rate; lower follows more lazily.
  const FOLLOW = 2;
  const yaw = { pos: -0.35, vel: 0 };
  const tilt = { pos: 0, vel: 0 };
  const spring = (s, target, dt) => {
    dt = Math.min(dt, 0.05);
    s.vel += (FOLLOW * FOLLOW * (target - s.pos) - 2 * FOLLOW * s.vel) * dt;
    s.pos += s.vel * dt;
    return s.pos;
  };

  const flights = [];
  const scratch = new THREE.Vector3();
  let elapsed = 0;
  let pulse = 0;
  let lastLaunch = -5.5; // first ambient launch ~1.5 s after load
  let nextKind = 'give';

  /** 'give': a parcel flies into the house. 'help': an item flies out to you. */
  function launch(kind) {
    if (reduceMotion || elapsed - lastLaunch < 0.9) return;
    lastLaunch = elapsed;
    const obj = kind === 'give' ? parcel() : ITEMS[Math.floor(Math.random() * ITEMS.length)]();
    const doorway = door.getWorldPosition(new THREE.Vector3());
    const path = kind === 'give'
      ? [new THREE.Vector3(-8, 4.5, 2), new THREE.Vector3(-3.5, 5.5, 2.5), doorway]
      : [doorway, new THREE.Vector3(3, 4.5, 3.5), new THREE.Vector3(8.5, 3.5, 5)];
    obj.userData = { kind, path, t: 0, duration: 1.9 };
    if (kind === 'help') pulse = Math.max(pulse, 0.6);
    scene.add(obj);
    flights.push(obj);
  }

  function step(dt) {
    elapsed += dt;
    const t = elapsed;

    world.rotation.set(
      spring(tilt, pointer.y * 0.22, dt),
      spring(yaw, -0.35 + 0.08 * Math.sin(t * 0.22) + pointer.x * 0.75, dt),
      0
    );

    for (const obj of orbiters) {
      const u = obj.userData;
      const a = u.angle + t * 0.18;
      obj.position.set(Math.cos(a) * 3.2, u.lift + 0.15 * Math.sin(t * 1.1 + u.phase), Math.sin(a) * 3.2);
      obj.rotation.set(0.3 * Math.sin(t * 0.7 + u.phase), t * u.spin, 0.2 * Math.cos(t * 0.5 + u.phase));
    }

    chimneyTop.getWorldPosition(scratch);
    for (const puff of puffs) {
      const life = (t * 0.22 + puff.userData.offset) % 1;
      puff.position.set(scratch.x + life * 0.6 + 0.12 * Math.sin(t * 1.3 + puff.userData.offset * 9),
        scratch.y + life * 2.2, scratch.z);
      puff.scale.setScalar(0.5 + 1.8 * life);
      puff.material.opacity = 0.75 * (1 - life) * Math.min(1, life * 10);
    }

    for (let i = flights.length - 1; i >= 0; i--) {
      const f = flights[i];
      const u = f.userData;
      u.t += dt / u.duration;
      const p = Math.min(u.t, 1);
      const e = easeInOut(p);
      bezier(u.path, e, f.position);
      f.rotation.x += dt * 2;
      f.rotation.y += dt * 3;
      f.scale.setScalar(u.kind === 'give' ? (p > 0.7 ? 1 - ((p - 0.7) / 0.3) * 0.85 : 1) : 0.3 + 1.1 * e);
      if (u.t >= 1) {
        if (u.kind === 'give') pulse = 1;
        scene.remove(f);
        dispose(f);
        flights.splice(i, 1);
      }
    }

    // Ambient story: every few seconds something arrives or leaves.
    if (!reduceMotion && t - lastLaunch > 7) {
      launch(nextKind);
      nextKind = nextKind === 'give' ? 'help' : 'give';
    }

    const flicker = 1 + 0.05 * Math.sin(t * 7.3) * Math.sin(t * 3.1);
    glow.emissiveIntensity = 1.6 * flicker * (1 + 1.3 * pulse);
    porchGlow.emissiveIntensity = 2.2 * (1 + 0.8 * pulse);
    pulse *= Math.exp(-dt * 2);

    camera.position.set(0, 3, distance);
    camera.lookAt(0, 0.55, 0);
  }

  function render() {
    renderer.setRenderTarget(target);
    renderer.render(scene, camera);
    renderer.setRenderTarget(null);
    post.uniforms.uTime.value = elapsed;
    renderer.render(postScene, postCamera);
  }

  let raf = 0;
  let running = false;
  let last = 0;
  let inView = true;
  function frame(now) {
    raf = requestAnimationFrame(frame);
    step(Math.min(0.05, Math.max(0, (now - last) / 1000)));
    last = now;
    render();
  }
  function start() {
    if (running || reduceMotion || !inView || document.hidden) return;
    running = true;
    last = performance.now();
    raf = requestAnimationFrame(frame);
  }
  function stop() {
    running = false;
    cancelAnimationFrame(raf);
  }
  function still() {
    // Reduced motion: one composed frame, redrawn only on resize.
    if (reduceMotion) render();
  }

  resize();
  step(reduceMotion ? 4 : 0);
  render();

  const resizeObserver = new ResizeObserver(() => { resize(); still(); });
  resizeObserver.observe(host);
  const visibility = new IntersectionObserver(([entry]) => {
    inView = entry.isIntersecting;
    inView ? start() : stop();
  });
  visibility.observe(host);
  const onVisibility = () => (document.hidden ? stop() : start());
  document.addEventListener('visibilitychange', onVisibility);
  start();

  return {
    launch,
    destroy() {
      stop();
      resizeObserver.disconnect();
      visibility.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
      removeEventListener('pointermove', onPointer);
      document.documentElement.removeEventListener('mouseleave', onLeave);
      dispose(scene);
      for (const f of flights) dispose(f);
      quad.geometry.dispose();
      post.uniforms.tGlyphs.value?.dispose();
      post.dispose();
      target.dispose();
      renderer.dispose();
      canvas.remove();
    }
  };
}
