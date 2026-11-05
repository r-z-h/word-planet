<template>
  <div class="mr">
    <div class="mr-stars">
      <span v-for="i in 5" :key="i" :class="{ on: i <= stars }">★</span>
    </div>

    <div class="mr-word">{{ question.stem }}</div>
    <div class="mr-phon">{{ question.phonetic || '' }}</div>

    <button
      class="mr-mic"
      :class="{ rec: recording, disabled: disabled }"
      :disabled="disabled || unsupported"
      @click="toggle"
    >
      {{ recording ? '⏹' : '🎤' }}
    </button>

    <div class="mr-vol">
      <i v-for="i in 20" :key="i" :class="{ on: i <= volLevel }" :style="{ height: (i <= volLevel ? 18 : 4) + 'px' }" />
    </div>

    <!-- 边说边出的字幕 -->
    <div class="mr-subtitle" :class="{ live: recording }">
      <template v-if="recording && !subtitle">听你说…</template>
      <template v-else>{{ subtitle || '　' }}</template>
    </div>

    <div v-if="scoreError" class="mr-error">{{ scoreError }}</div>

    <div class="mr-state">{{ stateText }}</div>

    <div v-if="score !== null" class="mr-score">
      <b>{{ score }}</b><span>分</span>
      <em :class="'s' + source">{{ sourceLabel }}</em>
    </div>

    <div class="mr-arc">
      <i v-for="i in 15" :key="i" :class="{ on: i <= litCount }" />
    </div>

    <div class="mr-ops">
      <button class="wp2-btn" :disabled="recording" @click="playStandard">🔊 听标准音</button>
      <button class="wp2-btn" :disabled="recording || !audioURL" @click="playMine">▶ 听听我刚才读的</button>
      <button v-if="serviceError" class="wp2-btn gold" :disabled="disabled" @click="retry">↻ 再读一次</button>
    </div>
    <div class="mr-hint wp2-dim">
      点一下麦克风开始，<b>读完再点一下停止</b>。边读边显示识别到的字，停麦后给出评分。
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { speak } from '../../utils/speech'

const props = defineProps({
  question: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
  litCount: { type: Number, default: 0 }
})
const emit = defineEmits(['submit'])

const recording = ref(false)
const stars = ref(0)
const subtitle = ref('')
const score = ref(null)
const source = ref('mock')
const scoreError = ref('')
const serviceError = ref(false)
const volLevel = ref(0)
const audioURL = ref(null)
const unsupported = ref(false)
const judged = ref(false)

let stream = null
let actx = null
let node = null
let srcNode = null
let ws = null
let volTimer = null
let maxTimer = null
const chunks = [] // Int16Array[]

const stateText = computed(() => {
  if (unsupported.value) return '这台设备听不到你读，听标准音后点「我读过了」'
  if (serviceError.value) return '评分服务暂时不可用，点「再读一次」'
  if (recording.value) return '正在听…（读完了点我）'
  if (judged.value) return '评分完成'
  return '点一下开始，读完再点一下'
})
const sourceLabel = computed(() =>
  source.value === 'iflytek' ? '讯飞评分' : source.value === 'fallback' ? '降级评分' : '演示评分'
)

function token() {
  return localStorage.getItem('wp_token') || ''
}
function wsUrl(word) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/api/pronunciation/stream?word=${encodeURIComponent(word)}&token=${encodeURIComponent(token())}`
}

function toggle() {
  if (recording.value) stop()
  else start()
}

async function start() {
  if (props.disabled || unsupported.value) return
  const word = props.question.answer || props.question.stem
  if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
    unsupported.value = true
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { noiseSuppression: true, echoCancellation: true, autoGainControl: true }
    })
  } catch {
    unsupported.value = true
    return
  }
  judged.value = false
  stars.value = 0
  score.value = null
  subtitle.value = ''
  scoreError.value = ''
  serviceError.value = false
  chunks.length = 0
  recording.value = true

  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    actx = new Ctx({ sampleRate: 16000 })
    await actx.audioWorklet.addModule('/pcm-worklet.js')
    srcNode = actx.createMediaStreamSource(stream)
    node = new AudioWorkletNode(actx, 'pcm16')
    // 高通滤波：去掉低频轰鸣 / 电流声
    const hp = actx.createBiquadFilter()
    hp.type = 'highpass'
    hp.frequency.value = 110
    hp.Q.value = 0.7
    srcNode.connect(hp)
    hp.connect(node)
    // 必须有出口，worklet 才会被渲染；用 0 增益接到 destination，避免自己听到自己
    const mute = actx.createGain()
    mute.gain.value = 0
    node.connect(mute)
    mute.connect(actx.destination)
    // 不接 destination，避免自己听到自己

    // 音量条（用 worklet 分片估算）
    volTimer = setInterval(() => {
      const last = chunks[chunks.length - 1]
      if (!last) return
      let peak = 0
      for (let i = 0; i < last.length; i += 8) peak = Math.max(peak, Math.abs(last[i]))
      volLevel.value = Math.min(20, Math.round((peak / 32768) * 60))
    }, 90)

    // 字幕 WS
    try {
      ws = new WebSocket(wsUrl(word))
      ws.binaryType = 'arraybuffer'
      ws.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data)
          if (d.type === 'interim' && d.text) subtitle.value = d.text
          if (d.type === 'final' && d.text && !subtitle.value) subtitle.value = d.text
        } catch {
          /* ignore */
        }
      }
    } catch {
      ws = null
    }

    node.port.onmessage = (ev) => {
      const ab = ev.data
      chunks.push(new Int16Array(ab))
      if (ws && ws.readyState === 1) ws.send(ab)
    }
  } catch {
    unsupported.value = true
    cleanupAudio()
    recording.value = false
    return
  }

  clearTimeout(maxTimer)
  maxTimer = setTimeout(() => {
    if (recording.value) stop()
  }, 60000)
}

function cleanupAudio() {
  clearInterval(volTimer)
  clearTimeout(maxTimer)
  volLevel.value = 0
  try {
    if (node && node.port) node.port.onmessage = null
  } catch {
    /* ignore */
  }
  try {
    if (srcNode) srcNode.disconnect()
    if (node) node.disconnect()
  } catch {
    /* ignore */
  }
  try {
    if (actx && actx.state !== 'closed') actx.close()
  } catch {
    /* ignore */
  }
  actx = null
  node = null
  srcNode = null
  try {
    if (stream) stream.getTracks().forEach((t) => t.stop())
  } catch {
    /* ignore */
  }
  stream = null
}

function mergePcm() {
  const total = chunks.reduce((n, c) => n + c.length, 0)
  const out = new Uint8Array(total * 2)
  const view = new DataView(out.buffer)
  let off = 0
  for (const c of chunks) {
    for (let i = 0; i < c.length; i += 1) {
      view.setInt16(off, c[i], true)
      off += 2
    }
  }
  return out
}

// 端点检测：按 100ms 能量块裁掉首尾静音/低能量噪声，只留有效发音段
function trimSilence(pcmBytes) {
  const n = Math.floor(pcmBytes.length / 2)
  if (n < 3200) return pcmBytes // <0.2s 不做处理
  const i16 = new Int16Array(pcmBytes.buffer, pcmBytes.byteOffset, n)
  const block = 1600
  const blocks = Math.ceil(n / block)
  const rms = new Array(blocks)
  let maxR = 0
  for (let b = 0; b < blocks; b += 1) {
    const s = b * block
    const e = Math.min(n, s + block)
    let sum = 0
    for (let i = s; i < e; i += 1) {
      const v = i16[i] / 32768
      sum += v * v
    }
    const r = Math.sqrt(sum / Math.max(1, e - s))
    rms[b] = r
    if (r > maxR) maxR = r
  }
  if (maxR < 0.01) return pcmBytes // 全静音，交给后端判定
  const thr = Math.max(0.015, maxR * 0.12)
  let first = -1
  let last = -1
  for (let b = 0; b < blocks; b += 1) {
    if (rms[b] >= thr) {
      if (first < 0) first = b
      last = b
    }
  }
  if (first < 0) return pcmBytes
  const sIdx = Math.max(0, first - 1) * block
  const eIdx = Math.min(n, (last + 2) * block)
  return pcmBytes.slice(sIdx * 2, eIdx * 2)
}

function makeWav(pcmBytes) {
  const h = new ArrayBuffer(44)
  const v = new DataView(h)
  const w = (o, s) => { for (let i = 0; i < s.length; i += 1) v.setUint8(o + i, s.charCodeAt(i)) }
  w(0, 'RIFF'); v.setUint32(4, 36 + pcmBytes.length, true); w(8, 'WAVE')
  w(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
  v.setUint32(24, 16000, true); v.setUint32(28, 32000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true)
  w(36, 'data'); v.setUint32(40, pcmBytes.length, true)
  return new Blob([h, pcmBytes], { type: 'audio/wav' })
}

async function stop() {
  if (!recording.value) return
  recording.value = false
  const word = props.question.answer || props.question.stem
  try {
    if (ws && ws.readyState === 1) ws.send('END')
  } catch {
    /* ignore */
  }
  cleanupAudio()

  let pcm = mergePcm()
  pcm = trimSilence(pcm)
  if (!pcm.length) {
    // 没有采到音频 → 走降级
    unsupported.value = true
    return
  }
  audioURL.value = URL.createObjectURL(makeWav(pcm))

  try {
    const fd = new FormData()
    fd.append('audio', new Blob([pcm], { type: 'application/octet-stream' }), 'a.pcm')
    fd.append('word', word)
    const res = await fetch('/api/pronunciation/score', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token()}` },
      body: fd
    })
    if (!res.ok) throw new Error('score ' + res.status)
    const data = await res.json()
    if (data.source !== 'iflytek') {
      // 未配置/调用失败：不当作真实评分，也不计入对错
      score.value = null
      source.value = data.source || 'fallback'
      scoreError.value =
        data.source === 'mock'
          ? '评分服务未接入（讯飞 key 未生效），本次不计分'
          : '评分失败，请重读（未计入对错）'
      serviceError.value = true
      return
    }
    score.value = data.score
    stars.value = data.stars
    source.value = 'iflytek'
    if (data.recognized) subtitle.value = data.recognized
    finish(data.stars, data.recognized || subtitle.value)
  } catch {
    // 网络/接口异常：不当作评分，不计对错
    score.value = null
    source.value = 'fallback'
    scoreError.value = '评分请求失败（未计入对错），请再读一次'
    serviceError.value = true
  }
  try {
    if (ws) ws.close()
  } catch {
    /* ignore */
  }
  ws = null
}

function finish(s, said) {
  if (judged.value) return
  judged.value = true
  emit('submit', { is_correct: s >= 2, transcript: said })
}

function retry() {
  serviceError.value = false
  scoreError.value = ''
  start()
}

function selfPass() {
  // 不再提供“自评通过=2星”的兜底：没有真实评分就不计分、不判对错
  return
}

function playStandard() {
  speak(props.question.answer || props.question.stem, { rate: 0.85 })
}

function playMine() {
  if (!audioURL.value) return
  try {
    new Audio(audioURL.value).play()
  } catch {
    /* ignore */
  }
}

onBeforeUnmount(() => {
  cleanupAudio()
  try {
    if (ws) ws.close()
  } catch {
    /* ignore */
  }
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
})
</script>

<style scoped>
.mr {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.mr-stars { display: flex; gap: 9px; font-size: 26px; }
.mr-stars span { color: var(--wp2-dim); transition: 0.2s; transform: scale(1); }
.mr-stars span.on { color: var(--wp2-gold); text-shadow: 0 0 14px rgba(255, 205, 76, 0.65); transform: scale(1.15); }
.mr-word {
  font-size: clamp(34px, 5vw, 52px);
  font-weight: 900;
  color: var(--wp2-ink);
  letter-spacing: 1px;
  text-shadow: 0 3px 0 rgba(20, 10, 40, 0.7);
}
.mr-phon { font-size: 14px; color: var(--wp2-muted); min-height: 18px; }
.mr-mic {
  width: 88px; height: 88px; border-radius: 50%; cursor: pointer;
  font-size: 30px; display: grid; place-items: center;
  background: radial-gradient(circle at 35% 30%, var(--wp2-l2b), var(--wp2-l2));
  border: 3px solid var(--wp2-inkline);
  box-shadow: 0 6px 0 var(--wp2-inkline);
  transition: 0.15s;
}
.mr-mic.rec {
  background: radial-gradient(circle at 35% 30%, #ff9a8a, #ff5a5a);
  box-shadow: 0 6px 0 var(--wp2-inkline), 0 0 0 9px rgba(255, 90, 90, 0.16);
}
.mr-mic:active:not(:disabled) { transform: scale(0.95); }
.mr-mic.disabled, .mr-mic:disabled { filter: grayscale(0.5) brightness(0.85); cursor: default; }
.mr-vol { display: flex; gap: 3px; align-items: flex-end; height: 24px; }
.mr-vol i { width: 4px; border-radius: 2px; background: rgba(255, 246, 225, 0.18); height: 4px; transition: 0.08s; }
.mr-vol i.on { background: var(--wp2-l2b); }
.mr-subtitle {
  min-height: 26px; font-size: 16px; font-weight: 800; color: var(--wp2-muted);
  letter-spacing: 1px; text-align: center; max-width: 90%;
}
.mr-subtitle.live { color: var(--wp2-gold); text-shadow: 0 0 12px rgba(255, 205, 76, 0.5); }
.mr-state { font-size: 12px; color: var(--wp2-muted); min-height: 17px; }
.mr-error { font-size: 11.5px; color: #ff9d9d; font-weight: 800; text-align: center; max-width: 90%; }
.mr-score { display: flex; align-items: baseline; gap: 6px; }
.mr-score b { font-size: 30px; font-weight: 900; color: var(--wp2-gold); }
.mr-score span { font-size: 12px; color: var(--wp2-muted); }
.mr-score em { font-style: normal; font-size: 10px; color: var(--wp2-dim); margin-left: 4px; }
.mr-arc { display: flex; gap: 5px; flex-wrap: wrap; justify-content: center; max-width: 520px; }
.mr-arc i {
  width: 10px; height: 10px; border-radius: 50%;
  background: rgba(255, 246, 225, 0.12); border: 1.5px solid rgba(255, 246, 225, 0.16);
  transition: 0.25s;
}
.mr-arc i.on { background: var(--wp2-gold); border-color: var(--wp2-gold); box-shadow: 0 0 7px rgba(255, 205, 76, 0.65); }
.mr-ops { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
.mr-hint { font-size: 11px; text-align: center; max-width: 600px; line-height: 1.6; }
.mr-hint b { color: var(--wp2-ink); }
</style>
