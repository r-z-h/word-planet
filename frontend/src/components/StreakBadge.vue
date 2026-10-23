<template>
  <div style="display: flex; gap: 12px">
    <div class="pill">
      <span style="font-size: 22px">🔥</span>
      <div>
        <div style="font-weight: 700; font-size: 18px">{{ streak.current_streak }} 天</div>
        <div class="muted">连续学习</div>
      </div>
    </div>
    <div class="pill">
      <span style="font-size: 22px">🏆</span>
      <div>
        <div style="font-weight: 700; font-size: 18px">{{ streak.longest_streak }} 天</div>
        <div class="muted">最长记录</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  streak: { type: Object, required: true }
})
</script>

<style scoped>
.pill {
  flex: 1;
  display: flex;
  gap: 10px;
  align-items: center;
  background: #f8fafc;
  border-radius: 12px;
  padding: 12px;
}
</style>
