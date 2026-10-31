<template>
  <div class="map">
    <svg class="routes" viewBox="0 0 1040 780" preserveAspectRatio="none">
      <path
        class="ro"
        vector-effect="non-scaling-stroke"
        d="M270,686 C426,692 563,657 697,577 C548,572 411,547 270,499 C421,483 557,448 697,390 C546,372 410,334 270,273 C420,260 557,227 697,172 C546,156 410,121 270,62"
      />
    </svg>

    <div class="zone l3" style="top: 3%">
      <span class="nm">挑战星海</span>
      <span class="tp">L3 · 初中 · {{ maxLevel >= 'L3' ? '已解锁' : '🔒 未解锁' }}</span>
    </div>
    <div class="zone l2" style="top: 31%">
      <span class="nm">探索星带</span>
      <span class="tp">L2 · 小学高年级 · {{ levelRank(maxLevel) >= 2 ? '已解锁' : '🔒 未解锁' }}</span>
    </div>
    <div class="zone l1" style="top: 71%">
      <span class="nm">启程星云</span>
      <span class="tp">L1 · 小学低年级</span>
    </div>

    <button
      v-for="p in planets"
      :key="p.id"
      class="planet"
      :class="[p.level.toLowerCase(), { locked: p.locked, current: p.is_current, pure: p.pure }]"
      :style="{ left: posOf(p)[0] + '%', top: posOf(p)[1] + '%' }"
      :disabled="p.locked"
      @click="$emit('select', p)"
    >
      <span class="disc" :style="{ '--p': pct(p) }">
        <span class="ball">
          <span v-if="!p.locked" class="face" :class="faceOf(p)">
            <i class="e1" /><i class="e2" /><b />
          </span>
        </span>
      </span>
      <span class="nm">{{ p.name }}</span>
      <span class="st">{{ stText(p) }}</span>
      <span v-if="!p.pure && !p.locked" class="medal">
        <span class="em">{{ medalEmoji(p) }}</span>{{ p.medals }}
      </span>
      <span v-if="p.pure && !p.locked" class="puretag" :class="{ ok: p.is_complete }">
        {{ p.is_complete ? '✓ 已完成' : '未完成' }}
      </span>
    </button>

    <!-- 星门：本级能力测试 -->
    <button class="gate" :class="{ off: !gateReady }" style="left: 47%; top: 31%" @click="$emit('gate')">
      <span class="ring">🚪</span>
      <span class="lbl">能力测试</span>
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  planets: { type: Array, default: () => [] },
  gateReady: { type: Boolean, default: false },
  nextLevel: { type: String, default: null },
  maxLevel: { type: String, default: 'L1' }
})
defineEmits(['select', 'gate'])

const POS = {
  听力理解: [26, 7],
  拼写进阶: [67, 21],
  单词跟读: [26, 34],
  简单拼写: [67, 48],
  常用单词: [26, 61],
  基础问候词: [67, 72],
  字母表: [26, 84]
}
const RANK = { L1: 1, L2: 2, L3: 3 }

function levelRank(lv) {
  return RANK[lv] || 0
}
function posOf(p) {
  return POS[p.name] || [50, 50]
}
function pct(p) {
  if (p.pure) return p.is_complete ? '100%' : '0%'
  if (!p.total_sets) return '0%'
  return Math.round((p.completed_sets / p.total_sets) * 100) + '%'
}
function faceOf(p) {
  if (p.is_current) return 'f-excited'
  if (p.pure) return p.is_complete ? 'f-proud' : 'f-sleepy'
  if (p.completed_sets > 0) return p.completed_sets / Math.max(p.total_sets, 1) > 0.5 ? 'f-focus' : 'f-curious'
  return 'f-sleepy'
}
function stText(p) {
  if (p.locked) return `${p.total_sets} 套 · 未解锁`
  if (p.pure) return `${p.completed_sets} / ${p.total_sets} 套`
  return `${p.completed_sets} / ${p.total_sets} 套` + (p.is_current ? ' · 当前' : '')
}
function medalEmoji(p) {
  return (
    {
      基础问候词: '🥚',
      常用单词: '🐻',
      简单拼写: '✍️',
      单词跟读: '🐦',
      拼写进阶: '🔮'
    }[p.name] || '🏅'
  )
}
</script>

<style scoped>
.map {
  position: relative;
  flex: 1;
  min-height: 0;
  border-radius: 18px;
  background: radial-gradient(80% 60% at 35% 15%, rgba(76, 110, 245, 0.1), transparent 65%);
}
.routes { position: absolute; inset: 0; width: 100%; height: 100%; }
.routes path { fill: none; stroke-linecap: round; }
.ro { stroke: rgba(255, 226, 168, 0.34); stroke-width: 3; stroke-dasharray: 9 11; opacity: 0.62; }

.zone {
  position: absolute; left: 1.5%; right: 1.5%; transform: translateY(-50%);
  display: flex; align-items: center; gap: 8px; font-size: 10.5px; color: var(--wp2-dim);
  pointer-events: none; font-weight: 800;
}
.zone::after {
  content: ''; flex: 1; height: 2px; border-radius: 2px;
  background: linear-gradient(90deg, rgba(255, 226, 168, 0.2), transparent);
}
.zone .nm { font-size: 12.5px; letter-spacing: 0.05em; }
.zone .tp { font-size: 10px; font-weight: 600; opacity: 0.85; }
.zone.l1 { color: var(--wp2-l1b); }
.zone.l2 { color: var(--wp2-l2b); }
.zone.l3 { color: rgba(192, 168, 255, 0.62); }

.planet {
  position: absolute; width: 180px; margin-left: -90px; transform: translateY(-46px);
  background: none; border: 0; color: inherit; font: inherit; cursor: pointer;
  display: flex; flex-direction: column; align-items: center; gap: 5px; transition: transform 0.18s;
  padding: 0;
}
.planet:hover:not(:disabled) { transform: translateY(-51px); }
.disc {
  width: 100px; height: 100px; border-radius: 50%; position: relative;
  background: conic-gradient(var(--c) var(--p), rgba(255, 255, 255, 0.09) 0);
  display: grid; place-items: center; box-shadow: 0 5px 0 rgba(15, 8, 34, 0.55);
}
.disc::before { content: ''; position: absolute; inset: 8px; border-radius: 50%; background: rgba(21, 13, 48, 0.94); }
.ball {
  position: relative; width: 80px; height: 80px; border-radius: 50%;
  background: radial-gradient(circle at 33% 27%, var(--c2), var(--c) 72%);
  border: 3px solid var(--wp2-inkline);
  box-shadow: 0 4px 0 var(--wp2-inkline), inset -5px -7px 0 rgba(0, 0, 0, 0.16);
  overflow: hidden; display: grid; place-items: center;
}
.face { position: absolute; inset: 0; }
.face i { position: absolute; background: var(--wp2-inkline); }
.face .e1 { left: 20px; }
.face .e2 { right: 20px; }
.face b { position: absolute; left: 50%; transform: translateX(-50%); border: 3px solid var(--wp2-inkline); }
.f-excited i { top: 25px; width: 9px; height: 12px; border-radius: 50%; }
.f-excited b { top: 40px; width: 21px; height: 14px; border: 0; background: var(--wp2-inkline); border-radius: 4px 4px 13px 13px; }
.f-proud i { top: 29px; width: 11px; height: 4px; border-radius: 4px; }
.f-proud b { top: 39px; width: 19px; height: 10px; border-radius: 0 0 13px 13px; }
.f-focus i { top: 27px; width: 8px; height: 9px; border-radius: 3px; }
.f-focus i::before { content: ''; position: absolute; top: -7px; left: -2px; width: 12px; height: 3px; border-radius: 3px; background: var(--wp2-inkline); }
.f-focus b { top: 45px; width: 13px; height: 0; border-width: 3px 0 0; border-radius: 0; }
.f-curious .e1 { top: 25px; width: 11px; height: 13px; border-radius: 50%; }
.f-curious .e2 { top: 28px; width: 7px; height: 8px; border-radius: 50%; }
.f-curious b { top: 42px; width: 9px; height: 9px; border-radius: 50%; border-top: 3px solid var(--wp2-inkline); }
.f-sleepy i { top: 30px; width: 10px; height: 3px; border-radius: 3px; }
.f-sleepy b { top: 42px; width: 9px; height: 5px; border-radius: 0 0 7px 7px; }

.planet .nm {
  font-size: 13.5px; font-weight: 900; white-space: nowrap; position: relative; z-index: 2;
  text-shadow: 0 2px 0 rgba(20, 10, 40, 0.95);
}
.planet .st { font-size: 10.5px; color: var(--wp2-muted); white-space: nowrap; position: relative; z-index: 2; font-weight: 700; }
.planet.l1 { --c: var(--wp2-l1); --c2: var(--wp2-l1b); }
.planet.l2 { --c: var(--wp2-l2); --c2: var(--wp2-l2b); }
.planet.l3 { --c: var(--wp2-l3); --c2: var(--wp2-l3b); }

.medal {
  display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px 2px 5px; border-radius: 999px;
  background: rgba(20, 10, 40, 0.6); border: 1.5px solid rgba(255, 205, 76, 0.44);
  font-size: 10.5px; font-weight: 900; color: var(--wp2-gold); position: relative; z-index: 2;
}
.medal .em { font-size: 13px; line-height: 1; }

.planet.pure .ball { background: radial-gradient(circle at 33% 27%, #b9c2d6, #6b7691 72%); }
.planet.pure .disc { background: conic-gradient(rgba(185, 194, 214, 0.5) var(--p), rgba(255, 255, 255, 0.07) 0); }
.puretag {
  display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 999px;
  border: 1.5px dashed rgba(255, 232, 180, 0.34); font-size: 10px; font-weight: 800;
  color: var(--wp2-dim); position: relative; z-index: 2;
}
.puretag.ok { color: #6ff0c4; border-color: rgba(111, 240, 196, 0.5); border-style: solid; background: rgba(111, 240, 196, 0.1); }

.planet.current { transform: translateY(-51px) scale(1.05); }
.planet.current .disc {
  box-shadow: 0 5px 0 rgba(15, 8, 34, 0.55), 0 0 0 6px rgba(255, 226, 168, 0.15), 0 0 26px rgba(255, 200, 120, 0.5);
}
.planet.current .disc::after {
  content: ''; position: absolute; inset: -8px; border-radius: 50%;
  border: 2px dashed rgba(255, 226, 168, 0.48); animation: pm-spin 14s linear infinite;
}
@keyframes pm-spin { to { transform: rotate(360deg); } }
.planet.locked { cursor: not-allowed; }
.planet.locked .disc { filter: grayscale(1) brightness(0.7); }
.planet.locked .nm, .planet.locked .st { color: var(--wp2-dim); }
.planet.locked .face { display: none; }
.planet.locked .medal, .planet.locked .puretag { display: none; }
.planet.locked .ball::after {
  content: '🔒'; position: absolute; inset: 0; display: grid; place-items: center; font-size: 25px; z-index: 2;
}

.gate {
  position: absolute; transform: translate(-50%, -50%); background: none; border: 0; color: inherit;
  display: flex; flex-direction: column; align-items: center; gap: 3px; cursor: pointer; padding: 0;
}
.gate .ring {
  width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center;
  border: 3px dashed rgba(255, 205, 76, 0.6); background: rgba(255, 205, 76, 0.12); font-size: 17px;
  animation: pm-spin 18s linear infinite;
}
.gate .lbl { font-size: 9.5px; font-weight: 900; color: var(--wp2-gold); white-space: nowrap; text-shadow: 0 2px 0 rgba(20, 10, 40, 0.9); }
.gate.off .ring { border-color: rgba(141, 124, 184, 0.4); background: rgba(141, 124, 184, 0.1); animation: none; }
.gate.off .lbl { color: var(--wp2-dim); }

@media (max-width: 767px) {
  .map { min-height: 620px; }
  .zone { display: none; }
  .planet { width: 104px; margin-left: -52px; transform: translateY(-34px); }
  .disc { width: 66px; height: 66px; }
  .ball { width: 52px; height: 52px; }
  .face .e1 { left: 12px; } .face .e2 { right: 12px; }
  .f-excited i { top: 16px; width: 6px; height: 8px; }
  .f-excited b { top: 26px; width: 14px; height: 9px; }
  .f-proud i { top: 19px; width: 8px; height: 3px; }
  .f-proud b { top: 25px; width: 12px; height: 7px; }
  .f-focus i { top: 18px; width: 5px; height: 6px; }
  .f-focus b { top: 30px; width: 9px; }
  .f-curious .e1 { top: 16px; width: 7px; height: 9px; }
  .f-curious .e2 { top: 18px; width: 5px; height: 6px; }
  .f-curious b { top: 27px; width: 6px; height: 6px; }
  .f-sleepy i { top: 19px; width: 7px; height: 2px; }
  .f-sleepy b { top: 27px; width: 6px; height: 4px; }
  .planet .nm { font-size: 10.5px; }
  .planet .st { font-size: 9px; }
  .planet .medal { font-size: 9px; padding: 1px 6px 1px 4px; }
  .puretag { font-size: 9px; padding: 1px 6px; }
}
</style>
