// Isometric line drawings for the "How it works" columns.
// Each figure is a pure function of
//   t      0 at rest → 1 while hovered (eased by WireFigure)
//   clock  seconds of hover motion so far (drives sways and loops)
//   shot   seconds since this hover began (drives one-shot sequences)
// and returns { paths, marks, labels } in a -175..175 SVG viewBox.
// Paths and marks may carry a `tone`; WireFigure keeps it grey at rest and
// brings the color in with t.

const PITCH = Math.atan(1 / Math.SQRT2); // true isometric tilt
const YAW = Math.PI / 4;
const TAU = Math.PI * 2;
const DEG = Math.PI / 180;

const clamp01 = (v) => Math.min(1, Math.max(0, v));
const ease = (v) => {
  v = clamp01(v);
  return v * v * (3 - 2 * v);
};
const lerp = (a, b, k) => a + (b - a) * k;
/** 0 → 1 over [start, start + duration] seconds, eased. */
const phase = (time, start, duration) => ease((time - start) / duration);

/** World [x, y, z] → screen [x, y, depth]. Larger depth is closer to the viewer. */
function view(yaw, shiftY = 0) {
  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  const cp = Math.cos(PITCH), sp = Math.sin(PITCH);
  return ([x, y, z]) => {
    const x1 = x * cy + z * sy;
    const z1 = -x * sy + z * cy;
    return [x1, -(y * cp - z1 * sp) + shiftY, z1 * cp + y * sp];
  };
}

function line(project, points, style = 'solid', opacity = 1, closed = false) {
  const d = points
    .map((p, i) => {
      const [x, y] = project(p);
      return `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join('');
  return { d: closed ? d + 'Z' : d, style, opacity };
}

const square = (y, r, [cx, cz] = [0, 0]) => [[cx - r, y, cz - r], [cx + r, y, cz - r], [cx + r, y, cz + r], [cx - r, y, cz + r]];
const rectZ = (x0, y0, x1, y1, z) => [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]];

/** Circle of radius r around c, facing +z ('z') or lying flat ('y'). */
function ring(c, r, plane = 'z', n = 48) {
  return Array.from({ length: n + 1 }, (_, i) => {
    const a = (i / n) * TAU;
    return plane === 'z'
      ? [c[0] + r * Math.cos(a), c[1] + r * Math.sin(a), c[2]]
      : [c[0] + r * Math.cos(a), c[1], c[2] + r * Math.sin(a)];
  });
}

/** Twelve box edges; the three meeting at the hidden back corner are dotted. */
function box(project, [x0, y0, z0], [x1, y1, z1], style = 'solid', opacity = 1) {
  const v = [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1],
    [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]];
  let hidden = 0;
  for (let i = 1; i < 4; i++) if (project(v[i])[2] < project(v[hidden])[2]) hidden = i;
  const edges = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];
  return edges.map(([a, b]) =>
    line(project, [v[a], v[b]], style === 'solid' && (a === hidden || b === hidden) ? 'dotted' : style, opacity));
}

/** Upright cylinder: two rings plus the two silhouette edges for this yaw. */
function cylinder(project, yaw, [cx, cz], r, y0, y1) {
  const paths = [line(project, ring([cx, y0, cz], r, 'y', 24)), line(project, ring([cx, y1, cz], r, 'y', 24))];
  for (const a of [yaw, yaw + Math.PI]) {
    const x = cx + r * Math.cos(a), z = cz + r * Math.sin(a);
    paths.push(line(project, [[x, y0, z], [x, y1, z]]));
  }
  return paths;
}

/** A box with four top flaps; ax and az are the flap angles (0 = closed). */
function flapBox(project, [cx, cz], w, bottom, top, ax, az) {
  const paths = box(project, [cx - w, bottom, cz - w], [cx + w, top, cz + w]);
  for (const s of [-1, 1]) {
    const fx = cx + s * (w - w * Math.cos(ax)), fyx = top + w * Math.sin(ax);
    paths.push(line(project, [[cx + s * w, top, cz - w], [fx, fyx, cz - w], [fx, fyx, cz + w], [cx + s * w, top, cz + w]]));
    const fz = cz + s * (w - w * Math.cos(az)), fyz = top + w * Math.sin(az);
    paths.push(line(project, [[cx - w, top, cz + s * w], [cx - w, fyz, fz], [cx + w, fyz, fz], [cx + w, top, cz + s * w]]));
  }
  return paths;
}

/** A gabled house with a door on its -x wall and a window facing +z. */
function house(project, [cx, cz], w, floor, eaves, ridge, style, opacity) {
  const x0 = cx - w, x1 = cx + w, z0 = cz - w, z1 = cz + w;
  return [
    ...box(project, [x0, floor, z0], [x1, eaves, z1], style, opacity),
    line(project, [[x0, eaves, z0], [cx, ridge, z0], [x1, eaves, z0]], style, opacity),
    line(project, [[x0, eaves, z1], [cx, ridge, z1], [x1, eaves, z1]], style, opacity),
    line(project, [[cx, ridge, z0], [cx, ridge, z1]], style, opacity),
    line(project, [[x0, floor, cz - 10], [x0, floor + 32, cz - 10], [x0, floor + 32, cz + 10], [x0, floor, cz + 10]], style, opacity),
    line(project, rectZ(cx - 8, floor + 16, cx + 16, floor + 34, z1), style, opacity, true)
  ];
}

/** A round marker dot at p. */
function mark(project, p, tone, opacity = 1, size = 3.5) {
  const [x, y] = project(p);
  return { x, y, tone, opacity, size };
}

// A sweater outline, unit size, y up.
const SWEATER = [[-0.38, -0.85], [-0.38, 0.25], [-0.62, 0.05], [-0.85, 0.38], [-0.42, 0.78], [-0.16, 0.78],
  [0, 0.6], [0.16, 0.78], [0.42, 0.78], [0.85, 0.38], [0.62, 0.05], [0.38, 0.25], [0.38, -0.85]];

// 1 · An instant camera: the shutter clicks, the flash fires, and the photo
//     slides out and develops into a listing.
export function photo(t, clock, shot) {
  const yaw = 0.42 + 0.22 * t * Math.sin(clock * 0.8);
  const project = view(yaw, -28);
  const F = 28; // front face
  const paths = [...box(project, [-64, -38, -F], [64, 38, F])];

  // Lens barrel, flash, viewfinder, rainbow stripe, film slot, shutter button
  paths.push(line(project, ring([-4, -2, F], 27)));
  paths.push(line(project, ring([-4, -2, F + 12], 27)));
  paths.push(line(project, ring([-4, -2, F + 12], 17)));
  paths.push(line(project, ring([-4, -2, F + 12], 7), 'dotted'));
  paths.push(line(project, rectZ(-56, 18, -34, 30, F), 'solid', 1, true));
  paths.push(line(project, rectZ(38, 18, 56, 30, F), 'solid', 1, true));
  ['lamp', 'brick', 'sage'].forEach((tone, i) =>
    paths.push({ ...line(project, [[31 + i * 4, -24, F], [31 + i * 4, 10, F]]), tone }));
  paths.push(line(project, rectZ(-46, -33, 46, -29, F), 'solid', 1, true));
  const press = t > 0.01 && shot < 0.3 ? Math.sin((Math.PI * shot) / 0.3) : 0;
  paths.push(...cylinder(project, yaw, [44, 0], 8, 38, 44 - 4 * press));

  const marks = [];
  const burst = phase(shot, 0.12, 0.22);
  const flash = t * burst * (1 - phase(shot, 0.4, 0.4));
  if (flash > 0.01) {
    for (let k = 0; k < 8; k++) {
      const a = (k / 8) * TAU;
      const ray = (r) => [-45 + Math.cos(a) * r, 24 + Math.sin(a) * r, F + 0.7 * r];
      paths.push({ ...line(project, [ray(14), ray(14 + 20 * burst)], 'solid', flash), tone: 'lamp' });
    }
    marks.push(mark(project, [-45, 24, F], 'lamp', flash, 5));
  }

  // The photo hangs out of the slot, develops, then gets its listing lines.
  const length = 92 * Math.min(phase(shot, 0.35, 0.9), t);
  if (length > 0.5) {
    const tilt = 14 * DEG;
    const at = (u, v) => [u, -31 - v * Math.cos(tilt), F + 1 + v * Math.sin(tilt)];
    paths.push(line(project, [at(-40, 0), at(40, 0), at(40, length), at(-40, length)], 'solid', 1, true));
    const shown = clamp01((length - 70) / 22) * phase(shot, 1.05, 0.25);
    if (shown > 0.01) {
      paths.push(line(project, [at(-32, 8), at(32, 8), at(32, 64), at(-32, 64)], 'solid', shown, true));
      const develop = phase(shot, 1.3, 1);
      const sweater = SWEATER.map(([u, v]) => at(u * 20, 36 - v * 20));
      paths.push(line(project, sweater, 'dotted', shown * (1 - develop), true));
      paths.push({ ...line(project, sweater, 'solid', shown * develop, true), tone: 'brick' });
      [54, 36, 46].forEach((len, i) => {
        const write = phase(shot, 2 + i * 0.22, 0.35);
        const v = 74 + i * 7;
        if (write > 0.02) paths.push(line(project, [at(-26, v), at(-26 + len * write, v)], 'solid', shown));
        marks.push(mark(project, at(-32, v), ['lamp', 'sage', 'brick'][i], shown * Math.min(1, write * 3), 1.8));
      });
    }
  }

  for (const [x, y] of [[-64, -38], [64, -38], [64, 38], [-64, 38]]) marks.push(mark(project, [x, y, F], 'lamp'));
  return { paths, marks, labels: [] };
}

// 2 · Context: a request in the middle, inferred needs rising around it.
const NEEDS = [['insulated', 72], ['snow', 40], ['water-resistant', 98], ['December', 54], ['hooded', 84], ['sub-freezing', 30]];

export function context(t, clock) {
  const project = view(YAW + clock * 0.35, 30);
  const Y = -30, R = 90;
  const paths = [line(project, ring([0, Y, 0], R, 'y', 72)), line(project, square(Y, 38), 'dotted', 1, true)];
  for (const a of [0, 60, 120]) {
    const c = Math.cos(a * DEG) * 38, s = Math.sin(a * DEG) * 38;
    paths.push(line(project, [[-c, Y, -s], [c, Y, s]]));
  }

  const hub = [0, Y + 28 + 46 * ease(t * 1.3), 0];
  paths.push(line(project, [[0, Y, 0], hub]));
  const marks = [mark(project, hub, 'ink')];
  const labels = [];

  NEEDS.forEach(([word, height], i) => {
    const a = (i / NEEDS.length) * TAU + 30 * DEG;
    const base = [Math.cos(a) * R, Y, Math.sin(a) * R];
    const rise = ease(t * 1.5 - i * 0.08);
    const pin = [base[0], Y + height * rise, base[2]];
    paths.push(line(project, [[0, Y, 0], base], 'dotted'));
    if (rise > 0.01) {
      paths.push(line(project, [base, pin], 'dotted'));
      paths.push(line(project, [hub, pin], 'solid', 0.7 * rise));
    }
    marks.push(mark(project, pin, 'sage'));
    // Each label stays centered on a point that slides smoothly outward as the
    // ring turns (left pins push their label left, right pins right), so labels
    // never jump. Neighbors alternate above and below their pins.
    const [x, y] = project(pin);
    const side = Math.max(-1, Math.min(1, (x - project([0, Y, 0])[0]) / R));
    labels.push({
      x: x + side * (word.length * 3.6 + 8),
      y: y + (i % 2 ? 16 : -9),
      text: word,
      opacity: ease(t * 1.5 - i * 0.08 - 0.25)
    });
  });
  return { paths, marks, labels };
}

// 3 · Rehome: the shelves thrust apart, the box on top opens, and the sweater
//     rises straight up into its new home. Leaving rewinds it all.
export function rehome(t, clock) {
  const project = view(YAW + 0.3 * t * Math.sin(clock * 0.6), -29);
  const spread = ease(t * 1.3);
  const H = 56, thick = 8;
  const levels = [-136 - 14 * spread, -114, -92 + 14 * spread];
  const paths = [];
  levels.forEach((y, i) => paths.push(...box(project, [-H, y, -H], [H, y + thick, H], i === 0 ? 'dotted' : 'solid')));
  const shelf = levels[2] + thick;

  const boxTop = shelf + 36;
  paths.push(...flapBox(project, [0, 0], 26, shelf, boxTop, 145 * DEG * ease(t * 1.6), 120 * DEG * ease(t * 1.6 - 0.3)));

  const floor = 62, eaves = 94, ridge = 120;
  const lift = ease(t * 1.4 - 0.3);
  if (lift > 0.01) {
    const y = lerp(boxTop - 6, floor + 16, lift) + 3 * t * Math.sin(clock * 2.2);
    const spin = clock * 1.6, size = 13;
    paths.push(line(project, [[0, boxTop, 0], [0, y - 11, 0]], 'dotted', t));
    const shape = SWEATER.map(([u, v]) => [u * size * Math.cos(spin), y + v * size, u * size * Math.sin(spin)]);
    paths.push({ ...line(project, shape, 'solid', Math.min(1, lift * 4), true), tone: 'brick' });
  }

  // The house waits as a dotted outline and firms up while hovered.
  paths.push(...house(project, [0, 0], 32, floor, eaves, ridge, 'dotted', 1 - t));
  paths.push(...house(project, [0, 0], 32, floor, eaves, ridge, 'solid', t));

  const marks = square(shelf, H).map((p) => mark(project, p, 'brick'));
  marks.push(mark(project, [4, floor + 25, 32], 'lamp', ease((lift - 0.8) / 0.2), 4.5));
  marks.push(mark(project, [0, ridge, 32], 'brick', t));
  return { paths, marks, labels: [] };
}
