<template>
  <div class="wp-stars" aria-hidden="true">
    <i
      v-for="s in stars"
      :key="s.id"
      :style="{
        width: s.size + 'px',
        height: s.size + 'px',
        left: s.left + '%',
        top: s.top + '%',
        animationDelay: s.delay + 's'
      }"
    />
  </div>
</template>

<script setup>
// 纯装饰的星空背景：固定铺满、不接收事件、不影响布局
const COUNT = 60
const stars = Array.from({ length: COUNT }, (_, i) => ({
  id: i,
  size: +(Math.random() * 1.5 + 0.7).toFixed(2),
  left: +(Math.random() * 100).toFixed(2),
  top: +(Math.random() * 100).toFixed(2),
  delay: +(Math.random() * 5).toFixed(2)
}))
</script>
