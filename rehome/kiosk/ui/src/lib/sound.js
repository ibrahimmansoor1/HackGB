// Small synthesized sounds, so there are no audio files to ship. Chromium on the Pi runs with
// --autoplay-policy=no-user-gesture-required; elsewhere the first key or button press unlocks audio.
let ctx;

function audio() {
  ctx ??= new AudioContext();
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}

export function unlock() {
  try {
    audio();
  } catch {}
}

function tone(freq, at, length, level = 0.08) {
  const a = audio();
  const osc = a.createOscillator();
  const gain = a.createGain();
  const t = a.currentTime + at;
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0, t);
  gain.gain.linearRampToValueAtTime(level, t + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + length);
  osc.connect(gain).connect(a.destination);
  osc.start(t);
  osc.stop(t + length + 0.05);
}

function play(fn) {
  try {
    fn();
  } catch {}
}

export const tick = () => play(() => tone(660, 0, 0.12, 0.05));

export const shutter = () =>
  play(() => {
    const a = audio();
    const noise = a.createBuffer(1, a.sampleRate * 0.15, a.sampleRate);
    const data = noise.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / data.length) ** 3;
    const src = a.createBufferSource();
    const filter = a.createBiquadFilter();
    const gain = a.createGain();
    src.buffer = noise;
    filter.type = 'bandpass';
    filter.frequency.value = 2400;
    gain.gain.value = 0.35;
    src.connect(filter).connect(gain).connect(a.destination);
    src.start();
  });

// A cash register: a coin rattle, then two bright bell strikes
export const chaChing = () =>
  play(() => {
    const a = audio();
    const rattle = a.createBuffer(1, a.sampleRate * 0.12, a.sampleRate);
    const data = rattle.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / data.length) ** 2;
    const src = a.createBufferSource();
    const filter = a.createBiquadFilter();
    const gain = a.createGain();
    src.buffer = rattle;
    filter.type = 'highpass';
    filter.frequency.value = 5000;
    gain.gain.value = 0.25;
    src.connect(filter).connect(gain).connect(a.destination);
    src.start();
    tone(2093, 0.08, 0.25, 0.07);
    tone(3136, 0.08, 0.25, 0.04);
    tone(2637, 0.22, 1.1, 0.09);
    tone(3951, 0.22, 0.9, 0.04);
  });

export const chime = () =>
  play(() => {
    tone(784, 0, 0.6);
    tone(1175, 0.14, 0.9);
  });
