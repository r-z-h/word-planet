<template>
  <div class="pe">
    <div class="pe-stem">{{ question.stem }}</div>

    <div class="pe-planetwrap" :class="{ golden: shownCombo >= 9 || grown >= 15 }">
      <div class="pe-ring" :style="ringStyle" />
      <div class="pe-sat" :class="{ orbit: shownCombo >= 9 || grown >= 15 }" />
      <div
        ref="planetEl"
        class="pe-planet"
        :style="planetStyle"
        @animationend="onAnimEnd"
      >
        <span class="pe-blush l" :style="{ opacity: grown >= 1 ? 0.85 : 0 }" />
        <span class="pe-blush r" :style="{ opacity: grown >= 1 ? 0.85 : 0 }" />
        <span class="pe-face"><i class="e1" /><i class="e2" /><b /></span>
      </div>
      <div ref="haloEl" class="pe-halo" />
      <div class="pe-fx">
        <span v-for="p in particles" :key="p.id" :style="p.style" />
      </div>
      <div class="pe-floats">
        <span v-for="f in floats" :key="f.id" class="pe-float" :style="f.style">{{ f.text }}</span>
      </div>
    </div>

    <div class="pe-cards">
      <button
        v-for="k in keys"
        :key="k"
        class="pe-card"
        :class="cardClass(k)"
        :disabled="disabled || !!pickedKey"
        @click="pick(k, $event)"
      >
        {{ question.options?.[k] }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { shakeSoft, burst } from '../../utils/fx'
import { sfxPop, sfxHit } from '../../utils/sfx'

const props = defineProps({
  question: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
  grown: { type: Number, default: 0 }, // 本关已答对题数：驱动体型/腮红/光环/卫星
  combo: { type: Number, default: 0 } // 连击：驱动四档「吃」动作
})
const emit = defineEmits(['pick'])

const planetEl = ref(null)
const haloEl = ref(null)
const pickedKey = ref('')
const shownCombo = ref(props.combo)
const animPhase = ref('') // '' | 'tier1' | 'tier2' | 'tier3' | 'tier4'
const particles = ref([])
const floats = ref([])
let fxId = 0

const keys = computed(() => Object.keys(props.question.options || {}).sort())

const planetStyle = computed(() => {
  const t = Math.min(props.grown, 15) / 15
  const size = Math.round(112 + 52 * t)
  const glow = Math.round(30 * t)
  return {
    width: size + 'px',
    height: size + 'px',
    filter: `saturate(${(0.6 + 0.4 * t).toFixed(2)}) brightness(${(0.85 + 0.25 * t).toFixed(2)})`,
    boxShadow: `0 6px 0 var(--wp2-inkline), 0 0 ${glow}px rgba(255,205,76,${(0.7 * t).toFixed(2)}), inset -6px -8px 0 rgba(0,0,0,.15)`
  }
})

const ringStyle = computed(() => {
  const visible = props.grown >= 6 || shownCombo.value >= 6
  const t = Math.min(props.grown, 15) / 15
  const size = Math.round(112 + 52 * t) + 58
  return {
    opacity: visible ? 0.75 : 0,
    width: size + 'px',
    height: size + 'px'
  }
})

function cardClass(k) {
  return { chosen: pickedKey.value === k && !!pickedKey.value }
}

// 点卡片：真·飞向星球（补间位移），点一下有触感
function pick(k, ev) {
  if (props.disabled || pickedKey.value) return
  pickedKey.value = k
  sfxPop()
  flyCard(ev?.currentTarget)
  emit('pick', k)
}

function flyCard(btn) {
  const planet = planetEl.value
  if (!btn || !planet) return
  const b = btn.getBoundingClientRect()
  const p = planet.getBoundingClientRect()
  const dx = p.left + p.width / 2 - (b.left + b.width / 2)
  const dy = p.top + p.height / 2 - (b.top + b.height / 2)
  btn.style.transition = 'transform .42s cubic-bezier(.45,-0.15,.7,1), opacity .42s ease-in'
  btn.style.transform = `translate(${dx}px, ${dy}px) scale(.12) rotate(28deg)`
  btn.style.opacity = '0'
  btn.style.zIndex = '30'
  btn.style.pointerEvents = 'none'
}

function popParticles(count = 16) {
  particles.value = burst(count, { dist: 92 })
  setTimeout(() => {
    particles.value = []
  }, 900)
}

function popFloat(text) {
  const id = ++fxId
  const item = { id, text, style: { animationDelay: '0ms' } }
  floats.value = [...floats.value, item]
  setTimeout(() => {
    floats.value = floats.value.filter((f) => f.id !== id)
  }, 1000)
}

/**
 * 由父组件在“答对之后”调用：播一档「吃」的动作。
 * 连击 1-3 → 档1（张嘴吞卡+腮红）；4-5 → 档2（鼓起弹）；6-8 → 档3（转圈+光环）；9+ → 档4（卫星加速）
 */
function celebrate(combo) {
  shownCombo.value = combo
  // 打击感：命中音 + 粒子 + 震屏 + 飘字
  sfxHit()
  popParticles(16)
  shakeSoft()
  popFloat('+🌸 1')
  if (combo >= 3) popFloat(`连击 ×${combo}`)
  const phase = combo <= 3 ? 'tier1' : combo <= 5 ? 'tier2' : combo <= 8 ? 'tier3' : 'tier4'
  const prog =
    combo <= 3 ? combo / 3 : combo <= 5 ? (combo - 3) / 2 : combo <= 8 ? (combo - 5) / 3 : Math.min(1, (combo - 8) / 7)
  animPhase.value = phase
  const el = planetEl.value
  if (!el) return
  // 档1：嘴张开幅度随进度；档2：鼓起；档3/4：光环+旋转
  el.style.setProperty('--pe-open', String(0.45 + 0.55 * prog))
  el.classList.remove('tier2', 'tier3', 'tier4')
  if (phase === 'tier2') el.classList.add('tier2')
  if (phase === 'tier3') el.classList.add('tier3')
  if (phase === 'tier4') el.classList.add('tier4')
  el.classList.add('eating')
  if (phase === 'tier3' || phase === 'tier4') {
    const halo = haloEl.value
    if (halo) {
      halo.classList.remove('burst')
      void halo.offsetWidth
      halo.classList.add('burst')
    }
  }
}

function onAnimEnd(e) {
  if (e.animationName && e.animationName.indexOf('pe-eat') === 0) {
    const el = planetEl.value
    if (el) el.classList.remove('eating', 'tier2', 'tier3', 'tier4')
  }
}

function reset() {
  pickedKey.value = ''
  const el = planetEl.value
  if (el) el.classList.remove('eating', 'tier2', 'tier3', 'tier4')
}

defineExpose({ celebrate, reset })
</script>

<style scoped>
.pe {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 8px 0 4px;
}
.pe-stem {
  font-size: clamp(18px, 2.2vw, 26px);
  font-weight: 900;
  text-align: center;
  line-height: 1.45;
  max-width: 720px;
  color: var(--wp2-ink);
  text-shadow: 0 2px 0 rgba(20, 10, 40, 0.85);
}
.pe-planetwrap {
  position: relative;
  display: grid;
  place-items: center;
  height: 210px;
  width: 300px;
}
.pe-ring {
  position: absolute;
  border-radius: 50%;
  border: 2px dashed rgba(255, 226, 168, 0.22);
  opacity: 0;
  transition: opacity 0.5s;
  pointer-events: none;
}
.pe-sat {
  position: absolute;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #ffe9a8, #ffcd4c);
  border: 2.5px solid var(--wp2-inkline);
  opacity: 0;
  transition: opacity 0.5s;
  pointer-events: none;
}
.pe-sat.orbit {
  opacity: 1;
  animation: pe-orbit 3.5s linear infinite;
}
@keyframes pe-orbit {
  from { transform: rotate(0) translateX(92px) rotate(0); }
  to { transform: rotate(360deg) translateX(92px) rotate(-360deg); }
}
.pe-planet {
  position: relative;
  border-radius: 50%;
  background: radial-gradient(circle at 33% 27%, var(--wp2-l1b), var(--wp2-l1) 72%);
  border: 3px solid var(--wp2-inkline);
  display: grid;
  place-items: center;
  transition: width 0.55s cubic-bezier(0.2, 1.3, 0.4, 1), height 0.55s cubic-bezier(0.2, 1.3, 0.4, 1),
    filter 0.5s, box-shadow 0.5s;
}
.pe-face {
  position: absolute;
  inset: 0;
}
.pe-face i {
  position: absolute;
  background: var(--wp2-inkline);
  border-radius: 50%;
  transition: transform 0.16s;
}
.pe-face .e1 { left: 31%; top: 33%; width: 12px; height: 16px; }
.pe-face .e2 { right: 31%; top: 33%; width: 12px; height: 16px; }
.pe-face b {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  top: 56%;
  width: 30px;
  height: 16px;
  background: var(--wp2-inkline);
  border-radius: 5px 5px 16px 16px;
  transform-origin: center;
  transition: transform 0.16s;
}
.pe-blush {
  position: absolute;
  top: 54%;
  width: 22px;
  height: 12px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 140, 180, 0.95), rgba(255, 140, 180, 0) 70%);
  transition: opacity 0.3s;
  pointer-events: none;
}
.pe-blush.l { left: 13%; }
.pe-blush.r { right: 13%; }
.pe-halo {
  position: absolute;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  border: 3px solid rgba(255, 205, 76, 0.85);
  opacity: 0;
  pointer-events: none;
}
.pe-halo.burst { animation: pe-halo 0.8s ease-out; }
@keyframes pe-halo {
  0% { transform: scale(0.6); opacity: 0.9; }
  100% { transform: scale(1.8); opacity: 0; }
}

/* 命中粒子 */
.pe-fx { position: absolute; inset: 0; pointer-events: none; z-index: 6; }
.pe-fx span {
  position: absolute; left: 50%; top: 50%; border-radius: 50%;
  animation: pe-part 0.72s ease-out forwards;
}
@keyframes pe-part {
  0% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
  100% { transform: translate(calc(-50% + var(--tx)), calc(-50% + var(--ty))) scale(0.25); opacity: 0; }
}

/* 飘字 */
.pe-floats { position: absolute; inset: 0; pointer-events: none; z-index: 7; }
.pe-float {
  position: absolute; left: 50%; top: 26%;
  transform: translateX(-50%);
  font-weight: 900; font-size: 16px; color: var(--wp2-gold);
  text-shadow: 0 2px 0 var(--wp2-inkline), 0 0 12px rgba(255, 205, 76, 0.6);
  white-space: nowrap;
  animation: pe-floatUp 0.95s cubic-bezier(0.2, 0.8, 0.4, 1) forwards;
}
.pe-float:nth-child(2) { top: 18%; font-size: 19px; color: #6ff0c4; }
@keyframes pe-floatUp {
  0% { opacity: 0; transform: translate(-50%, 10px) scale(0.7); }
  25% { opacity: 1; transform: translate(-50%, -6px) scale(1.1); }
  100% { opacity: 0; transform: translate(-50%, -52px) scale(1); }
}
@media (prefers-reduced-motion: reduce) {
  .pe-fx span, .pe-float { animation: none; }
  .pe-fx span { opacity: 0; }
}

/* 四档「吃」的动作 */
.pe-planet.eating .pe-face b {
  transform: translateX(-50%) scale(1.12, calc(1 + 0.9 * var(--pe-open, 0.7)));
}
.pe-planet.eating { animation: pe-eat 0.42s cubic-bezier(0.3, 1.2, 0.5, 1); }
@keyframes pe-eat {
  0% { transform: scale(1); }
  45% { transform: scale(1.06); }
  100% { transform: scale(1.04); }
}
.pe-planet.tier2 { animation: pe-puff 0.5s cubic-bezier(0.2, 1.6, 0.4, 1); }
@keyframes pe-puff {
  0% { transform: scale(1); }
  40% { transform: scale(1.16, 0.92); }
  70% { transform: scale(0.97, 1.05); }
  100% { transform: scale(1); }
}
.pe-planet.tier3 { animation: pe-twirl 0.7s cubic-bezier(0.4, 0.1, 0.3, 1); }
.pe-planet.tier4 { animation: pe-twirl 0.7s cubic-bezier(0.4, 0.1, 0.3, 1); }
@keyframes pe-twirl { to { transform: rotate(360deg); } }

.pe-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  width: 100%;
  max-width: 740px;
}
.pe-card {
  background: #fffaf0;
  border: 3px solid var(--wp2-inkline);
  border-radius: 14px;
  box-shadow: 0 5px 0 var(--wp2-inkline);
  color: #241338;
  font-family: inherit;
  font-weight: 900;
  font-size: 18px;
  min-height: 72px;
  display: grid;
  place-items: center;
  padding: 6px;
  cursor: pointer;
  text-align: center;
  line-height: 1.2;
  transition: transform 0.12s, box-shadow 0.12s, opacity 0.25s;
}
.pe-card:hover:not(:disabled) { transform: translateY(-3px); }
.pe-card:active:not(:disabled) { transform: translateY(3px); box-shadow: 0 1px 0 var(--wp2-inkline); }
.pe-card.chosen { opacity: 0.45; transform: translateY(6px) scale(0.96); }
.pe-card:disabled { cursor: default; }

@media (max-width: 767px) {
  .pe-cards { grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .pe-card { min-height: 64px; font-size: 16px; }
  .pe-planetwrap { height: 170px; width: 240px; }
}
</style>
