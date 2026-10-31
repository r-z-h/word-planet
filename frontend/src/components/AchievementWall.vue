<template>
  <div>
    <el-empty v-if="!items.length" description="还没有徽章，学完一个知识点试试" />
    <div v-else class="grid">
      <div v-for="item in items" :key="item.badge_id" class="badge">
        <div style="font-size: 32px">{{ iconOf(item.code) }}</div>
        <div style="font-weight: 600; margin-top: 6px">{{ item.name }}</div>
        <div class="muted">{{ formatDate(item.earned_at) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] }
})

function iconOf(code) {
  if (code?.startsWith('streak')) return '🔥'
  if (code === 'answer_100') return '💯'
  return '⭐'
}

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString('zh-CN')
}
</script>

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
