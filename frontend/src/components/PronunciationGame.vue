<template>
  <div>
    <el-alert
      v-if="!supported"
      title="当前浏览器不支持语音识别，换用 Chrome 或 Edge 试试"
      type="warning"
      :closable="false"
      style="margin-bottom: 16px"
    />

    <div style="text-align: center">
      <p class="word">{{ question.stem }}</p>
      <el-button size="large" :disabled="disabled" @click="speak">🔊 听一遍</el-button>
    </div>

    <div style="text-align: center; margin: 20px 0">
      <el-button
        type="primary"
        size="large"
        circle
        style="width: 84px; height: 84px; font-size: 30px"
        :disabled="disabled || !supported"
        :loading="recording"
        @click="startRecord"
      >
        🎤
      </el-button>
      <p class="muted" style="margin-top: 10px">
        {{ recording ? '正在听……请大声读出来' : '点一下麦克风，跟读这个单词' }}
      </p>
    </div>

    <p v-if="transcript" class="muted" style="text-align: center">
      听到的是：<b>{{ transcript }}</b>
    </p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  question: { type: Object, required: true },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['submit'])

const SR = window.SpeechRecognition || window.webkitSpeechRecognition
const supported = computed(() => Boolean(SR))

const recording = ref(false)
const transcript = ref('')
let recognition = null

function speak() {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const utter = new SpeechSynthesisUtterance(props.question.stem)
  utter.lang = 'en-US'
  utter.rate = 0.85
  window.speechSynthesis.speak(utter)
}

function distance(a, b) {
  const m = a.length
  const n = b.length
  const dp = Array.from({ length: m + 1 }, (_, i) => [i, ...Array(n).fill(0)])
  for (let j = 0; j <= n; j += 1) dp[0][j] = j
  for (let i = 1; i <= m; i += 1) {
    for (let j = 1; j <= n; j += 1) {
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,
        dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)
      )
    }
  }
  return dp[m][n]
}

async function startRecord() {
  if (!supported.value || recording.value) return
  try {
    await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch {
    ElMessage.error('没有拿到麦克风权限')
    return
  }

  recognition = new SR()
  recognition.lang = 'en-US'
  recognition.interimResults = false
  recognition.maxAlternatives = 1

  recording.value = true
  transcript.value = ''

  recognition.onresult = (event) => {
    const said = (event.results[0][0].transcript || '').trim()
    transcript.value = said
    const target = String(props.question.answer || '').trim().toLowerCase()
    const got = said.toLowerCase().replace(/[.,!?]/g, '')
    const ok = got === target || distance(got, target) <= 1
    emit('submit', { is_correct: ok, transcript: said })
  }

  recognition.onerror = () => {
    recording.value = false
    ElMessage.warning('没听清，再试一次')
  }

  recognition.onend = () => {
    recording.value = false
  }

  recognition.start()
}

onBeforeUnmount(() => {
  if (recognition) {
    try {
      recognition.abort()
    } catch {
      /* ignore */
    }
  }
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
})
</script>

<style scoped>
.word {
  font-size: 34px;
  font-weight: 700;
  margin: 12px 0 16px;
  letter-spacing: 1px;
}
</style>
