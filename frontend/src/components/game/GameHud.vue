<template>
  <div class="gh">
    <span class="gh-hearts" aria-label="生命">
      <b v-for="i in 3" :key="i" :class="{ off: i > hearts }">♥</b>
    </span>

    <span v-if="combo >= 3" class="gh-combo" :class="{ hot: combo >= 5, max: combo >= 10 }">
      {{ combo >= 5 ? '🔥 ' : '' }}×{{ combo }}
    </span>

    <span class="gh-name">
      第 {{ setNo || 1 }} 关 · {{ levelName || '' }}
    </span>

    <span class="gh-grow" />

    <span class="gh-prog">
      <span class="gh-prog-line">本套：已做 {{ done }} 道 · 未做 {{ (setTotal || 15) - done }} 道 · 共 {{ setTotal || 15 }} 道</span>
      <span class="gh-prog-line dim">本星球：已做 {{ kpDoneSets }} 套 · 未做 {{ kpTotalSets - kpDoneSets }} 套 · 共 {{ kpTotalSets }} 套</span>
    </span>

    <span class="gh-segs">
      <i
        v-for="(s, i) in normalizedSegs"
        :key="i"
        :class="[segClass(s), { clickable: segClickable(s) }]"
        :title="segClickable(s) ? '点这里回到这道未做的题' : ''"
        @click="onSegClick(s)"
      />
    </span>

    <span v-if="flowers !== null" class="gh-flower">🌸 {{ flowers }}</span>
    <button v-if="showExit" class="gh-exit" title="退出关卡" @click="$emit('exit')">✕</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  hearts: { type: Number, default: 3 },
  combo: { type: Number, default: 0 },
  levelName: { type: String, default: '' },
  setNo: { type: Number, default: 1 },
  setTotal: { type: Number, default: 15 },
  done: { type: Number, default: 0 },
  kpTotalSets: { type: Number, default: 0 },
  kpDoneSets: { type: Number, default: 0 },
  // 15 段：元素可为 'ok'|'no'|'cur'|''（旧）或 {id,state}（新，可点击）
  segs: { type: Array, default: () => [] },
  // null = 纯练星球，不显示花
  flowers: { type: Number, default: null },
  showExit: { type: Boolean, default: true }
})
const emit = defineEmits(['exit', 'seek'])

const normalizedSegs = computed(() => {
  const arr = []
  for (let i = 0; i < 15; i += 1) {
    if (i < props.segs.length) arr.push(props.segs[i])
    else if (i === props.done) arr.push('cur')
    else arr.push('')
  }
  return arr
})
function segClass(s) {
  return typeof s === 'string' ? s : (s && s.state) || ''
}
function segClickable(s) {
  return !!s && typeof s === 'object' && !!s.id && s.state === 'todo'
}
function onSegClick(s) {
  if (segClickable(s)) emit('seek', s)
}
</script>

<style scoped>
.gh {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 2px solid rgba(255, 226, 168, 0.14);
  font-size: 12.5px;
  flex: none;
}
.gh-hearts { display: flex; gap: 4px; font-size: 14px; }
.gh-hearts b { color: var(--wp2-red); font-weight: 400; transition: 0.2s; }
.gh-hearts b.off { color: rgba(255, 246, 225, 0.2); transform: scale(0.85); }
.gh-combo {
  padding: 3px 9px; border-radius: 99px; font-weight: 900; font-size: 11.5px;
  background: rgba(255, 246, 225, 0.11); color: var(--wp2-ink); white-space: nowrap;
}
.gh-combo.hot { background: rgba(255, 205, 76, 0.18); color: var(--wp2-gold); }
.gh-combo.max {
  background: rgba(255, 205, 76, 0.3); color: var(--wp2-gold);
  box-shadow: 0 0 12px rgba(255, 205, 76, 0.55);
}
.gh-name { color: var(--wp2-muted); font-weight: 800; white-space: nowrap; }
.gh-grow { flex: 1; }
.gh-prog { color: var(--wp2-dim); font-weight: 800; display: flex; flex-direction: column; line-height: 1.3; text-align: right; }
.gh-prog-line { white-space: nowrap; }
.gh-prog-line.dim { opacity: 0.72; font-size: 11px; }
.gh-segs { display: flex; gap: 4px; }
.gh-segs i {
  width: 14px; height: 22px; border-radius: 5px; box-sizing: border-box;
  background: rgba(255, 246, 225, 0.16); border: 2px solid rgba(255, 246, 225, 0.22);
  transition: transform 0.1s;
}
.gh-segs i.ok { background: var(--wp2-l2); border-color: var(--wp2-l2); }
.gh-segs i.no { background: var(--wp2-red); border-color: var(--wp2-red); }
.gh-segs i.cur { background: #4c6ef5; border-color: #4c6ef5; box-shadow: 0 0 8px rgba(76, 110, 245, 0.8); }
.gh-segs i.todo { background: #ffffff; border-color: #ffffff; }
.gh-segs i.clickable { cursor: pointer; }
.gh-segs i.clickable:hover { transform: scale(1.15); }
.gh-flower { color: var(--wp2-gold); font-weight: 900; white-space: nowrap; }
.gh-exit {
  flex: none; width: 30px; height: 30px; border-radius: 9px; cursor: pointer;
  background: rgba(255, 246, 225, 0.1); color: var(--wp2-ink); font-size: 13px;
  border: 2px solid rgba(255, 232, 180, 0.3); display: grid; place-items: center;
}
.gh-exit:hover { background: rgba(255, 246, 225, 0.18); }

@media (max-width: 767px) {
  .gh { gap: 8px; padding: 8px 12px; flex-wrap: wrap; }
  .gh-name { font-size: 11.5px; }
  .gh-segs { gap: 3px; }
  .gh-segs i { width: 10px; height: 16px; border-radius: 4px; }
}
</style>
