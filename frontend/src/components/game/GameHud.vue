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

    <span class="gh-prog">{{ Math.min(done + 1, setTotal || 15) }} / {{ setTotal || 15 }}</span>

    <span class="gh-segs">
      <i v-for="(s, i) in normalizedSegs" :key="i" :class="s" />
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
  // 15 段：'ok' | 'no' | 'cur' | ''
  segs: { type: Array, default: () => [] },
  // null = 纯练星球，不显示花
  flowers: { type: Number, default: null },
  showExit: { type: Boolean, default: true }
})
defineEmits(['exit'])

const normalizedSegs = computed(() => {
  const arr = []
  for (let i = 0; i < 15; i += 1) {
    if (i < props.segs.length) arr.push(props.segs[i] || '')
    else if (i === props.done) arr.push('cur')
    else arr.push('')
  }
  return arr
})
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
.gh-prog { color: var(--wp2-dim); font-weight: 800; }
.gh-segs { display: flex; gap: 3px; }
.gh-segs i {
  width: 8px; height: 14px; border-radius: 3px;
  background: rgba(255, 246, 225, 0.16); border: 1.5px solid rgba(255, 246, 225, 0.2);
}
.gh-segs i.ok { background: var(--wp2-l2); border-color: var(--wp2-l2); }
.gh-segs i.no { background: var(--wp2-red); border-color: var(--wp2-red); }
.gh-segs i.cur { border-color: var(--wp2-gold); }
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
  .gh-segs i { width: 6px; height: 12px; }
}
</style>
