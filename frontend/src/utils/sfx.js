/**
 * 极简 Web Audio 音效（无音频文件）。
 * 开关：localStorage.wp_sound === 'off' 时静音。
 */
let ctx = null

function masterVol() {
  const raw = localStorage.getItem('wp_volume')
  if (raw === null) return 0.8
  const n = Number(raw)
  return Number.isFinite(n) ? Math.min(1, Math.max(0, n / 100)) : 0.8
}

function audio() {
  if (localStorage.getItem('wp_sound') === 'off') return null
  if (masterVol() <= 0) return null
  try {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)()
    if (ctx.state === 'suspended') ctx.resume()
    return ctx
  } catch {
    return null
  }
}

function tone(freq, dur, { type = 'sine', vol = 0.16, delay = 0 } = {}) {
  const c = audio()
  if (!c) return
  const v = vol * masterVol()
  const t0 = c.currentTime + delay
  const o = c.createOscillator()
  const g = c.createGain()
  o.type = type
  o.frequency.value = freq
  o.connect(g)
  g.connect(c.destination)
  g.gain.setValueAtTime(0, t0)
  g.gain.linearRampToValueAtTime(v, t0 + 0.012)
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
  o.start(t0)
  o.stop(t0 + dur + 0.02)
}

/** 答对：叮—叮（上行两音） */
export function sfxDing() {
  tone(880, 0.16)
  tone(1318, 0.2, { vol: 0.1, delay: 0.06 })
}

/** 答错：低沉嗡嗡 */
export function sfxBuzz() {
  tone(150, 0.22, { type: 'square', vol: 0.12 })
  tone(92, 0.26, { type: 'sawtooth', vol: 0.1, delay: 0.02 })
}

/** 轻点 */
export function sfxPop() {
  tone(760, 0.09, { type: 'triangle', vol: 0.11 })
}

/** 字母砖落格 */
export function sfxTick() {
  tone(1500, 0.03, { type: 'square', vol: 0.05 })
}

/** 连击/升级 */
export function sfxLevelUp() {
  ;[523, 659, 784, 1047].forEach((f, i) => tone(f, 0.18, { vol: 0.12, delay: i * 0.08 }))
}

/** 命中（吞下 / 拼对瞬间）：短促下滑 */
export function sfxHit() {
  const c = audio()
  if (!c) return
  const t0 = c.currentTime
  const o = c.createOscillator()
  const g = c.createGain()
  o.type = 'triangle'
  o.frequency.setValueAtTime(660, t0)
  o.frequency.exponentialRampToValueAtTime(180, t0 + 0.16)
  o.connect(g)
  g.connect(c.destination)
  g.gain.setValueAtTime(0.14 * masterVol(), t0)
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.2)
  o.start(t0)
  o.stop(t0 + 0.22)
}

/** 碎裂（字母砖拼对）：短噪声 */
export function sfxShard() {
  const c = audio()
  if (!c) return
  const dur = 0.18
  const buf = c.createBuffer(1, Math.floor(c.sampleRate * dur), c.sampleRate)
  const d = buf.getChannelData(0)
  for (let i = 0; i < d.length; i += 1) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length)
  const src = c.createBufferSource()
  const g = c.createGain()
  const hp = c.createBiquadFilter()
  hp.type = 'highpass'
  hp.frequency.value = 1800
  src.buffer = buf
  src.connect(hp)
  hp.connect(g)
  g.connect(c.destination)
  g.gain.value = 0.12 * masterVol()
  src.start()
}

export function isSoundOn() {
  return localStorage.getItem('wp_sound') !== 'off'
}

export function setSoundOn(on) {
  localStorage.setItem('wp_sound', on ? 'on' : 'off')
}
