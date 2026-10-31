<template>
  <div class="pc">
    <div class="pc-stem">哪个词在句子里出现了？</div>

    <div class="pc-speaker">
      <button class="pc-disc" :class="{ playing }" :disabled="disabled" @click="play">
        <span class="pc-hole" />
      </button>
      <div class="pc-speaker-info">
        <button class="wp2-btn" :disabled="plays >= 2" @click="play">🔊 再听一次</button>
        <div class="pc-state wp2-dim">{{ stateText }}</div>
      </div>
    </div>

    <div v-if="!speechSupported" class="pc-fallback">
      {{ blankedSentence }}
    </div>

    <div class="pc-pipes">
      <button
        v-for="(k, i) in keys"
        :key="k"
        class="pc-pipe"
        :class="{ ok: resultMap[k] === 'ok', bad: resultMap[k] === 'bad' }"
        :style="{ width: pipeWidth + 'px' }"
        :disabled="disabled || resultMap[k] === 'ok'"
        @click="pick(k)"
      >
        <span class="pc-lbl">{{ i + 1 }}</span>
        <span class="pc-light"><i /><i /><i /></span>
        <span class="pc-track">
          <span class="pc-word" :style="{ animationDelay: -i * 1.25 + 's' }">
            {{ question.options?.[k] }}
          </span>
        </span>
        <span class="pc-box">{{ resultMap[k] === 'ok' ? '▣' : '▢' }}</span>
        <span class="pc-smoke">💨</span>
        <span class="pc-confetti"><i v-for="n in 14" :key="n" :style="confettiStyle(n)" /></span>
        <span class="pc-cheer">太棒了！</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { speak } from '../../utils/speech'

const props = defineProps({
  question: { type: Object, required: true },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['pick'])

const keys = computed(() => Object.keys(props.question.options || {}).sort())
const speechSupported = computed(() => 'speechSynthesis' in window)

const plays = ref(0)
const playing = ref(false)
const resultMap = ref({})
const maxPlays = 2
let playTimer = null

const stateText = computed(() => {
  if (!speechSupported.value) return '这台设备不能朗读，读下面的句子选词'
  if (plays.value === 0) return '共 2 次机会'
  if (plays.value >= maxPlays) return '听完了，点对的那条管道'
  return `还能听 ${maxPlays - plays.value} 次`
})

// 等宽的管道：按 4 个词里最长的算
const pipeWidth = computed(() => {
  const words = keys.value.map((k) => String(props.question.options?.[k] || ''))
  const maxLen = Math.max(...words.map((w) => w.length), 1)
  return Math.max(96, Math.min(190, maxLen * 13 + 34))
})

// 不支持朗读时的降级：把选项词挖成 ____
const blankedSentence = computed(() => {
  let s = String(props.question.stem || '')
  keys.value.forEach((k) => {
    const w = String(props.question.options?.[k] || '')
    if (!w) return
    const re = new RegExp(`\\b${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi')
    s = s.replace(re, '____')
  })
  return s
})

function play() {
  if (plays.value >= maxPlays) return
  plays.value += 1
  if (!speechSupported.value) return
  playing.value = true
  speak(props.question.stem, { rate: 0.85 })
  clearTimeout(playTimer)
  playTimer = setTimeout(() => {
    playing.value = false
  }, 1800)
}

function pick(k) {
  if (props.disabled || resultMap.value[k] === 'ok') return
  emit('pick', k)
}

/** 父组件判定后调用 */
function markResult(correctKey, ok) {
  if (ok) {
    resultMap.value = { ...resultMap.value, [correctKey]: 'ok' }
  } else {
    resultMap.value = { ...resultMap.value, [correctKey]: 'bad' }
    setTimeout(() => {
      const m = { ...resultMap.value }
      delete m[correctKey]
      resultMap.value = m
    }, 1000)
  }
}

/** 三次错完后，揭晓正确的那条管道（按选项文本匹配） */
function revealAnswer(text) {
  const t = String(text || '').trim().toLowerCase()
  if (!t) return
  const key = keys.value.find(
    (k) => String(props.question.options?.[k] || '').trim().toLowerCase() === t
  )
  if (key) resultMap.value = { ...resultMap.value, [key]: 'ok' }
}

function confettiStyle(n) {
  const colors = ['#ffcd4c', '#ff785a', '#6ff0c4', '#9fb6ff', '#ffd6e6']
  return {
    left: `${(n * 7.3) % 100}%`,
    background: colors[n % colors.length],
    animationDelay: `${(n % 5) * 0.05}s`,
    '--dx': `${((n * 37) % 80) - 40}px`
  }
}

onMounted(() => {
  // 进题自动播一次（不占重听次数）
  if (speechSupported.value) {
    setTimeout(() => {
      if (plays.value === 0) {
        playing.value = true
        speak(props.question.stem, { rate: 0.85 })
        playTimer = setTimeout(() => {
          playing.value = false
        }, 1800)
      }
    }, 400)
  }
})

onBeforeUnmount(() => {
  clearTimeout(playTimer)
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
})

defineExpose({ markResult, revealAnswer })
</script>

<style scoped>
.pc {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: 100%;
}
.pc-stem {
  font-size: clamp(18px, 2.1vw, 24px);
  font-weight: 900;
  color: var(--wp2-ink);
  text-shadow: 0 2px 0 rgba(20, 10, 40, 0.85);
}
.pc-speaker { display: flex; align-items: center; gap: 12px; }
.pc-disc {
  width: 84px; height: 84px; border-radius: 50%; cursor: pointer;
  background: repeating-radial-gradient(circle at 50% 50%, #2a1d4a 0 5px, #241338 5px 10px);
  border: 3px solid var(--wp2-inkline);
  box-shadow: 0 5px 0 var(--wp2-inkline);
  display: grid; place-items: center; padding: 0;
}
.pc-disc.playing { animation: pc-spin 1.6s linear infinite; }
@keyframes pc-spin { to { transform: rotate(360deg); } }
.pc-hole {
  width: 20px; height: 20px; border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #ffe9a8, #ffcd4c);
  border: 2px solid var(--wp2-inkline);
}
.pc-speaker-info { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
.pc-state { font-size: 12px; }
.pc-fallback {
  max-width: 640px; text-align: center; font-size: 18px; font-weight: 800;
  color: var(--wp2-ink); background: rgba(255, 246, 225, 0.06);
  border: 1.5px dashed rgba(255, 232, 180, 0.3); border-radius: 12px; padding: 10px 14px;
}
.pc-pipes { display: flex; gap: 14px; justify-content: center; align-items: flex-end; }
.pc-pipe {
  position: relative; height: 270px; border-radius: 14px; padding: 0; cursor: pointer;
  background: linear-gradient(180deg, rgba(20, 10, 40, 0.72), rgba(30, 18, 58, 0.5));
  border: 3px solid rgba(255, 232, 180, 0.22);
  box-shadow: inset 0 0 22px rgba(0, 0, 0, 0.55);
  overflow: hidden; flex: none; font-family: inherit;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.pc-pipe:hover:not(:disabled) { border-color: rgba(255, 205, 76, 0.55); }
.pc-lbl {
  position: absolute; top: 5px; left: 50%; transform: translateX(-50%);
  font-size: 9px; font-weight: 900; color: var(--wp2-dim); z-index: 3;
}
.pc-track { position: absolute; inset: 0; }
.pc-word {
  position: absolute; left: 50%; top: 8%; transform: translateX(-50%);
  padding: 9px 14px; border-radius: 9px; background: #fffaf0;
  border: 2.5px solid var(--wp2-inkline); box-shadow: 0 3px 0 var(--wp2-inkline);
  color: #241338; font-weight: 900; font-size: 17px; white-space: nowrap;
  z-index: 2; animation: pc-drop 5s linear infinite;
}
@keyframes pc-drop { 0% { top: -14%; } 100% { top: 104%; } }
.pc-box {
  position: absolute; left: 50%; bottom: 6px; transform: translateX(-50%);
  width: 34px; height: 26px; border-radius: 6px; background: rgba(255, 246, 225, 0.07);
  border: 2px solid rgba(255, 232, 180, 0.2); display: grid; place-items: center;
  font-size: 13px; color: var(--wp2-dim); z-index: 3;
}
.pc-light { position: absolute; inset: 0; display: flex; flex-direction: column-reverse; gap: 2px; padding: 4px; opacity: 0; z-index: 1; }
.pc-light i { flex: 1; border-radius: 6px; background: linear-gradient(180deg, rgba(255, 205, 76, 0.85), rgba(255, 205, 76, 0.3)); transform: scaleY(0); transform-origin: bottom; }
.pc-smoke { position: absolute; left: 50%; top: 32%; transform: translateX(-50%); font-size: 32px; opacity: 0; z-index: 4; pointer-events: none; }
.pc-confetti { position: absolute; inset: 0; overflow: hidden; opacity: 0; pointer-events: none; z-index: 5; }
.pc-confetti i { position: absolute; top: -10px; width: 7px; height: 12px; border-radius: 1px; opacity: 0; }
.pc-cheer {
  position: absolute; left: 50%; top: 44%; transform: translate(-50%, -50%) scale(0.4);
  z-index: 6; font-size: 24px; font-weight: 900; color: var(--wp2-gold);
  text-shadow: 0 2px 0 var(--wp2-inkline), 0 0 20px rgba(255, 205, 76, 0.9);
  opacity: 0; white-space: nowrap; pointer-events: none;
}

/* 答对：管道自下而上全亮 + 彩带 + 喝彩 */
.pc-pipe.ok {
  border-color: var(--wp2-gold);
  box-shadow: inset 0 0 26px rgba(255, 205, 76, 0.35), 0 0 40px rgba(255, 205, 76, 0.9);
  animation: pc-gold 0.85s ease-out;
}
@keyframes pc-gold { 0% { transform: scale(1); } 35% { transform: scale(1.06); } 100% { transform: scale(1); } }
.pc-pipe.ok .pc-word {
  background: #fff1b8; border-color: var(--wp2-gold); color: #3a2109;
  box-shadow: 0 0 26px rgba(255, 205, 76, 0.95); top: 34% !important;
  animation: pc-lock 0.85s cubic-bezier(0.2, 1.5, 0.4, 1) forwards;
}
@keyframes pc-lock { 0% { transform: translateX(-50%) scale(1); } 50% { transform: translateX(-50%) scale(1.3); } 100% { transform: translateX(-50%) scale(1.12); } }
.pc-pipe.ok .pc-box { background: var(--wp2-gold); border-color: var(--wp2-gold); color: #3a2109; }
.pc-pipe.ok .pc-light { opacity: 1; }
.pc-pipe.ok .pc-light i:nth-child(1) { animation: pc-lt 0.28s 0s forwards; }
.pc-pipe.ok .pc-light i:nth-child(2) { animation: pc-lt 0.28s 0.14s forwards; }
.pc-pipe.ok .pc-light i:nth-child(3) { animation: pc-lt 0.28s 0.28s forwards; }
@keyframes pc-lt { to { transform: scaleY(1); } }
.pc-pipe.ok .pc-confetti { opacity: 1; }
.pc-pipe.ok .pc-confetti i { animation: pc-fall 1.1s ease-in forwards; }
@keyframes pc-fall {
  0% { top: -10%; opacity: 1; transform: translateX(0) rotate(0); }
  100% { top: 110%; opacity: 0; transform: translateX(var(--dx, 0)) rotate(540deg); }
}
.pc-pipe.ok .pc-cheer { animation: pc-cheer 0.9s 0.1s both; }
@keyframes pc-cheer {
  0% { opacity: 0; transform: translate(-50%, -50%) scale(0.4); }
  40% { opacity: 1; transform: translate(-50%, -50%) scale(1.25); }
  70% { transform: translate(-50%, -50%) scale(1); }
  100% { opacity: 0; transform: translate(-50%, -130%) scale(1); }
}

/* 答错：剧烈抖动 + 冒烟（红警交给父级全屏） */
.pc-pipe.bad {
  border-color: var(--wp2-red);
  box-shadow: inset 0 0 26px rgba(255, 90, 90, 0.5), 0 0 30px rgba(255, 90, 90, 0.7);
  animation: pc-shake 0.55s ease-in-out;
}
@keyframes pc-shake {
  0%, 100% { transform: translateX(0); }
  15% { transform: translateX(-12px); } 30% { transform: translateX(12px); }
  45% { transform: translateX(-9px); } 60% { transform: translateX(9px); }
  75% { transform: translateX(-5px); }
}
.pc-pipe.bad .pc-word { background: #ffd9d9; border-color: var(--wp2-red); animation: pc-wshake 0.55s ease-in-out; }
@keyframes pc-wshake {
  0%, 100% { transform: translateX(-50%) rotate(0); }
  25% { transform: translateX(-50%) rotate(-9deg); }
  75% { transform: translateX(-50%) rotate(9deg); }
}
.pc-pipe.bad .pc-smoke { opacity: 1; animation: pc-smoke 1.1s ease-out; }
@keyframes pc-smoke {
  0% { transform: translate(-50%, 0) scale(0.6); opacity: 0.95; }
  100% { transform: translate(-50%, -90px) scale(1.9); opacity: 0; }
}

@media (max-width: 767px) {
  .pc-pipes { gap: 8px; }
  .pc-pipe { height: 210px; }
  .pc-word { font-size: 14px; padding: 7px 10px; }
}
</style>
