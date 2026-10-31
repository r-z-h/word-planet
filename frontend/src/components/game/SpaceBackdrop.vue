<template>
  <div ref="rootEl" class="sb" aria-hidden="true">
    <!-- 星云底 -->
    <span class="neb n1" />
    <span class="neb n2" />
    <span class="neb n3" />
    <span class="neb n4" />

    <!-- 星点：全屏铺满 -->
    <span v-for="s in stars" :key="'s' + s.id" class="st" :style="s.style" />

    <!-- 多中心环绕：左右 + 中上/中下，保证宽屏两边不空 -->
    <span
      v-for="o in orbits"
      :key="'o' + o.id"
      class="orbit"
      :class="{ rev: o.rev }"
      :style="{
        left: o.ax + '%',
        top: o.ay + '%',
        width: o.w + 'vmax',
        height: o.w + 'vmax',
        marginLeft: -(o.w / 2) + 'vmax',
        marginTop: -(o.w / 2) + 'vmax',
        animationDuration: o.dur + 's',
        animationDelay: -(o.delay || 0) + 's'
      }"
    >
      <span
        class="obj"
        :class="{ dot: o.dot }"
        :data-base="o.op"
        :style="{ fontSize: o.size + 'px', animationDuration: o.dur + 's', animationDelay: -(o.delay || 0) + 's' }"
      >
        {{ o.icon }}
      </span>
    </span>

    <!-- 横向漂移：贯穿整屏，填满左右 -->
    <span
      v-for="d in drifters"
      :key="'d' + d.id"
      class="drift"
      :class="{ rev: d.rev, dot: d.dot }"
      :data-base="d.op"
      :style="{
        top: d.y + '%',
        fontSize: d.size + 'px',
        animationDuration: d.dur + 's',
        animationDelay: -(d.delay || 0) + 's'
      }"
    >
      {{ d.icon }}
    </span>

    <!-- 流星 -->
    <span class="shoot s1" />
    <span class="shoot s2" />
    <span class="shoot s3" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const rootEl = ref(null)
let raf = null
let reduce = false

const stars = Array.from({ length: 110 }, (_, i) => ({
  id: i,
  style: {
    left: (Math.random() * 100).toFixed(2) + '%',
    top: (Math.random() * 100).toFixed(2) + '%',
    width: (Math.random() * 1.7 + 0.7).toFixed(2) + 'px',
    height: (Math.random() * 1.7 + 0.7).toFixed(2) + 'px',
    animationDelay: (Math.random() * 7).toFixed(2) + 's',
    animationDuration: (3 + Math.random() * 4).toFixed(2) + 's'
  }
}))

// 环绕物：锚点分散在左/中/右、上/下，避免宽屏两边空
const orbits = [
  { id: 1, icon: '🚀', ax: 12, ay: 22, w: 40, dur: 32, size: 32, rev: false, op: 0.8, delay: 3 },
  { id: 2, icon: '🛰️', ax: 13, ay: 76, w: 32, dur: 24, size: 24, rev: true, op: 0.75, delay: 8 },
  { id: 3, icon: '🪐', ax: 50, ay: 13, w: 36, dur: 44, size: 32, rev: false, op: 0.6, delay: 5 },
  { id: 4, icon: '✈️', ax: 51, ay: 88, w: 44, dur: 56, size: 28, rev: true, op: 0.6, delay: 12 },
  { id: 5, icon: '🌍', ax: 88, ay: 24, w: 38, dur: 48, size: 26, rev: false, op: 0.62, delay: 2 },
  { id: 6, icon: '☄️', ax: 87, ay: 78, w: 30, dur: 38, size: 22, rev: true, op: 0.7, delay: 14 },
  { id: 7, icon: '•', ax: 26, ay: 48, w: 26, dur: 28, size: 18, rev: false, op: 0.6, dot: true, delay: 6 },
  { id: 8, icon: '•', ax: 74, ay: 52, w: 28, dur: 34, size: 16, rev: true, op: 0.55, dot: true, delay: 10 },
  { id: 9, icon: '•', ax: 50, ay: 50, w: 60, dur: 80, size: 14, rev: false, op: 0.35, dot: true, delay: 18 }
]

// 横向漂移物：从左到右 / 从右到左穿过整屏
const drifters = [
  { id: 1, icon: '🚀', y: 12, dur: 78, size: 24, op: 0.7, rev: false, delay: 5 },
  { id: 2, icon: '✈️', y: 34, dur: 108, size: 20, op: 0.55, rev: true, delay: 20 },
  { id: 3, icon: '🛰️', y: 62, dur: 96, size: 18, op: 0.6, rev: false, delay: 40 },
  { id: 4, icon: '☄️', y: 88, dur: 120, size: 18, op: 0.55, rev: true, delay: 12 },
  { id: 5, icon: '•', y: 20, dur: 66, size: 14, op: 0.5, rev: true, dot: true, delay: 30 },
  { id: 6, icon: '•', y: 72, dur: 84, size: 12, op: 0.45, rev: false, dot: true, delay: 8 },
  { id: 7, icon: '🌍', y: 6, dur: 140, size: 16, op: 0.4, rev: true, delay: 50 }
]

function tick() {
  const vw = window.innerWidth
  const vh = window.innerHeight
  // 中央题目安全区（进入这里才压淡）
  const L = vw * 0.24
  const R = vw * 0.76
  const T = vh * 0.17
  const B = vh * 0.83
  const root = rootEl.value
  if (root) {
    root.querySelectorAll('[data-base]').forEach((el) => {
      const base = Number(el.dataset.base) || 0.6
      const r = el.getBoundingClientRect()
      const cx = r.left + r.width / 2
      const cy = r.top + r.height / 2
      const inside = cx > L && cx < R && cy > T && cy < B
      el.style.opacity = String(base * (inside ? 0.2 : 1))
    })
  }
  raf = requestAnimationFrame(tick)
}

onMounted(() => {
  reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce) {
    const root = rootEl.value
    if (root) {
      root.querySelectorAll('[data-base]').forEach((el) => {
        el.style.opacity = String((Number(el.dataset.base) || 0.6) * 0.45)
      })
    }
    return
  }
  raf = requestAnimationFrame(tick)
})

onBeforeUnmount(() => {
  if (raf) cancelAnimationFrame(raf)
})
</script>

<style scoped>
.sb {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

/* 星云：四角分布，铺满整屏 */
.neb { position: absolute; border-radius: 50%; filter: blur(48px); opacity: 0.5; animation: sb-drift 26s ease-in-out infinite alternate; }
.neb.n1 { width: 44vw; height: 44vw; left: -12vw; top: -14vw; background: radial-gradient(circle, rgba(132, 94, 247, 0.5), transparent 68%); }
.neb.n2 { width: 40vw; height: 40vw; right: -14vw; top: 4vh; background: radial-gradient(circle, rgba(76, 110, 245, 0.42), transparent 68%); animation-duration: 34s; animation-delay: -8s; }
.neb.n3 { width: 50vw; height: 34vw; left: 6vw; bottom: -18vw; background: radial-gradient(circle, rgba(18, 184, 134, 0.22), transparent 70%); animation-duration: 40s; animation-delay: -14s; }
.neb.n4 { width: 38vw; height: 30vw; right: -6vw; bottom: -14vw; background: radial-gradient(circle, rgba(255, 120, 160, 0.16), transparent 70%); animation-duration: 46s; animation-delay: -20s; }
@keyframes sb-drift {
  from { transform: translate3d(0, 0, 0) scale(1); }
  to { transform: translate3d(2.4vw, 1.6vh, 0) scale(1.08); }
}

.st {
  position: absolute; background: #fff; border-radius: 50%;
  animation-name: sb-twinkle; animation-iteration-count: infinite; animation-timing-function: ease-in-out;
}
@keyframes sb-twinkle {
  0%, 100% { opacity: 0.12; transform: scale(0.9); }
  50% { opacity: 0.8; transform: scale(1.15); }
}

/* 环绕轨道 */
.orbit {
  position: absolute; border-radius: 50%;
  animation-name: sb-orbit; animation-timing-function: linear; animation-iteration-count: infinite;
  will-change: transform;
}
.orbit.rev { animation-direction: reverse; }
@keyframes sb-orbit { to { transform: rotate(360deg); } }

.obj {
  position: absolute; left: 50%; top: 0; transform: translate(-50%, -50%); line-height: 1;
  animation-name: sb-counter; animation-timing-function: linear; animation-iteration-count: infinite;
  filter: drop-shadow(0 0 8px rgba(159, 182, 255, 0.35));
  transition: opacity 0.5s linear;
  will-change: transform, opacity;
}
.orbit.rev .obj { animation-direction: reverse; }
@keyframes sb-counter { to { transform: translate(-50%, -50%) rotate(-360deg); } }

.obj.dot, .drift.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #fff, rgba(159, 182, 255, 0.5));
  box-shadow: 0 0 10px rgba(159, 182, 255, 0.7);
  text-indent: -9999px;
}

/* 横向漂移 */
.drift {
  position: absolute; left: 0; line-height: 1; white-space: nowrap;
  animation-name: sb-x; animation-timing-function: linear; animation-iteration-count: infinite;
  filter: drop-shadow(0 0 8px rgba(159, 182, 255, 0.3));
  transition: opacity 0.5s linear;
  will-change: transform, opacity;
}
.drift.rev { animation-direction: reverse; }
@keyframes sb-x {
  from { transform: translateX(-14vw) translateY(0); }
  to { transform: translateX(114vw) translateY(0); }
}

/* 流星 */
.shoot {
  position: absolute; width: 130px; height: 2px; border-radius: 2px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.8));
  opacity: 0; transform: rotate(24deg);
}
.shoot.s1 { top: 14%; left: 4%; animation: sb-shoot 9s ease-in 2s infinite; }
.shoot.s2 { top: 60%; left: 44%; animation: sb-shoot 13s ease-in 7s infinite; }
.shoot.s3 { top: 36%; left: 78%; animation: sb-shoot 16s ease-in 12s infinite; }
@keyframes sb-shoot {
  0% { opacity: 0; transform: translate(0, 0) rotate(24deg); }
  4% { opacity: 0.85; }
  12% { opacity: 0; transform: translate(34vw, 15vh) rotate(24deg); }
  100% { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .neb, .st, .shoot, .orbit, .obj, .drift { animation: none; }
  .shoot { opacity: 0; }
  .st { opacity: 0.4; }
}
</style>
