<template>
  <div class="mr">
    <div class="mr-stars">
      <span v-for="i in 3" :key="i" :class="{ on: i <= stars }">★</span>
    </div>

    <div class="mr-word">{{ question.stem }}</div>
    <div class="mr-phon">{{ question.phonetic || '' }}</div>

    <button class="mr-mic" :class="{ rec: recording, disabled }" :disabled="disabled || unsupported" @click="toggle">
      {{ recording ? '⏹' : '🎤' }}
    </button>

    <div class="mr-vol">
      <i v-for="i in 20" :key="i" :class="{ on: i <= volLevel }" :style="{ height: (i <= volLevel ? 18 : 4) + 'px' }" />
    </div>

    <div class="mr-state">{{ stateText }}</div>

    <div class="mr-arc">
      <i v-for="i in 15" :key="i" :class="{ on: i <= litCount }" />
    </div>

    <div class="mr-ops">
      <button class="wp2-btn" :disabled="recording" @click="playStandard">🔊 听标准音</button>
      <button class="wp2-btn" :disabled="recording || !audioURL" @click="playMine">▶ 听听我刚才读的</button>
      <button v-if="unsupported" class="wp2-btn gold" :disabled="disabled" @click="selfPass">✓ 我读过了</button>
    </div>
    <div class="mr-hint wp2-dim">
      点一下麦克风开始，<b>读完再点一下停止</b>。读对一个词亮一颗灯。
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

const SR = window.SpeechRecognition || window.webkitSpeechRecognition
const recording = ref(false)
const stars = ref(0)
const volLevel = ref(0)
const audioURL = ref(null)
const unsupported = ref(false)
const judged = ref(false)

let rec = null
let mediaRec = null
let stream = null
let volTimer = null
let maxTimer = null
let chunks = []

const stateText = computed(() => {
  if (unsupported.value) return '这台设备听不到你读，听标准音后点「我读过了」'
  if (recording.value) return '正在听…（读完了点我）'
  if (judged.value) return '评分完成'
  return '点一下开始，读完再点一下'
})

function toggle() {
  if (recording.value) stop()
  else start()
}

async function start() {
  if (props.disabled || unsupported.value) return
  if (!SR || !navigator.mediaDevices?.getUserMedia) {
    unsupported.value = true
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch {
    unsupported.value = true
    return
  }
  judged.value = false
  stars.value = 0
  recording.value = true
  chunks = []

  try {
    mediaRec = new MediaRecorder(stream)
    mediaRec.ondataavailable = (e) => {
      if (e.data && e.data.size) chunks.push(e.data)
    }
    mediaRec.onstop = () => {
      try {
        audioURL.value = URL.createObjectURL(new Blob(chunks, { type: 'audio/webm' }))
      } catch {
        /* ignore */
      }
    }
    mediaRec.start()
  } catch {
    /* ignore */
  }

  volTimer = setInterval(() => {
    volLevel.value = Math.max(0, Math.min(20, volLevel.value + (Math.random() > 0.5 ? 2 : -2)))
  }, 110)

  try {
    rec = new SR()
    rec.lang = 'en-US'
    rec.interimResults = false
    rec.maxAlternatives = 5
    rec.onresult = (ev) => {
      const target = String(props.question.answer || '').toLowerCase().trim()
      const alts = []
      for (let i = 0; i < ev.results[0].length; i += 1) {
        alts.push(String(ev.results[0][i].transcript || '').toLowerCase().trim())
      }
      const rank = alts.indexOf(target)
      finish(rank === 0 ? 3 : rank >= 1 && rank <= 2 ? 2 : 1, alts[0] || '')
    }
    rec.onerror = () => {
      /* fallback below */
    }
    rec.start()
  } catch {
    unsupported.value = true
  }

  clearTimeout(maxTimer)
  maxTimer = setTimeout(() => {
    if (recording.value) stop()
  }, 60000)
}

function stop() {
  if (!recording.value) return
  recording.value = false
  clearInterval(volTimer)
  clearTimeout(maxTimer)
  volLevel.value = 0
  try {
    if (mediaRec && mediaRec.state !== 'inactive') mediaRec.stop()
  } catch {
    /* ignore */
  }
  try {
    if (rec) rec.stop()
  } catch {
    /* ignore */
  }
  try {
    if (stream) stream.getTracks().forEach((t) => t.stop())
  } catch {
    /* ignore */
  }
  setTimeout(() => {
    if (!judged.value) finish(2, '（本机识别不可用，按 2 星）')
  }, 1500)
}

function finish(s, said) {
  if (judged.value) return
  judged.value = true
  stars.value = s
  emit('submit', { is_correct: s >= 2, transcript: said })
}

function selfPass() {
  if (props.disabled || judged.value) return
  judged.value = true
  stars.value = 2
  emit('submit', { is_correct: true, transcript: '（自评通过）' })
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
  clearInterval(volTimer)
  clearTimeout(maxTimer)
  try {
    if (rec) rec.abort()
  } catch {
    /* ignore */
  }
  try {
    if (stream) stream.getTracks().forEach((t) => t.stop())
  } catch {
    /* ignore */
  }
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
})
</script>

<style scoped>
.mr { display: flex; flex-direction: column; align-items: center; gap: 8px; width: 100%; }
.mr-stars { display: flex; gap: 9px; font-size: 26px; }
.mr-stars span { color: var(--wp2-dim); transition: 0.2s; transform: scale(1); }
.mr-stars span.on { color: var(--wp2-gold); text-shadow: 0 0 14px rgba(255, 205, 76, 0.65); transform: scale(1.15); }
.mr-word { font-size: clamp(34px, 5vw, 52px); font-weight: 900; color: var(--wp2-ink); letter-spacing: 1px; text-shadow: 0 3px 0 rgba(20, 10, 40, 0.7); }
.mr-phon { font-size: 14px; color: var(--wp2-muted); min-height: 18px; }
.mr-mic { width: 88px; height: 88px; border-radius: 50%; cursor: pointer; font-size: 30px; display: grid; place-items: center; background: radial-gradient(circle at 35% 30%, var(--wp2-l2b), var(--wp2-l2)); border: 3px solid var(--wp2-inkline); box-shadow: 0 6px 0 var(--wp2-inkline); transition: 0.15s; }
.mr-mic.rec { background: radial-gradient(circle at 35% 30%, #ff9a8a, #ff5a5a); box-shadow: 0 6px 0 var(--wp2-inkline), 0 0 0 9px rgba(255, 90, 90, 0.16); }
.mr-mic:active:not(:disabled) { transform: scale(0.95); }
.mr-mic.disabled, .mr-mic:disabled { filter: grayscale(0.5) brightness(0.85); cursor: default; }
.mr-vol { display: flex; gap: 3px; align-items: flex-end; height: 24px; }
.mr-vol i { width: 4px; border-radius: 2px; background: rgba(255, 246, 225, 0.18); height: 4px; transition: 0.08s; }
.mr-vol i.on { background: var(--wp2-l2b); }
.mr-state { font-size: 12px; color: var(--wp2-muted); min-height: 17px; }
.mr-arc { display: flex; gap: 5px; flex-wrap: wrap; justify-content: center; max-width: 520px; }
.mr-arc i { width: 10px; height: 10px; border-radius: 50%; background: rgba(255, 246, 225, 0.12); border: 1.5px solid rgba(255, 246, 225, 0.16); transition: 0.25s; }
.mr-arc i.on { background: var(--wp2-gold); border-color: var(--wp2-gold); box-shadow: 0 0 7px rgba(255, 205, 76, 0.65); }
.mr-ops { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
.mr-hint { font-size: 11px; text-align: center; max-width: 600px; line-height: 1.6; }
.mr-hint b { color: var(--wp2-ink); }
</style>
