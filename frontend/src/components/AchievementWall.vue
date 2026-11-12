<template>
  <div>
    <el-empty v-if="!items.length" description="还没有徽章，学完一个知识点试试" />
    <div v-else class="grid">
      <el-tooltip v-for="item in items" :key="item.badge_id" placement="top" effect="dark" :trigger="touch ? 'click' : 'hover'">
        <template #content>
          <div style="max-width: 240px; line-height: 1.6">
            <div>获取条件：{{ item.condition || '—' }}</div>
            <div>获取时间：{{ fmtDateTime(item.earned_at) }}</div>
          </div>
        </template>
        <div class="badge" @click="onBadgeClick(item)">
          <div class="aw-ic"><MedalIcon :icon="item.icon || '🏅'" /></div>
          <div style="font-weight: 600; margin-top: 6px">{{ item.name }}</div>
          <div class="muted">{{ formatDate(item.earned_at) }}</div>
        </div>
      </el-tooltip>
    </div>
  </div>
</template>

<script setup>
import MedalIcon from './MedalIcon.vue'
import { playUltimate } from '../utils/ultimateFx'

const touch = typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia('(hover: none)').matches

function onBadgeClick(item) {
  if (item && item.code === 'ultimate_all') playUltimate(item.icon || '/badges/ultimate.svg')
}

defineProps({
  items: { type: Array, default: () => [] }
})

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString('zh-CN')
}

function fmtDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
</script>

<style scoped>
.aw-ic {
  font-size: 40px;
  line-height: 1;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 12px;
}
.badge {
  background: rgba(255, 246, 225, 0.07);
  border: 1.5px solid rgba(255, 232, 180, 0.18);
  border-radius: 14px;
  padding: 16px 8px;
  text-align: center;
  color: var(--wp2-ink);
}
</style>
