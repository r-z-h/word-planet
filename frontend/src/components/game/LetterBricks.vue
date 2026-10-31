<template>
  <div class="lb">
    <div class="lb-main">
      <div class="lb-stem">{{ question.stem }}</div>

      <div class="lb-slots">
        <button
          v-for="(ch, i) in slots"
          :key="i"
          class="lb-slot filled"
          :class="slotState"
          :disabled="disabled"
          @click="undoTo(i)"
        >
          {{ ch }}
        </button>
        <span class="lb-slot cur" />
      </div>

      <div class="lb-bricks" :class="{ shatter: shattering }">
        <button
          v-for="(t, i) in tiles"
          :key="i"
          class="lb-brick"
          :disabled="disabled"
          @click="pushTile(t, $event)"
        >
          {{ t }}
        </button>
      </div>

      <div class="lb-fx">
        <span v-for="p in particles" :key="p.id" :style="p.style" />
      </div>

      <button class="wp2-btn gold lb-submit" :disabled="disabled || !slots.length" @click="submit">
        ✓ 就这样
      </button>
      <div class="lb-hint wp2-dim">
        点字母砖落格，<b>同一块砖可反复点</b>；点已填的格子退回到那一格。填一个字就能交，自己判断拼对没有。
      </div>
    </div>

    <div class="lb-wall">
      <div class="lb-wall-title">单词墙 {{ wallWords.length }}/15</div>
      <div
        v-for="i in 15"
        :key="i"
        class="lb-wall-cell"
        :class="{ on: wallWords[i - 1] }"
        :style="wallWords[i - 1] ? { background: cellColor(wallWords[i - 1]) } : null"
      >
        {{ wallWords[i - 1] || '' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { shakeSoft, burst } from '../../utils/fx'
import { sfxTick, sfxShard } from '../../utils/sfx'

const props = defineProps({
  question: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
  wallWords: { type: Array, default: () => [] }
})
const emit = defineEmits(['submit'])

const slots = ref([])
const slotState = ref('') // '' | 'ok' | 'bad'
const particles = ref([])
const shattering = ref(false)

const tiles = computed(() => props.question.tiles || [])

function pushTile(ch, ev) {
  if (props.disabled || slotState.value) return
  // 先量当前空槽位置，再落格，再播放「飞入」
  const cur = document.querySelector('.lb-slot.cur')
  const target = cur ? cur.getBoundingClientRect() : null
  slots.value.push(ch)
  sfxTick()
  flyBrick(ev?.currentTarget, ch, target)
}

function flyBrick(btn, ch, target) {
  if (!btn || !target) return
  const b = btn.getBoundingClientRect()
  const ghost = document.createElement('div')
  ghost.textContent = ch
  Object.assign(ghost.style, {
    position: 'fixed',
    left: b.left + 'px',
    top: b.top + 'px',
    width: b.width + 'px',
    height: b.height + 'px',
    display: 'grid',
    placeItems: 'center',
    borderRadius: '10px',
    background: '#fffaf0',
    border: '3px solid #241338',
    color: '#241338',
    fontFamily: 'inherit',
    fontWeight: '900',
    fontSize: '21px',
    zIndex: '9999',
    pointerEvents: 'none',
    transition: 'transform .26s cubic-bezier(.4,0,.6,1), opacity .26s'
  })
  document.body.appendChild(ghost)
  const dx = target.left + target.width / 2 - (b.left + b.width / 2)
  const dy = target.top + target.height / 2 - (b.top + b.height / 2)
  requestAnimationFrame(() => {
    ghost.style.transform = `translate(${dx}px, ${dy}px) scale(.7)`
    ghost.style.opacity = '0.25'
  })
  setTimeout(() => ghost.remove(), 320)
}

function undoTo(i) {
  if (props.disabled || slotState.value) return
  slots.value = slots.value.slice(0, i)
}

function submit() {
  if (props.disabled || !slots.value.length || slotState.value) return
  emit('submit', slots.value.join(''))
}

/** 父组件拿到判定结果后调用 */
function markResult(ok) {
  slotState.value = ok ? 'ok' : 'bad'
  if (ok) {
    // 拼对：碎裂音 + 砖块碎裂 + 粒子 + 震屏（单词墙格子靠 .on 翻转点亮）
    sfxShard()
    particles.value = burst(18, { dist: 96 })
    shattering.value = true
    shakeSoft()
    setTimeout(() => {
      particles.value = []
      shattering.value = false
    }, 900)
  } else {
    shakeSoft()
  }
}

function reset() {
  slots.value = []
  slotState.value = ''
}

function cellColor(word) {
  let h = 0
  for (const c of word) h = (h * 31 + c.charCodeAt(0)) % 360
  return `hsl(${h}, 58%, 62%)`
}

defineExpose({ markResult, reset })
</script>

<style scoped>
.lb {
  display: flex;
  gap: 14px;
  width: 100%;
  max-width: 1040px;
  align-items: stretch;
}
.lb-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  position: relative;
}
.lb-stem {
  font-size: clamp(18px, 2.1vw, 26px);
  font-weight: 900;
  text-align: center;
  line-height: 1.45;
  max-width: 720px;
  color: var(--wp2-ink);
  text-shadow: 0 2px 0 rgba(20, 10, 40, 0.85);
}
.lb-slots {
  display: flex;
  gap: 7px;
  justify-content: center;
  align-items: center;
  min-height: 62px;
  flex-wrap: wrap;
}
.lb-slot {
  width: 46px;
  height: 54px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-family: inherit;
  font-size: 24px;
  font-weight: 900;
  color: var(--wp2-ink);
  background: rgba(255, 246, 225, 0.06);
  border: 2px dashed rgba(255, 232, 180, 0.3);
  cursor: pointer;
}
.lb-slot.filled {
  background: rgba(255, 205, 76, 0.16);
  border: 2px solid rgba(255, 205, 76, 0.75);
}
.lb-slot.cur {
  border-color: rgba(255, 205, 76, 0.65);
  animation: lb-pulse 1.3s ease-in-out infinite;
  cursor: default;
}
.lb-slot.ok {
  background: rgba(18, 184, 134, 0.4);
  border: 2px solid var(--wp2-l2);
}
.lb-slot.bad {
  background: rgba(255, 90, 90, 0.35);
  border: 2px solid var(--wp2-red);
}
@keyframes lb-pulse {
  50% { box-shadow: 0 0 0 3px rgba(255, 205, 76, 0.3); }
}
.lb-bricks {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 640px;
}
.lb-brick {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  background: #fffaf0;
  border: 3px solid var(--wp2-inkline);
  box-shadow: 0 4px 0 var(--wp2-inkline);
  color: #241338;
  font-family: inherit;
  font-weight: 900;
  font-size: 21px;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: transform 0.12s, box-shadow 0.12s;
}
.lb-brick:active:not(:disabled) {
  transform: translateY(3px);
  box-shadow: 0 1px 0 var(--wp2-inkline);
}
.lb-brick:disabled {
  filter: grayscale(0.4) brightness(0.9);
  cursor: default;
}

/* 命中粒子 */
.lb-fx {
  position: absolute;
  left: 0;
  right: 0;
  top: 34%;
  height: 0;
  pointer-events: none;
  z-index: 8;
}
.lb-fx span {
  position: absolute;
  left: 50%;
  top: 0;
  border-radius: 50%;
  animation: lb-part 0.75s ease-out forwards;
}
@keyframes lb-part {
  0% { transform: translate(-50%, 0) scale(1); opacity: 1; }
  100% { transform: translate(calc(-50% + var(--tx)), var(--ty)) scale(0.25); opacity: 0; }
}

/* 拼对：字母砖碎裂 */
.lb-bricks.shatter .lb-brick {
  animation: lb-shard 0.5s ease-in forwards;
}
.lb-bricks.shatter .lb-brick:nth-child(2n) { animation-delay: 0.04s; }
.lb-bricks.shatter .lb-brick:nth-child(3n) { animation-delay: 0.08s; }
@keyframes lb-shard {
  0% { transform: translateY(0) rotate(0); opacity: 1; }
  100% { transform: translateY(-18px) rotate(14deg) scale(0.6); opacity: 0; }
}
.lb-submit {
  min-width: 180px;
}
.lb-hint {
  font-size: 11.5px;
  text-align: center;
  max-width: 640px;
  line-height: 1.6;
}
.lb-hint b {
  color: var(--wp2-ink);
}
.lb-wall {
  flex: none;
  width: 132px;
  padding: 8px;
  border-radius: 12px;
  background: rgba(20, 10, 40, 0.4);
  border: 1.5px solid rgba(255, 232, 180, 0.16);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.lb-wall-title {
  font-size: 10px;
  font-weight: 900;
  color: var(--wp2-dim);
  text-align: center;
  margin-bottom: 2px;
}
.lb-wall-cell {
  flex: 1;
  min-height: 0;
  border-radius: 6px;
  display: grid;
  place-items: center;
  font-size: 10px;
  font-weight: 900;
  color: transparent;
  background: rgba(255, 246, 225, 0.05);
  border: 1.5px dashed rgba(255, 232, 180, 0.16);
  transition: 0.35s;
  transform-style: preserve-3d;
}
.lb-wall-cell.on {
  border: 1.5px solid var(--wp2-inkline);
  color: #241338;
  box-shadow: 0 2px 0 rgba(0, 0, 0, 0.3);
  animation: lb-flip 0.5s cubic-bezier(0.2, 1.4, 0.4, 1) both;
}
@keyframes lb-flip {
  0% { transform: perspective(220px) rotateY(90deg) scale(0.8); }
  60% { transform: perspective(220px) rotateY(-12deg) scale(1.06); }
  100% { transform: perspective(220px) rotateY(0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .lb-fx span, .lb-bricks.shatter .lb-brick, .lb-wall-cell.on { animation: none; }
  .lb-fx span { opacity: 0; }
}

@media (max-width: 767px) {
  .lb { flex-direction: column; }
  .lb-wall {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 3px;
  }
  .lb-wall-title { width: 100%; }
  .lb-wall-cell { flex: 0 0 calc((100% - 12px) / 5); height: 26px; }
  .lb-slot { width: 40px; height: 48px; font-size: 20px; }
  .lb-brick { width: 44px; height: 44px; font-size: 18px; }
}
</style>
