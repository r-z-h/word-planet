<template>
  <!-- Phase A：全站常驻的卡通助手入口（先用占位形象，后续换正式图） -->
  <div v-if="visible" class="help-root">
    <!-- 对话面板 -->
    <transition name="help-pop">
      <section v-if="open" class="help-panel" role="dialog" aria-label="小星助手">
        <header class="help-head">
          <span class="help-title">🪐 小星助手</span>
          <div class="head-actions">
            <button
              class="auto-speak"
              :class="{ on: autoSpeak }"
              :title="autoSpeak ? '关闭自动朗读' : '开启自动朗读'"
              @click="autoSpeak = !autoSpeak"
            >{{ autoSpeak ? '🔊' : '🔈' }}</button>
            <button class="help-close" aria-label="收起" @click="open = false">×</button>
          </div>
        </header>

        <div ref="scroller" class="help-body">
          <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
            <div class="bubble">
              {{ m.text }}
              <div v-if="m.sources && m.sources.length" class="sources">
                <a
                  v-for="s in m.sources"
                  :key="s.path"
                  class="source-link"
                  href="javascript:void(0)"
                  @click="goto(s.path)"
                >↗ {{ s.title }}</a>
              </div>
              <button
                v-if="m.role === 'assistant'"
                class="speak-btn"
                title="朗读这条回答"
                @click="speak(m.text)"
              >🔊</button>
            </div>
            <div v-if="m.suggestions && m.suggestions.length" class="chips">
              <button
                v-for="s in m.suggestions"
                :key="s"
                class="chip"
                :disabled="loading"
                @click="send(s)"
              >{{ s }}</button>
            </div>
          </div>

          <div v-if="loading" class="msg assistant">
            <div class="bubble typing">小星正在想…</div>
          </div>
        </div>

        <form class="help-input" @submit.prevent="send()">
          <button
            type="button"
            class="mic-btn"
            :class="{ recording }"
            :disabled="loading"
            :title="recording ? '结束语音' : '语音提问'"
            @click="toggleVoice"
          >🎤</button>
          <input
            v-model="input"
            type="text"
            maxlength="500"
            :placeholder="recording ? '正在听…（说完会自动结束）' : '问点什么，比如：怎么才能做能力测试？'"
            :disabled="loading"
          />
          <button type="submit" :disabled="loading || !input.trim()">发送</button>
        </form>
      </section>
    </transition>

    <!-- 角落卡通形象（占位） -->
    <button class="help-mascot" aria-label="打开小星助手" @click="toggle">
      <img class="mascot-img" :src="assistantIcon" alt="小星助手" />
    </button>
  </div>
</template>

<script setup>
import { computed, nextTick, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import { useUserStore } from '../stores/user'
import assistantIcon from '../assets/ai_assistant.png'

const user = useUserStore()
const route = useRoute()
const router = useRouter()

const open = ref(false)
const input = ref('')
const loading = ref(false)
const autoSpeak = ref(false)
const speaking = ref(false)
let curAudio = null
const context = ref({})
const scroller = ref(null)
const recording = ref(false)
let ws = null
let actx = null
let micStream = null
let srcNode = null
let node = null
let recog = null
const messages = ref([
  {
    role: 'assistant',
    text: '嗨，我是小星助手～ 关于怎么解锁、怎么兑换、今天任务完成没，都可以问我。',
    suggestions: ['怎么做能力测试？', '徽章怎么解锁？', '花、星、徽记怎么换？']
  }
])

// 只在已登录、且非登录/注册/游客页显示
const visible = computed(
  () => !!user.token && !['/login', '/register', '/guest'].includes(route.path)
)

function toggle() {
  open.value = !open.value
  if (open.value) scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}

function goto(path) {
  if (path) router.push(path)
  open.value = false
}

async function send(text) {
  const q = (text ?? input.value).trim()
  if (!q || loading.value) return
  messages.value.push({ role: 'user', text: q })
  input.value = ''
  loading.value = true
  scrollToBottom()
  try {
    const { data } = await http.post('/help/ask', { question: q, context: context.value })
    context.value = data.context || {}
    messages.value.push({
      role: 'assistant',
      text: data.answer,
      sources: data.sources || [],
      suggestions: data.suggestions || []
    })
    if (autoSpeak.value) speak(data.answer)
  } catch (e) {
    messages.value.push({ role: 'assistant', text: '抱歉，我这边出错了：' + apiError(e) })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}
function asrUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/api/help/asr/stream?token=${encodeURIComponent(user.token || '')}`
}

let awaitingFinal = false
let finalTimer = null

function teardownAudio() {
  try {
    if (node) node.disconnect()
    if (srcNode) srcNode.disconnect()
    if (actx) actx.close()
  } catch {}
  node = null
  srcNode = null
  actx = null
  try {
    if (micStream) micStream.getTracks().forEach((t) => t.stop())
  } catch {}
  micStream = null
}

function closeWs() {
  try {
    if (ws) ws.close()
  } catch {}
  ws = null
}

function stopVoice() {
  recording.value = false
  awaitingFinal = false
  clearTimeout(finalTimer)
  try {
    if (ws && ws.readyState === 1) ws.send('END')
  } catch {}
  closeWs()
  teardownAudio()
  try {
    if (recog) recog.stop()
  } catch {}
  recog = null
}

// 手动结束：停止采音、请求服务器转写、等 final（第二次点话筒触发）
function finishVoice() {
  if (!recording.value) return
  recording.value = false
  awaitingFinal = true
  clearTimeout(finalTimer)
  teardownAudio()
  try {
    if (ws && ws.readyState === 1) ws.send('END')
  } catch {}
  finalTimer = setTimeout(() => {
    if (awaitingFinal) {
      awaitingFinal = false
      closeWs()
      if (!input.value.trim()) ElMessage.warning('没听清，请再说一次或直接打字')
    }
  }, 6000)
}

function toggleVoice() {
  if (recording.value) finishVoice()
  else startVoice()
}

async function startVoice() {
  if (loading.value || recording.value || awaitingFinal) return
  if (!navigator.mediaDevices?.getUserMedia) {
    fallbackSR()
    return
  }
  // 在点击的同步任务里先建 AudioContext（早于任何 await），否则 Edge 会一直 suspended
  try {
    if (!window.AudioWorkletNode) throw new Error('no AudioWorklet')
    const Ctx = window.AudioContext || window.webkitAudioContext
    actx = new Ctx()
    try {
      actx.resume()
    } catch {}
  } catch {
    fallbackSR()
    return
  }
  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { noiseSuppression: true, echoCancellation: true, autoGainControl: true }
    })
  } catch (e) {
    const n = e && e.name
    if (n === 'NotAllowedError' || n === 'PermissionDeniedError') {
      ElMessage.error('麦克风被拒绝：请在地址栏允许麦克风权限后重试')
    } else if (n === 'NotFoundError' || n === 'DevicesNotFoundError') {
      ElMessage.error('未检测到麦克风')
    } else {
      ElMessage.error('麦克风不可用：' + (n || '未知'))
    }
    return
  }
  recording.value = true
  try {
    try {
      if (actx.state === 'suspended') await actx.resume()
    } catch {}
    await actx.audioWorklet.addModule('/pcm-worklet.js')
    srcNode = actx.createMediaStreamSource(micStream)
    node = new AudioWorkletNode(actx, 'pcm16', { processorOptions: { minRms: 0 } })
    const hp = actx.createBiquadFilter()
    hp.type = 'highpass'
    hp.frequency.value = 110
    hp.Q.value = 0.7
    srcNode.connect(hp)
    hp.connect(node)
    const mute = actx.createGain()
    mute.gain.value = 0
    node.connect(mute)
    mute.connect(actx.destination)

    ws = new WebSocket(asrUrl())
    ws.binaryType = 'arraybuffer'
    ws.onmessage = (ev) => {
      let d
      try {
        d = JSON.parse(ev.data)
      } catch {
        return
      }
      if (d.type === 'interim' && d.text) input.value = d.text
      if (d.type === 'final') {
        awaitingFinal = false
        clearTimeout(finalTimer)
        recording.value = false
        teardownAudio()
        closeWs()
        if (d.text) input.value = d.text
        else if (!input.value.trim()) ElMessage.warning('没听清，请再说一次或直接打字')
      }
      if (d.type === 'error') {
        stopVoice()
        if (!fallbackSR()) ElMessage.warning('语音识别不可用，请改用打字')
      }
    }
    ws.onerror = () => {
      if (!recording.value && !awaitingFinal) return
      stopVoice()
      if (!fallbackSR()) ElMessage.warning('语音识别不可用，请改用打字')
    }
    ws.onclose = () => {
      if (awaitingFinal) {
        awaitingFinal = false
        clearTimeout(finalTimer)
        if (!input.value.trim()) ElMessage.warning('没听清，请再说一次或直接打字')
      }
    }
    node.port.onmessage = (ev) => {
      if (ws && ws.readyState === 1) ws.send(ev.data)
    }
  } catch {
    stopVoice()
    if (!fallbackSR()) ElMessage.warning('当前浏览器不支持语音输入，请打字')
  }
}

function fallbackSR() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) return false
  try {
    recog = new SR()
    recog.lang = 'zh-CN'
    recog.interimResults = true
    recog.continuous = false
    recording.value = true
    recog.onresult = (e) => {
      let t = ''
      for (const r of e.results) t += r[0].transcript
      input.value = t
    }
    recog.onerror = () => {
      recording.value = false
      recog = null
    }
    recog.onend = () => {
      recording.value = false
      recog = null
    }
    recog.start()
    return true
  } catch {
    recording.value = false
    return false
  }
}

function pickZhVoice() {
  const synth = window.speechSynthesis
  if (!synth) return null
  const vs = synth.getVoices() || []
  return (
    vs.find((v) => /^zh/i.test(v.lang) && v.localService) ||
    vs.find((v) => /^zh/i.test(v.lang)) ||
    null
  )
}

async function speak(text) {
  const clean = String(text || '').replace(/\[[0-9]+\]/g, '').trim()
  if (!clean) return
  // 再点一次 = 停止当前朗读
  if (curAudio && speaking.value) {
    try {
      curAudio.pause()
    } catch {}
    curAudio = null
    speaking.value = false
    return
  }
  try {
    if (curAudio) {
      try {
        curAudio.pause()
      } catch {}
      curAudio = null
    }
    const token = user.token || ''
    const resp = await fetch('/api/help/tts', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: 'Bearer ' + token } : {})
      },
      body: JSON.stringify({ text: clean })
    })
    if (!resp.ok) throw new Error('tts ' + resp.status)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    curAudio = new Audio(url)
    speaking.value = true
    curAudio.onended = () => {
      speaking.value = false
      curAudio = null
      URL.revokeObjectURL(url)
    }
    curAudio.onerror = () => {
      speaking.value = false
      curAudio = null
    }
    await curAudio.play()
  } catch (e) {
    // 兜底：系统语音
    try {
      if (!('speechSynthesis' in window)) {
        ElMessage.warning('语音朗读不可用')
        return
      }
      const synth = window.speechSynthesis
      const u = new SpeechSynthesisUtterance(clean)
      u.lang = 'zh-CN'
      u.rate = 1.0
      const v = pickZhVoice()
      if (v) u.voice = v
      u.onend = () => {
        speaking.value = false
      }
      u.onerror = () => {
        speaking.value = false
      }
      speaking.value = true
      synth.cancel()
      synth.speak(u)
    } catch {}
  }
}

onUnmounted(() => {
  try {
    stopVoice()
  } catch {}
  try {
    if (curAudio) curAudio.pause()
  } catch {}
  try {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
  } catch {}
})
</script>

<style scoped>
.help-root {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 9998;
  font-size: 14px;
}
.help-mascot {
  position: relative;
  width: 88px;
  height: 88px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  background: transparent;
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.45);
  animation: wpGlow 4.5s ease-in-out infinite;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  transition: transform 0.15s ease;
}
.mascot-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
  display: block;
  animation: wpFloat 4.5s ease-in-out infinite;
}
.help-mascot:active { transform: scale(0.96); }

@keyframes wpFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2px); }
}
@keyframes wpGlow {
  0%, 100% { box-shadow: 0 8px 22px rgba(0, 0, 0, 0.42), 0 0 0 0 rgba(255, 170, 60, 0.28); }
  50% { box-shadow: 0 9px 24px rgba(0, 0, 0, 0.45), 0 0 0 8px rgba(255, 170, 60, 0); }
}
.reduce-motion .help-mascot,
.reduce-motion .mascot-img { animation: none !important; }
@media (prefers-reduced-motion: reduce) {
  .help-mascot, .mascot-img { animation: none !important; }
}
.help-mascot:hover {
  transform: translateY(-2px) scale(1.04);
}
.mascot-emoji {
  font-size: 30px;
  line-height: 1;
}
.mascot-bubble {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #ff4d6d;
  color: #fff;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: bob 1.6s ease-in-out infinite;
}
@keyframes bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}

.help-panel {
  position: absolute;
  right: 0;
  bottom: 100px;
  width: min(360px, 92vw);
  height: min(560px, 70vh);
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 16px 48px rgba(20, 20, 50, 0.25);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.help-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: linear-gradient(135deg, #6c5ce7, #a29bfe);
  color: #fff;
  font-weight: 700;
}
.help-close {
  background: transparent;
  border: none;
  color: #fff;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}
.help-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  background: #f7f7fb;
}
.msg {
  display: flex;
  flex-direction: column;
  margin-bottom: 12px;
}
.msg.user {
  align-items: flex-end;
}
.msg.assistant {
  align-items: flex-start;
}
.bubble {
  max-width: 84%;
  padding: 9px 12px;
  border-radius: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg.assistant .bubble {
  background: #fff;
  color: #23233b;
  border: 1px solid #ececff;
}
.msg.user .bubble {
  background: #6c5ce7;
  color: #fff;
}
.bubble.typing {
  color: #888;
  font-style: italic;
}
.sources {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.source-link {
  font-size: 12px;
  color: #6c5ce7;
  text-decoration: underline;
}
.chips {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  border: 1px solid #c9c4ff;
  background: #f2f0ff;
  color: #5b4bd6;
  border-radius: 999px;
  padding: 5px 11px;
  font-size: 12px;
  cursor: pointer;
}
.chip:disabled {
  opacity: 0.5;
  cursor: default;
}
.help-input {
  display: flex;
  gap: 8px;
  padding: 10px;
  border-top: 1px solid #eee;
  background: #fff;
}
.help-input input {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 10px;
  padding: 9px 12px;
  outline: none;
  font-size: 14px;
}
.help-input input:focus {
  border-color: #a29bfe;
}
.help-input button {
  border: none;
  background: #6c5ce7;
  color: #fff;
  border-radius: 10px;
  padding: 0 16px;
  font-weight: 600;
  cursor: pointer;
}
.help-input button:disabled {
  background: #c7c3ee;
  cursor: default;
}
.help-pop-enter-active,
.help-pop-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
  transform-origin: bottom right;
}
.help-pop-enter-from,
.help-pop-leave-to {
  opacity: 0;
  transform: scale(0.94) translateY(8px);
}
.help-input .mic-btn {
  border: 1px solid #ddd;
  background: #fff;
  color: #444;
  border-radius: 10px;
  width: 40px;
  padding: 0;
  font-size: 17px;
  cursor: pointer;
}
.help-input .mic-btn.recording {
  background: #ffe6e6;
  border-color: #ff6b6b;
  color: #e11;
}
.help-input .mic-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.head-actions { display: flex; align-items: center; gap: 6px; }
.auto-speak {
  background: rgba(255, 255, 255, 0.18);
  border: none;
  color: #fff;
  border-radius: 8px;
  padding: 2px 8px;
  cursor: pointer;
  font-size: 14px;
}
.auto-speak.on { background: #ffd76e; color: #5a3a00; }
.speak-btn {
  display: inline-block;
  margin-top: 6px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px;
  opacity: 0.7;
}
.speak-btn:hover { opacity: 1; }
</style>
